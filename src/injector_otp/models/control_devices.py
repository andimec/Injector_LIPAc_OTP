"""First executable models of RF, chopper, timing and diagnostics.

All numerical relationships below are intentionally low-fidelity OTP
hypotheses. Detailed hardware behaviour requires calibration/validation.
"""
from __future__ import annotations

from math import exp, sqrt

from .base import SubsystemModel
from .catalog import DeviceCatalog


class RFSystemModel(SubsystemModel):
    name = "rf"

    def __init__(self, catalog: DeviceCatalog, parameters: dict) -> None:
        super().__init__()
        self.catalog = catalog
        self.parameters = parameters
        self.filament_warm_s = 0.0
        self.forward_W = 0.0
        self._on = False

    def read(self, context, suffix: str) -> float:
        pv = self.catalog.pv("SRC:RF_GENE", suffix)
        try:
            return float(context.pv.get(pv, 0) or 0) if pv else 0.0
        except (ValueError, TypeError):
            return 0.0

    def emit(self, context, value, suffix: str):
        pv = self.catalog.pv("SRC:RF_GENE", suffix)
        if pv:
            context.emit(pv, value, "rf_system")

    def update(self, dt: float, context) -> None:
        super().update(dt)
        p = self.parameters.get("rf", {})
        filament = bool(self.read(context, "FilOnCmd"))
        self.filament_warm_s = (
            self.filament_warm_s + dt if filament else 0.0
        )
        ready = self.filament_warm_s >= float(p.get("warmup_s", 4.0))
        permit = bool(
            context.interlocks.get("RF:PLASMA:ENABLE", False)
            or context.interlocks.get("RF:BEAM:ENABLE", False)
        )
        fault = bool(context.device_faults.get("rf", False))
        if "RF_FAILURE" in context.faults:
            fault = True
        self._on = bool(self.read(context, "MOCmdOn")) and ready and permit and not fault
        request = max(0.0, self.read(context, "RfPwr") + self.read(context, "RfOffset"))
        tau = max(0.001, float(p.get("power_tau_s", 0.5)))
        self.forward_W += ((request if self._on else 0.0) - self.forward_W) * (
            1.0 - exp(-dt / tau)
        )
        self.forward_W = max(0.0, self.forward_W)

        x_pv = self.catalog.pv("SRC:RF_ATU", "WrtX")
        y_pv = self.catalog.pv("SRC:RF_ATU", "WrtY")
        x = float(context.pv.get(x_pv, 0) or 0) if x_pv else 0.0
        y = float(context.pv.get(y_pv, 0) or 0) if y_pv else 0.0
        x_ref = float(p.get("reference_stub_x", 1860))
        y_ref = float(p.get("reference_stub_y", 2756))
        mismatch = ((x - x_ref) ** 2 + (y - y_ref) ** 2) ** 0.5
        reflect_fraction = min(
            0.95, float(p.get("minimum_reflection_fraction", 0.02)) + mismatch / 8000.0
        )
        reflected = self.forward_W * reflect_fraction
        self.emit(context, int(ready), "PretRF")
        self.emit(context, int(self._on), "MarcheRF")
        self.emit(context, int(fault), "DefRF")
        self.emit(context, reflected, "PwrRef")
        context.metrics["rf.forward_W"] = self.forward_W
        context.metrics["rf.reflected_W"] = reflected
        context.metrics["rf.ready"] = float(ready)
        context.metrics["rf.on"] = float(self._on)


class PositionerModel(SubsystemModel):
    """Simple inserted/removed actuators: FC, chopper, beam stop, etc."""

    def __init__(self, prefix: str, catalog: DeviceCatalog, *, inserted: bool = False) -> None:
        super().__init__()
        self.name = prefix
        self.prefix = prefix
        self.catalog = catalog
        self.inserted = inserted
        self._previous = {}

    def _edge(self, context, suffix: str) -> bool:
        pv = self.catalog.pv(self.prefix, suffix)
        if pv is None:
            return False
        current = bool(context.pv.get(pv, 0))
        old = self._previous.get(pv, False)
        self._previous[pv] = current
        return current and not old

    def update(self, dt: float, context) -> None:
        super().update(dt)
        if self._edge(context, "InCmd"):
            self.inserted = True
        if self._edge(context, "OutCmd"):
            self.inserted = False
        for suffix, state in (("InStat", self.inserted), ("OutStat", not self.inserted)):
            name = self.catalog.pv(self.prefix, suffix)
            if name:
                context.emit(name, int(state), f"positioner:{self.prefix}")
        context.metrics[f"{self.prefix}.inserted"] = float(self.inserted)


class ChopperFBIModel(SubsystemModel):
    """Fast Beam Inhibit observable, without inventing the cRIO firmware."""

    name = "chopper_im"

    def __init__(self, catalog: DeviceCatalog) -> None:
        super().__init__()
        self.catalog = catalog
        self.latched = False

    def update(self, dt: float, context) -> None:
        super().update(dt)
        # Threshold algorithms and clear/acknowledge semantics depend on the
        # actual cRIO specification. Only explicit fault injection is modelled.
        if ("FBI_TRIGGER" in context.faults
                or context.device_faults.get("chopper", False)):
            self.latched = True
        if self.latched:
            name = "LEBT:CHOP_IM:Fbi"
            if self.catalog.has(name):
                context.emit(name, 1, "chopper_fbi")
        context.metrics["chopper.fbi"] = float(self.latched)


class TimingSystemModel(SubsystemModel):
    name = "timing"

    def __init__(self, catalog: DeviceCatalog) -> None:
        super().__init__()
        self.catalog = catalog

    def update(self, dt: float, context) -> None:
        super().update(dt)
        period_pv = "SRC:TIM:Trep"
        pulse_pv = "SRC:TIM:TPulse"
        period_ms = float(context.pv.get(period_pv, 0) or 0)
        width_ms = float(context.pv.get(pulse_pv, 0) or 0)
        is_cw = bool(context.pv.get("SRC:TIM:Mode", 0))
        duty = 1.0 if is_cw else (
            min(1.0, max(0.0, width_ms / period_ms)) if period_ms > 0 else 0.0
        )
        if self.catalog.has("SRC:TIM:DutyCycle"):
            context.emit("SRC:TIM:DutyCycle", duty * 100, "timing")
        context.metrics["timing.duty_cycle"] = duty


class BeamTransportModel(SubsystemModel):
    """Qualitative, bounded beam observable for OPI acceptance testing.

    This does not simulate meniscus formation or beam optics. It must not be
    used to predict a real source current, emittance or transmission.
    """

    name = "beam"

    def __init__(self, catalog: DeviceCatalog, parameters: dict) -> None:
        super().__init__()
        self.catalog = catalog
        self.parameters = parameters

    def update(self, dt: float, context) -> None:
        super().update(dt)
        settings = self.parameters.get("beam", {})
        nominal = float(settings.get("nominal_faraday_current_mA", 145.0))
        power = context.metrics.get("rf.forward_W", 0.0)
        gas = context.metrics.get("SRC:MFCD.flow_sccm", 0.0)
        voltage = context.metrics.get("LEBT:HV_PS.voltage", 0.0)
        enabled = bool(context.interlocks.get("BEAM:ENABLE", False))
        rf_on = bool(context.metrics.get("rf.on", False))
        beam_exists = enabled and rf_on and power > 0 and gas > 0 and voltage > 0
        scale = (
            min(1.2, sqrt(power / max(1.0, float(settings.get("reference_rf_W", 880.0)))))
            * min(1.2, gas / max(0.001, float(settings.get("reference_d2_sccm", 2.3))))
            * min(1.0, voltage / max(1.0, float(settings.get("reference_hv_kV", 100.0))))
        )
        current = nominal * scale if beam_exists else 0.0
        duty = context.metrics.get("timing.duty_cycle", 0.0)
        faraday_inserted = bool(context.metrics.get("LEBT:FC.inserted", False))
        value = current * duty if faraday_inserted else 0.0
        if self.catalog.has("LEBT:FC:I"):
            context.emit("LEBT:FC:I", value, "beam_qualitative")
        context.metrics["beam.current_mA"] = current
        context.metrics["beam.fc_current_mA"] = value


class InterfaceOnlyModel(SubsystemModel):
    """Explicit placeholder for hardware requiring a validated physical law.

    It is present in the model inventory but deliberately does not write PVs.
    It allows the OTP to cover the complete equipment taxonomy without
    fabricating telemetry or protection states.
    """

    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name

    def update(self, dt: float, context) -> None:
        super().update(dt)
