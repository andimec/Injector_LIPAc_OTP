#!/usr/bin/env bash
# OTP-only Start SNL launcher for the EMU offline Python replay.
# The Phoebus EMU OPI already executes: /bin/bash Scripts/emitShell_v2.sh
# NEVER deploy this script over the LIPAc production shell installation.
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
exec /bin/bash "$REPO_ROOT/scripts/launch_emu_snl_replay.sh" "$@"
