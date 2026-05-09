#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BNOT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PREFIX="${BNOT_ROOT}/.conda/ibnot_cli"
CONDA_EXE="${CONDA_EXE:-$HOME/miniconda3/bin/conda}"

if [[ ! -x "${CONDA_EXE}" ]]; then
  echo "conda executable not found: ${CONDA_EXE}" >&2
  exit 1
fi

if [[ -d "${PREFIX}/conda-meta" ]]; then
  "${CONDA_EXE}" env update --prefix "${PREFIX}" --file "${SCRIPT_DIR}/environment.yml" --prune
else
  "${CONDA_EXE}" env create --prefix "${PREFIX}" --file "${SCRIPT_DIR}/environment.yml"
fi

echo "Environment ready at ${PREFIX}"
echo "Activate with: source \"${CONDA_EXE%/bin/conda}/bin/activate\" \"${PREFIX}\""
