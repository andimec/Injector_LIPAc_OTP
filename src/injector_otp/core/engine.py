from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Any

from ..epics.backend import PVBackend
from ..faults.manager import FaultManager
from .state import InjectorState, StateMachine


class Model(Protocol):
    def update(self, dt: float) -> None: ...


@dataclass
class SimulationContext:
    """Deterministic state shared by the simulation engine and its observers."""

    time: float = 0.0
    state: InjectorState = InjectorState.OFF
    pv: dict[str, object] = field(default_factory=dict)
    faults: set[str] = field(default_factory=set)


class SimulationEngine:
    """Coordinates the deterministic simulation cycle and PV boundary."""

    def __init__(
        self,
        models: list[Model] | None = None,
        dt: float = 0.1,
        pv_backend: PVBackend | None = None,
        fault_manager: FaultManager | None = None,
    ) -> None:
        if dt <= 0:
            raise ValueError("dt must be positive")
        self.dt = dt
        self.context = SimulationContext()
        self.state_machine = StateMachine()
        self.models = models or []
        self.pv_backend = pv_backend
        self.fault_manager = fault_manager

    def step(self, dt: float | None = None) -> SimulationContext:
        step_dt = self.dt if dt is None else dt
        if step_dt <= 0:
            raise ValueError("dt must be positive")

        # 1. Read the current simulation PV state.
        self._sync_context_from_pv()

        # 2. Apply active synthetic faults as engine-visible state.
        self._sync_faults()

        # 3. Update physical/reduced-order subsystem models.
        for model in self.models:
            model.update(step_dt)

        # 4-6. Protection and state evaluation will be populated as subsystem
        # models acquire their authorization interfaces.
        self.context.state = self.state_machine.state

        # 7. Advance simulation time after the completed model cycle.
        self.context.time += step_dt

        # 8. Publish standard simulator status PVs.
        self._publish_state()
        self._publish_time()

        # 9. Refresh the context snapshot after all publications.
        self._sync_context_from_pv()

        return self.context

    def _sync_context_from_pv(self) -> None:
        if self.pv_backend is None:
            return
        self.context.pv = {
            name: self.pv_backend.get(name)
            for name in self.pv_backend.names()
        }

    def _sync_faults(self) -> None:
        if self.fault_manager is not None:
            self.context.faults = set(self.fault_manager.active)
        else:
            self.context.faults = set()

    def _publish_state(self) -> None:
        """Publish standard simulator state when the PV exists."""
        if self.pv_backend is not None and "OTP:STATE" in set(self.pv_backend.names()):
            self.pv_backend.publish("OTP:STATE", self.context.state.value)

    def _publish_time(self) -> None:
        if self.pv_backend is not None and "OTP:SIM_TIME" in set(self.pv_backend.names()):
            self.pv_backend.publish("OTP:SIM_TIME", self.context.time)

    def snapshot(self) -> dict[str, Any]:
        """Return a deterministic simulation snapshot for logging/replay."""
        return {
            "time": self.context.time,
            "state": self.context.state.value,
            "faults": sorted(self.context.faults),
            "pv": dict(self.context.pv),
        }
