from __future__ import annotations

from typing import Any, Protocol


class PVBackend(Protocol):
    """Backend contract between the simulator and an EPICS-facing layer.

    The simulator only depends on this interface. A real EPICS implementation
    can be added later without coupling the physical models to EPICS libraries.
    """

    def get(self, name: str) -> Any: ...

    def put(self, name: str, value: Any) -> None: ...

    def publish(self, name: str, value: Any) -> None: ...

    def names(self) -> list[str]: ...
