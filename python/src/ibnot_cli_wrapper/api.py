from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import os
import shutil
import subprocess
import tempfile
from typing import Iterable, Mapping, Optional, Sequence


NumberGrid = Sequence[Sequence[float | int]]


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


def _normalize_value(value: float | int) -> int:
    if math.isnan(float(value)) or math.isinf(float(value)):
        raise ValueError("PGM values must be finite")

    numeric = float(value)
    if 0.0 <= numeric <= 1.0:
        numeric *= 255.0
    numeric = max(0.0, min(255.0, numeric))
    return int(round(numeric))


def write_pgm(path: Path | str, pixels: NumberGrid) -> Path:
    output = Path(path)
    rows = [list(row) for row in pixels]
    if not rows or not rows[0]:
        raise ValueError("pixels must be a non-empty rectangular grid")

    width = len(rows[0])
    for row in rows:
        if len(row) != width:
            raise ValueError("pixels must be rectangular")

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        handle.write("P2\n")
        handle.write(f"{width} {len(rows)}\n")
        handle.write("255\n")
        for row in rows:
            handle.write(" ".join(str(_normalize_value(value)) for value in row))
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
    dpi: int = 300,
) -> Path:
    gs = shutil.which(ghostscript)
    if gs is None:
        raise FileNotFoundError(f"Ghostscript executable not found: {ghostscript}")

    eps = Path(eps_path)
    png = Path(png_path)
    png.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        gs,
        "-dSAFER",
        "-dBATCH",
        "-dNOPAUSE",
        "-dEPSCrop",
        "-sDEVICE=png16m",
        f"-r{dpi}",
        f"-sOutputFile={png}",
        str(eps),
    ]
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
    invert: bool = False,
    timer: bool = False,
    weight_solver: str = "newton",
    write_png: bool = False,
    ghostscript: str = "gs",
) -> RunResult:
    cli = find_default_executable(executable)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

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
        "--weight-solver",
        weight_solver,
    ]

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
        convert_eps_to_png(eps_path, png_path, ghostscript=ghostscript)

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
    invert: bool = False,
    timer: bool = False,
    weight_solver: str = "newton",
    write_png: bool = False,
    ghostscript: str = "gs",
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
        invert=invert,
        timer=timer,
        weight_solver=weight_solver,
        write_png=write_png,
        ghostscript=ghostscript,
    )
