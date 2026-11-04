from __future__ import annotations

from ..core.engine import SimulationContext
from .base import SubsystemModel


class SourceModel(SubsystemModel):
    name = "source"

    def update(self, dt: float, context: SimulationContext) -> None:
        super().update(dt)


class VacuumModel(SubsystemModel):
    name = "vacuum"

    def update(self, dt: float, context: SimulationContext) -> None:
        super().update(dt)


class MagnetModel(SubsystemModel):
    name = "magnets"

    def update(self, dt: float, context: SimulationContext) -> None:
        super().update(dt)


class HVModel(SubsystemModel):
    name = "hv"

    def update(self, dt: float, context: SimulationContext) -> None:
        super().update(dt)


class RFModel(SubsystemModel):
    name = "rf"

    def update(self, dt: float, context: SimulationContext) -> None:
        super().update(dt)


class ChopperModel(SubsystemModel):
    name = "chopper"

    def update(self, dt: float, context: SimulationContext) -> None:
        super().update(dt)


class DiagnosticsModel(SubsystemModel):
    name = "diagnostics"

    def update(self, dt: float, context: SimulationContext) -> None:
        super().update(dt)


class CoolingModel(SubsystemModel):
    name = "cooling"

    def update(self, dt: float, context: SimulationContext) -> None:
        super().update(dt)


class MPSModel(SubsystemModel):
    name = "mps"

    def update(self, dt: float, context: SimulationContext) -> None:
        super().update(dt)


class PPSModel(SubsystemModel):
    name = "pps"

    def update(self, dt: float, context: SimulationContext) -> None:
        super().update(dt)
