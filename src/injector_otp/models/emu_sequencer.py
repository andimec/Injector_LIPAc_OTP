"""EMU SNL v2 operational sequencer reimplemented as deterministic Python.

Source: topIFMIF_INJ/emitApp/src/emitSnlEmu_v2.st (Oct-2026 main).
Modes: wide voltage scan, upper/lower beam-edge detection and optimized
global-voltage-grid emittance measurement. This reproduces documented
setpoint sequencing and geometry, not real charged-particle trajectories.

The source can wait forever on PV events and uses unsafe ratio comparisons.
Here each wait is bounded, motor limits are checked before command, and
operator abort/pause is available in every active stage. Such safeguards are
documented training extensions, not claims about the deployed SNL.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import floor, isfinite

from .base import SubsystemModel
from .catalog import DeviceCatalog
from .emu_geometry import EmuGeometry, EmuROI, build_roi
from .emu_analysis import rms_emittance, samples_to_csv


class EmuMode(str, Enum):
    EMITTANCE = "EMITTANCE"
    WIDE = "WIDE"
    UPPER = "UPPER"
    LOWER = "LOWER"


class EmuStage(str, Enum):
    IDLE = "IDLE"
    WAIT_MOTOR_ENABLE = "WAIT_MOTOR_ENABLE"
    WAIT_PLATES_ENABLE = "WAIT_PLATES_ENABLE"
    WAIT_MOTOR = "WAIT_MOTOR"
    WAIT_PLATES = "WAIT_PLATES"
    WAIT_ACQUISITION = "WAIT_ACQUISITION"
    PAUSED = "PAUSED"
    COMPLETE = "COMPLETE"
    ABORTED = "ABORTED"


@dataclass(frozen=True)
class EmuTarget:
    motor_mm: float
    voltage_difference_V: float


@dataclass(frozen=True)
class EmuSample:
    t_s: float
    motor_mm: float
    voltage_set_V: float
    voltage_measured_V: float
    angle_rad: float
    current_mA: float
    mode: EmuMode


@dataclass(frozen=True)
class EmuSequenceSettings:
    motor_tolerance_mm: float = 0.01
    voltage_fraction_tolerance: float = 0.02
    voltage_absolute_tolerance_V: float = 2.0
    enable_timeout_s: float = 15.0
    motor_timeout_s: float = 30.0
    plate_timeout_s: float = 30.0
    acquisition_timeout_s: float = 10.0
    max_targets: int = 20000
    min_motor_limit_mm: float = -3.0
    max_motor_limit_mm: float = 182.0


class EmuScanSequencer(SubsystemModel):
    name = "emu_scan"

    ACTIONS = {
        EmuMode.EMITTANCE: "LEBT:EMIT:Actemit",
        EmuMode.WIDE: "LEBT:EMIT:Actscan",
        EmuMode.UPPER: "LEBT:EMIT:Actupper",
        EmuMode.LOWER: "LEBT:EMIT:Actlower",
    }

    def __init__(self, catalog: DeviceCatalog,
                 settings: EmuSequenceSettings | None = None) -> None:
        super().__init__()
        self.catalog = catalog
        self.settings = settings or EmuSequenceSettings()
        self.geometry = EmuGeometry()
        self.mode: EmuMode | None = None
        self.stage = EmuStage.IDLE
        self.resume_stage: EmuStage | None = None
        self.validated_roi: EmuROI | None = None
        self.targets: list[EmuTarget] = []
        self.samples: list[EmuSample] = []
        self.target_index = 0
        self.elapsed_s = 0.0
        self.previous_validate = False
        self.previous_actions = {mode: False for mode in EmuMode}
        self.last_sample_id = -1
        self._enable_requested = False
        self._supplies_requested = False
        self.message = ""

    def _num(self, context, suffix: str, default: float = 0.0) -> float:
        name = f"LEBT:EMIT:{suffix}"
        try:
            return float(context.pv.get(name, default))
        except (TypeError, ValueError):
            return default

    def _read(self, context, name: str, default: float = 0.0) -> float:
        try:
            return float(context.pv.get(name, default))
        except (TypeError, ValueError):
            return default

    def _input(self, context, name: str, value: object) -> None:
        if not self.catalog.has(name):
            raise ValueError(f"Missing EMU operator command in registry: {name}")
        context.request_command(name, value, "python:emu_scan")

    def _emit(self, context, name: str, value: object) -> None:
        if self.catalog.has(name):
            context.emit(name, value, "emu_scan")

    def _status(self, context, message: str) -> None:
        self.message = message
        name = "LEBT:EMIT:Emitext" if self.mode == EmuMode.EMITTANCE else "LEBT:EMIT:Scantext"
        self._emit(context, name, message)

    def _transition(self, stage: EmuStage) -> None:
        self.stage = stage
        self.elapsed_s = 0.0

    def _external_ok(self, context) -> bool:
        return (
            bool(context.pv.get("LEBT:EMIT:ExtSec", 0))
            and bool(context.pv.get("LEBT:EMIT:FSDefStat", 0))
            and not context.device_faults.get("emu", False)
        )

    def validate(self, context) -> EmuROI:
        roi = build_roi(
            energy_keV=self._num(context, "Energy"),
            angle_init_mrad=self._num(context, "AnglePicInit", -9999),
            angle_end_mrad=self._num(context, "AnglePicEnd", 9999),
            angle_delta_mrad=self._num(context, "AngleDelta"),
            border_up_mm=self._num(context, "Borderup"),
            border_low_mm=self._num(context, "Borderlow"),
            motor_step_mm=self._num(context, "Pasmotdet"),
            hv_points=int(self._num(context, "Nptemit")),
        )
        if not (self.settings.min_motor_limit_mm <= roi.motor_upper_mm
                < roi.motor_lower_mm <= self.settings.max_motor_limit_mm):
            raise ValueError("ROI motor trajectory exceeds configured soft travel")
        self.validated_roi = roi
        for name, v in {
            "Vpic": roi.vpic_init_V, "VpicEnd": roi.vpic_end_V,
            "Deltav": roi.delta_v_V, "Vstart": roi.start_voltage_V,
            "Vend": roi.end_voltage_V, "Vstep": roi.half_plate_step_V,
            "Upper": roi.motor_upper_mm, "Lower": roi.motor_lower_mm,
            "Mstep": roi.motor_step_mm,
        }.items():
            self._emit(context, "LEBT:EMIT:" + name, v)
        return roi

    def _positions(self, begin: float, end: float, step: float):
        if step == 0 or (end - begin) * step < 0:
            raise ValueError("Motor scan step must advance toward its limit")
        count = floor(abs(end - begin) / abs(step) + 1e-9)
        if count > self.settings.max_targets:
            raise ValueError("Too many motor steps requested")
        positions = [begin + i * step for i in range(count + 1)]
        # SNL can overshoot, but a training actuator must not silently exceed
        # requested scan limits. Include the endpoint when not on the grid.
        if abs(positions[-1] - end) > 1e-8:
            positions.append(end)
        return positions

    def _wide_voltages(self, context) -> list[float]:
        begin = self._num(context, "Debscanl")
        end = self._num(context, "Finscanl")
        step = self._num(context, "Passcanl")
        if not all(map(isfinite, (begin, end, step))) or step <= 0 or begin < end:
            raise ValueError("Wide scan needs start>=end and positive voltage step")
        n = floor((begin - end) / step + 1e-9)
        if n > self.settings.max_targets:
            raise ValueError("Wide scan point count exceeds safety limit")
        voltages = [begin - i * step for i in range(n + 1)]
        if abs(voltages[-1] - end) > 1e-8:
            voltages.append(end)
        # SNL sends (+V,-V) to the plates, so the difference is 2*V.
        return [2.0 * voltage for voltage in voltages]

    def _make_targets(self, context, mode: EmuMode) -> list[EmuTarget]:
        if mode == EmuMode.EMITTANCE:
            if self.validated_roi is None:
                raise ValueError("Validate ROI geometry before emittance scan")
            roi = self.validated_roi
            positions = self._positions(
                roi.motor_upper_mm, roi.motor_lower_mm, roi.motor_step_mm
            )
            rows = (
                EmuTarget(p, voltage)
                for p in positions
                for voltage in roi.snapped_voltages(p)
            )
        else:
            voltages = self._wide_voltages(context)
            if mode == EmuMode.WIDE:
                positions = [self._read(context, "LEBT:EMIT:MOTOR.RBV")]
            else:
                step = self._num(context, "Pasmotdet")
                limit = self._num(context, "Limdet")
                if step <= 0:
                    raise ValueError("Beam edge detection needs positive motor step")
                if mode == EmuMode.UPPER:
                    positions = self._positions(0.0, limit, step)[1:]
                else:
                    positions = self._positions(180.0, limit, -step)[1:]
            rows = (EmuTarget(p, v) for p in positions for v in voltages)

        targets = []
        for item in rows:
            if not (self.settings.min_motor_limit_mm <= item.motor_mm
                    <= self.settings.max_motor_limit_mm):
                raise ValueError("Motor target exceeds configured limits")
            if len(targets) >= self.settings.max_targets:
                raise ValueError("EMU requested target count exceeds maximum")
            targets.append(item)
        if not targets:
            raise ValueError("No valid scan points")
        return targets

    def _start(self, context, mode: EmuMode) -> None:
        if not self._external_ok(context):
            self.mode = mode
            self._abort(context, "EMU external safety is not available")
            return
        self.mode = mode
        self.samples = []
        self.target_index = 0
        self._enable_requested = False
        self._supplies_requested = False
        try:
            self.targets = self._make_targets(context, mode)
        except ValueError as exc:
            self._abort(context, str(exc))
            return
        self._transition(EmuStage.WAIT_MOTOR_ENABLE)
        self._status(context, f"{mode.value} starting, {len(self.targets)} points")

    def _abort(self, context, reason: str) -> None:
        self._transition(EmuStage.ABORTED)
        self._status(context, "ABORTED: " + reason)
        if self.mode is not None:
            self._input(context, self.ACTIONS[self.mode], 0)
        # This is an explicit training fail-closed improvement over original
        # STOP paths, which sometimes left plate voltages energized.
        for key in ("PS1", "PS2"):
            self._input(context, f"LEBT:EMIT_{key}:VSet", 0.0)
        # Hold position at the latest measured readback instead of leaving
        # an in-flight motor command running after a training abort.
        self._input(context, "LEBT:EMIT:MOTOR.VAL",
                    self._read(context, "LEBT:EMIT:MOTOR.RBV"))

    def _complete(self, context) -> None:
        self._transition(EmuStage.COMPLETE)
        self._status(context, f"COMPLETE: {len(self.samples)} measurement points")
        if self.mode is not None:
            self._input(context, self.ACTIONS[self.mode], 0)
        if self.mode == EmuMode.EMITTANCE:
            for key in ("PS1", "PS2"):
                self._input(context, f"LEBT:EMIT_{key}:VSet", 0.0)
            self._input(context, "LEBT:EMIT:MOTOR.VAL", 0.0)

    def _command_target(self, context) -> None:
        target = self.targets[self.target_index]
        if self.mode == EmuMode.EMITTANCE and self.validated_roi is not None:
            # SNL cmdMoteur updates the local ROI center for every motor row.
            roi = self.validated_roi
            vpic = roi.vpic_at(target.motor_mm)
            self._emit(context, "LEBT:EMIT:Vpic", vpic)
            self._emit(context, "LEBT:EMIT:Vstart", vpic + roi.delta_v_V / 2)
            self._emit(context, "LEBT:EMIT:Vend", vpic - roi.delta_v_V / 2)
        self._input(context, "LEBT:EMIT:MOTOR.VAL", target.motor_mm)
        self._input(context, "LEBT:EMIT_PS1:VSet", target.voltage_difference_V / 2)
        self._input(context, "LEBT:EMIT_PS2:VSet", -target.voltage_difference_V / 2)
        self._transition(EmuStage.WAIT_MOTOR)

    def _plates_reached(self, context) -> bool:
        target = self.targets[self.target_index].voltage_difference_V / 2
        a = self._read(context, "LEBT:EMIT_PS1:VRdbk")
        b = self._read(context, "LEBT:EMIT_PS2:VRdbk")
        tolerance = max(
            self.settings.voltage_absolute_tolerance_V,
            abs(target) * self.settings.voltage_fraction_tolerance,
        )
        return abs(a - target) <= tolerance and abs(b + target) <= tolerance

    def _motor_reached(self, context) -> bool:
        target = self.targets[self.target_index].motor_mm
        return (
            abs(self._read(context, "LEBT:EMIT:MOTOR.RBV") - target)
            <= self.settings.motor_tolerance_mm
            and self._read(context, "LEBT:EMIT:MOTOR.MOVN", 1) == 0
            and self._read(context, "LEBT:EMIT:MOTOR.DMOV", 0) == 1
        )

    def _sample(self, context) -> None:
        target = self.targets[self.target_index]
        readback = self._read(context, "LEBT:EMIT:VhtRdbk")
        energy = (self.validated_roi.energy_keV if self.validated_roi
                  else self._num(context, "Energy", 100))
        sample = EmuSample(
            t_s=context.time,
            motor_mm=self._read(context, "LEBT:EMIT:MOTOR.RBV"),
            voltage_set_V=target.voltage_difference_V,
            voltage_measured_V=readback,
            angle_rad=self.geometry.vht_to_angle_rad(
                target.voltage_difference_V, energy
            ),
            current_mA=self._read(context, "LEBT:EMIT_FC:I"),
            mode=self.mode,
        )
        self.samples.append(sample)
        self.target_index += 1
        if self.target_index >= len(self.targets):
            self._complete(context)
        else:
            self._command_target(context)

    def update(self, dt: float, context) -> None:
        super().update(dt)
        # Original emitProcess.db Nptscanl/Nptdet expressions:
        # (abs(Debscanl)+abs(Finscanl))/abs(step). These are legacy
        # OPI calculator outputs, not necessarily actual sample counts.
        begin = self._num(context, "Debscanl")
        end = self._num(context, "Finscanl")
        for step_key, out_key in (("Passcanl", "Nptscanl"),
                                  ("Pasald", "Nptdet")):
            delta = self._num(context, step_key)
            if delta != 0:
                self._emit(context, "LEBT:EMIT:" + out_key,
                           (abs(begin) + abs(end)) / abs(delta))
        validation = bool(context.pv.get("LEBT:EMIT:Validate", 0))
        if validation and not self.previous_validate:
            try:
                self.validate(context)
                self._status(context, "EMU ROI validated")
            except ValueError as exc:
                self.validated_roi = None
                self._status(context, "ROI validation failed: " + str(exc))
            self._input(context, "LEBT:EMIT:Validate", 0)
        self.previous_validate = validation

        edges = []
        for mode, action in self.ACTIONS.items():
            now = bool(context.pv.get(action, 0))
            if now and not self.previous_actions[mode]:
                edges.append(mode)
            self.previous_actions[mode] = now

        active = self.stage in {
            EmuStage.WAIT_MOTOR_ENABLE, EmuStage.WAIT_PLATES_ENABLE,
            EmuStage.WAIT_MOTOR, EmuStage.WAIT_PLATES,
            EmuStage.WAIT_ACQUISITION, EmuStage.PAUSED,
        }
        if active:
            if not self._external_ok(context):
                self._abort(context, "external safety lost")
            elif self.mode and not bool(context.pv.get(self.ACTIONS[self.mode], 0)):
                self._abort(context, "operator stop")
            elif context.device_faults.get("emu_motor", False) or context.device_faults.get("emu_plates", False):
                self._abort(context, "motor or plate power supply fault")
            elif edges and any(mode != self.mode for mode in edges):
                self._abort(context, "conflicting scan operation")
        elif edges:
            self._start(context, edges[0])

        if self.stage in {EmuStage.IDLE, EmuStage.COMPLETE, EmuStage.ABORTED}:
            self._metrics(context)
            return

        # Pause is a training extension available in all wait stages.
        paused = bool(context.pv.get("LEBT:EMIT:Pausemit", 0))
        if paused and self.stage != EmuStage.PAUSED:
            self.resume_stage = self.stage
            self._transition(EmuStage.PAUSED)
            self._status(context, "PAUSED")
        elif not paused and self.stage == EmuStage.PAUSED:
            self._transition(self.resume_stage or EmuStage.WAIT_ACQUISITION)
            self._status(context, "RESUMED")
        if self.stage == EmuStage.PAUSED:
            self._metrics(context)
            return

        self.elapsed_s += dt
        if self.stage == EmuStage.WAIT_MOTOR_ENABLE:
            if not self._enable_requested:
                self._input(context, "LEBT:EMIT:Actenable", 1)
                self._enable_requested = True
            motor = str(context.pv.get("LEBT:EMIT:MOTOR.CNEN", "")).lower()
            servo = bool(context.pv.get("LEBT:EMIT_SERV:EnaDisa", 0))
            if motor == "enable" and servo:
                self._transition(EmuStage.WAIT_PLATES_ENABLE)
            elif self.elapsed_s > self.settings.enable_timeout_s:
                self._abort(context, "motor enable timeout")

        elif self.stage == EmuStage.WAIT_PLATES_ENABLE:
            if not self._supplies_requested:
                for key in ("PS1", "PS2"):
                    self._input(context, f"LEBT:EMIT_{key}:Softbo", 1)
                self._supplies_requested = True
            elif all(self._read(context, f"LEBT:EMIT_{key}:OnOffCmd.RVAL") == 1
                     for key in ("PS1", "PS2")):
                self._command_target(context)
            elif self.elapsed_s > self.settings.enable_timeout_s:
                self._abort(context, "plate supply ON timeout")

        elif self.stage == EmuStage.WAIT_MOTOR:
            if self._motor_reached(context):
                self._transition(EmuStage.WAIT_PLATES)
            elif self.elapsed_s > self.settings.motor_timeout_s:
                self._abort(context, "motor movement timeout or limit violation")

        elif self.stage == EmuStage.WAIT_PLATES:
            if self._plates_reached(context):
                self.last_sample_id = int(context.metrics.get("emu.facq_sample_id", -1))
                self._transition(EmuStage.WAIT_ACQUISITION)
            elif self.elapsed_s > self.settings.plate_timeout_s:
                self._abort(context, "plate voltage readback timeout")

        elif self.stage == EmuStage.WAIT_ACQUISITION:
            sample_id = int(context.metrics.get("emu.facq_sample_id", -1))
            if sample_id >= 0 and sample_id != self.last_sample_id:
                self.last_sample_id = sample_id
                self._sample(context)
            elif self.elapsed_s > self.settings.acquisition_timeout_s:
                self._abort(context, "no new FACQ sample event")

        self._metrics(context)

    def results_csv(self) -> str:
        """Return source-column EMU scan points, with no disk side effects."""
        return samples_to_csv(self.samples)

    def preliminary_emittance(self):
        """Uncorrected current-weighted RMS/Twiss, not a certified result."""
        if self.mode != EmuMode.EMITTANCE:
            raise ValueError("RMS emittance needs an emittance scan")
        return rms_emittance(self.samples)

    def _metrics(self, context) -> None:
        context.metrics["emu.scan_active"] = float(self.stage not in (
            EmuStage.IDLE, EmuStage.COMPLETE, EmuStage.ABORTED))
        context.metrics["emu.scan_points_done"] = float(len(self.samples))
        context.metrics["emu.scan_points_total"] = float(len(self.targets))
        context.metrics["emu.scan_aborted"] = float(self.stage == EmuStage.ABORTED)
        context.metrics["emu.scan_complete"] = float(self.stage == EmuStage.COMPLETE)
