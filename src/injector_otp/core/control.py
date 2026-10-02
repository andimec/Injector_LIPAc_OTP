from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class SimulationControlPlane:
    """External control inputs consumed by simulation models.

    Interlock values use one explicit convention:
    True means authorization/permission is granted.
    False means authorization is blocked.

    Device faults are independent from interlocks. A device may be healthy while
    an interlock blocks it, or faulty while external authorizations remain true.
    """

    interlocks: dict[str, bool] = field(default_factory=dict)
    device_faults: dict[str, bool] = field(default_factory=dict)

    def set_interlock(self, name: str, allowed: bool) -> None:
        if not name:
            raise ValueError("interlock name must not be empty")
        self.interlocks[name] = bool(allowed)

    def interlock_ok(self, name: str, default: bool = True) -> bool:
        return self.interlocks.get(name, default)

    def set_device_fault(self, device: str, active: bool = True) -> None:
        if not device:
            raise ValueError("device name must not be empty")
        self.device_faults[device] = bool(active)

    def device_in_fault(self, device: str) -> bool:
        return self.device_faults.get(device, False)

    def clear_device_fault(self, device: str) -> None:
        self.device_faults[device] = False

    def clear(self) -> None:
        self.interlocks.clear()
        self.device_faults.clear()

    def snapshot(self) -> dict[str, Any]:
        return {
            "interlocks": dict(sorted(self.interlocks.items())),
            "device_faults": dict(sorted(self.device_faults.items())),
        }


class SimulationLogic(Protocol):
    """External logic evaluated by the engine before model integration."""

    def evaluate(
        self,
        context: Any,
        controls: SimulationControlPlane,
    ) -> None: ...
