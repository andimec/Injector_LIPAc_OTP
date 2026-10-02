from __future__ import annotations

from time import time
from typing import Any

from .contract import SimulationIOCContract
from .store import PVStore


class SimulationPVBackend:
    """Explicitly namespaced PV backend for the Digital Twin.

    This backend is intentionally local. It cannot write to production PV names.
    A future soft IOC adapter must preserve the same namespace and validation rules.
    """

    def __init__(self) -> None:
        self._store = PVStore()

    def define(self, name: str, value: Any = 0, writable: bool = False) -> None:
        sim_name = SimulationIOCContract.simulation_name(name)
        self._store.define(sim_name, value=value, writable=writable)

    def get(self, name: str) -> Any:
        sim_name = SimulationIOCContract.simulation_name(name)
        return self._store.get(sim_name)

    def put(self, name: str, value: Any) -> None:
        sim_name = SimulationIOCContract.simulation_name(name)
        SimulationIOCContract.require_simulation_namespace(sim_name)
        self._store.put(sim_name, value)

    def publish(self, name: str, value: Any) -> None:
        sim_name = SimulationIOCContract.simulation_name(name)
        self._store.publish(sim_name, value)

    def names(self) -> list[str]:
        return self._store.names()

    def timestamp(self, name: str) -> float:
        sim_name = SimulationIOCContract.simulation_name(name)
        return self._store._pvs[sim_name].timestamp

    def snapshot(self) -> dict[str, tuple[Any, float]]:
        now = time()
        return {
            name: (self._store.get(name), self.timestamp(name))
            for name in self.names()
        }
