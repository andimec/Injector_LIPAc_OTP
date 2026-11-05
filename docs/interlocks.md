# Injector interlock logic

## 1. Purpose

The interlock layer converts the observed Injector equipment state into normalized
authorization signals for the Simulation Engine.

The implementation follows one explicit internal convention:

```
True  = authorization granted / condition allowed
False = authorization blocked
```

Device faults are kept separate from interlocks. A training scenario may therefore
inject a device fault without changing the interlock implementation, and external
logic can also block an authorization while the device itself remains healthy.

## 2. Documentation strategy

The Engine 2.0 model treats the available Injector documentation as complementary.

The current Injector LCS User Manual v4.0 provides the current LCS/OPI
authorization chains. The older PLC maintenance manual provides additional
Boolean relationships and signal relationships that are useful for modelling
MPS/PPS behaviour. The current manual itself notes that PPS/MPS interfaces are
evolving and that detailed protection logic is maintained in the corresponding
PPS/MPS documentation.

Therefore the code distinguishes:

- Current LCS authorization chains: used for the main normalized authorization signals.
- Legacy PLC relationships: retained as complementary diagnostic signals.
- Undocumented or ambiguous logic: deliberately not invented.

## 3. Current authorization chains implemented

### 3.1 HVPS

The current manual describes HVPS authorization as an AND chain containing:

- control-room key;
- HV relay remote status;
- HV relay closed status;
- vacuum safety;
- IE power-supply availability;
- cooling availability;
- Coil 1 fault status;
- Coil 2 fault status;
- RF fault status;
- PPS HV authorization;
- external HV safety.

The normalized result is:

```
HV:ENABLE
```

### 3.2 IEPS

The current manual gives a dedicated IEPS authorization panel. Its chain
shares most HVPS conditions and additionally contains IE-specific safety
conditions. The simulator therefore exposes:

```
IE:ENABLE
```

### 3.3 RF for Plasma

The current manual describes the Plasma authorization path using coil 1,
coil 2, IEPS, Repeller, gas availability, RF health, vacuum and PPS plasma
permit.

For Engine 2.0, gas availability is represented using the currently
configured deuterium path:

```
D2 security valve open
AND gas flow interlock healthy
AND gas-system status healthy
```

This is a modelling interpretation of the documented gas-availability
condition, not a claim that the manual defines this exact Boolean expression.

Normalized result:

```
RF:PLASMA:ENABLE
```

### 3.4 RF for Beam

The current manual lists the required beam-side categories:

- chopper;
- emittance measurement;
- Faraday Cup;
- current transformer;
- solenoid cooling;
- solenoid power supplies;
- RF;
- gate valve;
- chopper position;
- gas;
- HVPS;
- IEPS;
- Repeller;
- PPS beam permission.

The reconciled V2.0 PV registry retains PPS:ACCL:PermStat and PPS:BEAM:InhibitStat,
rather than a PV named PPS:BEAM:PermStat. Engine 2.0 therefore represents
the beam-side PPS condition as:

```
PPS:ACCL:PermStat
AND NOT PPS:BEAM:InhibitStat
```

This mapping is explicitly documented as a complementary mapping and must be
revisited if the authoritative PPS documentation provides a dedicated beam
permit signal.

Normalized result:

```
RF:BEAM:ENABLE
```

The final normalized beam permission is:

```
BEAM:ENABLE =
    RF:BEAM:ENABLE
    AND NOT FBI
```

The CIM/FBI signal is consumed when available as LEBT:CHOP_IM:Fbi. Its
internal trigger equation is intentionally not reproduced yet because the
available LCS manual documents the configurable thresholds and monitored
quantities but does not provide the complete Boolean trigger equation.

## 4. Legacy PLC relationships retained

The older PLC maintenance manual explicitly documents several Boolean
relationships. They are preserved as normalized diagnostic signals rather than
silently replacing the current LCS chains:

```
LEGACY:MPS:FOCALIZATION:OK
LEGACY:MPS:VACUUM:OK
LEGACY:MPS:GV_PROTECTION
LEGACY:MPS:CHOPPER:STATUS
```

The source relationships include:

```
focalization fault =
    Repeller fault OR Solenoid 1 fault OR Solenoid 2 fault

vacuum fault =
    GP1 vacuum fault OR GP2 vacuum fault [where those source signals exist]

GV protection =
    Faraday Cup inserted AND gate/VI valve closed

chopper status =
    Chopper inserted AND Chopper power supply ON
```

The source PLC document states that its PPS/MPS chapter described acceptance-test
logic from CEA/Saclay in 2012 and that the logic could evolve at Rokkasho.
For that reason these signals are traceability aids, not assumptions that the
2012 equations are the current hardware protection implementation.

## 5. Fault injection interaction

Interlocks and faults remain independent:

```
device_faults["chopper"] = True
```

does not directly modify a physical model or a source PV. The interlock layer
can use the normalized fault state when calculating derived authorization.

This separation permits scenarios such as:

```
device healthy + authorization blocked
device faulty  + authorization externally granted
```

which is useful for operator-training scenarios and for testing the protection
logic independently of the physical model.

## 6. Missing information policy

When a source does not define a complete Boolean equation, the simulator does
not manufacture one.

Examples currently left deliberately open:

- the complete CIM/FBI trigger equation;
- detailed modern PPS/MPS hardware equations;
- any exact beam-permit signal that supersedes the current registry mapping;
- detailed timing/debounce/latching/recovery behaviour.

Those items should be added after the corresponding authoritative signal or
protection documentation is available.


### 6.1 Legacy signal qualification (legacy equation context)

The legacy PLC equation refers to a dedicated Repeller fault condition. The
current V2.0 registry exposes the Repeller power-supply ON status but does not
provide a dedicated Repeller FSDefStat signal in the same naming family.

For that reason the implementation uses Repeller availability as a readiness
proxy in LEGACY:MPS:FOCALIZATION:OK. This signal must not be interpreted as a
literal reconstruction of the historical MPS fault bit. It can be replaced by
the exact Repeller fault PV when the authoritative current signal definition
is available.


## 7. Current scope and PV naming

The Python interlock layer uses native PV names from the active V2.0 registry. External PPS permits/inhibits are scenario conditions, **not operator-write PVs**. The normalized `LEGACY:MPS:*` signals are internal diagnostic logic, not a mandate to publish corresponding EPICS records. The real PPS/MPS hardware and PLC timing/latching behavior remain outside the currently validated simulator. Running Phoebus and the Soft IOC on a VM isolated from LIPAc is still pending. Consult [architecture](architecture.md), [PV ownership](pv_runtime_contract.md) and [source logic](original_lcs_model_logic.md).
