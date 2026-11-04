"""Read-only compatibility calculations for vacuum OPI preconditions.

These are *display* formulas from plcInjector_StatusForOpi.db; they are NOT
the real Siemens PLC interlock implementation and are not used as permissive
actuation rules without validated PLC ladder semantics.
"""
from __future__ import annotations

from .base import SubsystemModel
from .catalog import DeviceCatalog
from .original_lcs_logic import (
    vacuum01_pv_precondition,
    vacuum01_sv_precondition,
    vacuum02_sv_precondition,
)


class VacuumOPIPreconditions(SubsystemModel):
    name = "vacuum_opi_preconditions"

    def __init__(self, catalog: DeviceCatalog) -> None:
        super().__init__()
        self.catalog = catalog

    def update(self, dt: float, context) -> None:
        super().update(dt)

        def status(name: str) -> bool:
            return bool(context.pv.get(name, 0))

        force = status("LEBT:VAC:SVForcing")
        # PVC precondition is identical for VAC01 and VAC02.
        for region in ("LEBT:VAC01", "LEBT:VAC02"):
            result = vacuum01_pv_precondition(
                status(f"{region}:TPDefStat"),
                status(f"{region}:PPOnStat"),
                status(f"{region}:AIVOpenStat"),
            )
            name = f"{region}:PVOpenPrecond"
            if self.catalog.has(name):
                context.emit(name, int(result), "plc_opi_formula")
        p1 = vacuum01_sv_precondition(
            status("LEBT:VAC01:AIVOpenStat"),
            status("LEBT:VAC01:NIVOpenStat"),
            status("LEBT:VAC01:TPDefStat"),
            status("LEBT:VAC01:SVOpenStat"),
            status("LEBT:VAC01:PGTPDefStat"),
            status("LEBT:VAC01:SGTPDefStat"),
            status("LEBT:VAC01:PGVCDefStat"),
            force,
        )
        p2 = vacuum02_sv_precondition(
            status("LEBT:VAC02:PGTPDefStat"),
            status("LEBT:VAC02:SGTPDefStat"),
            status("LEBT:VAC02:PGVCDefStat"),
            status("LEBT:VAC02:TPSpeedStat"),
            force,
        )
        for region, value in (("LEBT:VAC01", p1), ("LEBT:VAC02", p2)):
            name = f"{region}:SVOpenPrecond"
            if self.catalog.has(name):
                context.emit(name, int(value), "plc_opi_formula")
