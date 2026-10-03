# Injector_LIPAc_OTP

LIPAc Injector Operator Training Platform (OTP) and Digital Twin.

## Purpose

This repository provides an offline, non-invasive digital twin of the LIPAc Injector for operator training, procedure validation, fault injection, logging/replay, and Phoebus/EPICS integration without commanding the real machine.

## Architecture

```text
                 +----------------------+
                 |   Phoebus / OPI      |
                 +----------+-----------+
                            |
                         EPICS PVs
                            |
                 +----------v-----------+
                 |   Simulation IOC      |
                 |  backend boundary     |
                 +----------+-----------+
                            |
                 +----------v-----------+
                 |   Simulation Engine   |
                 |  deterministic loop   |
                 +----+-----+-----+-----+
                      |     |     |
                 +----v+ +--v--+ +-v-----+
                 |Gas  | |Vac. | |HV/RF  |
                 |Flow | |uum   | |Models |
                 +-----+ +------+ +-------+
                      |
                 +----v------------------+
                 | State / Interlocks /  |
                 | Fault Injection       |
                 +-----------------------+
```

The physical models, simulation engine, PV registry, EPICS boundary and OPI layer are kept separate. This allows the simulator to expose the same PV contract through a future simulation IOC while remaining isolated from the production Injector IOC.

## Package layout

- `src/injector_otp/core`: simulation clock, state machine, PV contract and registry loader.
- `src/injector_otp/models`: subsystem model interfaces and composition point.
- `src/injector_otp/epics`: backend-neutral PV boundary and in-memory simulation store.
- `src/injector_otp/faults`: deterministic fault definitions and injection manager.
- `src/injector_otp/interlocks`: documented Injector authorization chains and complementary legacy PPS/MPS relationships.
- `src/injector_otp/app.py`: application composition and simulation bootstrap.
- `config/pv_registry_v1_2.json`: machine-readable September 2026 Injector PV snapshot.
- `tests/`: architecture and registry tests.
- `docs/`: architecture and registry design documentation.

## V1.2 PV registry

The simulator now bootstraps its PV namespace from `config/pv_registry_v1_2.json` rather than a hard-coded list. The registry preserves the source EPICS metadata and does not invent engineering attributes that are not supported by the source workbook.

The current JSON snapshot contains 891 unique PV entries. The earlier engineering target of 870 active PVs remains a validation item because the source workbook does not expose an unambiguous inactive flag for those 21 entries. They are therefore retained rather than silently discarded.

## Safety boundary

This repository is a training/simulation platform. It must never write to production LIPAc control PVs. The current backend is in-memory only. Any future EPICS implementation must target an explicitly configured simulation IOC namespace and must fail closed if production endpoints are configured.


## Interlock logic

The Simulation Engine now includes the documented Injector interlock layer by
default through InjectorInterlockLogic.

The interlock layer is intentionally external to the physical subsystem
models. It reads observed PV states and writes normalized authorization
signals into the SimulationControlPlane using:

```
True  = authorized / allowed
False = blocked
```

The implementation integrates the available documentation rather than
classifying one source as valid and another as invalid:

- the current Injector LCS User Manual v4.0 supplies the current HVPS, IEPS,
  RF-for-Plasma and RF-for-Beam authorization paths;
- the PLC maintenance documentation supplies complementary historical Boolean
  relationships for PPS/MPS behaviour;
- the V1.2 PV registry supplies the concrete PV names available to the
  simulation;
- ambiguous protection equations are explicitly left open instead of being
  invented.

Implemented normalized signals include:

```
VACUUM:READY
COOLING:READY
COILS:READY
GAS:READY
MAGNETS:READY
CHOPPER:READY
HV:ENABLE
IE:ENABLE
RF:PLASMA:ENABLE
RF:BEAM:ENABLE
BEAM:ENABLE
```

Legacy relationships are exposed separately under the LEGACY:MPS namespace
inside the control plane. They do not silently replace the current LCS
authorization chains.

Detailed design decisions and source traceability are documented in
docs/interlocks.md.

### Important boundary

The LCS manual states that PPS/MPS OPI information is for monitoring and
diagnostic purposes and that the actual protection functions are implemented
by the hardware protection systems. The OTP therefore models the observable
authorization/protection behaviour for training; it is not a replacement for
the real PPS/MPS hardware.

The CIM/FBI trigger equation is not invented at this stage. The simulator
consumes the available FBI status PV and will add the trigger/latching logic
when the authoritative equation is available.
