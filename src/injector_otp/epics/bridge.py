from __future__ import annotations

from typing import Any, Protocol

from ..pv.state import SimulationPVState
from .contract import SimulationIOCContract


class PVBridge(Protocol):
    """Transport contract between Python PV state and an EPICS IOC."""

    def start(self) -> None: ...
    def stop(self) -> None: ...
    def pull_inputs(self) -> dict[str, Any]: ...
    def push_outputs(self, values: dict[str, Any]) -> None: ...


class SoftIOCAdapter(PVBridge, Protocol):
    """Contract implemented by the real simulation Soft IOC adapter."""

    pass


class LocalPVBridge:
    """Deterministic bridge used before the real EPICS Soft IOC exists.

    It deliberately performs no network I/O. Its purpose is to exercise the
    same ownership direction that the future IOC adapter will implement.
    """

    def __init__(self, state: SimulationPVState) -> None:
        self.state = state
        self.running = False

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def pull_inputs(self) -> dict[str, Any]:
        return self.state.values()

    def push_outputs(self, values: dict[str, Any]) -> None:
        for name, value in values.items():
            source_name = self._source_name(name)
            self.state.publish(source_name, value, source="epics-bridge")

    @staticmethod
    def _source_name(name: str) -> str:
        if SimulationIOCContract.is_simulation_name(name):
            return name[len(SimulationIOCContract.SIM_NAMESPACE):]
        return name
