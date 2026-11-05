# Injector_LIPAc_OTP

LIPAc Injector Operator Training Platform (OTP) and Digital Twin.

## Purpose

This repository provides an offline, non-invasive Digital Twin of the LIPAc
Injector for operator training, procedure validation, fault injection,
logging/replay, and Phoebus/EPICS integration without commanding the real
machine.

## Core architectural principle

**Python owns the Injector behaviour. EPICS exposes the behaviour.**

The Soft IOC is deliberately a thin interface layer. It owns the EPICS
representation of PVs, transport, access and monitoring, but it does not own
Injector physics, equipment dynamics, interlocks, MPS/PPS causal logic, fault
propagation, ramp algorithms, or the Injector state machine.

    PHOEBUS
       |
     CA/PVA
       |
    SOFT IOC
       |
    EPICS bridge
       |
    PYTHON ENGINE
       |
       +-- PV State
       +-- Models
       +-- Interlocks
       +-- Faults
       +-- State machine

The Python runtime can run without EPICS or Phoebus. The EPICS implementation
is an adapter around the simulation-owned PV state.

## Package layout

- src/injector_otp/core: simulation clock, state machine and engine.
- src/injector_otp/pv: authoritative simulation PV state and runtime ownership
  contract. This package has no EPICS dependency.
- src/injector_otp/models: subsystem model interfaces and composition point.
- src/injector_otp/epics: transport contracts and adapters between Python PV
  state and the future simulation Soft IOC.
- src/injector_otp/faults: deterministic fault definitions and injection manager.
- src/injector_otp/interlocks: documented Injector authorization chains and
  complementary legacy PPS/MPS relationships.
- src/injector_otp/app.py: application composition and simulation bootstrap.
- config/pv_registry_v2_0.json: active reconciled registry (1052 PV references,
  including six EMU SNL interfaces), sourced from historic PV snapshot,
  original DB definitions and current OPIs.
- config/pv_registry_v1_2.json: preserved historical September 2026 snapshot
  (891 entries); not used by the default application bootstrap.
- config/pv_runtime_overrides.yaml: explicitly verified runtime ownership
  overrides for the pilot.
- config/simulation/default.yaml: startup conditions only.
- tests/: architecture, registry, state and simulation tests.
- docs/: architecture, runtime contract, interlock and configuration design.

## PV registry and runtime ownership

The active V2.0 registry contains 1052 PV references; the historical V1.2
snapshot contains 891 unique entries.

The source EPICS read/write flags do not uniquely determine Digital Twin
semantics. A read/write PV may be writable for implementation reasons while
being a monitor, status or calculated value from the simulation perspective.

Therefore:

1. The V2.0 registry defines the active PV inventory and source metadata.
2. Runtime overrides define only verified pilot inputs.
3. Unresolved PVs remain unresolved until their semantics are documented.
4. SimulationPVState is the source of truth for simulation values.

## Ownership rules

Operator inputs are commands and setpoints.

Simulation outputs are readbacks, equipment status and calculated values.

Configuration provides initial conditions only.

A simulation-owned PV cannot be written by an operator through the Python
runtime.

## Safety boundary

This repository is a training/simulation platform. It must never write to
production LIPAc control PVs.

The isolated virtual machine exposes the **original LIPAc PV names unchanged**.
For example, `LEBT:HV_PS:OnStat` remains `LEBT:HV_PS:OnStat` in
Python, the simulation Soft IOC and Phoebus. No `OTP:` renaming is applied.

**Deployment boundary:** the VM must have no connection or route to the LIPAc
production control network. CA/PVA interfaces must bind only to the isolated
VM or training-only network. Network isolation does not replace the Python
command allowlist, which prevents operator writes to readback and safety
signals. Never attach this unqualified naming scheme to the production LAN.

See [write/readback traceability](docs/pv_readback_traceability.md).

## Interlock logic

The Simulation Engine includes the documented Injector interlock layer through
InjectorInterlockLogic.

The interlock layer is intentionally external to physical subsystem models.
It reads observed PV states and writes normalized authorization signals into
SimulationControlPlane using:

    True  = authorized / allowed
    False = blocked

The implementation integrates the available documentation rather than
classifying one source as valid and another as invalid:

- current Injector LCS User Manual v4.0 supplies current HVPS, IEPS, RF-for-Plasma
  and RF-for-Beam authorization paths;
- PLC maintenance documentation supplies complementary historical Boolean
  relationships;
- V2.0 PV registry supplies reconciled concrete PV names;
- ambiguous protection equations remain open rather than invented.

The LCS manual states that PPS/MPS OPI information is for monitoring and
diagnostic purposes and that actual protection functions are implemented by
hardware protection systems. The OTP therefore models observable
authorization/protection behaviour for training; it is not a replacement for
real PPS/MPS hardware.

Detailed design decisions and source traceability are documented in
docs/interlocks.md and docs/pv_runtime_contract.md.

## EMU: SNL v2 simulation and experimental Fast Scan replay

The EMU provides **two distinct offline workflows**:

- **Python device/state models:** `emu_geometry.py`, `emu_hardware.py`,
  `emu_sequencer.py`, `emu_beam.py`, and `emu_analysis.py` reproduce
  SNL-derived geometry, the motor/plate/FACQ *training* responses, the scan
  sequence, and provisional RMS diagnostics. Acquisition is synthetic by
  default, not a calibrated beam measurement.
- **Recorded-data replay:** `emu_replay.py` reads the 2026 experimental
  five-column `_optm.txt` files, prints the saved samples in `xterm`,
  and generates a compatible `emitYYYYMMDD-HHmm_optm.txt` result with
  an additional `*.replay.json` provenance file. This adapter does not
  publish EPICS PVs, run the physical model or fabricate waveforms.

The archived **Fast Scan** (6 July 2026) has **45 motor positions × 31
voltage points = 1,395 samples**. Its operator parameters are upper 46 mm,
lower -42 mm, step 2 mm, 100 keV (D+), angle peaks -37/+45 mrad, angular
width 20 mrad, and 30 HV intervals. A Full Scan reference uses upper 60 mm,
lower -44 mm, step 2 mm, 0/0 mrad, angular width 100 mrad and 120 HV
intervals. The Python sequencer uses a generic ROI scan; it does not yet
offer named Fast/Full preset selection.

The OTP OPI `Injector_OPI/emitMeasurement_v2.bob` retains its **Start SNL**
action, calling `Injector_OPI/Scripts/emitShell_v2.sh`. That **training
copy** now opens the Python replay in xterm. It initially shows **waiting**,
then accepts `validate` and `on` typed in the terminal. The actual
Phoebus **Validate/ON** controls are not yet connected to this process
through the EPICS bridge. Do not install the OTP script on LIPAc.

```bash
python3 -m pip install -e ".[dev]"
# Synthetic internal model
python scripts/demo_emu.py --mode emittance --synthetic-signal --out /tmp/emu_training.csv
# Recorded Fast Scan with xterm on a local X11 desktop (about 3 minutes)
./scripts/launch_emu_snl_replay.sh --duration 180
# Immediate headless reproduction with output + provenance
python3 -m injector_otp.models.emu_replay --auto --output-dir output/emu
# Regression checks
pytest tests/test_emu_replay.py tests/test_emu_sequences.py tests/test_emu_geometry.py
```

Documentation: [Fast Scan experimental replay](docs/emu_fast_scan_replay.md),
[SNL v2 reconstruction](docs/emu_reconstruction.md),
[model inventory](src/injector_otp/models/README.md),
[technical documentation index](docs/README.md).

**Boundary:** Neither path contacts production LIPAc CA/PVA endpoints;
the future Soft IOC must be isolated. CI tests do not validate xterm
rendering, OPI-to-PV connectivity or calibrated machine physics.
