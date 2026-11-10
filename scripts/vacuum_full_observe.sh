#!/usr/bin/env bash
# Short, read-only end-to-end exercise. No CA publishes.
set -euo pipefail
sudo podman run --rm --name injector-vacuum-observe \
  --network internal --read-only --security-opt no-new-privileges \
  -e EPICS_CA_AUTO_ADDR_LIST=NO -e EPICS_CA_ADDR_LIST=10.0.3.16 \
  -e BRIDGE_ALLOW_WRITES=NO -e BRIDGE_ISOLATED_ACK=NO \
  localhost/injector-ca-bridge:vacuum-full \
  python -m injector_otp.epics.vacuum_full_bridge \
  --mode observe --ioc 10.0.3.16 --steps 100 --report-every 20
