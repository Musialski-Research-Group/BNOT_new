#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLI_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${CLI_DIR}/.." && pwd)"
ENV_PREFIX="${REPO_ROOT}/.conda/ibnot_cli"
BUILD_DIR="${CLI_DIR}/build-linux-x86_64-release"
DEPLOY_DIR="${CLI_DIR}/prebuilt/linux-x86_64"
BIN_NAME="ibnot_new_cli"
RPATH_VALUE="\$ORIGIN/../../../.conda/ibnot_cli/lib"

CONDA_EXE="${CONDA_EXE:-$HOME/miniconda3/bin/conda}"
if [[ ! -x "${CONDA_EXE}" ]]; then
  echo "conda executable not found: ${CONDA_EXE}" >&2
  exit 1
fi

if [[ ! -d "${ENV_PREFIX}/conda-meta" ]]; then
  echo "repo-local env missing at ${ENV_PREFIX}" >&2
  echo "run ./setup_env.sh inside ibnot_cli first" >&2
  exit 1
fi

mkdir -p "${DEPLOY_DIR}"

"${CONDA_EXE}" run --prefix "${ENV_PREFIX}" cmake \
  -S "${CLI_DIR}" \
  -B "${BUILD_DIR}" \
  -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_PREFIX_PATH="${ENV_PREFIX}" \
  -DCMAKE_BUILD_RPATH="${RPATH_VALUE}" \
  -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON \
  -DCMAKE_INSTALL_RPATH="${RPATH_VALUE}" \
  -DCMAKE_INSTALL_RPATH_USE_LINK_PATH=FALSE

"${CONDA_EXE}" run --prefix "${ENV_PREFIX}" cmake --build "${BUILD_DIR}"

cp "${BUILD_DIR}/${BIN_NAME}" "${DEPLOY_DIR}/${BIN_NAME}"
chmod +x "${DEPLOY_DIR}/${BIN_NAME}"
"${CONDA_EXE}" run --prefix "${ENV_PREFIX}" patchelf --set-rpath "${RPATH_VALUE}" "${DEPLOY_DIR}/${BIN_NAME}"

{
  echo "artifact: ${BIN_NAME}"
  echo "platform: linux-x86_64"
  echo "build_type: Release"
  echo "rpath: ${RPATH_VALUE}"
  echo "env_prefix: .conda/ibnot_cli"
  echo "built_at_utc: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo "git_head: $(git -C "${REPO_ROOT}" describe --always --dirty 2>/dev/null || echo unknown)"
} > "${DEPLOY_DIR}/BUILD_INFO.txt"
