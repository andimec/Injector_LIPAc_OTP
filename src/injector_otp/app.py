from __future__ import annotations

from pathlib import Path
from typing import Any

from .core.engine import SimulationEngine
from .core.pv_registry_loader import load_registry
from .epics.simulation_backend import SimulationPVBackend
from .faults.manager import FaultDefinition, FaultManager
from .models.injector import InjectorModel


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
) -> tuple[SimulationEngine, SimulationPVBackend, FaultManager]:
    """Build a fully populated offline simulation from the V1.2 PV contract."""
    pv = SimulationPVBackend()
    faults = FaultManager()

    payload_registry = load_registry(registry_path)

    import json
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
    engine = SimulationEngine(models=[model], dt=0.1, pv_backend=pv)
    return engine, pv, faults


def step_once() -> None:
    engine, _, _ = build_application()
    engine.step()


if __name__ == "__main__":
    step_once()
