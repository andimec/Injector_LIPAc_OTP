from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .core.control import SimulationControlPlane, SimulationLogic
from .core.engine import SimulationEngine
from .core.state import InjectorState
from .config.loader import load_simulation_config
from .core.pv_registry_loader import load_registry
from .epics.simulation_backend import SimulationPVBackend
from .faults.manager import FaultDefinition, FaultManager
from .models.injector import InjectorModel
from .interlocks.logic import InjectorInterlockLogic


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
    registry_path: str | Path = "config/pv_registry_v1_2.json",
    simulation_config_path: str | Path = "config/simulation/default.yaml",
    logic: list[SimulationLogic] | None = None,
    control_plane: SimulationControlPlane | None = None,
) -> tuple[SimulationEngine, SimulationPVBackend, FaultManager]:
    """Build an offline simulation from the PV registry and startup config.

    The configuration supplies initial external conditions only. Calculated
    interlock outputs remain owned by the interlock logic and simulation engine.
    The default application includes InjectorInterlockLogic. Additional external
    logic objects can be supplied through ``logic``.
    """
    pv = SimulationPVBackend()
    faults = FaultManager()
    simulation_config = load_simulation_config(simulation_config_path)

    payload_registry = load_registry(registry_path)
    payload = json.loads(Path(registry_path).read_text(encoding="utf-8"))
    source_by_name = {
        item["name"]: item.get("source_data", {})
        for item in payload.get("pvs", [])
    }

    for definition in payload_registry.all():
        source_data = source_by_name.get(definition.name, {})
        pv.define(
            definition.name,
            _default_value(source_data),
            writable=bool(source_data.get("write_access", False)),
        )

    pv.define("OTP:STATE", "OFF", writable=False)
    pv.define("OTP:SIM_TIME", 0.0, writable=False)

    # Initial PVs are external conditions, not calculated outputs. Use publish()
    # deliberately so read-only monitor PVs can still be initialized at startup.
    defined_names = set(pv.names())
    for name, value in simulation_config.initial_pvs.items():
        sim_name = f"OTP:{name}" if not name.startswith("OTP:") else name
        if sim_name not in defined_names:
            raise ValueError(f"Initial PV is not present in the PV registry: {name}")
        pv.publish(sim_name, value)

    faults.register(FaultDefinition(
        "VACUUM_LOSS",
        severity="trip",
        description="Synthetic vacuum degradation/loss scenario.",
        state_impact="fault",
    ))
    faults.register(FaultDefinition(
        "RF_FAILURE",
        severity="trip",
        description="Synthetic RF availability failure.",
        state_impact="inhibit",
    ))
    faults.register(FaultDefinition(
        "MAGNET_DRIFT",
        severity="warning",
        description="Synthetic magnet setpoint-to-feedback drift.",
        state_impact="none",
    ))

    model = InjectorModel()
    simulation_control = control_plane or SimulationControlPlane()
    for device, active in simulation_config.device_faults.items():
        simulation_control.set_device_fault(device, active)

    simulation_logic = [InjectorInterlockLogic(), *(logic or [])]
    engine = SimulationEngine(
        models=[model],
        dt=simulation_config.timestep_s,
        pv_backend=pv,
        fault_manager=faults,
        control_plane=simulation_control,
        logic=simulation_logic,
    )
    engine.state_machine.transition(InjectorState(simulation_config.initial_state))
    engine.context.state = engine.state_machine.state
    pv.publish("OTP:STATE", engine.context.state.value)
    return engine, pv, faults


def step_once() -> None:
    engine, _, _ = build_application()
    engine.step()


if __name__ == "__main__":
    step_once()
