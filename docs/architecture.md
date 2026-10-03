# Injector OTP architecture

## 1. Design principles

1. **Simulation first.** Physical models do not depend on EPICS or Phoebus.
2. **PV contract first.** EPICS names and semantics form the interface between the model and operator layer.
3. **No production writes.** The simulator is isolated from the real Injector control system.
4. **Deterministic time.** A simulation step receives an explicit `dt`, enabling accelerated, real-time and replay modes.
5. **Faults are first-class objects.** Fault injection modifies model state through an explicit interface rather than hidden test code.
6. **PBS traceability.** PVs, models and training scenarios should carry the four-level PBS path.

## 2. Runtime layers

### Model layer

Owns physical behavior and subsystem state. Candidate model domains are:

- ion source and gas injection
- source coils
- LEBT magnets
- vacuum
- high voltage
- RF
- chopper/timing
- diagnostics and Faraday cup
- water cooling
- MPS/PPS/interlocks

The first code only provides interfaces and a top-level placeholder. Physics is intentionally not embedded in the architecture skeleton.

### Simulation engine

Coordinates the models, simulation clock, state machine, faults and PV publication. The target update period is configurable. The initial default is 100 ms.

### EPICS adapter

The adapter translates model state into the EPICS PV contract and translates operator commands into model inputs. The current `PVStore` is an in-memory backend. A real EPICS backend should be added behind the same interface.

Recommended future backends:

```text
PVStore (test)
    |
    +-- EPICS CA/PVA backend
    |
    +-- Replay backend
```

### Phoebus / OPI

Phoebus is an external operator interface. It should communicate only through the simulation EPICS IOC in training mode. OPI files are not part of the first architecture commit.

## 3. State machine

Initial states:

`OFF -> GAS_READY -> VACUUM_READY -> HV_READY -> RF_READY -> BEAM_READY -> BEAM_ON`

Fault paths:

`any operational state -> FAULT`

Protection paths:

`any operational state -> INHIBITED`

Shutdown is represented separately so procedures can later trace each transition to training steps.

The transition rules are intentionally permissive in v0.1. Procedure-specific guards will be implemented after the PV and interlock contracts are validated.

## 4. PV ownership

A PV should eventually have a unique owner model. Example:

```text
SRC:COIL01_PS:ISet
  -> PBS 04.04.01.02
  -> coils model
  -> operator command
```

and:

```text
PPS:BEAM:InhibitStat
  -> PBS 04.04.05.01 (provisional)
  -> PPS/MPS logic
  -> protection status
```

The same PV contract should be usable by a simulation IOC and, where appropriate, by an adapter to recorded real-machine data. This does not imply that the simulator is allowed to command the real IOC.

## 5. Fault injection

Fault IDs should be stable and scenario-oriented. Initial categories:

- vacuum loss
- RF failure
- HV trip
- magnet/current drift
- cooling fault
- diagnostic/sensor fault
- communication/PV fault
- MPS/PPS trip

Each fault should define trigger conditions, affected PVs, model effect, recovery behavior and expected operator response.

## 6. Data and traceability

The future authoritative registry should connect:

```text
PV <-> PBS <-> model variable <-> procedure step <-> fault scenario <-> OPI widget
```

The V1.1 Excel matrix is the working source for the current PV/PBS cross-check. It should later be converted into machine-readable CSV/YAML generated from a controlled source, rather than manually maintaining two independent lists.

## 7. Proposed repository evolution

```text
Phase 1  Architecture skeleton                 [current]
Phase 2  Complete PV registry + PBS mapping
Phase 3  EPICS simulation IOC
Phase 4  Subsystem behavioral models
Phase 5  Injector startup/CW procedure engine
Phase 6  MPS/PPS and fault injection
Phase 7  Phoebus OPIs
Phase 8  Logging, replay and scenario validation
Phase 9  Real/virtual IOC interchangeability
```


## 8. Interlock architecture

The interlock layer is an external simulation-logic component. Physical
subsystem models do not contain the Injector authorization equations.

The SimulationEngine evaluates external logic before the physical-model update:

```
PV state
   |
   v
InjectorInterlockLogic
   |
   +--> normalized authorization signals
   |
   +--> SimulationControlPlane
             |
             +--> physical models
             +--> state/protection observers
```

The internal authorization convention is:

- True: authorized / allowed.
- False: blocked.

The logic integrates the available documentation as complementary evidence.
The current LCS User Manual v4.0 supplies the main authorization chains, while
the PLC maintenance documentation contributes legacy signal relationships and
Boolean equations. A legacy relationship is never silently substituted for a
current authorization chain.

The implemented authorization groups are:

1. HVPS authorization.
2. IEPS authorization.
3. RF-for-Plasma authorization.
4. RF-for-Beam authorization.
5. normalized beam authorization including the available FBI status.

The legacy relationships are exposed separately under the normalized
LEGACY:MPS namespace.

### 8.1 Source-to-model traceability

Each implemented condition should be traceable to:

```
source document
    -> documented condition / signal
    -> PV registry entry
    -> interlock expression
    -> normalized control-plane signal
    -> test case
```

If the documentation does not define a complete Boolean equation, the
implementation records the missing information rather than inventing a rule.

### 8.2 Fault separation

Device faults are independent from authorization signals. The external
control plane may contain, for example:

```
device_faults["hv"] = True
interlocks["HV:ENABLE"] = False
```

This separation is required so that training scenarios can exercise fault
injection, interlock response and recovery independently.

### 8.3 Protection boundary

The OTP reproduces observable protection and authorization behaviour for
training and simulation. It does not replace the real Injector PPS/MPS
hardware. Detailed latching, timing, reset and recovery behaviour should only
be implemented when supported by the corresponding authoritative
documentation.
