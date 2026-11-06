# Injector LIPAc OTP: current software architecture

> **Baseline:** 6 November 2026. Includes proposed VAC01/VAC02 coupled vacuum V1.4 on the PR #11 feature branch, as well as the offline EMU Fast/Full replay. Neither this model nor the Soft IOC is a deployed or physically validated replica of LIPAc.

## 1. Design and deployment rules

1. **Python owns Injector behaviour.** Physical/reduced-order models, state, fault propagation, ramp sequencing, authorization calculations, and readback values run in Python.
2. **EPICS is a transport/interface.** A future thin Soft IOC exposes PV types, field metadata and CA/PVA subscriptions; it must not independently calculate machine behaviour.
3. **Native source names.** Keep `SRC:...`, `LEBT:...`, `PPS:...` etc. unchanged across Python, the simulated IOC and Phoebus. Do **not** prepend `OTP:`.
4. **Strict write ownership.** Only allowlisted operator commands/setpoints are writable. Readbacks and external PPS/PLC conditions are not writable through the operator backend.
5. **Network isolation is mandatory.** The VM and its training interfaces must have no connection, route, broadcast, discovery or VPN path to the actual LIPAc controls. Identical PV names are acceptable only in that isolated environment.
6. **Traceability and model maturity.** A source PV, source formula or OPI widget does not prove that a physically realistic Python model exists.

## 2. Current data flow

```text
Phoebus OPI  (future end-to-end integration)
    |  EPICS CA/PVA, native Injector PV names
    v
Thin simulation Soft IOC  (not yet implemented end-to-end)
    |  local bridge/adapter
    v
SimulationPVState (src/injector_otp/pv/state.py)
    |  commands/setpoints, model-owned readbacks
    v
SimulationEngine (src/injector_otp/core/engine.py)
    +-- SimulationControlPlane + InjectorInterlockLogic
    +-- InjectorModel / device models
    +-- FaultManager
    +-- injector operating state
    +-- internal SIM:STATE and SIM:TIME
```

The **existing** `SimulationPVBackend` and `LocalPVBridge` are in-memory/local adapters. Neither is proof of a running networked Soft IOC. `SIM:STATE` and `SIM:TIME` are internal runtime indicators, not original Injector device PVs.

## 3. Runtime implementation

- Entry point: `src/injector_otp/app.py:build_application()`. The default registry is `config/pv_registry_v2_0.json`.
- PV metadata, original DB fields and clamping: `models/catalog.py`.
- Time-step and publication: `core/engine.py`. The default step is **0.1 s**, not an EPICS network publication guarantee.
- Operator writes vs simulation publication: `pv/state.py` and `config/pv_runtime_overrides.yaml`.
- Deterministic faults: `faults/manager.py`, injected through control/model states.
- Injector state machine: `core/state.py`. Its state progression is a framework, not a validated operational procedure controller.
- Pre/post model authorization: `interlocks/logic.py` and `core/control.py`.

The engine reads the current PV state, applies faults, evaluates pre-model authorization, advances models, evaluates authorization again, processes internal allowlisted command requests, publishes outputs, and advances its simulation clock. See [PV runtime contract](pv_runtime_contract.md) for the precise interface rules.

## 4. Implemented model families

| Domain | Python implementation | Current maturity |
|---|---|---|
| HV, IE, repellers, coils, solenoids and steerers | `models/power_supplies.py`; `hv_auto_ramp.py` | Rate-limited responses, status and source scaling; no verified transient calibration |
| H₂/D₂/Kr MFC, valves and cooling | `models/plant.py` | MFC first-order response, valve states and per-device synthetic faults; legacy `VacuumRegionModel` only for compatibility |
| VAC01/VAC02 vacuum coupled by GV | `models/vacuum_network.py`; `vacuum_calibration.py`; `vacuum_opi.py` | Six C/T/F volumes, ideal partial pressures, configurable pumpdown hours/target/ultimate, flow-pressure CSV, PV states; uncalibrated training model, original PLC permits unresolved |
| RF generator, ATU encoding and timing | `models/control_devices.py` | Source register/bit calculations plus synthetic dynamics; not a full RF/coupling model |
| Chopper/CIM | `models/chopper_cim.py` | Synthetic PRE-ARM/ARMED/FBI and snapshots; FPGA logic unverified |
| Faraday cup, positioners and calorimetry | `models/control_devices.py`; `calorimetry.py` | Qualitative beam signal and recovered legacy equations |
| EMU motor, servo, HV plates, FACQ and scans | `models/emu_hardware.py`; `emu_sequencer.py`; `emu_geometry.py`; `emu_analysis.py` | Source-derived in-memory SNL model; synthetic FACQ, motor/plate dynamics unvalidated |
| EMU archived Fast/Full scan playback | `models/emu_replay.py`; `scripts/launch_emu_snl_replay.sh`; `Injector_OPI/Scripts/emitShell_v2.sh` | Standalone xterm replay of three archived datasets, legacy TXT output plus provenance; no PV bridge |
| Current authorization and selected historical PLC equations | `interlocks/logic.py`; `original_lcs_logic.py` | Training logic, not an implementation of the real safety system |

Model registration and maturity labels are in `src/injector_otp/models/injector.py` and `src/injector_otp/models/README.md`. Some source signals are **interface-only** and deliberately have no fabricated readback.

## 5. PV inventory and traceability

- **Active:** `config/pv_registry_v2_0.json`, **1,052 PV/field references**, including six EMU SNL-related additions.
- **Historical:** `config/pv_registry_v1_2.json`, 891 entries, kept for provenance, not selected by default.
- Source evidence: copied DBs in `db/`, original-index audit in `audit/original_lcs/`, PV comparison in `audit/registry_v2/`, and historic/current OPI assets in `Injector_OPI/`.
- Readback traceability and known missing pairs: [PV write/readback matrix](pv_readback_traceability.md).
- Verified operator write allowlist: `config/pv_runtime_overrides.yaml`. PV access metadata must not be treated as proof of semantic write ownership.

A registry entry may represent a record field, a macro-dependent name, an OPI reference, an old DB record or a physical process monitor. Presence alone is neither executable IOC coverage nor evidence of a calibrated model.

## 6. Protection boundary

`PPS:*:PermStat` and related inhibit signals are simulated **external conditions** until authoritative PPS behaviour is implemented. Current and historical authorization equations are modeled separately. No part of this repository replaces PPS/MPS hardware. Consult [interlocks](interlocks.md).

## 7. Development milestones

| Area | Status as of baseline |
|---|---|
| Architecture, local Python state and tests | Implemented |
| VAC01/VAC02 coupled vacuum network + configurable pumpdown + fault injections | Implemented on PR #11 feature branch; OEM/procedure calibration pending |
| Measured gas-flow/pressure CSV interface | Implemented for steady-state delta pressure at nominal pumping; calibration datasets pending |
| V2.0 PV inventory and Python models | Implemented in varying levels of maturity |
| EMU offline scanning and provisional analysis | Implemented in memory; physical calibration pending |
| EMU recorded-data replay in xterm | CLI and OPI Start SNL script hook implemented, GUI on Debian unverified |
| OPI Validate/ON linked to the Python replay via a Soft IOC | **Pending** |
| Native PV naming and local write authorization | Implemented in Python |
| Generated dumb IOC records with record-field fidelity | **Pending** |
| EPICS 7 CA/PVA + Python bidirectional bridge | **Pending** |
| Phoebus end-to-end operation on isolated Debian VM/Podman | **Pending** |
| Calibrated beam, vacuum, RF, EMU, protections | **Pending**: pressure-network implementation does not equal LIPAc experimental validation |
| Procedures, logging/replay, complete automated PV/OPI coverage | Partial/planned |

## 8. Related documents

[Vacuum network V1.4](vacuum_model.md) · [Vacuum physics](models/vacuum_network.md) · [Vacuum calibration](models/vacuum_calibration.md) · [Configuration](configuration.md) · [EPICS architecture](epics_architecture.md) · [IOC contract](simulation_ioc_contract.md) · [PV runtime contract](pv_runtime_contract.md) · [Readback matrix](pv_readback_traceability.md) · [Modeling baseline](modeling_baseline.md) · [Original LCS provenance](original_lcs_model_logic.md) · [EMU reconstruction](emu_reconstruction.md) · [EMU archived Fast Scan replay](emu_fast_scan_replay.md).

### Separate EMU recorded-data path

```text
Training Phoebus OPI Start SNL (command action)
  -> Injector_OPI/Scripts/emitShell_v2.sh
  -> scripts/launch_emu_snl_replay.sh
  -> xterm + Python models/emu_replay.py
  -> read-only Data/EMU/emit*_optm.txt
  -> local output/emu/emitYYYYMMDD-HHmm_optm.txt + *.replay.json
```

This path **does not run the in-memory `EmuScanSequencer` or
`SimulationPVBackend`**, and does not write EPICS PVs. The OPI
Validate and ON controls remain unconnected to it; the terminal
accepts `validate` and `on` instead. Isolation and provenance are
required to avoid confusing replay output with a fresh beam acquisition.

### Vacuum V1.4 state ownership and limitations

```text
Commands PV (operator owned)          MFC flow readbacks (plant.py)
    |                                             |
    +-- ValveDevice (PV, SV, AIV, NIV01, GV)      |
    +-- Pump commands                             |
              |                                  |
              +---------------+------------------+
                              v
                     VacuumNetworkModel
                C1/T1/F1 <--> GV <--> C2/T2/F2
                              |
                        Pump and gauge PVs
                              |
                    SimulationContext.emit()
```

`vacuum_calibration.py` supplies configurable pressure/time profiles,
SCCM-to-throughput and optional steady-state MFC delta-pressure tables.
An individual `device_faults["LEBT:VAC01:TP"]` affects TP01 rather than
all vacuum devices. **VAC02 has no physical NIV**; the original DB command
names are retained only as inactive historical references.

**Training boundary:** the `VacuumOPIPreconditions` results reproduce
OPI visual formulas. They must not authorize the real Siemens PLC or silently
activate `SVForcing`. TP speed at 70% is observable internally but does
not automatically close PV. See [red de vacío](models/vacuum_network.md).
