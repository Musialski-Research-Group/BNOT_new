from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import numpy as np
import os
import shutil
import subprocess
from typing import Mapping, Optional, Sequence


NumberGrid = Sequence[Sequence[float | int]] | np.ndarray


@dataclass
class RunResult:
    image_path: Path
    eps_path: Path
    stats_path: Path
    png_path: Optional[Path]
    command: list[str]
    stdout: str
    stderr: str
    stats: Mapping[str, object]


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
    return np.full((size, size), np.clip(float(value), 0.0, 1.0), dtype=float)


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
) -> RunResult:
    cli = find_default_executable(executable)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    if (render_width is None) != (render_height is None):
        raise ValueError("render_width and render_height must be provided together")
    if render_width is not None and render_width <= 0:
        raise ValueError("render_width must be positive")
    if render_height is not None and render_height <= 0:
        raise ValueError("render_height must be positive")
    if point_radius <= 0.0:
        raise ValueError("point_radius must be positive")
    if dpi <= 0:
        raise ValueError("dpi must be positive")

    eps_path = output_root / f"{output_stem}.eps"
    stats_path = output_root / f"{output_stem}.txt"

    cmd = [
        str(cli),
        "--image",
        str(Path(image_path)),
        "--output",
        str(eps_path),
        "--stats",
        str(stats_path),
        "--seed",
        str(seed),
        "--max-iters",
        str(max_iters),
        "--max-newton-iters",
        str(max_newton_iters),
        "--step-x",
        str(step_x),
        "--step-w",
        str(step_w),
        "--epsilon",
        str(epsilon),
        "--point-radius",
        str(point_radius),
        "--weight-solver",
        weight_solver,
    ]

    if render_width is not None and render_height is not None:
        cmd.extend(["--render-width", str(render_width), "--render-height", str(render_height)])

    if points_path is not None:
        cmd.extend(["--points", str(Path(points_path))])
    elif num_sites is not None:
        cmd.extend(["--num-sites", str(num_sites)])
    else:
        raise ValueError("provide either points_path or num_sites")

    if invert:
        cmd.append("--invert")
    if timer:
        cmd.append("--timer")

    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(
            "ibnot_new_cli failed\n"
            f"command: {' '.join(cmd)}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )

    png_path: Optional[Path] = None
    if write_png:
        png_path = output_root / f"{output_stem}.png"
        convert_eps_to_png(
            eps_path,
            png_path,
            ghostscript=ghostscript,
            width=render_width,
            height=render_height,
            dpi=dpi,
        )

    return RunResult(
        image_path=Path(image_path),
        eps_path=eps_path,
        stats_path=stats_path,
        png_path=png_path,
        command=cmd,
        stdout=completed.stdout,
        stderr=completed.stderr,
        stats=parse_stats_file(stats_path),
    )


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
) -> RunResult:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    pgm_path = output_root / f"{output_stem}_input.pgm"
    write_pgm(pgm_path, pixels)

    return run_from_image(
        pgm_path,
        output_root,
        output_stem,
        executable=executable,
        num_sites=num_sites,
        seed=seed,
        max_iters=max_iters,
        max_newton_iters=max_newton_iters,
        step_x=step_x,
        step_w=step_w,
        epsilon=epsilon,
        render_width=render_width,
        render_height=render_height,
        point_radius=point_radius,
        invert=invert,
        timer=timer,
        weight_solver=weight_solver,
        write_png=write_png,
        ghostscript=ghostscript,
        dpi=dpi,
    )


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
) -> RunResult:
    return run_from_array(
        pixels,
        output_dir,
        output_stem,
        executable=executable,
        num_sites=num_sites,
        seed=seed,
        max_iters=max_iters,
        max_newton_iters=max_newton_iters,
        step_x=step_x,
        step_w=step_w,
        epsilon=epsilon,
        render_width=render_width,
        render_height=render_height,
        point_radius=point_radius,
        invert=invert,
        timer=timer,
        weight_solver=weight_solver,
        write_png=write_png,
        ghostscript=ghostscript,
        dpi=dpi,
    )
