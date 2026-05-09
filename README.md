# BNOT_new

`BNOT_new` is a cleaned, headless baseline for capacity-constrained stippling derived from the original BNOT (`Blue Noise through Optimal Transport`) `ibnot` implementation.

This repo is intended for internal group use and student experimentation. The shared tool lives in [`ibnot_new/`](ibnot_new).

## What Is Included

- Headless C++ source for `ibnot_new_cli`
- Repo-local Conda environment bootstrap
- Smoke-test input data
- A few example outputs in `ibnot_new/results/`

## Quick Start

Assumptions:

- Linux or WSL
- Miniconda available at the default path, or `CONDA_EXE` set explicitly

Create the local environment:

```bash
cd ibnot_new
./setup_env.sh
```

Build:

```bash
conda run --prefix ../.conda/ibnot_new cmake -S . -B build -G Ninja -DCMAKE_PREFIX_PATH=../.conda/ibnot_new
conda run --prefix ../.conda/ibnot_new cmake --build build
```

Smoke test:

```bash
conda run --prefix ../.conda/ibnot_new ./build/ibnot_new_cli \
  --image testdata/smoke_8x8.pgm \
  --num-sites 16 \
  --seed 7 \
  --max-iters 10 \
  --max-newton-iters 20 \
  --output smoke_result.eps \
  --stats smoke_result.txt
```

## Notes

- Current input format is grayscale `.pgm`.
- The main supported path is `--weight-solver newton`.
- The `gd` path is kept for debugging, not as the preferred comparison mode.

See [`PROVENANCE.md`](PROVENANCE.md) for derivation and licensing context.
