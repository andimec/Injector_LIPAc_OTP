from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SubsystemModel:
    """Minimal model boundary. Physics and control behaviour are added later."""

    name: str

    def update(self, dt: float) -> None:
        if dt <= 0:
            raise ValueError("dt must be positive")


class SourceModel(SubsystemModel):
    pass


class VacuumModel(SubsystemModel):
    pass


class MagnetModel(SubsystemModel):
    pass


class HVModel(SubsystemModel):
    pass


class RFModel(SubsystemModel):
    pass


class ChopperModel(SubsystemModel):
    pass


class DiagnosticsModel(SubsystemModel):
    pass


class CoolingModel(SubsystemModel):
    pass


class MPSModel(SubsystemModel):
    pass


class PPSModel(SubsystemModel):
    pass
