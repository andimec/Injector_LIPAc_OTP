from __future__ import annotations

from .base import SubsystemModel
from ..core.engine import SimulationContext


class InjectorModel(SubsystemModel):
    """Top-level composition point for physical subsystem models."""

    name = "injector"

    def __init__(self) -> None:
        super().__init__()
        self.beam_current_mA = 0.0
        self.hv_kV = 0.0
        self.rf_forward_W = 0.0
        self.vacuum_mbar = 1.0

    def update(self, dt: float, context: SimulationContext) -> None:
        super().update(dt)
        # External interlocks/faults are inputs to the model boundary and are
        # deliberately not calculated here.
        if not self.state.enabled or self.state.fault:
            return

        if self.in_fault(context):
            return
