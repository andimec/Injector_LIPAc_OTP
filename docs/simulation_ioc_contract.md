# Simulation IOC contract

## Purpose

The digital twin runs inside a VM physically/logically isolated from the LIPAc
production network. PV names remain **identical** to the original Injector
interface. Phoebus screens should not require an `OTP:` prefix.

- Example: `LEBT:SOL01_PS:ISet` stays `LEBT:SOL01_PS:ISet`.
- The local `SimulationPVBackend` performs no name translation.
- The future Soft IOC must publish only on the private VM/training interfaces.
  Deployment must verify absent LIPAc routing, CA discovery and PVA address
  lists before enabling any EPICS listener.
- Python owns readback generation. The Soft IOC transports the model's
  outputs and accepts only allowlisted commands/setpoints.

## Ownership and access

The runtime `config/pv_runtime_overrides.yaml` provides the explicit
operator-input allowlist. EPICS read/write transport metadata alone cannot
authorize a write. PVs that represent status, readback, external PPS/PLC
conditions or unresolved signals are not operator-writable.
Model publication is separate from operator writes.

The backend provides `get`, `put`, `publish`, `names`, timestamps and
snapshots. The bridge does not implement machine logic.

## Internal simulation status

The local runtime uses `SIM:STATE` and `SIM:TIME` for internal indicators.
These are **not** source LIPAc equipment PVs.

## Relationship to current code and PV inventory

The active V2.0 registry contains 1,052 PV/field references; historical V1.2 contains 891 entries. `build_application()` loads V2.0 by default. The local `SimulationPVBackend` and `LocalPVBridge` now preserve names identically and use `SimulationPVState`'s write ownership rules. The copied historical `db/` files are **not** a production-ready thin IOC database: they contain legacy processing and source device drivers.

Read [architecture](architecture.md), [configuration](configuration.md), [PV runtime contract](pv_runtime_contract.md) and [readback matrix](pv_readback_traceability.md) for the full implementation boundaries.

## Validation limits

This contract does not certify that the VM is isolated. Isolation is a
deployment-level requirement, and there is no real CA/PVA Soft IOC in this
Python baseline. No path to the production accelerator is intended.

See [PV/readback traceability](pv_readback_traceability.md).
