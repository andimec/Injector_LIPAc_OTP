from dataclasses import dataclass, field


@dataclass
class FaultManager:
    """Explicit fault registry for training scenarios."""

    active: set[str] = field(default_factory=set)

    def inject(self, fault_id: str) -> None:
        self.active.add(fault_id)

    def clear(self, fault_id: str) -> None:
        self.active.discard(fault_id)

    def clear_all(self) -> None:
        self.active.clear()

    def is_active(self, fault_id: str) -> bool:
        return fault_id in self.active
