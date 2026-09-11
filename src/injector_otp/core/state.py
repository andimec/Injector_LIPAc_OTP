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


class StateMachine:
    """Minimal deterministic state machine for the training simulator."""

    def __init__(self) -> None:
        self.state = InjectorState.OFF

    def transition(self, target: InjectorState) -> None:
        if target == self.state:
            return
        self.state = target

    def fault(self) -> None:
        self.state = InjectorState.FAULT

    def inhibit(self) -> None:
        self.state = InjectorState.INHIBITED

    def reset(self) -> None:
        self.state = InjectorState.OFF
