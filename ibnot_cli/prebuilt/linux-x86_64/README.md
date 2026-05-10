# Linux x86_64 Prebuilt

This folder is for Linux/WSL users who want to run `ibnot_new_cli` without
compiling it locally.

Assumption:

- the repo-local Conda environment has already been created at `.conda/ibnot_cli`

Required step before running the binary:

```bash
cd ibnot_cli
./setup_env.sh
```

Then from the repo root:

```bash
./ibnot_cli/prebuilt/linux-x86_64/ibnot_new_cli --help
```

The binary is intentionally minimal. It relies on the repo-local Conda
environment for CGAL-related runtime dependencies instead of bundling shared
libraries into the repo.
