# Injector_LIPAc_OTP

LIPAc Injector Operator Training Platform (OTP) and Digital Twin.

## Purpose

This repository provides a software architecture for an offline, non-invasive digital twin of the LIPAc Injector. The platform is intended for operator training, procedure validation, fault injection, logging/replay, and Phoebus/EPICS integration without commanding the real machine.

## Architecture

```text
                 +----------------------+
                 |   Phoebus / OPI      |
                 +----------+-----------+
                            |
                         EPICS PVs
                            |
                 +----------v-----------+
                 |   EPICS Adapter      |
                 |  read/write boundary |
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

The physical models, simulation engine, EPICS interface and OPI layer are kept separate so that a real and a simulation IOC can expose the same PV contract in a later phase.

## Initial package layout

- `src/injector_otp/core`: simulation clock, state machine and common types.
- `src/injector_otp/models`: subsystem models. Initial models are intentionally simple placeholders with explicit interfaces.
- `src/injector_otp/epics`: EPICS boundary. The initial implementation is a backend-agnostic in-memory PV store so model development does not depend on EPICS availability.
- `src/injector_otp/faults`: deterministic fault injection interface.
- `src/injector_otp/app.py`: application composition and simulation loop.
- `config/`: configuration and PV/PBS mapping baseline.
- `tests/`: architecture-level tests.
- `docs/architecture.md`: detailed design decisions and next steps.

## Safety boundary

This repository is a training/simulation platform. The simulator must never write to production LIPAc control PVs. A future EPICS backend must require an explicit simulation IOC namespace and configuration guard before it can publish PVs.

## Current baseline

The PV architecture is based on the September 2026 active-PV snapshot and the V1.1 cross-check. The repository does not yet claim that the full PV list is authoritative. The controlled EPICS database, OPI configuration and PBS should be used for later verification.
