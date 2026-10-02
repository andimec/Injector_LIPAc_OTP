# Simulation IOC contract

## Purpose

The Digital Twin exposes an EPICS-like PV interface without connecting to the real LIPAc Injector control system.

The contract has three rules:
1. Injector PV names are treated as the source contract.
2. The simulation backend exposes them under the explicit OTP: namespace.
3. Only the OTP: namespace can be written through the simulation interface.

Example: LEBT:SOL01_PS:ISet becomes OTP:LEBT:SOL01_PS:ISet.

## PV operations

The backend provides get(name), put(name, value), publish(name, value), and names().
The V1.2 registry remains the source of EPICS type and access metadata.

## Namespace boundary

Source PVs are transformed as: source PV -> OTP:<source PV>.
Simulator-owned status PVs beginning with OTP: are not prefixed again.

A future EPICS soft IOC adapter must preserve this rule and reject configurations that map the simulator directly onto production PV names.

## Access semantics

write_access=true makes a simulated PV operator-writable. write_access=false makes it read-only to the operator. Model publication is a separate path.

## Timestamps

The in-memory backend records a timestamp whenever a value is written or published. A future soft IOC adapter should expose timestamps derived from simulation time where deterministic replay is required.

## Safety boundary

The initial implementation is local and in-memory. It has no EPICS Channel Access or PVAccess client and therefore has no production network path.

A future soft IOC implementation should require mode=simulation, namespace=OTP:, and production_write_enabled=false.

## Future soft IOC adapter

PV Registry -> SimulationPVBackend -> In-memory backend or Soft IOC adapter -> EPICS -> Phoebus.

Physical models must depend only on the backend-neutral interface. EPICS-specific libraries belong exclusively in the adapter layer.

## Out of scope for V1.4

- connection to a real Injector IOC
- writes to production PVs
- Channel Access/PVA networking
- Phoebus OPI files
- alarm server integration
- real-time scheduling guarantees
- replacement of the controlled LIPAc EPICS database