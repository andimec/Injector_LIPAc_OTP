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
- `src/injector_otp/app.py`: application composition and simulation bootstrap.
- `config/pv_registry_v1_2.json`: machine-readable September 2026 Injector PV snapshot.
- `tests/`: architecture and registry tests.
- `docs/`: architecture and registry design documentation.

## V1.2 PV registry

The simulator now bootstraps its PV namespace from `config/pv_registry_v1_2.json` rather than a hard-coded list. The registry preserves the source EPICS metadata and does not invent engineering attributes that are not supported by the source workbook.

The current JSON snapshot contains 891 unique PV entries. The earlier engineering target of 870 active PVs remains a validation item because the source workbook does not expose an unambiguous inactive flag for those 21 entries. They are therefore retained rather than silently discarded.

## Safety boundary

This repository is a training/simulation platform. It must never write to production LIPAc control PVs. The current backend is in-memory only. Any future EPICS implementation must target an explicitly configured simulation IOC namespace and must fail closed if production endpoints are configured.
