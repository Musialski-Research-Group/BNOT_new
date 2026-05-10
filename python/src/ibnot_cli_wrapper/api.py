from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import math
import os
import re
import shutil
import subprocess
from time import perf_counter
from typing import Any, Mapping, Optional, Sequence

import numpy as np


NumberGrid = Sequence[Sequence[float | int]] | np.ndarray

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")
_TIMER_LINE_RE = re.compile(
    r"(?P<stage>[A-Za-z][A-Za-z0-9_ ]+?)\s+\.\.\.\s+done\s+\((?P<seconds>[0-9eE+.\-]+)\s+s\)"
)


@dataclass(frozen=True)
class NativeConfig:
    num_sites: Optional[int] = 1024
    points_path: Optional[Path | str] = None
    seed: int = 0
    max_iters: int = 500
    max_newton_iters: int = 500
    step_x: float = 0.0
    step_w: float = 0.0
    epsilon: float = 1.0
    invert: bool = False
    weight_solver: str = "newton"
    native_timer: bool = False


@dataclass(frozen=True)
class RenderConfig:
    enabled: bool = True
    render_width: Optional[int] = None
    render_height: Optional[int] = None
    point_radius: float = 0.002
    png_enabled: bool = True
    dpi: int = 300
    ghostscript: str = "gs"


@dataclass(frozen=True)
class OutputConfig:
    output_dir: Path | str = Path(".")
    output_stem: str = "result"
    keep_pgm: bool = True
    keep_eps: bool = True
    keep_stats_txt: bool = True


@dataclass(frozen=True)
class InferenceRequest:
    image_path: Optional[Path | str] = None
    image_array: Optional[NumberGrid] = None
    native: NativeConfig = field(default_factory=NativeConfig)
    render: RenderConfig = field(default_factory=RenderConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    executable: Optional[Path | str] = None


@dataclass(frozen=True)
class ResolvedPaths:
    pgm_path: Optional[Path] = None
    dat_path: Optional[Path] = None
    eps_path: Optional[Path] = None
    png_path: Optional[Path] = None
    stats_path: Optional[Path] = None


@dataclass(frozen=True)
class TimingInfo:
    pgm_write_seconds: float = 0.0
    native_wall_seconds: float = 0.0
    render_wall_seconds: float = 0.0
    total_wall_seconds: float = 0.0
    native_stage_seconds: dict[str, float] = field(default_factory=dict)


@dataclass
class InferenceResult:
    request: InferenceRequest
    resolved_paths: ResolvedPaths
    stats: Mapping[str, object]
    timings: TimingInfo
    stdout: str
    stderr: str
    command: list[str]
    warnings: list[str] = field(default_factory=list)

    @property
    def image_path(self) -> Optional[Path]:
        return self.resolved_paths.pgm_path

    @property
    def eps_path(self) -> Optional[Path]:
        return self.resolved_paths.eps_path

    @property
    def png_path(self) -> Optional[Path]:
        return self.resolved_paths.png_path

    @property
    def stats_path(self) -> Optional[Path]:
        return self.resolved_paths.stats_path


RunResult = InferenceResult


def find_default_executable(explicit: Optional[Path | str] = None) -> Path:
    if explicit is not None:
        path = Path(explicit).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"CLI executable not found: {path}")
        return path

    env_value = os.environ.get("IBNOT_CLI_BIN")
    if env_value:
        path = Path(env_value).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"IBNOT_CLI_BIN points to missing path: {path}")
        return path

    candidates: list[Path] = []
    for anchor in [Path.cwd(), Path(__file__).resolve()]:
        for parent in [anchor, *anchor.parents]:
            candidates.append(parent / "ibnot_cli" / "prebuilt" / "linux-x86_64" / "ibnot_new_cli")
            candidates.append(parent / "ibnot_cli" / "build" / "ibnot_new_cli")

    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "Could not locate ibnot_new_cli. Set IBNOT_CLI_BIN or pass executable= explicitly."
    )


def make_uniform(size: int = 512, value: float = 1.0) -> np.ndarray:
    return np.full((int(size), int(size)), np.clip(float(value), 0.0, 1.0), dtype=float)


def make_linear_ramp(size: int = 512, left: float = 1.0, right: float = 0.0) -> np.ndarray:
    row = np.linspace(float(left), float(right), int(size), dtype=float)
    return np.tile(np.clip(row, 0.0, 1.0), (int(size), 1))


def make_sine_landscape(size: int = 512, fx: float = 4.0, fy: float = 4.0) -> np.ndarray:
    coords = np.linspace(0.0, 1.0, int(size), dtype=float)
    xx, yy = np.meshgrid(coords, coords, indexing="xy")
    field = 0.5 + 0.5 * np.sin(2.0 * np.pi * float(fx) * xx) * np.sin(2.0 * np.pi * float(fy) * yy)
    return np.clip(field, 0.0, 1.0)


def _as_normalized_array(pixels: NumberGrid) -> np.ndarray:
    array = np.asarray(pixels, dtype=float)
    if array.ndim != 2:
        raise ValueError("pixels must be a 2D grid")
    if array.size == 0:
        raise ValueError("pixels must be a non-empty rectangular grid")
    if not np.all(np.isfinite(array)):
        raise ValueError("PGM values must be finite")

    if float(array.min()) >= 0.0 and float(array.max()) <= 1.0:
        return np.clip(array, 0.0, 1.0)

    return np.clip(array / 255.0, 0.0, 1.0)


def write_pgm(path: Path | str, pixels: NumberGrid) -> Path:
    output = Path(path)
    array = _as_normalized_array(pixels)
    height, width = array.shape

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        handle.write("P2\n")
        handle.write(f"{width} {height}\n")
        handle.write("255\n")
        for row in array:
            row_uint8 = np.rint(row * 255.0).astype(int)
            handle.write(" ".join(str(int(value)) for value in row_uint8))
            handle.write("\n")
    return output


def parse_stats_file(path: Path | str) -> dict[str, object]:
    result: dict[str, object] = {}
    with Path(path).open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            result[key] = _coerce_scalar(value)
    return result


def _coerce_scalar(value: str) -> object:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"

    for caster in (int, float):
        try:
            parsed = caster(value)
            if isinstance(parsed, float) and not math.isfinite(parsed):
                return value
            return parsed
        except ValueError:
            pass
    return value


def _strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE_RE.sub("", text)


def _parse_native_stage_seconds(stdout: str) -> tuple[dict[str, float], list[str]]:
    clean_stdout = _strip_ansi(stdout)
    stage_seconds: dict[str, float] = {}
    warnings: list[str] = []

    for match in _TIMER_LINE_RE.finditer(clean_stdout):
        stage = match.group("stage").strip()
        seconds = float(match.group("seconds"))
        stage_seconds[stage] = stage_seconds.get(stage, 0.0) + seconds

    if "done (" in clean_stdout and not stage_seconds:
        warnings.append("native timer output detected but no stage timings were parsed")

    return stage_seconds, warnings


def _safe_parse_stats(path: Path) -> tuple[dict[str, object], list[str]]:
    if not path.exists():
        return {}, [f"stats file missing: {path}"]
    try:
        return parse_stats_file(path), []
    except Exception as exc:  # pragma: no cover - defensive
        return {}, [f"failed to parse stats file {path}: {exc}"]


def _validate_request(request: InferenceRequest) -> list[str]:
    warnings: list[str] = []

    if (request.image_path is None) == (request.image_array is None):
        raise ValueError("provide exactly one of image_path or image_array")

    if request.native.points_path is not None and request.native.num_sites is not None:
        raise ValueError("provide either native.points_path or native.num_sites, not both")
    if request.native.points_path is None and request.native.num_sites is None:
        raise ValueError("provide one of native.points_path or native.num_sites")
    if request.native.weight_solver not in {"newton", "gd"}:
        raise ValueError("native.weight_solver must be one of: newton, gd")

    if request.render.render_width is not None and request.render.render_width <= 0:
        raise ValueError("render.render_width must be positive")
    if request.render.render_height is not None and request.render.render_height <= 0:
        raise ValueError("render.render_height must be positive")
    if (request.render.render_width is None) != (request.render.render_height is None):
        raise ValueError("render.render_width and render.render_height must be provided together")
    if request.render.point_radius <= 0.0:
        raise ValueError("render.point_radius must be positive")
    if request.render.dpi <= 0:
        raise ValueError("render.dpi must be positive")

    if not request.render.enabled:
        if request.render.png_enabled:
            warnings.append("render.png_enabled ignored because render.enabled is False")
        if request.render.render_width is not None or request.render.render_height is not None:
            warnings.append("render_width/render_height ignored because render.enabled is False")
        if request.render.point_radius != 0.002:
            warnings.append("point_radius ignored because render.enabled is False")

    return warnings


def convert_eps_to_png(
    eps_path: Path | str,
    png_path: Path | str,
    ghostscript: str = "gs",
    width: Optional[int] = None,
    height: Optional[int] = None,
    dpi: int = 300,
) -> Path:
    gs = shutil.which(ghostscript)
    if gs is None:
        raise FileNotFoundError(f"Ghostscript executable not found: {ghostscript}")

    eps = Path(eps_path)
    png = Path(png_path)
    png.parent.mkdir(parents=True, exist_ok=True)

    if (width is None) != (height is None):
        raise ValueError("width and height must be provided together")
    if width is not None and width <= 0:
        raise ValueError("width must be positive")
    if height is not None and height <= 0:
        raise ValueError("height must be positive")
    if dpi <= 0:
        raise ValueError("dpi must be positive")

    cmd = [
        gs,
        "-dSAFER",
        "-dBATCH",
        "-dNOPAUSE",
        "-dEPSCrop",
        "-sDEVICE=png16m",
        f"-sOutputFile={png}",
    ]
    if width is not None and height is not None:
        cmd.append(f"-g{width}x{height}")
    else:
        cmd.append(f"-r{dpi}")
    cmd.append(str(eps))
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return png


def run_inference(request: InferenceRequest) -> InferenceResult:
    warnings = _validate_request(request)
    cli = find_default_executable(request.executable)
    output_root = Path(request.output.output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    total_start = perf_counter()
    pgm_write_seconds = 0.0
    generated_pgm = False

    if request.image_array is not None:
        pgm_path = output_root / f"{request.output.output_stem}_input.pgm"
        generated_pgm = True
        pgm_start = perf_counter()
        write_pgm(pgm_path, request.image_array)
        pgm_write_seconds = perf_counter() - pgm_start
    else:
        pgm_path = Path(request.image_path).expanduser().resolve()
        if not pgm_path.exists():
            raise FileNotFoundError(f"input image not found: {pgm_path}")

    stats_path = output_root / f"{request.output.output_stem}.txt"
    dat_path: Optional[Path] = None
    eps_path: Optional[Path] = None
    png_path: Optional[Path] = None

    if request.render.enabled:
        eps_path = output_root / f"{request.output.output_stem}.eps"
        native_output_path = eps_path
    else:
        dat_path = output_root / f"{request.output.output_stem}.dat"
        native_output_path = dat_path

    native_cfg = request.native
    render_cfg = request.render

    cmd = [
        str(cli),
        "--image",
        str(pgm_path),
        "--output",
        str(native_output_path),
        "--stats",
        str(stats_path),
        "--seed",
        str(native_cfg.seed),
        "--max-iters",
        str(native_cfg.max_iters),
        "--max-newton-iters",
        str(native_cfg.max_newton_iters),
        "--step-x",
        str(native_cfg.step_x),
        "--step-w",
        str(native_cfg.step_w),
        "--epsilon",
        str(native_cfg.epsilon),
        "--weight-solver",
        native_cfg.weight_solver,
    ]

    if render_cfg.enabled:
        cmd.extend(["--point-radius", str(render_cfg.point_radius)])
        if render_cfg.render_width is not None and render_cfg.render_height is not None:
            cmd.extend(
                ["--render-width", str(render_cfg.render_width), "--render-height", str(render_cfg.render_height)]
            )

    if native_cfg.points_path is not None:
        cmd.extend(["--points", str(Path(native_cfg.points_path))])
    elif native_cfg.num_sites is not None:
        cmd.extend(["--num-sites", str(native_cfg.num_sites)])
    else:  # pragma: no cover - already guarded
        raise ValueError("provide one of native.points_path or native.num_sites")

    if native_cfg.invert:
        cmd.append("--invert")
    if native_cfg.native_timer:
        cmd.append("--timer")

    native_start = perf_counter()
    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    native_wall_seconds = perf_counter() - native_start
    if completed.returncode != 0:
        raise RuntimeError(
            "ibnot_new_cli failed\n"
            f"command: {' '.join(cmd)}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )

    stats, stats_warnings = _safe_parse_stats(stats_path)
    warnings.extend(stats_warnings)

    native_stage_seconds: dict[str, float] = {}
    if native_cfg.native_timer:
        native_stage_seconds, timer_warnings = _parse_native_stage_seconds(completed.stdout)
        warnings.extend(timer_warnings)

    render_wall_seconds = 0.0
    if render_cfg.enabled and render_cfg.png_enabled:
        assert eps_path is not None
        png_path = output_root / f"{request.output.output_stem}.png"
        render_start = perf_counter()
        try:
            convert_eps_to_png(
                eps_path,
                png_path,
                ghostscript=render_cfg.ghostscript,
                width=render_cfg.render_width,
                height=render_cfg.render_height,
                dpi=render_cfg.dpi,
            )
        except FileNotFoundError as exc:
            warnings.append(str(exc))
            png_path = None
        else:
            render_wall_seconds = perf_counter() - render_start

    resolved_pgm_path: Optional[Path] = pgm_path
    resolved_eps_path: Optional[Path] = eps_path
    resolved_stats_path: Optional[Path] = stats_path

    if generated_pgm and not request.output.keep_pgm and pgm_path.exists():
        pgm_path.unlink()
        resolved_pgm_path = None

    if eps_path is not None and not request.output.keep_eps and eps_path.exists():
        eps_path.unlink()
        resolved_eps_path = None

    if not request.output.keep_stats_txt and stats_path.exists():
        stats_path.unlink()
        resolved_stats_path = None

    total_wall_seconds = perf_counter() - total_start

    return InferenceResult(
        request=request,
        resolved_paths=ResolvedPaths(
            pgm_path=resolved_pgm_path,
            dat_path=dat_path,
            eps_path=resolved_eps_path,
            png_path=png_path,
            stats_path=resolved_stats_path,
        ),
        stats=stats,
        timings=TimingInfo(
            pgm_write_seconds=pgm_write_seconds,
            native_wall_seconds=native_wall_seconds,
            render_wall_seconds=render_wall_seconds,
            total_wall_seconds=total_wall_seconds,
            native_stage_seconds=native_stage_seconds,
        ),
        stdout=completed.stdout,
        stderr=completed.stderr,
        command=cmd,
        warnings=warnings,
    )


def run_from_image(
    image_path: Path | str,
    output_dir: Path | str,
    output_stem: str,
    *,
    executable: Optional[Path | str] = None,
    points_path: Optional[Path | str] = None,
    num_sites: Optional[int] = None,
    seed: int = 0,
    max_iters: int = 500,
    max_newton_iters: int = 500,
    step_x: float = 0.0,
    step_w: float = 0.0,
    epsilon: float = 1.0,
    render_width: Optional[int] = None,
    render_height: Optional[int] = None,
    point_radius: float = 0.002,
    invert: bool = False,
    timer: bool = False,
    weight_solver: str = "newton",
    write_png: bool = False,
    ghostscript: str = "gs",
    dpi: int = 300,
) -> InferenceResult:
    request = InferenceRequest(
        image_path=image_path,
        native=NativeConfig(
            num_sites=num_sites,
            points_path=points_path,
            seed=seed,
            max_iters=max_iters,
            max_newton_iters=max_newton_iters,
            step_x=step_x,
            step_w=step_w,
            epsilon=epsilon,
            invert=invert,
            weight_solver=weight_solver,
            native_timer=timer,
        ),
        render=RenderConfig(
            enabled=True,
            render_width=render_width,
            render_height=render_height,
            point_radius=point_radius,
            png_enabled=write_png,
            dpi=dpi,
            ghostscript=ghostscript,
        ),
        output=OutputConfig(output_dir=output_dir, output_stem=output_stem),
        executable=executable,
    )
    return run_inference(request)


def run_from_array(
    pixels: NumberGrid,
    output_dir: Path | str,
    output_stem: str,
    *,
    executable: Optional[Path | str] = None,
    num_sites: int,
    seed: int = 0,
    max_iters: int = 500,
    max_newton_iters: int = 500,
    step_x: float = 0.0,
    step_w: float = 0.0,
    epsilon: float = 1.0,
    render_width: Optional[int] = None,
    render_height: Optional[int] = None,
    point_radius: float = 0.002,
    invert: bool = False,
    timer: bool = False,
    weight_solver: str = "newton",
    write_png: bool = False,
    ghostscript: str = "gs",
    dpi: int = 300,
) -> InferenceResult:
    request = InferenceRequest(
        image_array=pixels,
        native=NativeConfig(
            num_sites=num_sites,
            seed=seed,
            max_iters=max_iters,
            max_newton_iters=max_newton_iters,
            step_x=step_x,
            step_w=step_w,
            epsilon=epsilon,
            invert=invert,
            weight_solver=weight_solver,
            native_timer=timer,
        ),
        render=RenderConfig(
            enabled=True,
            render_width=render_width,
            render_height=render_height,
            point_radius=point_radius,
            png_enabled=write_png,
            dpi=dpi,
            ghostscript=ghostscript,
        ),
        output=OutputConfig(output_dir=output_dir, output_stem=output_stem),
        executable=executable,
    )
    return run_inference(request)


def run_case(
    pixels: NumberGrid,
    output_dir: Path | str,
    output_stem: str,
    *,
    executable: Optional[Path | str] = None,
    num_sites: int = 1024,
    seed: int = 7,
    max_iters: int = 25,
    max_newton_iters: int = 50,
    step_x: float = 0.0,
    step_w: float = 0.0,
    epsilon: float = 1.0,
    render_width: Optional[int] = None,
    render_height: Optional[int] = None,
    point_radius: float = 0.002,
    invert: bool = False,
    timer: bool = False,
    weight_solver: str = "newton",
    write_png: bool = True,
    ghostscript: str = "gs",
    dpi: int = 300,
) -> InferenceResult:
    request = InferenceRequest(
        image_array=pixels,
        native=NativeConfig(
            num_sites=num_sites,
            seed=seed,
            max_iters=max_iters,
            max_newton_iters=max_newton_iters,
            step_x=step_x,
            step_w=step_w,
            epsilon=epsilon,
            invert=invert,
            weight_solver=weight_solver,
            native_timer=timer,
        ),
        render=RenderConfig(
            enabled=True,
            render_width=render_width,
            render_height=render_height,
            point_radius=point_radius,
            png_enabled=write_png,
            dpi=dpi,
            ghostscript=ghostscript,
        ),
        output=OutputConfig(output_dir=output_dir, output_stem=output_stem),
        executable=executable,
    )
    return run_inference(request)
