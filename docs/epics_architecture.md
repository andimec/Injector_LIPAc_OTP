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

The Soft IOC is intentionally simple:

- define PVs;
- expose EPICS data types and metadata;
- accept permitted operator writes;
- publish Python-generated values;
- provide CA/PVA connectivity and monitors;
- enforce the simulation namespace and EPICS access rules.

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

The initial simulation timestep is 0.1 s.

Simulation and EPICS publication frequencies are independent. A future model may
run at a finer internal timestep while EPICS publication remains slower.

## Namespace safety

Production-like source:

    LEBT:HV_PS:OnStat

Simulation endpoint:

    OTP:LEBT:HV_PS:OnStat

The OTP: namespace is mandatory.

The Python state may use source Injector names internally because it is not a
network endpoint. The EPICS adapter maps them to OTP:.

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

The old in-memory SimulationPVBackend is retained as a compatibility adapter
for tests and pre-IOC development. The engine no longer imports it.

## First integration milestone

Use only PVs verified to exist in the current V1.2 registry. The initial pilot
should be based on:

    OTP:LEBT:HV_PS:HTOnCmd
    OTP:LEBT:HV_PS:OnStat
    OTP:LEBT:HV_PS:ICmd
    OTP:SRC:COIL01_PS:ON
    OTP:SRC:COIL01_PS:ISet
    OTP:SRC:COIL01_PS:IRdbk
    OTP:SRC:COIL01_PS:OnStat
    OTP:PPS:HV:PermStat
    OTP:PPS:BEAM:InhibitStat

The exact semantic classification of PVs not covered by the runtime override
file remains unresolved.

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

The OTP must never use production Injector PV names as network endpoints.

A future EPICS adapter must reject:

- production PV names;
- production IOC addresses;
- missing OTP: prefix where a network-facing PV is expected.

EPICS access security may add user/host restrictions, but the Python ownership
rules remain authoritative for simulation semantics.
