from dataclasses import dataclass
from time import time
from typing import Any


@dataclass
class PV:
    name: str
    value: Any = 0
    timestamp: float = 0.0
    writable: bool = False


class PVStore:
    """In-memory PV boundary used before connecting an EPICS backend."""

    def __init__(self) -> None:
        self._pvs: dict[str, PV] = {}

    def define(self, name: str, value: Any = 0, writable: bool = False) -> None:
        self._pvs[name] = PV(name=name, value=value, timestamp=time(), writable=writable)

    def get(self, name: str) -> Any:
        return self._pvs[name].value

    def put(self, name: str, value: Any) -> None:
        pv = self._pvs[name]
        if not pv.writable:
            raise PermissionError(f"PV is read-only: {name}")
        pv.value = value
        pv.timestamp = time()

    def publish(self, name: str, value: Any) -> None:
        """Publish a model-generated value, bypassing operator write permissions."""
        pv = self._pvs[name]
        pv.value = value
        pv.timestamp = time()

    def names(self) -> list[str]:
        return sorted(self._pvs)
