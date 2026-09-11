from __future__ import annotations

from typing import Any

from .backend import PVBackend


class PVAccessor:
    """Small model-facing facade for reading commands and publishing signals."""

    def __init__(self, backend: PVBackend) -> None:
        self.backend = backend

    def read(self, name: str, default: Any = None) -> Any:
        try:
            return self.backend.get(name)
        except KeyError:
            return default

    def command(self, name: str, value: Any) -> None:
        self.backend.put(name, value)

    def publish(self, name: str, value: Any) -> None:
        self.backend.publish(name, value)
