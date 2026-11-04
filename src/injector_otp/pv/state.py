from __future__ import annotations

from dataclasses import dataclass
from time import time
from typing import Any, Iterable

from ..core.pv_registry import PVDirection, PVDefinition, PVRegistry


@dataclass(frozen=True)
class PVValue:
    """Value owned by the simulation runtime."""

    name: str
    value: Any
    timestamp: float
    source: str


class SimulationPVState:
    """Authoritative in-process PV state for the Digital Twin.

    This object is the source of truth between models and the EPICS adapter.
    Models never access EPICS directly.

    Operator-facing writes are accepted only for explicitly configured command
    and setpoint inputs. Model-generated values are written through publish().
    """

    def __init__(
        self,
        registry: PVRegistry | None = None,
        *,
        writable_names: Iterable[str] = (),
    ) -> None:
        self.registry = registry
        self._writable_names = set(writable_names)
        self._values: dict[str, PVValue] = {}

    def define(
        self,
        name: str,
        value: Any = 0,
        *,
        source: str = "initialization",
    ) -> None:
        self._require_registered(name)
        self._values[name] = PVValue(name, value, time(), source)

    def allow_operator_write(self, name: str) -> None:
        """Explicitly mark a PV as writable by the local adapter/test harness."""
        self._writable_names.add(name)

    def is_operator_writable(self, name: str) -> bool:
        return name in self._writable_names

    def get(self, name: str) -> Any:
        return self._values[name].value

    def record(self, name: str) -> PVValue:
        return self._values[name]

    def put(self, name: str, value: Any, *, source: str = "operator") -> None:
        if name not in self._writable_names:
            definition = self._definition(name)
            if definition is None or definition.direction not in (
                PVDirection.COMMAND,
                PVDirection.SETPOINT,
            ):
                raise PermissionError(
                    f"PV is simulation-owned/read-only or unresolved: {name}"
                )
            raise PermissionError(
                f"PV is not explicitly enabled as an operator input: {name}"
            )
        self._values[name] = PVValue(name, value, time(), source)

    def publish(self, name: str, value: Any, *, source: str = "simulation") -> None:
        """Publish a model/interlock-generated output."""
        self._require_registered(name)
        self._values[name] = PVValue(name, value, time(), source)

    def names(self) -> list[str]:
        return sorted(self._values)

    def snapshot(self) -> dict[str, PVValue]:
        return dict(self._values)

    def values(self) -> dict[str, Any]:
        return {name: item.value for name, item in self._values.items()}

    def _definition(self, name: str) -> PVDefinition | None:
        if self.registry is None:
            return None
        try:
            return self.registry.get(name)
        except KeyError:
            return None

    def _require_registered(self, name: str) -> None:
        if self.registry is None:
            return
        if name in self.registry.names() or name.startswith("OTP:"):
            return
        raise KeyError(f"PV is not registered: {name}")
