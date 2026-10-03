from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Any

from ..faults.manager import FaultManager
from ..pv.state import SimulationPVState
from .control import SimulationControlPlane, SimulationLogic
from .state import InjectorState, StateMachine


class Model(Protocol):
    def update(self, dt: float, context: "SimulationContext") -> None: ...


@dataclass
class SimulationContext:
    """Deterministic state shared by the simulation runtime.

    This context contains simulation data only. It deliberately has no EPICS
    dependency. Transport is handled by an adapter outside the engine.
    """

    time: float = 0.0
    state: InjectorState = InjectorState.OFF
    pv: dict[str, object] = field(default_factory=dict)
    faults: set[str] = field(default_factory=set)
    interlocks: dict[str, bool] = field(default_factory=dict)
    device_faults: dict[str, bool] = field(default_factory=dict)


class SimulationEngine:
    """Coordinates the Python Digital Twin runtime.

    EPICS is intentionally outside this class. The engine consumes and
    publishes values through SimulationPVState; an EPICS bridge may transport
    those values to a Soft IOC.
    """

    def __init__(
        self,
        models: list[Model] | None = None,
        dt: float = 0.1,
        pv_state: SimulationPVState | None = None,
        fault_manager: FaultManager | None = None,
        control_plane: SimulationControlPlane | None = None,
        logic: list[SimulationLogic] | None = None,
    ) -> None:
        if dt <= 0:
            raise ValueError("dt must be positive")
        self.dt = dt
        self.context = SimulationContext()
        self.state_machine = StateMachine()
        self.models = models or []
        self.pv_state = pv_state
        self.fault_manager = fault_manager
        self.control_plane = control_plane or SimulationControlPlane()
        self.logic = logic or []

    def step(self, dt: float | None = None) -> SimulationContext:
        step_dt = self.dt if dt is None else dt
        if step_dt <= 0:
            raise ValueError("dt must be positive")

        # 1. Read the current command/setpoint/input state.
        self._sync_context_from_pv()

        # 2. Apply synthetic faults before the physical update.
        self._sync_faults()

        # 3. Evaluate external authorization/control logic.
        for logic in self.logic:
            logic.evaluate(self.context, self.control_plane)
        self._sync_control_plane()

        # 4. Update physical/reduced-order subsystem models.
        for model in self.models:
            model.update(step_dt, self.context)

        # 5. Re-evaluate authorization after model consequences. This allows
        # a newly generated device fault/status to affect protection outputs in
        # the same simulation cycle.
        for logic in self.logic:
            logic.evaluate(self.context, self.control_plane)
        self._sync_control_plane()

        # 6. State-machine ownership remains in Python.
        self.context.state = self.state_machine.state

        # 7. Advance deterministic simulation time.
        self.context.time += step_dt

        # 8. Publish simulator-owned status values.
        self._publish_state()
        self._publish_time()

        # 9. Refresh the context snapshot after all publications.
        self._sync_context_from_pv()
        return self.context

    def _sync_context_from_pv(self) -> None:
        if self.pv_state is None:
            return
        self.context.pv = self.pv_state.values()

    def _sync_control_plane(self) -> None:
        self.context.interlocks = dict(self.control_plane.interlocks)
        self.context.device_faults = dict(self.control_plane.device_faults)

    def _sync_faults(self) -> None:
        if self.fault_manager is not None:
            self.context.faults = set(self.fault_manager.active)
        else:
            self.context.faults = set()

    def _publish_state(self) -> None:
        if self.pv_state is not None and "OTP:STATE" in self.pv_state.names():
            self.pv_state.publish(
                "OTP:STATE",
                self.context.state.value,
                source="engine",
            )

    def _publish_time(self) -> None:
        if self.pv_state is not None and "OTP:SIM_TIME" in self.pv_state.names():
            self.pv_state.publish(
                "OTP:SIM_TIME",
                self.context.time,
                source="engine",
            )

    def snapshot(self) -> dict[str, Any]:
        """Return a deterministic simulation snapshot for logging/replay."""
        return {
            "time": self.context.time,
            "state": self.context.state.value,
            "faults": sorted(self.context.faults),
            "interlocks": dict(sorted(self.context.interlocks.items())),
            "device_faults": dict(sorted(self.context.device_faults.items())),
            "pv": dict(self.context.pv),
        }
