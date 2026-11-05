#!/usr/bin/env bash
# Drop-in xterm launcher for OFFLINE EMU v2 playback only.
# It does not launch the original VxWorks/EPICS SNL executable.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export EPICS_CA_MAX_ARRAY_BYTES=10485760
export PYTHONPATH="$ROOT/src${PYTHONPATH+:$PYTHONPATH}"

if ! command -v xterm >/dev/null 2>&1; then
    printf 'Missing xterm. Install it or run: python3 -m injector_otp.models.emu_replay\n' >&2
    exit 1
fi
if [[ -z "${DISPLAY:-}" ]]; then
    printf 'DISPLAY is not set: launch from an X11 desktop or X-forwarded session.\n' >&2
    exit 1
fi

# Unlike the original ps|grep xterm, other independent xterms must not
# prevent this one from starting. Avoid duplicate EMU replay processes only.
if pgrep -f '^python3 -m injector_otp.models.emu_replay( |$)' >/dev/null 2>&1; then
    echo 'EMU replay console already running.'
    exit 0
fi
cd "$ROOT"
/usr/bin/xterm -g 110x60+995+80 -j +ah -hold -fg green -bg black -rightbar \
    -T 'EMU Fast Scan (OFFLINE REPLAY)' \
    -e python3 -m injector_otp.models.emu_replay "$@" &
