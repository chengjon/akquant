#!/usr/bin/env bash
set -euo pipefail
PY_LIB_DIR="$(python -c 'import pathlib,sys; print(pathlib.Path(sys.prefix) / "lib")')"
if [[ -n "${DYLD_FALLBACK_LIBRARY_PATH:-}" ]]; then
  export DYLD_FALLBACK_LIBRARY_PATH="${PY_LIB_DIR}:${DYLD_FALLBACK_LIBRARY_PATH}"
else
  export DYLD_FALLBACK_LIBRARY_PATH="${PY_LIB_DIR}"
fi
cargo test "$@"
