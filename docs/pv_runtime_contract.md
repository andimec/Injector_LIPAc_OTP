# PV Runtime Contract

## Purpose

This document defines the boundary between the LIPAc Injector Digital Twin
runtime and its EPICS/Phoebus interface.

The central architectural rule is:

> **EPICS exposes simulation state; Python owns the Injector behaviour.**

The Soft IOC must therefore remain as simple as practical. It defines and
publishes PVs, accepts permitted operator inputs, and transports values between
Phoebus and the Python runtime. It does not implement Injector physics,
interlocks, MPS/PPS behaviour, ramp algorithms, fault propagation, or the
simulation state machine.

## 1. PV ownership

Every PV has one logical owner of its value:

| Ownership | Meaning |
|---|---|
| Operator | Phoebus supplies a command or setpoint; Python consumes it. |
| Simulation | Python generates the value; EPICS only exposes it. |
| Configuration | Initial condition supplied when a simulation instance starts. |
| Unresolved | Source information is insufficient to assign semantic ownership. |

A PV must not have two competing sources of truth.

The source workbook's EPICS read/write flags are treated as transport metadata,
not as a complete semantic ownership definition. A PV that is technically
read/write in the existing IOC is not automatically considered an operator
input in the Digital Twin.

## 2. Input/output classification

The runtime distinguishes:

- COMMAND: discrete operator action, e.g. OnCmd.
- SETPOINT: requested physical value, e.g. ISet.
- MONITOR: measured/read-back process value.
- STATUS: equipment or state indication.
- CALCULATED: value derived by simulation or protection logic.
- INITIAL_CONDITION: startup input supplied by scenario configuration.
- UNRESOLVED: semantics not yet verified from authoritative documentation.

The existing source PV registry remains the interface inventory. Runtime
ownership and semantic role are an additional layer.

## 3. Command, setpoint and monitor semantics

A command expresses an action:

    SRC:COIL01_PS:OnCmd = 1

A setpoint expresses a requested value:

    SRC:COIL01_PS:ISet = 41.6

A readback expresses simulated equipment behaviour:

    SRC:COIL01_PS:IRdbk = 37.8

A status expresses the resulting equipment state:

    SRC:COIL01_PS:OnStat = 1

An authorization result expresses calculated protection logic:

    PPS:HV:PermStat = 0

ISet and IRdbk are intentionally different variables. The Python model
determines the dynamic response between them.

## 4. Write ownership

Only commands and setpoints explicitly classified as operator inputs may be
written by Phoebus.

Calculated/status/readback PVs are simulation-owned and must reject external
writes.

This rule is enforced twice:

1. At the EPICS access boundary.
2. In the Python PV state layer.

EPICS access security can additionally restrict writes by user/host when the
Soft IOC is deployed. This is an additional control layer, not a substitute for
Python ownership enforcement. EPICS supports field-level access security and
read/write rules for IOC records.

## 5. PV generation

Every simulation-owned PV should have a clear generator.

| PV | Generator |
|---|---|
| SRC:COIL01_PS:ISet | Operator |
| SRC:COIL01_PS:OnCmd | Operator |
| SRC:COIL01_PS:IRdbk | CoilModel |
| SRC:COIL01_PS:OnStat | CoilModel |
| SRC:COIL01:FSDefStat | CoilModel / FaultManager |
| LEBT:HV_PS:VMon | HVModel |
| LEBT:HV_PS:OnStat | HVModel |
| PPS:HV:PermStat | external PPS condition / future PPSModel |
| PPS:PLSM:PermStat | external PPS condition / future PPSModel |
| PPS:BEAM:InhibitStat | external protection condition / future PPSModel |

Where documentation does not establish the generator, it remains unresolved
rather than being invented.

## 6. Simulation cycle

The canonical runtime cycle is:

    EPICS inputs
        |
        v
    1. Read commands/setpoints
        |
        v
    2. Apply external conditions
        |
        v
    3. Apply active synthetic faults
        |
        v
    4. Update physical/reduced-order models
        |
        v
    5. Evaluate interlocks / MPS / PPS consequences
        |
        v
    6. Generate readbacks/status/calculated outputs
        |
        v
    7. Publish simulation-owned PV state
        |
        v
    8. Advance deterministic simulation time
        |
        +---- repeat

The exact ordering may be refined when coupled models require pre- and
post-protection evaluation, but physical models never call EPICS directly.

## 7. Timing

The simulation clock is independent of the EPICS transport clock.

Initial default:

- Simulation timestep: 0.1 s (10 Hz).
- EPICS publication: configurable independently.
- Phoebus display rate: determined by the OPI/EPICS monitoring configuration.

Future high-rate models may run at a finer internal timestep without requiring
the same publication rate to EPICS.

The first implementation must prioritise deterministic behaviour over maximum
rate.

## 8. Timestamps

Each PV value maintained by Python has:

- PV name;
- value;
- wall-clock update timestamp;
- logical source.

The engine separately maintains deterministic simulation time.

This distinction is required for logging, replay, debugging and comparison with
experimental data.

## 9. Fault injection

Faults are causal model inputs, not direct PV manipulations.

Correct:

    COIL01_FLOW_FAILURE
        -> CoilModel fault condition
        -> SRC:COIL01:FSDefStat = FALSE
        -> interlock evaluation
        -> PPS:HV:PermStat = FALSE
        -> HV model response

Incorrect:

    COIL01_FLOW_FAILURE
        -> directly force PPS:HV:PermStat = FALSE

The FaultManager therefore requests a fault condition; the affected model and
protection logic determine the observable consequences.

## 10. Native PV names and isolated VM

No EPICS `OTP:` name rewriting is used. The original source names are exposed
unchanged on the offline VM; for example `LEBT:HV_PS:OnStat` is the same
name in Python, Soft IOC and Phoebus. The VM must not connect or route to
LIPAc production controls. The operator-input allowlist remains mandatory.

## 11. EPICS is an interface, not the Injector logic

The Soft IOC is intentionally limited to:

- PV definitions;
- EPICS data types and metadata;
- read/write access;
- transport;
- publication of values supplied by Python;
- connection/monitor behaviour.

The Soft IOC must not implement:

- Injector physics;
- equipment dynamics;
- interlock equations;
- MPS/PPS causal logic;
- power-supply ramp algorithms;
- fault propagation;
- Injector operating-state transitions.

This is a deliberate difference from the existing Injector implementation,
where some device behaviour is represented in EPICS/SNL. The OTP reproduces
the externally observable behaviour in Python rather than reproducing the
implementation language of the production controls.

## 12. Independence and safety boundary

The Python simulation must run without EPICS or Phoebus.

The intended dependency direction is:

    Phoebus
       |
       v
    EPICS Soft IOC
       |
       v
    EPICS adapter / bridge
       |
       v
    Python Digital Twin
       |
       +-- models
       +-- interlocks
       +-- faults
       +-- PV state

The reverse dependency is forbidden: physical models must not import EPICS
libraries.

The isolated VM uses unmodified source PV names. Its EPICS adapter must
be configured to bind only to private VM/training network interfaces and
must never discover or route to the LIPAc control network.

## 13. Current verified pilot contract (Python-side)

The first **future end-to-end** slice should use the following names, provided they are verified against the source V2.0 catalog and the current input allowlist:

    LEBT:HV_PS:HTOnCmd
    LEBT:HV_PS:OnStat
    LEBT:HV_PS:ScaleVHT
    SRC:COIL01_PS:ISet
    SRC:COIL01_PS:IRdbk
    PPS:HV:PermStat
    PPS:BEAM:InhibitStat

The acceptance path is:

    Phoebus
      -> EPICS PUT
      -> Soft IOC
      -> Python input state
      -> simulation model / logic
      -> Python output state
      -> Soft IOC
      -> Phoebus monitor

The internal indicators `SIM:STATE` and `SIM:TIME` are **not** LIPAc equipment PVs. The read/write matrices, known readback gaps, and source scaling caveats are detailed in [PV write/readback traceability](pv_readback_traceability.md). The local backend currently preserves native names without a prefix.

## Source traceability

The current Injector LCS User Manual v4.0 documents the current LCS
architecture, operator interfaces, vacuum controls, power-supply controls and
interlock panels. The maintenance documentation provides lower-level PLC/EPICS
signal relationships. These sources are complementary; unresolved semantics
are not invented.

The current User Manual states that the LCS is distributed and that EPICS
services, operator interfaces and PLC/OPC components are separate system
elements. It also documents power-supply setpoints, commands and readbacks and
the existing EPICS/SNL ramp implementation.

The Digital Twin deliberately places the behavioural intelligence in Python
while preserving the observable PV contract.


## Current PPS boundary

The current interlock implementation consumes raw PPS permit/inhibit PVs as
external protection conditions because the authoritative hardware PPS
implementation is outside the Digital Twin. The normalized Python control
signals such as HV:ENABLE and BEAM:ENABLE remain simulation-owned control-plane
results.

A future PPSModel may generate the raw PPS PVs once the authoritative PPS
behaviour required for training has been specified. Until then, the simulator
does not invent a hardware PPS implementation.
