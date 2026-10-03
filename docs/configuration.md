# Simulation configuration

The simulation uses four separate concepts.

## 1. PV registry

config/pv_registry_v1_2.json answers:

Which EPICS PVs exist in the source Injector snapshot?

It is the machine-readable interface inventory.

The source read_access / write_access flags describe the source EPICS
transport interface. They do not uniquely determine Digital Twin ownership.

## 2. Runtime ownership overrides

config/pv_runtime_overrides.yaml answers:

Which PVs have a verified semantic role in the Python runtime?

Only verified pilot inputs are made operator-writable here.

Unlisted read/write PVs remain unresolved rather than being silently treated as
commands.

## 3. Operating parameters

config/injector_operating_parameters.yaml answers:

Which physical/operating values are useful as modelling references?

It is not a startup-state database and does not define EPICS ownership.

## 4. Simulation configuration

config/simulation/default.yaml answers:

In which initial external condition should this simulation instance start?

It contains initial conditions required by the simulation but not yet generated
by a physical model.

Calculated values do not belong here.

The Python runtime generates dynamic state and calculated outputs.

## Separation of sources of truth

    PV registry
        -> interface inventory

    Runtime overrides
        -> verified ownership semantics

    Operating parameters
        -> modelling reference

    Simulation config
        -> initial conditions

    Python runtime
        -> dynamic state and calculated outputs

## Configuration safety

Configuration must never contain a production IOC address or production PV
endpoint.

The network-facing simulation namespace is always OTP:.
