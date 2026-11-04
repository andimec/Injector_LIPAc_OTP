"""Reduced-order gas, vacuum and cooling equipment models.

This is the first operational OTP baseline, not a vacuum-network solver or
a thermal-hydraulic model. Device PV names come from the V2.0 catalog.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp

from .base import SubsystemModel
from .catalog import DeviceCatalog


@dataclass
class ValveState:
    opened: bool = False


class ValveDevice(SubsystemModel):
    def __init__(self, prefix: str, catalog: DeviceCatalog, *, initially_open: bool = False):
        super().__init__()
        self.name = prefix
        self.prefix = prefix
        self.catalog = catalog
        self.valve = ValveState(initially_open)
        self._previous = {}

    def _edge(self, context, suffix: str) -> bool:
        pv = self.catalog.pv(self.prefix, suffix)
        if not pv:
            return False
        active = bool(context.pv.get(pv, 0))
        previous = self._previous.get(pv, False)
        self._previous[pv] = active
        return active and not previous

    def update(self, dt: float, context) -> None:
        super().update(dt)
        if self._edge(context, "OpenCmd"):
            self.valve.opened = True
        if self._edge(context, "CloseCmd"):
            self.valve.opened = False
        for name, value in (("OpenStat", self.valve.opened),
                            ("CloseStat", not self.valve.opened)):
            pv = self.catalog.pv(self.prefix, name)
            if pv:
                context.emit(pv, int(value), f"valve:{self.prefix}")
        context.metrics[f"{self.prefix}.open"] = float(self.valve.opened)


class GasFlowController(SubsystemModel):
    """First-order MFC response in sccm, coupled to gas-valve status."""

    def __init__(self, prefix: str, valve_prefix: str, catalog: DeviceCatalog, params: dict):
        super().__init__()
        self.name = prefix
        self.prefix = prefix
        self.valve_prefix = valve_prefix
        self.catalog = catalog
        self.params = params
        self.actual_sccm = 0.0
        self.enabled = False

    def update(self, dt: float, context) -> None:
        super().update(dt)
        cmd = self.catalog.pv(self.prefix, "OpenCmd")
        if cmd is not None:
            self.enabled = bool(context.pv.get(cmd, 0))
        main_open = bool(context.metrics.get(f"{self.valve_prefix}.open", 0))
        target_pv = self.catalog.pv(self.prefix, "Debit")
        requested = max(0.0, float(context.pv.get(target_pv, 0) or 0)) if target_pv else 0.0
        if target_pv:
            requested = self.catalog.clamp(target_pv, requested)
        target = requested if self.enabled and main_open else 0.0
        tau = max(0.001, float(self.params.get("gas", {}).get("response_tau_s", 0.5)))
        self.actual_sccm += (target - self.actual_sccm) * (1.0 - exp(-dt / tau))
        self.actual_sccm = max(0.0, self.actual_sccm)
        suffix = "Deb1Mes" if self.prefix.endswith("MFCD") else "Deb2Mes"
        readback = self.catalog.pv(self.prefix, suffix)
        if readback:
            context.emit(readback, self.actual_sccm, f"mfc:{self.prefix}")
        status = self.catalog.pv(self.prefix, "StsVanne")
        if status:
            context.emit(status, int(self.enabled), f"mfc:{self.prefix}")
        context.metrics[f"{self.prefix}.flow_sccm"] = self.actual_sccm


class CoolingSkidModel(SubsystemModel):
    """Cooling status is an external initial condition until skid data exists.

    The known sensor status can be driven low by a synthetic cooling fault.
    No unverified thermal or hydraulic correlations are implemented.
    """

    name = "cooling_skid"

    def __init__(self, catalog: DeviceCatalog) -> None:
        super().__init__()
        self.catalog = catalog

    def update(self, dt: float, context) -> None:
        super().update(dt)
        name = "INJ:WS:ResPCDefStat"
        if (context.device_faults.get("cooling", False)
                or "COOLING_FAILURE" in context.faults):
            if self.catalog.has(name):
                context.emit(name, 0, "cooling_skid")
        context.metrics["cooling.healthy"] = float(bool(context.pv.get(name, False)))


class VacuumRegionModel(SubsystemModel):
    """Empirical pressure balance for one VAC region.

    The parameters are explicit training hypotheses, not a claimed measured
    pumping curve. Pressure units are mbar.
    """

    def __init__(self, prefix: str, catalog: DeviceCatalog, params: dict) -> None:
        super().__init__()
        self.name = prefix
        self.prefix = prefix
        self.catalog = catalog
        self.params = params
        self.pressure_mbar = float(params.get("vacuum", {}).get("initial_pressure_mbar", 1e-6))
        self.pp_on = False
        self.tp_on = False
        self._prev = {}

    def _edge(self, context, suffix: str) -> bool:
        name = self.catalog.pv(self.prefix, suffix)
        if name is None:
            return False
        now = bool(context.pv.get(name, 0))
        was = self._prev.get(name, False)
        self._prev[name] = now
        return now and not was

    def update(self, dt: float, context) -> None:
        super().update(dt)
        if self._edge(context, "PPOnCmd"):
            self.pp_on = True
        if self._edge(context, "PPOffCmd"):
            self.pp_on = False
        if self._edge(context, "TPOnCmd"):
            self.tp_on = True
        if self._edge(context, "TPOffCmd"):
            self.tp_on = False

        for suffix, value in (("PPOnStat", self.pp_on), ("TPOnStat", self.tp_on)):
            name = self.catalog.pv(self.prefix, suffix)
            if name:
                context.emit(name, int(value), f"vacuum:{self.prefix}")

        settings = self.params.get("vacuum", {})
        floor = float(settings.get("base_pressure_mbar", 1e-8))
        leak = float(settings.get("leak_rate_mbar_s", 2e-8))
        gas_gain = float(settings.get("gas_coupling_mbar_s_per_sccm", 2e-6))
        pump_tau = max(0.01, float(settings.get("pumping_tau_s", 10.0)))
        gas = sum(float(v) for k, v in context.metrics.items() if k.endswith(".flow_sccm"))
        pump_factor = 1 if self.pp_on or self.tp_on else 0
        derivative = leak + gas_gain * gas
        if pump_factor:
            derivative -= (self.pressure_mbar - floor) / pump_tau
        if context.device_faults.get("vacuum", False) or "VACUUM_LOSS" in context.faults:
            derivative += float(settings.get("fault_inrush_mbar_s", 1e-3))
        self.pressure_mbar = max(floor, self.pressure_mbar + dt * derivative)
        for suffix in ("VacSGVC", "VacPGVC", "VacSGTP", "VacPGTP"):
            name = self.catalog.pv(self.prefix, suffix)
            if name:
                context.emit(name, self.pressure_mbar, f"vacuum:{self.prefix}")
        name = self.catalog.pv(self.prefix, "SGVCDefStat")
        if name:
            limit = float(settings.get("vacuum_ok_threshold_mbar", 1e-5))
            context.emit(name, int(self.pressure_mbar <= limit), f"vacuum:{self.prefix}")
        context.metrics[f"{self.prefix}.pressure_mbar"] = self.pressure_mbar
