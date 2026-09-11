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
