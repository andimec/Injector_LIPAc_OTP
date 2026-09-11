from .base import SubsystemModel


class InjectorModel(SubsystemModel):
    """Top-level composition point for physical subsystem models."""

    name = "injector"

    def __init__(self) -> None:
        super().__init__()
        self.beam_current_mA = 0.0
        self.hv_kV = 0.0
        self.rf_forward_W = 0.0
        self.vacuum_mbar = 1.0

    def update(self, dt: float) -> None:
        super().update(dt)
        # Placeholder dynamics. Real subsystem equations are added independently.
        if not self.state.enabled or self.state.fault:
            return
