from __future__ import annotations

from typing import Any

from ..pv.state import SimulationPVState
from .contract import SimulationIOCContract


class SimulationPVBackend:
    """Local EPICS-like adapter. Exposes native LIPAc PV names unchanged.

    It never connects to a production network. Writes are authorized only by
    SimulationPVState's explicit allowlist, irrespective of PV spelling.
    """

    def __init__(self, state: SimulationPVState | None = None) -> None:
        self.state = state or SimulationPVState()

    def define(self, name: str, value: Any = 0, writable: bool = False) -> None:
        name = SimulationIOCContract.simulation_name(name)
        if writable:
            self.state.allow_operator_write(name)
        self.state.define(name, value=value)

    def get(self, name: str) -> Any:
        return self.state.get(SimulationIOCContract.simulation_name(name))

    def put(self, name: str, value: Any) -> None:
        self.state.put(SimulationIOCContract.simulation_name(name), value)

    def publish(self, name: str, value: Any) -> None:
        self.state.publish(SimulationIOCContract.simulation_name(name), value)

    def names(self) -> list[str]:
        return self.state.names()

    def timestamp(self, name: str) -> float:
        return self.state.record(SimulationIOCContract.simulation_name(name)).timestamp

    def snapshot(self) -> dict[str, tuple[Any, float]]:
        return {
            name: (self.get(name), self.timestamp(name))
            for name in self.names()
        }
