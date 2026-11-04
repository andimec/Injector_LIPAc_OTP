from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PVDirection(str, Enum):
    MONITOR = "monitor"
    COMMAND = "command"
    SETPOINT = "setpoint"
    CALCULATED = "calculated"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class PVDefinition:
    name: str
    direction: PVDirection
    type: str
    pbs: str | None = None
    model: str | None = None
    units: str | None = None
    description: str | None = None


class PVRegistry:
    """In-memory registry of the PV inventory and semantic contract."""

    def __init__(self, definitions: list[PVDefinition] | None = None) -> None:
        self._definitions = {item.name: item for item in definitions or []}

    def register(self, definition: PVDefinition) -> None:
        if definition.name in self._definitions:
            raise ValueError(f"PV already registered: {definition.name}")
        self._definitions[definition.name] = definition

    def get(self, name: str) -> PVDefinition:
        return self._definitions[name]

    def all(self) -> list[PVDefinition]:
        return list(self._definitions.values())

    def names(self) -> list[str]:
        return list(self._definitions)

    def __len__(self) -> int:
        return len(self._definitions)


def load_seed_registry() -> PVRegistry:
    """Load the small architecture seed used by the first simulator tests."""
    return PVRegistry([
        PVDefinition("SRC:COIL01_PS:ISet", PVDirection.SETPOINT, "number", "04.04.01.02", "coils"),
        PVDefinition("SRC:COIL01_PS:IRdbk", PVDirection.MONITOR, "number", "04.04.01.02", "coils"),
        PVDefinition("LEBT:SOL01_PS:OnStat", PVDirection.MONITOR, "boolean", "04.04.02.03", "magnets"),
        PVDefinition("LEBT:FC:InStat", PVDirection.MONITOR, "boolean", "04.04.03.04", "diagnostics"),
        PVDefinition("LEBT:Chop:InStat", PVDirection.MONITOR, "boolean", "04.04.03.11", "chopper"),
        PVDefinition("PPS:BEAM:InhibitStat", PVDirection.MONITOR, "boolean", "04.04.05.01", "pps"),
        PVDefinition("MPS:INJ:DefStat", PVDirection.MONITOR, "boolean", "04.04.05.01", "mps"),
    ])
