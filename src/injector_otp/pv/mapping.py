from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..core.pv_registry import PVDirection, PVDefinition, PVRegistry


class PVOwner(str, Enum):
    """Logical owner of the current PV value."""

    OPERATOR = "operator"
    SIMULATION = "simulation"
    CONFIGURATION = "configuration"
    UNRESOLVED = "unresolved"


class PVRole(str, Enum):
    """Runtime semantic role exposed through EPICS."""

    COMMAND = "command"
    SETPOINT = "setpoint"
    MONITOR = "monitor"
    STATUS = "status"
    CALCULATED = "calculated"
    INITIAL_CONDITION = "initial_condition"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class PVRuntimeSpec:
    """Runtime ownership metadata layered on top of the source PV registry."""

    name: str
    owner: PVOwner
    role: PVRole
    writable_from_operator: bool
    generator: str | None = None


def role_from_definition(definition: PVDefinition) -> PVRole:
    if definition.direction is PVDirection.COMMAND:
        return PVRole.COMMAND
    if definition.direction is PVDirection.SETPOINT:
        return PVRole.SETPOINT
    if definition.direction is PVDirection.MONITOR:
        return PVRole.MONITOR
    if definition.direction is PVDirection.UNRESOLVED:
        return PVRole.UNRESOLVED
    return PVRole.CALCULATED


def runtime_spec(
    definition: PVDefinition,
    *,
    generator: str | None = None,
) -> PVRuntimeSpec:
    role = role_from_definition(definition)

    # Source workbook read/write metadata is not sufficient to infer semantic
    # ownership. A source PV can be read/write for implementation reasons.
    operator_writable = role in (PVRole.COMMAND, PVRole.SETPOINT)
    owner = PVOwner.OPERATOR if operator_writable else (
        PVOwner.UNRESOLVED if role is PVRole.UNRESOLVED else PVOwner.SIMULATION
    )

    return PVRuntimeSpec(
        name=definition.name,
        owner=owner,
        role=role,
        writable_from_operator=operator_writable,
        generator=generator,
    )


def build_runtime_specs(
    registry: PVRegistry,
    generators: dict[str, str] | None = None,
) -> dict[str, PVRuntimeSpec]:
    generators = generators or {}
    return {
        definition.name: runtime_spec(
            definition,
            generator=generators.get(definition.name),
        )
        for definition in registry.all()
    }
