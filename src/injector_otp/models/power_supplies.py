"""Reduced-order power-supply dynamics for the LIPAc Injector OTP.

These models reproduce command/feedback causality and EPICS engineering limits.
They are NOT calibrated representations of power electronics or extraction
physics. Hardware safety and authoritative protection logic are external.
"""
from __future__ import annotations

from dataclasses import dataclass

from .base import SubsystemModel
from .catalog import DeviceCatalog


POWER_SUPPLY_PREFIXES = (
    "SRC:COIL01_PS", "SRC:COIL02_PS",
    "LEBT:SOL01_PS", "LEBT:SOL02_PS",
    "LEBT:STV01_PS", "LEBT:STV02_PS",
    "LEBT:STH01_PS", "LEBT:STH02_PS",
    "SRC:IE_PS", "LEBT:R_PS", "LEBT:RC_PS",
    "LEBT:HV_PS",
)


@dataclass
class SupplyState:
    powered: bool = False
    auxiliary: bool = False
    ready: bool = True
    fault_latched: bool = False
    current_A: float = 0.0
    voltage: float = 0.0


def _advance(value: float, target: float, rate: float, dt: float) -> float:
    amount = max(0.0, rate) * dt
    if target > value:
        return min(target, value + amount)
    return max(target, value - amount)


class PowerSupplyDevice(SubsystemModel):
    """One physical PS with ON/OFF commands, ramp and independent readbacks.

    The DB's DRVH/DRVL and the configured training slew rate are respected.
    Real hardware transfer functions, alarm delays and calibration factors
    remain pending experimental verification.
    """

    def __init__(self, prefix: str, catalog: DeviceCatalog, parameters: dict) -> None:
        super().__init__()
        self.name = prefix
        self.prefix = prefix
        self.catalog = catalog
        self.parameters = parameters
        self.supply = SupplyState()
        self._last_cmds: dict[str, bool] = {}

    def _pv(self, *suffixes: str) -> str | None:
        return self.catalog.pv(self.prefix, *suffixes)

    def _read(self, context, *suffixes: str) -> float:
        name = self._pv(*suffixes)
        try:
            return float(context.pv.get(name, 0)) if name else 0.0
        except (TypeError, ValueError):
            return 0.0

    def _edge(self, context, *suffixes: str) -> bool:
        activated = False
        for suffix in suffixes:
            name = self._pv(suffix)
            if name is None:
                continue
            value = bool(context.pv.get(name, False))
            if value and not self._last_cmds.get(name, False):
                activated = True
            self._last_cmds[name] = value
        return activated

    def _emit(self, context, value, *suffixes: str) -> None:
        name = self._pv(*suffixes)
        if name is not None:
            context.emit(name, value, f"power_supply:{self.prefix}")

    def _fault_key(self) -> str:
        if "COIL01" in self.prefix:
            return "coil1"
        if "COIL02" in self.prefix:
            return "coil2"
        if self.prefix == "LEBT:HV_PS":
            return "hv"
        if self.prefix == "SRC:IE_PS":
            return "ie"
        if self.prefix == "LEBT:R_PS":
            return "repeller"
        return self.prefix

    def _permission(self, context) -> bool:
        if self.prefix == "LEBT:HV_PS":
            return context.interlocks.get("HV:ENABLE", False)
        if self.prefix == "SRC:IE_PS":
            return context.interlocks.get("IE:ENABLE", False)
        return context.interlocks.get("COOLING:READY", False)

    def _rate(self, quantity: str) -> float:
        by_device = self.parameters.get("supplies", {}).get(self.prefix, {})
        if quantity == "current":
            default = 1.0 if "COIL" in self.prefix else (
                2.0 if "SOL" in self.prefix else 10.0
            )
            return float(by_device.get("current_rate_per_s", default))
        return float(by_device.get("voltage_rate_per_s", 1.0))

    def update(self, dt: float, context) -> None:
        super().update(dt)
        s = self.supply
        fault = bool(context.device_faults.get(self._fault_key(), False))
        if "MAGNET_DRIFT" in context.faults and self.prefix.startswith("SRC:COIL"):
            drift = 0.05
        else:
            drift = 0.0
        if fault:
            s.fault_latched = True
        if self._edge(context, "RESET", "RstCmd", "Reset"):
            if not fault:
                s.fault_latched = False
                s.ready = True

        if self._edge(context, "AuxOnCmd"):
            s.auxiliary = True
        if self._edge(context, "AuxOffCmd"):
            s.auxiliary = False
            s.powered = False
        if self._edge(context, "OFF", "OffCmd", "HTOffCmd"):
            s.powered = False

        permit = self._permission(context)
        if self._edge(context, "ON", "OnCmd", "HTOnCmd"):
            hv_aux_ok = self.prefix != "LEBT:HV_PS" or s.auxiliary
            if permit and hv_aux_ok and not s.fault_latched:
                s.powered = True

        if s.fault_latched or not permit:
            s.powered = False

        current_pv = self._pv("ISet")
        voltage_pv = self._pv("VSet", "HTCmd")
        requested_current = self._read(context, "ISet")
        requested_voltage = self._read(context, "VSet", "HTCmd")
        if current_pv:
            requested_current = self.catalog.clamp(current_pv, requested_current)
        if voltage_pv:
            requested_voltage = self.catalog.clamp(voltage_pv, requested_voltage)

        # A positive Rampe value is used as the user-selected slew rate.
        manual_rate = self._read(context, "Rampe")
        irate = manual_rate if manual_rate > 0 else self._rate("current")
        vrate = self._rate("voltage")
        s.current_A = _advance(
            s.current_A, requested_current if s.powered else 0.0, irate, dt
        )
        s.voltage = _advance(
            s.voltage, requested_voltage if s.powered else 0.0, vrate, dt
        )

        s.ready = not s.fault_latched
        self._emit(context, int(s.powered), "OnStat")
        self._emit(context, int(s.ready), "RdyStat")
        self._emit(context, int(s.auxiliary), "AuxStat")

        feedback_current = s.current_A * (1 - drift)
        for suffix in ("IRdbk", "IRdbkcalc"):
            self._emit(context, feedback_current, suffix)
        for suffix in ("VRdbk", "VRdbkcalc"):
            self._emit(context, s.voltage, suffix)
        if self.prefix == "LEBT:HV_PS":
            self._emit(context, s.voltage, "ScaleVHT")
            # LectVht is device-specific raw readback and requires calibration;
            # it is not silently overwritten with a fabricated raw value.
        context.metrics[f"{self.prefix}.powered"] = float(s.powered)
        context.metrics[f"{self.prefix}.current_A"] = s.current_A
        context.metrics[f"{self.prefix}.voltage"] = s.voltage
