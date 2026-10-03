from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

@dataclass(frozen=True)
class SimulationConfig:
    """Initial conditions for one Injector simulation instance."""
    initial_state: str = "OFF"
    timestep_s: float = 0.1
    external_conditions: dict[str, Any] = field(default_factory=dict)
    initial_pvs: dict[str, Any] = field(default_factory=dict)
    device_faults: dict[str, bool] = field(default_factory=dict)

def load_simulation_config(path: str | Path = "config/simulation/default.yaml") -> SimulationConfig:
    """Load and validate simulation startup configuration from YAML."""
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    simulation = dict(payload.get("simulation", {}))
    timestep = float(simulation.get("timestep_s", 0.1))
    if timestep <= 0:
        raise ValueError("simulation.timestep_s must be positive")
    return SimulationConfig(
        initial_state=str(simulation.get("initial_state", "OFF")),
        timestep_s=timestep,
        external_conditions=dict(payload.get("external_conditions", {})),
        initial_pvs=dict(payload.get("initial_pvs", {})),
        device_faults={str(k): bool(v) for k, v in dict(payload.get("device_faults", {})).items()},
    )
