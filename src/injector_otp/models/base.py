from dataclasses import dataclass


@dataclass
class ModelState:
    """Common state container for a subsystem model."""

    enabled: bool = True
    fault: bool = False


class SubsystemModel:
    name = "generic"

    def __init__(self) -> None:
        self.state = ModelState()

    def update(self, dt: float) -> None:
        if dt < 0:
            raise ValueError("dt must be non-negative")

    def interlock_ok(self, context, name: str, default: bool = True) -> bool:
        """Read an external authorization without implementing its logic."""
        return context.interlocks.get(name, default)

    def in_fault(self, context, device: str | None = None) -> bool:
        """Read an externally injected device fault."""
        return context.device_faults.get(device or self.name, False)
