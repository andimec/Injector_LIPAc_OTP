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
- config/pv_registry_v1_2.json: machine-readable September 2026 Injector PV
  snapshot.
- config/pv_runtime_overrides.yaml: explicitly verified runtime ownership
  overrides for the pilot.
- config/simulation/default.yaml: startup conditions only.
- tests/: architecture, registry, state and simulation tests.
- docs/: architecture, runtime contract, interlock and configuration design.

## PV registry and runtime ownership

The V1.2 JSON snapshot contains 891 unique PV entries.

The source EPICS read/write flags do not uniquely determine Digital Twin
semantics. A read/write PV may be writable for implementation reasons while
being a monitor, status or calculated value from the simulation perspective.

Therefore:

1. The V1.2 registry defines the available PV inventory and source metadata.
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

All EPICS-facing simulation names use the OTP: namespace:

    LEBT:HV_PS:OnStat
    ->
    OTP:LEBT:HV_PS:OnStat

Any future Soft IOC adapter must fail closed if configured with a production
endpoint or production PV name.

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
- V1.2 PV registry supplies concrete PV names;
- ambiguous protection equations remain open rather than invented.

The LCS manual states that PPS/MPS OPI information is for monitoring and
diagnostic purposes and that actual protection functions are implemented by
hardware protection systems. The OTP therefore models observable
authorization/protection behaviour for training; it is not a replacement for
real PPS/MPS hardware.

Detailed design decisions and source traceability are documented in
docs/interlocks.md and docs/pv_runtime_contract.md.
