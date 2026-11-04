from __future__ import annotations

from enum import Enum


class InjectorState(str, Enum):
    OFF = "OFF"
    GAS_READY = "GAS_READY"
    VACUUM_READY = "VACUUM_READY"
    HV_READY = "HV_READY"
    RF_READY = "RF_READY"
    BEAM_READY = "BEAM_READY"
    BEAM_ON = "BEAM_ON"
    FAULT = "FAULT"
    INHIBITED = "INHIBITED"
    SHUTDOWN = "SHUTDOWN"


_ALLOWED: dict[InjectorState, set[InjectorState]] = {
    InjectorState.OFF: {InjectorState.GAS_READY, InjectorState.SHUTDOWN},
    InjectorState.GAS_READY: {InjectorState.VACUUM_READY, InjectorState.OFF, InjectorState.FAULT, InjectorState.INHIBITED},
    InjectorState.VACUUM_READY: {InjectorState.HV_READY, InjectorState.OFF, InjectorState.FAULT, InjectorState.INHIBITED},
    InjectorState.HV_READY: {InjectorState.RF_READY, InjectorState.OFF, InjectorState.FAULT, InjectorState.INHIBITED},
    InjectorState.RF_READY: {InjectorState.BEAM_READY, InjectorState.OFF, InjectorState.FAULT, InjectorState.INHIBITED},
    InjectorState.BEAM_READY: {InjectorState.BEAM_ON, InjectorState.OFF, InjectorState.FAULT, InjectorState.INHIBITED},
    InjectorState.BEAM_ON: {InjectorState.BEAM_READY, InjectorState.FAULT, InjectorState.INHIBITED, InjectorState.SHUTDOWN},
    InjectorState.FAULT: {InjectorState.OFF, InjectorState.SHUTDOWN},
    InjectorState.INHIBITED: {InjectorState.OFF, InjectorState.FAULT, InjectorState.SHUTDOWN},
    InjectorState.SHUTDOWN: {InjectorState.OFF},
}


class StateMachine:
    """Deterministic operating-state machine for the training simulator."""

    def __init__(self) -> None:
        self.state = InjectorState.OFF

    def transition(self, target: InjectorState) -> None:
        if target == self.state:
            return
        if target not in _ALLOWED[self.state]:
            raise ValueError(f"Invalid injector transition: {self.state.value} -> {target.value}")
        self.state = target

    def fault(self) -> None:
        self.state = InjectorState.FAULT

    def inhibit(self) -> None:
        self.state = InjectorState.INHIBITED

    def reset(self) -> None:
        self.state = InjectorState.OFF
