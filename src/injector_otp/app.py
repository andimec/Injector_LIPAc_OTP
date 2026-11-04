from __future__ import annotations

import json

import yaml
from pathlib import Path
from typing import Any

from .config.loader import (
    load_pv_runtime_overrides,
    load_simulation_config,
)
from .core.control import SimulationControlPlane, SimulationLogic
from .core.engine import SimulationEngine
from .core.pv_registry_loader import load_registry
from .core.state import InjectorState
from .epics.simulation_backend import SimulationPVBackend
from .faults.manager import FaultDefinition, FaultManager
from .interlocks.logic import InjectorInterlockLogic
from .models.injector import InjectorModel
from .models.catalog import DeviceCatalog
from .pv.state import SimulationPVState


def _default_value(source_data: dict[str, Any]) -> Any:
    if source_data.get("is_array"):
        return []
    epics_type = str(source_data.get("epics_type", "")).lower()
    if "enum" in epics_type:
        return 0
    if "double" in epics_type or "float" in epics_type:
        return 0.0
    if "int" in epics_type:
        return 0
    if "string" in epics_type:
        return ""
    return 0


def build_application(
    registry_path: str | Path = "config/pv_registry_v2_0.json",
    model_parameters_path: str | Path = "config/model_parameters.yaml",
    simulation_config_path: str | Path = "config/simulation/default.yaml",
    runtime_overrides_path: str | Path = "config/pv_runtime_overrides.yaml",
    logic: list[SimulationLogic] | None = None,
    control_plane: SimulationControlPlane | None = None,
) -> tuple[SimulationEngine, SimulationPVBackend, FaultManager]:
    """Build the Python Digital Twin and its local EPICS-facing adapter.

    The simulation engine owns all behaviour. The returned SimulationPVBackend
    is only a transport adapter used by tests and by the pre-Soft-IOC phase.
    """

    faults = FaultManager()
    simulation_config = load_simulation_config(simulation_config_path)
    runtime_overrides = load_pv_runtime_overrides(runtime_overrides_path)

    registry = load_registry(registry_path)
    payload = json.loads(Path(registry_path).read_text(encoding="utf-8"))
    source_by_name = {
        item["name"]: item.get("source_data") or (
            item.get("snapshot_v1_2") or {}
        ).get("source_data", {})
        for item in payload.get("pvs", [])
    }

    registry_names = set(registry.names())
    override_names = (
        set(runtime_overrides.inputs)
        | set(runtime_overrides.outputs)
        | set(runtime_overrides.external_conditions)
    )
    missing_overrides = sorted(override_names - registry_names)
    if missing_overrides:
        raise ValueError(
            "Runtime ownership override is not present in the PV registry: "
            + ", ".join(missing_overrides)
        )

    pv_state = SimulationPVState(
        registry,
        writable_names=runtime_overrides.inputs,
    )

    for definition in registry.all():
        source_data = source_by_name.get(definition.name, {})
        pv_state.define(
            definition.name,
            _default_value(source_data),
            source="registry-default",
        )

    # Runtime status PVs belong to the simulation and are not part of the
    # machine snapshot registry.
    pv_state.define("OTP:STATE", "OFF", source="engine")
    pv_state.define("OTP:SIM_TIME", 0.0, source="engine")

    # Initial PVs represent external/startup conditions. They are applied by
    # the application layer and never become calculated outputs.
    for name, value in simulation_config.initial_pvs.items():
        if name not in registry_names:
            raise ValueError(f"Initial PV is not present in the PV registry: {name}")
        pv_state.publish(name, value, source="startup-config")

    faults.register(
        FaultDefinition(
            "VACUUM_LOSS",
            severity="trip",
            description="Synthetic vacuum degradation/loss scenario.",
            state_impact="fault",
        )
    )
    faults.register(
        FaultDefinition(
            "RF_FAILURE",
            severity="trip",
            description="Synthetic RF availability failure.",
            state_impact="inhibit",
        )
    )
    faults.register(
        FaultDefinition(
            "MAGNET_DRIFT",
            severity="warning",
            description="Synthetic magnet setpoint-to-feedback drift.",
            state_impact="none",
        )
    )

    catalog = DeviceCatalog.from_registry(registry_path)
    model_parameters = yaml.safe_load(
        Path(model_parameters_path).read_text(encoding="utf-8")
    ) or {}
    for name, description in (
        ("COOLING_FAILURE", "Synthetic cooling/skid failure"),
        ("FBI_TRIGGER", "Synthetic chopper Fast Beam Inhibit trigger"),
    ):
        faults.register(
            FaultDefinition(name, severity="trip", description=description,
                            state_impact="inhibit")
        )

    model = InjectorModel(catalog, model_parameters)
    simulation_control = control_plane or SimulationControlPlane()
    for device, active in simulation_config.device_faults.items():
        simulation_control.set_device_fault(device, active)

    simulation_logic = [InjectorInterlockLogic(), *(logic or [])]
    engine = SimulationEngine(
        models=[model],
        dt=simulation_config.timestep_s,
        pv_state=pv_state,
        fault_manager=faults,
        control_plane=simulation_control,
        logic=simulation_logic,
    )

    engine.state_machine.transition(InjectorState(simulation_config.initial_state))
    engine.context.state = engine.state_machine.state
    pv_state.publish("OTP:STATE", engine.context.state.value, source="engine")

    # The adapter is deliberately constructed after the engine-owned state.
    backend = SimulationPVBackend(pv_state)
    return engine, backend, faults


def step_once() -> None:
    engine, _, _ = build_application()
    engine.step()


if __name__ == "__main__":
    step_once()
