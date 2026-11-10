#!/usr/bin/env bash
# Runtime preflight with NO EPICS writes. The probe is strictly scoped to the
# training IOC connected via isolated Podman bridge.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
CONTAINER_IMAGE="${CONTAINER_IMAGE:-localhost/injector-ca-bridge:vacuum-full}"
IOCADDR="${IOCADDR:-10.0.3.16}"

printf '%s\n' '== Read-only isolated vacuum bridge preflight =='
if [[ "$IOCADDR" != "10.0.3.16" ]]; then
  echo 'STOP: this deployment script only accepts the known training IOC 10.0.3.16' >&2
  exit 2
fi
sudo podman run --rm --name injector-vacuum-preflight \
  --network internal --read-only --security-opt no-new-privileges \
  -e EPICS_CA_AUTO_ADDR_LIST=NO \
  -e EPICS_CA_ADDR_LIST="$IOCADDR" \
  -e BRIDGE_ALLOW_WRITES=NO -e BRIDGE_ISOLATED_ACK=NO \
  "$CONTAINER_IMAGE" \
  python -m injector_otp.epics.vacuum_full_bridge \
  --mode validate --ioc "$IOCADDR"
