# EPICS / Phoebus integration architecture

## Purpose

The Python Digital Twin owns simulated process behaviour and simulated PV
state. The Soft IOC owns only the EPICS representation and transport of that
state. Phoebus interacts with the Digital Twin exclusively through EPICS.

The authoritative boundary is:

    Phoebus
        |
        | CA / PVA
        v
    Simulation Soft IOC
        |
        | EPICS adapter / bridge
        v
    Python PV State
        |
        +-- Simulation Engine
        +-- Physical/reduced-order models
        +-- Interlocks / MPS / PPS
        +-- Fault Manager

## Responsibility boundary

### Phoebus

- operator visualization;
- operator commands;
- setpoint entry;
- alarms and graphical state representation.

Phoebus contains no simulation logic.

### Simulation Soft IOC

The Soft IOC is **planned**, not yet an end-to-end deployed CA/PVA interface. Its intended responsibilities are:

- define PVs;
- expose EPICS data types and metadata;
- accept permitted operator writes;
- publish Python-generated values;
- provide CA/PVA connectivity and monitors;
- enforce the operator-write allowlist and EPICS access rules.

It must not implement Injector behaviour.

EPICS databases can technically implement calculations and record links, but
that capability is deliberately not used for Digital Twin behavioural logic.
This keeps the simulation deterministic, testable and independent of the IOC.

### Python PV State

src/injector_otp/pv/state.py is the authoritative in-process state.

It stores:

- current PV values;
- wall-clock timestamps;
- source of the last update;
- operator input permissions.

It has no dependency on EPICS.

### Simulation Engine

The engine owns:

- simulation time;
- command/setpoint consumption;
- physical/reduced-order model execution;
- interlock evaluation;
- fault injection;
- state-machine behaviour;
- calculated output generation.

### EPICS bridge

The bridge translates between:

- simulation-owned PV state in Python;
- EPICS PVs in the Soft IOC.

It must not contain Injector logic.

## PV ownership

The runtime distinguishes:

| Role | Direction | Owner |
|---|---|---|
| COMMAND | EPICS -> Python | Operator |
| SETPOINT | EPICS -> Python | Operator |
| MONITOR | Python -> EPICS | Simulation |
| STATUS | Python -> EPICS | Simulation |
| CALCULATED | Python -> EPICS | Simulation |
| INITIAL_CONDITION | configuration -> Python | Configuration |
| UNRESOLVED | not yet verified | Unresolved |

Source workbook read/write flags are transport metadata and are not treated as
semantic ownership.

## Runtime cycle

The canonical cycle is:

1. Read current input PV state.
2. Apply active synthetic faults.
3. Evaluate pre-model authorization/control logic.
4. Update physical/reduced-order models.
5. Evaluate post-model protection consequences.
6. Generate simulation-owned readbacks/status/calculated values.
7. Publish them into Python PV state.
8. Advance deterministic simulation time.
9. EPICS bridge exposes updated values to the Soft IOC.

The physical model never calls EPICS directly.

## Timing

The configured default simulation timestep is 0.1 s.

Simulation and EPICS publication frequencies are independent. A future model may
run at a finer internal timestep while EPICS publication remains slower.

## Naming and isolated network boundary

Source LIPAc PV names are **preserved unchanged** in the Python state,
EPICS bridge, Soft IOC and Phoebus. There is no `OTP:` prefix translation.
For example, `LEBT:HV_PS:OnStat` remains `LEBT:HV_PS:OnStat`.

The VM must remain disconnected from the real LIPAc network. Restrict CA/PVA
listening and discovery to the VM's training-only interface, with no production
routes. Python's PV ownership allowlist still rejects writes to monitors and
external safety conditions.

## Backend/adapter design

The dependency direction is:

    Python models
        |
        v
    SimulationPVState
        |
        v
    EPICS bridge
        |
        v
    Soft IOC

The existing in-memory `SimulationPVBackend` is used by Python tests and local callers; the `LocalPVBridge` is likewise in-process. The engine does not depend on either transport. Both preserve source PV names without a namespace transform.

## First integration milestone

Use only PVs verified to exist in the active V2.0 registry, with confirmed ownership and correct EPICS record-field semantics. The initial pilot
should be based on:

    LEBT:HV_PS:HTOnCmd
    LEBT:HV_PS:OnStat
    LEBT:HV_PS:ICmd
    SRC:COIL01_PS:ON
    SRC:COIL01_PS:ISet
    SRC:COIL01_PS:IRdbk
    SRC:COIL01_PS:OnStat
    PPS:HV:PermStat
    PPS:BEAM:InhibitStat

The exact semantic classification of PVs not covered by the runtime override file remains unresolved. The examples are model/contract checks, not proof of OPI connectivity. Detailed write/readback pairs and known gaps are in [PV traceability](pv_readback_traceability.md).

Acceptance path:

    Phoebus command
        -> EPICS PUT
        -> Soft IOC
        -> Python input state
        -> simulation model / logic
        -> Python output state
        -> Soft IOC
        -> Phoebus monitor

## Production safety

Never connect this simulator with native PV names to the production LIPAc
network. Before exposing EPICS, verify VM network isolation, interfaces,
firewall rules and CA/PVA discovery. PV command allowlisting applies even
inside the isolated VM.

The network-isolation requirement is not yet validated by end-to-end tests.
