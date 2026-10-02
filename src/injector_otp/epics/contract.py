from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SIM_NAMESPACE = "OTP:"
SIMULATION_IOC_MARKER = "SIMULATION"

# Production namespaces are deliberately not accepted by the simulation backend.
FORBIDDEN_PRODUCTION_PREFIXES = (
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
    """Safety and naming contract for the Digital Twin IOC boundary."""

    @staticmethod
    def validate_name(name: str) -> None:
        if not name or not isinstance(name, str):
            raise ValueError("PV name must be a non-empty string")
        if name.startswith(FORBIDDEN_PRODUCTION_PREFIXES):
            raise PermissionError(
                f"Production PV namespace is forbidden in simulation: {name}"
            )

    @staticmethod
    def simulation_name(name: str) -> str:
        """Return an explicit simulation namespace for an Injector PV."""
        SimulationIOCContract.validate_name(name)
        if name.startswith(SIM_NAMESPACE):
            return name
        return f"{SIM_NAMESPACE}{name}"

    @staticmethod
    def is_simulation_name(name: str) -> bool:
        return isinstance(name, str) and name.startswith(SIM_NAMESPACE)

    @staticmethod
    def require_simulation_namespace(name: str) -> None:
        if not SimulationIOCContract.is_simulation_name(name):
            raise PermissionError(
                f"Only the OTP simulation namespace is writable: {name}"
            )
