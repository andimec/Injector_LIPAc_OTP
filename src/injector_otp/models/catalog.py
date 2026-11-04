"""Device inventory and EPICS metadata for the Python model runtime.

The catalog is a read-only description of the existing Injector PV interface.
It does not execute control logic and does not import any EPICS library.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DevicePV:
    name: str
    record_type: str | None
    fields: dict[str, str]
    subsystem: str
    source: str

    def limit(self, field: str) -> float | None:
        value = self.fields.get(field)
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


class DeviceCatalog:
    """Catalog assembled from V2.0, preserving DB and OPI traceability.

    A PV can belong to a functional subsystem without having a validated
    physical model. Coverage is reported separately from PV existence.
    """

    def __init__(self, pvs: dict[str, DevicePV]) -> None:
        self.pvs = pvs

    @classmethod
    def from_registry(cls, path: str | Path) -> "DeviceCatalog":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        catalog = {}
        for item in payload.get("pvs", []):
            records = item.get("db_records", [])
            rec = next(
                (rec for rec in records if rec.get("source_classification") != "opi_inferred_standalone"),
                records[0] if records else None,
            )
            catalog[item["name"]] = DevicePV(
                name=item["name"],
                record_type=rec["record_type"] if rec else None,
                fields=dict(rec["fields"]) if rec else {},
                subsystem=item.get("model_contract", {}).get("subsystem", "unassigned"),
                source="db" if rec else ("opi" if item.get("opi_references") else "snapshot"),
            )
        return cls(catalog)

    def has(self, name: str) -> bool:
        return name in self.pvs

    def get(self, name: str) -> DevicePV | None:
        return self.pvs.get(name)

    def contains_prefix(self, prefix: str) -> bool:
        return any(name.startswith(prefix) for name in self.pvs)

    def pv(self, prefix: str, *suffixes: str) -> str | None:
        for suffix in suffixes:
            name = f"{prefix}:{suffix}"
            if name in self.pvs:
                return name
        return None

    def names(self, prefix: str) -> list[str]:
        return sorted(name for name in self.pvs if name.startswith(f"{prefix}:"))

    def subsystems(self) -> dict[str, int]:
        totals: dict[str, int] = {}
        for definition in self.pvs.values():
            totals[definition.subsystem] = totals.get(definition.subsystem, 0) + 1
        return dict(sorted(totals.items()))

    def clamp(self, name: str, value: float) -> float:
        """Apply the verified DRVL/DRVH limits of a DB record when available."""
        pv = self.get(name)
        if pv is None:
            return value
        lower = pv.limit("DRVL")
        upper = pv.limit("DRVH")
        if lower is not None and upper is not None and upper >= lower:
            return max(lower, min(upper, value))
        return value
