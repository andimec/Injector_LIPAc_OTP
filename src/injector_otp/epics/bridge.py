from __future__ import annotations

from typing import Any, Protocol

from ..pv.state import SimulationPVState


class PVBridge(Protocol):
    """Transport contract between Python PV state and an EPICS IOC."""

    def start(self) -> None: ...
    def stop(self) -> None: ...
    def pull_inputs(self) -> dict[str, Any]: ...
    def push_outputs(self, values: dict[str, Any]) -> None: ...


class SoftIOCAdapter(PVBridge, Protocol):
    """Future simulation Soft IOC transport, preserving native PV names."""
    pass


class LocalPVBridge:
    """In-process bridge, with no network I/O and no PV-name rewriting."""

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
            self.state.publish(name, value, source="epics-bridge")
