# Simulation Engine modelling baseline

## Source integration

The Engine 2.0 treats the available Injector documentation as complementary
sources of evidence rather than imposing a strict "newer document replaces
older document" hierarchy.

The current Injector LCS User Manual v4.0 provides the current LCS/OPI
authorization paths and operating references. The older Injector LCS/PLC
maintenance manuals provide additional architecture, signal relationships and
Boolean PPS/MPS relationships. The PV registry and operating-parameter
configuration provide machine-readable representations used by the simulator.

When two sources describe the same condition differently, the simulator does
not silently choose one. The relationship is documented, the source context
is preserved, and unresolved differences remain explicit until the relevant
authoritative information is available.

Numerical operating values and protection limits are kept distinct: a typical
operating value is not automatically promoted to a protection threshold.

## Subsystem boundaries

The first simulation-engine model decomposition follows the actual Injector control structure:

- Source and gas injection
- Vacuum
- High-voltage power supplies
- RF and automatic tuning
- Coils and LEBT solenoids
- Water cooling
- Diagnostics
- Chopper / Fast Beam Inhibit
- PPS / MPS / interlocks

The current user manual describes the Main Injector OPI as the operator entry point for vacuum, power supplies, gas injection, RF, coils/solenoids, Faraday Cup, Chopper and valves. The startup sequence is explicitly ordered around gas preparation, HV/IE/Repeller activation, magnets, vacuum/interlocks and RF readiness.

## Control dependencies recovered from the documentation

The documentation establishes several dependencies that should become model interfaces rather than isolated PV calculations:

1. **Vacuum gates HV operation.** IV602 is identified as a reference gauge during operation and conditioning. Vacuum status is therefore an input to HV authorization.
2. **Cooling gates critical equipment.** Older PLC maintenance logic shows cooling flow, conductivity and temperature-related signals contributing to injector protection. The current manual gives representative skid temperature and pressure values.
3. **RF authorization is conditional.** The current manual describes separate RF-for-Plasma and RF-for-Beam authorization paths. They depend on equipment status, vacuum, cooling, gas configuration, diagnostics, machine protection and PPS permits.
4. **PPS/MPS are authorization boundaries.** The current manual states that the OPI visualizes these conditions while the actual protection functions remain in the hardware protection systems. The simulator therefore models their effects and observable status, not a replacement for real protection hardware.
5. **Chopper/FBI is a dynamic protection subsystem.** The current manual defines configurable thresholds for chopper HV and ACCT current and records a snapshot when FBI is triggered.
6. **Gas injection is safety-controlled.** The older maintenance documentation shows PPS authorization associated with the hydrogen/deuterium security valves. Gas flow setpoints therefore cannot be treated as independent of protection state.

## Engine consequences

The SimulationEngine should evolve from a list of independent update(dt) calls into an ordered deterministic cycle:

The **implemented** cycle in `SimulationEngine.step()` is:

1. Refresh context from operator commands/setpoints and scenario PVs using **native PV names**.
2. Synchronize synthetic faults.
3. Evaluate pre-model interlocks and the control plane.
4. Advance physical/reduced-order Python models.
5. Re-evaluate authorization after model changes.
6. Synchronize the Python state machine and increment simulation time.
7. Apply internal sequencer commands through the input allowlist.
8. Publish simulation-generated readbacks and runtime indicators (`SIM:STATE`, `SIM:TIME`).
9. Refresh the context PV snapshot.

A networked Soft IOC and deterministic log/replay integration are separate pending steps.

The order is intentional. In particular, authorization is derived from subsystem conditions and must not be represented as an arbitrary operator-controlled status PV.

## Current numerical baseline

The numerical references extracted from the current user manual are stored in config/injector_operating_parameters.yaml.

Examples include:

- Main HV: 100 kV
- Intermediate electrode: 25 kV
- Repeller: 4.5 kV
- SOL1: 280 A
- SOL2: 0 A
- RF CW forward power: 800-900 W
- Extracted beam current: 145-152 mA
- IV602 operating vacuum reference: 1e-6 to 1e-5 mbar
- Cooling skid: approximately 20 °C and 9.6 bar
- Chopper HV OFF/ON thresholds: 1 kV / 6 kV
- ACCT threshold: 5 mA

These are modelling references. They are not automatically interpreted as hard protection thresholds unless the source explicitly identifies them as such.

## Deferred physics

The engine **currently uses** reduced-order deterministic models. Detailed plasma physics, beam transport, RF electromagnetic simulation, thermal-fluid CFD and detailed vacuum conductance networks remain separate model implementations and can later be coupled through the same interfaces.

This keeps the OTP useful for operator training and control integration without inventing undocumented physical behaviour.

## EMU reconstruction baseline

The EMU is now executable as separate Python models for MAXv motor and servo
coordination, ICV plate supplies, FACQ scalar event and the original
measurement state machine. Exact geometry and SNL voltage-grid calculations
are kept separate from explicitly uncalibrated movement/response parameters.
See [EMU reconstruction](emu_reconstruction.md) and [readback traceability](pv_readback_traceability.md). The in-memory simulator must
not be interpreted as a deployed interlock, real FACQ waveform acquisition or
calibrated transverse emittance measurement.
