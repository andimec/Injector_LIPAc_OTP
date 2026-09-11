from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..epics.backend import PVBackend
from .state import InjectorState, StateMachine


class Model(Protocol):
    def update(self, dt: float) -> None: ...


@dataclass
class SimulationContext:
    time: float = 0.0
    state: InjectorState = InjectorState.OFF
    pv: dict[str, object] = field(default_factory=dict)
    faults: set[str] = field(default_factory=set)


class SimulationEngine:
    """Coordinates models, state and the backend-neutral PV boundary."""

    def __init__(
        self,
        models: list[Model] | None = None,
        dt: float = 0.1,
        pv_backend: PVBackend | None = None,
    ) -> None:
        if dt <= 0:
            raise ValueError("dt must be positive")
        self.dt = dt
        self.context = SimulationContext()
        self.state_machine = StateMachine()
        self.models = models or []
        self.pv_backend = pv_backend

    def step(self, dt: float | None = None) -> SimulationContext:
        step_dt = self.dt if dt is None else dt
        if step_dt <= 0:
            raise ValueError("dt must be positive")
        for model in self.models:
            model.update(step_dt)
        self.context.time += step_dt
        self.context.state = self.state_machine.state
        self.context.pv = {
            name: self.pv_backend.get(name) for name in self.pv_backend.names()
        } if self.pv_backend is not None else self.context.pv
        if self.pv_backend is not None:
            self._publish_state()
        return self.context

    def _publish_state(self) -> None:
        """Publish standard simulator status PVs when they exist."""
        names = set(self.pv_backend.names())
        if "OTP:STATE" in names:
            self.pv_backend.publish("OTP:STATE", self.context.state.value)
        if "OTP:SIM_TIME" in names:
            self.pv_backend.publish("OTP:SIM_TIME", self.context.time)
