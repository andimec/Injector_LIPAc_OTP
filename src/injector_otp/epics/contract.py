from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SIM_NAMESPACE = "OTP:"

# These prefixes identify the real Injector control namespace. They are never
# accepted as writable names by a future external IOC adapter.
PRODUCTION_PREFIXES = (
    "SRC:",
    "LEBT:",
    "MEBT:",
    "RFQ:",
    "INJ:",
    "PPS:",
    "MPS:",
    "VAC:",
)


@dataclass(frozen=True)
class PVRecord:
    name: str
    value: Any
    timestamp: float
    source: str = "simulation"


class SimulationIOCContract:
    """Naming and safety contract for the Digital Twin IOC boundary."""

    @staticmethod
    def simulation_name(name: str) -> str:
        if not isinstance(name, str) or not name:
            raise ValueError("PV name must be a non-empty string")
        if name.startswith(SIM_NAMESPACE):
            return name
        return f"{SIM_NAMESPACE}{name}"

    @staticmethod
    def is_simulation_name(name: str) -> bool:
        return isinstance(name, str) and name.startswith(SIM_NAMESPACE)

    @staticmethod
    def is_production_name(name: str) -> bool:
        return isinstance(name, str) and name.startswith(PRODUCTION_PREFIXES)

    @staticmethod
    def require_simulation_namespace(name: str) -> None:
        if not SimulationIOCContract.is_simulation_name(name):
            raise PermissionError(
                f"Only the OTP simulation namespace is writable: {name}"
            )
