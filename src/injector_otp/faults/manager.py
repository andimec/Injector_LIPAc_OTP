from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FaultDefinition:
    """Static metadata for a training fault scenario."""

    fault_id: str
    severity: str = "warning"
    description: str = ""
    affected_pvs: tuple[str, ...] = ()
    state_impact: str = "none"


@dataclass
class FaultManager:
    """Explicit fault registry for deterministic training scenarios."""

    definitions: dict[str, FaultDefinition] = field(default_factory=dict)
    active: set[str] = field(default_factory=set)

    def register(self, definition: FaultDefinition) -> None:
        if definition.fault_id in self.definitions:
            raise ValueError(f"Fault already registered: {definition.fault_id}")
        self.definitions[definition.fault_id] = definition

    def inject(self, fault_id: str) -> None:
        if self.definitions and fault_id not in self.definitions:
            raise KeyError(f"Unknown fault: {fault_id}")
        self.active.add(fault_id)

    def clear(self, fault_id: str) -> None:
        self.active.discard(fault_id)

    def clear_all(self) -> None:
        self.active.clear()

    def is_active(self, fault_id: str) -> bool:
        return fault_id in self.active

    def active_definitions(self) -> list[FaultDefinition]:
        return [self.definitions[f] for f in sorted(self.active) if f in self.definitions]
