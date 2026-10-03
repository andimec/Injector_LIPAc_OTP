from __future__ import annotations

from typing import Any

from ..pv.state import SimulationPVState
from .contract import SimulationIOCContract


class SimulationPVBackend:
    """Compatibility adapter exposing SimulationPVState through EPICS-like names.

    The engine does not depend on this class. It exists as a local transport
    adapter for tests and for the pre-Soft-IOC development phase.
    """

    def __init__(self, state: SimulationPVState | None = None) -> None:
        self.state = state or SimulationPVState()

    def define(self, name: str, value: Any = 0, writable: bool = False) -> None:
        # Writable is retained for compatibility with the previous in-memory
        # backend. New applications should configure writable names explicitly
        # in SimulationPVState.
        if writable and name not in self.state._writable_names:
            self.state._writable_names.add(name)
        self.state.define(name, value=value)

    def get(self, name: str) -> Any:
        source_name = self._source_name(name)
        return self.state.get(source_name)

    def put(self, name: str, value: Any) -> None:
        sim_name = SimulationIOCContract.simulation_name(name)
        SimulationIOCContract.require_simulation_namespace(sim_name)
        self.state.put(self._source_name(sim_name), value)

    def publish(self, name: str, value: Any) -> None:
        sim_name = SimulationIOCContract.simulation_name(name)
        self.state.publish(self._source_name(sim_name), value)

    def names(self) -> list[str]:
        return [
            SimulationIOCContract.simulation_name(name)
            for name in self.state.names()
        ]

    def timestamp(self, name: str) -> float:
        return self.state.record(self._source_name(name)).timestamp

    def snapshot(self) -> dict[str, tuple[Any, float]]:
        return {
            name: (self.get(name), self.timestamp(name))
            for name in self.names()
        }

    @staticmethod
    def _source_name(name: str) -> str:
        if SimulationIOCContract.is_simulation_name(name):
            return name[len(SimulationIOCContract.SIM_NAMESPACE):]
        return name
