#!/usr/bin/env bash
# Run the in-memory Python Injector simulation, from any working directory.
# Never connects to production EPICS CA/PVA endpoints.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -n "${PYTHON:-}" ]]; then
    PYTHON_EXEC="$PYTHON"
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
    PYTHON_EXEC="$ROOT/.venv/bin/python"
else
    PYTHON_EXEC="python3"
fi
export PYTHONPATH="$ROOT/src${PYTHONPATH+:$PYTHONPATH}"
cd "$ROOT"
exec "$PYTHON_EXEC" -m injector_otp.runner "$@"
