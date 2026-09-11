from dataclasses import dataclass, field
from typing import Protocol

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
    """Coordinates models, state and PV publication without real hardware access."""

    def __init__(self, models: list[Model] | None = None, dt: float = 0.1) -> None:
        self.dt = dt
        self.context = SimulationContext()
        self.state_machine = StateMachine()
        self.models = models or []

    def step(self, dt: float | None = None) -> SimulationContext:
        step_dt = self.dt if dt is None else dt
        for model in self.models:
            model.update(step_dt)
        self.context.time += step_dt
        self.context.state = self.state_machine.state
        return self.context
