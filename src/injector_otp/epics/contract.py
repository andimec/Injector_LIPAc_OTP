from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PVRecord:
    name: str
    value: Any
    timestamp: float
    source: str = "simulation"


class SimulationIOCContract:
    """Preserve original LIPAc PV names inside the isolated simulator.

    Network isolation is a deployment property, not a name prefix.
    Authorization to write remains the responsibility of SimulationPVState.
    """

    @staticmethod
    def simulation_name(name: str) -> str:
        if not isinstance(name, str) or not name:
            raise ValueError("PV name must be a non-empty string")
        return name

    @staticmethod
    def is_simulation_name(name: str) -> bool:
        return isinstance(name, str) and bool(name)

    @staticmethod
    def require_simulation_namespace(name: str) -> None:
        # Backward-compatible method name. No namespace transformation occurs.
        SimulationIOCContract.simulation_name(name)
