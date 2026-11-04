from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .pv_registry import PVDirection, PVDefinition, PVRegistry


_DIRECTION_BY_ACCESS = {
    (True, False): PVDirection.MONITOR,
    (False, True): PVDirection.SETPOINT,
    # Read/write in the source IOC does not identify semantic ownership.
    # Treat it as unresolved until the command/setpoint/output role is verified.
    (True, True): PVDirection.UNRESOLVED,
}


def _direction(source_data: dict[str, Any]) -> PVDirection:
    read = bool(source_data.get("read_access", False))
    write = bool(source_data.get("write_access", False))
    return _DIRECTION_BY_ACCESS.get((read, write), PVDirection.UNRESOLVED)


def _normalise_type(epics_type: str | None) -> str:
    if not epics_type:
        return "unknown"
    value = epics_type.lower()
    if "enum" in value:
        return "enum"
    if "double" in value or "float" in value:
        return "number"
    if "int" in value:
        return "integer"
    if "string" in value:
        return "string"
    return value


def load_registry(path: str | Path) -> PVRegistry:
    """Load the machine-readable PV inventory without inventing semantics."""
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))

    definitions: list[PVDefinition] = []
    for item in payload.get("pvs", []):
        source_data = item.get("source_data") or (
            item.get("snapshot_v1_2") or {}
        ).get("source_data", {})
        definitions.append(
            PVDefinition(
                name=item["name"],
                direction=_direction(source_data),
                type=_normalise_type(source_data.get("epics_type")),
            )
        )

    return PVRegistry(definitions)


def load_v1_2_registry(repo_root: str | Path = ".") -> PVRegistry:
    """Load the current Injector V1.2 registry from the repository config."""
    return load_registry(Path(repo_root) / "config" / "pv_registry_v1_2.json")


def load_v2_0_registry(repo_root: str | Path = ".") -> PVRegistry:
    """Load reconciled PV registry V2.0 from the repository config."""
    return load_registry(Path(repo_root) / "config" / "pv_registry_v2_0.json")
