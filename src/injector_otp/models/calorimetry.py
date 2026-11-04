"""Original EPICS FC/BS/IC calorimetry equations evaluated in Python.

Sources (topIFMIF_INJ/main at 3586551):
- emitApp/db/injectorFC_Calorimetry.db
- emitApp/db/injectorBS_Calorimetry.db
- emitApp/db/injectorIC_Calorimetry.db

These are exact legacy display/processing formulas, NOT a measured thermal
hydraulic model. In particular, SRC:TIM:DutyCycle is the original EPICS
display quantity, not necessarily the physical beam pulse duty fraction.
"""
from __future__ import annotations

from .base import SubsystemModel
from .catalog import DeviceCatalog


def legacy_delta_t(tin_V: float, tout_V: float, compensation_K: float) -> float:
    """Original Tincalc=5*TinRdbk; Toutcalc=5*ToutRdbk; DeltaT=(B-A)-C."""
    return 5.0 * (tout_V - tin_V) - compensation_K


def legacy_current(delta_t: float, mass_flow: float, voltage: float,
                   duty_factor: float = 1.0) -> float | None:
    """Original ((E/C)*B*A)/D * F with B=4186.8, C=60.

    The units/calibration of E are historical process settings. No new unit
    conversion is inferred. A zero voltage is undefined, not a zero current.
    """
    if voltage == 0.0:
        return None
    return (mass_flow / 60.0) * 4186.8 * delta_t / voltage * duty_factor


class LegacyCalorimetryModel(SubsystemModel):
    """Reconstruct original calorimetric readouts without EPICS calc records."""

    name = "calorimetry"

    def __init__(self, catalog: DeviceCatalog):
        super().__init__()
        self.catalog = catalog

    def _read(self, context, name: str) -> float:
        try:
            return float(context.pv.get(name, 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    def _has_measurement(self, context, name: str) -> bool:
        # A live IOC passes records with timestamps, but the MVP PV store
        # initializes all readbacks to 0. A zero inlet voltage cannot be
        # distinguished from an unread device. Avoid advertising validity.
        return name in context.pv and self._read(context, name) != 0.0

    def _emit(self, context, name: str, value: float | None):
        if value is not None and self.catalog.has(name):
            context.emit(name, value, "original_lcs_calorimetry")

    def _temperatures(self, context, prefix: str) -> tuple[float, float] | None:
        inlet = f"{prefix}:TinRdbk"
        outlet = f"{prefix}:ToutRdbk"
        if not (self._has_measurement(context, inlet)
                and self._has_measurement(context, outlet)):
            return None
        tin = 5.0 * self._read(context, inlet)
        tout = 5.0 * self._read(context, outlet)
        self._emit(context, f"{prefix}:Tincalc", tin)
        self._emit(context, f"{prefix}:Toutcalc", tout)
        return tin, tout

    def _efficiency(self, context, prefix: str, calculated: float | None,
                    denominator_name: str, gated: bool = False) -> None:
        if calculated is None or not self.catalog.has(denominator_name):
            return
        if gated and not bool(context.pv.get("LEBT:FC:InStat", 0)):
            self._emit(context, f"{prefix}:IRendement", 0.0)
            return
        measured = self._read(context, denominator_name)
        if measured == 0.0:
            return
        self._emit(context, f"{prefix}:IRendement",
                   calculated / measured * 100.0)

    def update(self, dt: float, context) -> None:
        super().update(dt)
        temps = {}
        for prefix in ("LEBT:FC", "LEBT:BS", "LEBT:IC"):
            t = self._temperatures(context, prefix)
            if t is not None:
                temps[prefix] = t

        hv_kV = self._read(context, "LEBT:HV_PS:HTCmd")
        legacy_duty = self._read(context, "SRC:TIM:DutyCycle")

        # Faraday cup is used as inlet reference by the legacy BS/IC
        # DeltaT records. This apparently surprising cross-reference is
        # deliberately kept from the original DB definitions.
        if "LEBT:FC" in temps:
            tin, tout = temps["LEBT:FC"]
            delta = tout - tin - self._read(context, "LEBT:FC:Comp")
            self._emit(context, "LEBT:FC:DeltaT", delta)
            current = legacy_current(delta, 40.0, hv_kV, legacy_duty)
            self._emit(context, "LEBT:FC:ICalc", current)
            self._efficiency(context, "LEBT:FC", current, "LEBT:EMIT_FC:I",
                             gated=True)

        for device in ("LEBT:BS", "LEBT:IC"):
            if device not in temps or "LEBT:FC" not in temps:
                continue
            inlet_reference = temps["LEBT:FC"][0]
            inlet_local, outlet = temps[device]
            comp = self._read(context, f"{device}:Comp")
            delta_shared = outlet - inlet_reference - comp
            self._emit(context, f"{device}:DeltaT", delta_shared)

            if device == "LEBT:BS":
                current = legacy_current(delta_shared, 40.0, hv_kV, legacy_duty)
                self._emit(context, f"{device}:Icalc", current)
                delta_local = outlet - inlet_local - comp
                self._emit(context, f"{device}:DeltaT2", delta_local)
                self._emit(context, f"{device}:Icalc2",
                           legacy_current(delta_local, 40.0, hv_kV, legacy_duty))
                self._efficiency(context, device, current, "LEBT:BS:I")
            else:
                current = legacy_current(delta_shared, 320.0, 100.0)
                self._emit(context, f"{device}:Icalc", current)
                self._efficiency(context, device, current, "LEBT:IC:I")
