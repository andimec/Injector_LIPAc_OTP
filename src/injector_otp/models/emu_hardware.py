"""EMU actuator models, owned exclusively by the Python simulation.

Source: topIFMIF_INJ/emitApp/src/emitSnlMotor.st, emitSnlAlims.st,
emitApp/db/emitMotor.db and ICV196/150/714 template records.

No hardware network link, CA/PVA client, motor record processing, or
undocumented PLC/FACQ protection is implemented here.
"""
from __future__ import annotations

from dataclasses import dataclass

from .base import SubsystemModel
from .catalog import DeviceCatalog
from .emu_geometry import EmuGeometry
from .emu_beam import SyntheticPhaseSpace


def _bool(value: object) -> bool:
    return str(value).lower() in {"1", "true", "enable", "enabled", "on", "go"}


def _float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _approach(actual: float, requested: float, rate: float, dt: float) -> float:
    distance = max(0.0, rate * dt)
    if requested > actual:
        return min(requested, actual + distance)
    return max(requested, actual - distance)


class EmuMotorSupervisor(SubsystemModel):
    """Translate 2012 SNL MaxV/servo 1-second stage sequence into Python.

    Original script defines ExtSec but does not check it in its transitions.
    This simulator explicitly requires that external input to be healthy
    before enabling the motor. That is a conservative simulation safety rule,
    NOT an assertion about the deployed safety PLC.
    """

    name = "emu_motor_supervisor"

    def __init__(self, catalog: DeviceCatalog, stage_delay_s: float = 1.0) -> None:
        super().__init__()
        self.catalog = catalog
        self.stage_delay_s = stage_delay_s
        self.phase = "IDLE"
        self.elapsed_s = 0.0
        self._previous_enable = False
        self._previous_disable = False

    def _request(self, context, name: str, value: object) -> None:
        if self.catalog.has(name):
            context.request_command(name, value, "python:emu_motor_supervisor")

    def update(self, dt: float, context) -> None:
        super().update(dt)
        enable = _bool(context.pv.get("LEBT:EMIT:Actenable", 0))
        disable = _bool(context.pv.get("LEBT:EMIT:Actdisable", 0))
        enable_edge = enable and not self._previous_enable
        disable_edge = disable and not self._previous_disable
        self._previous_enable, self._previous_disable = enable, disable

        healthy = _bool(context.pv.get("LEBT:EMIT:ExtSec", 0)) and _bool(
            context.pv.get("LEBT:EMIT:FSDefStat", 0)
        ) and not context.device_faults.get("emu", False)
        if (disable_edge or not healthy) and self.phase not in (
            "DISABLE_SERVO", "DISABLE_REFRESH", "DISABLE_MAXV"
        ):
            if self.phase != "IDLE" or _bool(context.pv.get("LEBT:EMIT:MOTOR.CNEN")):
                self.phase = "DISABLE_SERVO"
                self.elapsed_s = 0.0
        elif enable_edge and self.phase == "IDLE" and healthy:
            self.phase = "ENABLE_MAXV"
            self.elapsed_s = 0.0

        if self.phase == "IDLE":
            return
        self.elapsed_s += dt
        if self.elapsed_s < self.stage_delay_s:
            return
        self.elapsed_s = 0.0
        if self.phase == "ENABLE_MAXV":
            self._request(context, "LEBT:EMIT:MOTOR.CNEN", "Enable")
            self.phase = "ENABLE_SERVO"
        elif self.phase == "ENABLE_SERVO":
            self._request(context, "LEBT:EMIT_SERV:EnaDisa", 1)
            self.phase = "ENABLE_REFRESH"
        elif self.phase == "ENABLE_REFRESH":
            self._request(context, "LEBT:EMIT_SERV:Refresh", 1)
            self._request(context, "LEBT:EMIT:Actenable", 0)
            self.phase = "IDLE"
        elif self.phase == "DISABLE_SERVO":
            self._request(context, "LEBT:EMIT_SERV:EnaDisa", 0)
            self.phase = "DISABLE_REFRESH"
        elif self.phase == "DISABLE_REFRESH":
            self._request(context, "LEBT:EMIT_SERV:Refresh", 1)
            self.phase = "DISABLE_MAXV"
        elif self.phase == "DISABLE_MAXV":
            self._request(context, "LEBT:EMIT:MOTOR.CNEN", "Disable")
            self._request(context, "LEBT:EMIT:Actdisable", 0)
            self.phase = "IDLE"


class EmuMotorModel(SubsystemModel):
    """Servo motor with physical travel, in-position confirmation and limits."""

    name = "emu_motor"

    def __init__(self, catalog: DeviceCatalog, params: dict | None = None) -> None:
        super().__init__()
        self.catalog = catalog
        p = params or {}
        self.position_mm = float(p.get("initial_position_mm", 0.0))
        self.target_mm = self.position_mm
        # Movement speed and home are TRAINING hypotheses, not MAXv VELO raw.
        self.rate_mm_s = float(p.get("rate_mm_s", 20.0))
        self.tolerance_mm = float(p.get("position_tolerance_mm", 0.01))
        self.lower_limit_mm = float(p.get("lower_limit_mm", -3.0))
        self.upper_limit_mm = float(p.get("upper_limit_mm", 182.0))
        self._last_home = False
        self.limit_violation = False
        self.enabled = False

    def _emit(self, context, suffix: str, value: object) -> None:
        key = "LEBT:EMIT:MOTOR." + suffix
        if self.catalog.has(key):
            context.emit(key, value, "emu_motor")

    def update(self, dt: float, context) -> None:
        super().update(dt)
        p = context.pv
        self.enabled = _bool(p.get("LEBT:EMIT:MOTOR.CNEN", "Disable")) and _bool(
            p.get("LEBT:EMIT_SERV:EnaDisa", 0)
        ) and _bool(p.get("LEBT:EMIT:ExtSec", 0)) and _bool(
            p.get("LEBT:EMIT:FSDefStat", 0)
        ) and not context.device_faults.get("emu_motor", False)

        home = _bool(p.get("LEBT:EMIT:MOTOR.HOMR", 0))
        if home and not self._last_home:
            self.target_mm = 0.0
        self._last_home = home

        setpoint = _float(p.get("LEBT:EMIT:MOTOR.VAL", self.target_mm), self.target_mm)
        if not home:
            self.target_mm = setpoint
        self.limit_violation = not self.lower_limit_mm <= self.target_mm <= self.upper_limit_mm
        mode = str(p.get("LEBT:EMIT:MOTOR.SPMG", "Go")).lower()
        move_allowed = mode in {"go", "3", ""} and self.enabled and not self.limit_violation
        if move_allowed:
            self.position_mm = _approach(self.position_mm, self.target_mm,
                                          self.rate_mm_s, dt)
        done = abs(self.position_mm - self.target_mm) <= self.tolerance_mm
        moving = move_allowed and not done

        self._emit(context, "RBV", self.position_mm)
        self._emit(context, "MOVN", int(moving))
        self._emit(context, "DMOV", int(done and not self.limit_violation))
        self._emit(context, "ATHM", int(abs(self.position_mm) <= self.tolerance_mm))
        self._emit(context, "HLS", int(self.position_mm >= self.upper_limit_mm))
        self._emit(context, "LLS", int(self.position_mm <= self.lower_limit_mm))
        self._emit(context, "LVIO", int(self.limit_violation))
        # emitMotor.db calculates Position=-MOTOR.RBV, not the same sign.
        if self.catalog.has("LEBT:EMIT:Position"):
            context.emit("LEBT:EMIT:Position", -self.position_mm, "emu_motor")
        if self.catalog.has("LEBT:EMIT:HARD_LIM_VIO"):
            context.emit("LEBT:EMIT:HARD_LIM_VIO",
                         int(self.position_mm <= self.lower_limit_mm
                             or self.position_mm >= self.upper_limit_mm),
                         "emu_motor")
        if self.catalog.has("LEBT:EMIT:SOFT_LIM_VIO"):
            context.emit("LEBT:EMIT:SOFT_LIM_VIO",
                         int(self.limit_violation), "emu_motor")
        context.metrics["emu.motor_position_mm"] = self.position_mm
        context.metrics["emu.motor_moving"] = float(moving)
        context.metrics["emu.motor_done"] = float(done and not self.limit_violation)
        context.metrics["emu.motor_ready"] = float(self.enabled)


@dataclass
class EmuPlatePSState:
    on: bool = False
    voltage_V: float = 0.0
    elapsed_s: float = 0.0


class EmuPlatePSModel(SubsystemModel):
    """Two ICV196 switched PS and ICV714 setpoint / ICV150 readback pairs."""

    name = "emu_plates"

    def __init__(self, catalog: DeviceCatalog, params: dict | None = None) -> None:
        super().__init__()
        self.catalog = catalog
        p = params or {}
        self.rate_V_s = float(p.get("plate_rate_V_s", 10000.0))
        self.turn_on_delay_s = float(p.get("turn_on_delay_s", 0.0))
        self.supplies = {"PS1": EmuPlatePSState(), "PS2": EmuPlatePSState()}

    def _emit(self, context, name: str, value: object) -> None:
        if self.catalog.has(name):
            context.emit(name, value, "emu_plates")

    def update(self, dt: float, context) -> None:
        super().update(dt)
        for key, supply in self.supplies.items():
            prefix = f"LEBT:EMIT_{key}:"
            requested_on = _bool(context.pv.get(prefix + "Softbo", 0))
            if requested_on:
                supply.elapsed_s += dt
                supply.on = supply.elapsed_s >= self.turn_on_delay_s
            else:
                supply.elapsed_s = 0.0
                supply.on = False
            command = _float(context.pv.get(prefix + "VSet", 0))
            if context.device_faults.get("emu_plates", False):
                supply.on = False
            self._emit(context, prefix + "OnOffCmd", int(supply.on))
            self._emit(context, prefix + "OnOffCmd.RVAL", int(supply.on))
            self._emit(context, prefix + "Calcdly.ODLY", 0.0 if supply.on else 30.0)
            supply.voltage_V = _approach(
                supply.voltage_V, command if supply.on else 0.0, self.rate_V_s, dt
            )
            self._emit(context, prefix + "VRdbk", supply.voltage_V)
            context.metrics[f"emu.{key}.on"] = float(supply.on)
            context.metrics[f"emu.{key}.V"] = supply.voltage_V
        difference = self.supplies["PS1"].voltage_V - self.supplies["PS2"].voltage_V
        if self.catalog.has("LEBT:EMIT:VhtRdbk"):
            context.emit("LEBT:EMIT:VhtRdbk", difference, "emu_plates")
        context.metrics["emu.VhtRdbk"] = difference


class EmuAcquisitionModel(SubsystemModel):
    """Deliberately synthetic scalar trigger to drive operator training.

    This is NOT a model of the fast acquisition waveform, FPGA, or actual
    emittance distribution. A future FACQ adapter should replace this model.
    """

    name = "emu_facq"

    def __init__(self, catalog: DeviceCatalog, params: dict | None = None):
        super().__init__()
        self.catalog = catalog
        p = params or {}
        self.period_s = max(0.001, float(p.get("synthetic_period_s", 0.1)))
        self.synthetic_enabled = bool(p.get("synthetic_enabled", True))
        fixture = p.get("synthetic_phase_space", {})
        self.fixture_enabled = bool(fixture.get("enabled", False))
        self.fixture = SyntheticPhaseSpace(**{
            k: v for k, v in fixture.items() if k != "enabled"
        }) if self.fixture_enabled else None
        self.geometry = EmuGeometry()
        self.elapsed_s = 0.0
        self.number = 0

    def update(self, dt: float, context) -> None:
        super().update(dt)
        if not self.synthetic_enabled:
            return
        self.elapsed_s += dt
        if self.elapsed_s + 1e-10 < self.period_s:
            return
        self.elapsed_s = 0.0
        self.number += 1
        # A scenario may inject real-like samples via the local PV adapter;
        # the optional Gaussian fixture is *explicitly synthetic* and off by
        # default. A future live acquisition adapter will publish true events.
        current = _float(context.pv.get("LEBT:EMIT_FC:I", 0))
        if self.fixture is not None:
            motor = float(context.metrics.get("emu.motor_position_mm", 0))
            vht = float(context.metrics.get("emu.VhtRdbk", 0))
            energy = _float(context.pv.get("LEBT:EMIT:Energy", 100), 100)
            angle_mrad = self.geometry.vht_to_angle_rad(vht, energy) * 1000
            current = self.fixture.current_mA(motor, angle_mrad)
        if self.catalog.has("LEBT:EMIT_FC:I"):
            context.emit(
                "LEBT:EMIT_FC:I", current,
                "emu_facq_uncalibrated_gaussian" if self.fixture is not None
                else "emu_facq_synthetic_clock",
            )
        context.metrics["emu.facq_sample_id"] = float(self.number)
