"""Python-owned HV/IE/Repeller automatic ramp for the LIPAc training simulator.

Documented basis:
- Injector LCS User Manual v4.0, section 3.5.4: verify supplies ON,
  initialize HV/IE to 1 kV, verify each step within +/-1%, ramp repeller
  from 0.1 to 4.5 kV, and abort on failure.
- BA_D_2E9QH7 v2.0 (July 2026), steps 8--18: ordered HV/IE
  setpoint table (1/1, 10/5, 20/10, 30/15, 40/20, 50/25, 100/25);
  1 kV steps at one-second rate, then repeller 0.1 kV steps to 4.5 kV.

Undocumented actuator settling, retry and repeller dwell are explicit
simulation parameters. This is a training sequence, NOT a physical safety
controller and it never drives EPICS hardware directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .base import SubsystemModel
from .catalog import DeviceCatalog


class RampPhase(str, Enum):
    IDLE = "IDLE"
    HV_IE = "HV_IE"
    REPELLER = "REPELLER"
    COMPLETE = "COMPLETE"
    ABORTED = "ABORTED"


@dataclass(frozen=True)
class HVRampSettings:
    hv_ie_profile_kV: tuple[tuple[float, float], ...] = (
        (1.0, 1.0), (10.0, 5.0), (20.0, 10.0), (30.0, 15.0),
        (40.0, 20.0), (50.0, 25.0), (100.0, 25.0),
    )
    hv_step_kV: float = 1.0
    ie_step_kV: float = 1.0
    repeller_step_kV: float = 0.1
    repeller_final_kV: float = 4.5
    hv_ie_step_interval_s: float = 1.0
    # Source procedure does not specify the repeller time between steps.
    repeller_step_interval_s: float = 1.0
    feedback_tolerance_fraction: float = 0.01
    feedback_timeout_s: float = 20.0


class HVAutoRampModel(SubsystemModel):
    """A testable sequence of HV setpoints, enforced in Python with PV ACLs."""

    name = "hv_auto_ramp"
    ACTIVE = frozenset({RampPhase.HV_IE, RampPhase.REPELLER})
    COMMAND = {
        "HV": "LEBT:HV_PS:HTCmd",
        "IE": "SRC:IE_PS:VSet",
        "R": "LEBT:R_PS:VSet",
    }
    READBACK = {
        "HV": "LEBT:HV_PS:ScaleVHT",
        "IE": "SRC:IE_PS:VRdbkcalc",
        "R": "LEBT:R_PS:VRdbkcalc",
    }
    STATUS = {
        "HV": "LEBT:HV_PS:OnStat",
        "IE": "SRC:IE_PS:OnStat",
        "R": "LEBT:R_PS:OnStat",
    }

    def __init__(self, catalog: DeviceCatalog, settings: HVRampSettings | None = None):
        super().__init__()
        self.catalog = catalog
        self.settings = settings or HVRampSettings()
        self.phase = RampPhase.IDLE
        self.profile_index = 0
        self.target = {"HV": 0.0, "IE": 0.0, "R": 0.0}
        self.wait_elapsed_s = 0.0
        self.step_elapsed_s = 0.0
        self._previous_start = False
        self._previous_stop = False
        self.reason = ""

    def _edge(self, context, name: str, prior: str) -> bool:
        current = bool(context.pv.get(name, 0))
        old = getattr(self, prior)
        setattr(self, prior, current)
        return current and not old

    def _say(self, context, text: str) -> None:
        self.reason = text
        pv = "LEBT:AUTO:Dialog"
        if self.catalog.has(pv):
            context.emit(pv, text, "hv_auto_ramp")

    def _set_target(self, context, device: str, value: float) -> None:
        self.target[device] = round(value, 6)
        name = self.COMMAND[device]
        if not self.catalog.has(name):
            raise ValueError(f"Missing ramp control PV in catalog: {name}")
        context.request_command(name, self.target[device], "python:hv_auto_ramp")

    def _ready(self, context, device: str) -> bool:
        if self.READBACK[device] not in context.pv:
            return False
        actual = float(context.pv[self.READBACK[device]])
        target = self.target[device]
        return abs(actual - target) <= abs(target) * self.settings.feedback_tolerance_fraction

    def _all_ready(self, context, devices: tuple[str, ...]) -> bool:
        return all(self._ready(context, dev) for dev in devices)

    def _aborted(self, context, reason: str) -> None:
        self.phase = RampPhase.ABORTED
        self._say(context, "HV auto ramp ABORTED: " + reason)

    def _can_start(self, context) -> bool:
        # A real automatic ramp must not switch equipment on implicitly.
        return (
            all(bool(context.pv.get(pv, False)) for pv in self.STATUS.values())
            and bool(context.interlocks.get("HV:ENABLE", False))
            and bool(context.interlocks.get("IE:ENABLE", False))
        )

    def update(self, dt: float, context) -> None:
        super().update(dt)
        stopped = self._edge(context, "LEBT:AUTO:StopHT", "_previous_stop")
        started = self._edge(context, "LEBT:AUTO:UptoHT", "_previous_start")

        if stopped and self.phase in self.ACTIVE:
            self._aborted(context, "operator stop")
        elif started and self.phase not in self.ACTIVE:
            if not self._can_start(context):
                self._aborted(context, "missing ON feedback or authorization")
            else:
                self.phase = RampPhase.HV_IE
                self.profile_index = 0
                self.wait_elapsed_s = 0.0
                self.step_elapsed_s = 0.0
                hv, ie = self.settings.hv_ie_profile_kV[0]
                self._set_target(context, "HV", hv)
                self._set_target(context, "IE", ie)
                self._say(context, "HV/IE initial 1 kV: checking readbacks")

        if self.phase in self.ACTIVE:
            if not self._can_start(context):
                self._aborted(context, "authorization or power supply lost")
            elif self.phase == RampPhase.HV_IE:
                self._step_hv_ie(dt, context)
            elif self.phase == RampPhase.REPELLER:
                self._step_repeller(dt, context)

        context.metrics["hv_auto.active"] = float(self.phase in self.ACTIVE)
        context.metrics["hv_auto.complete"] = float(self.phase == RampPhase.COMPLETE)
        context.metrics["hv_auto.aborted"] = float(self.phase == RampPhase.ABORTED)
        context.metrics["hv_auto.profile_index"] = float(self.profile_index)

    def _tick_ready(self, dt: float, context, devices: tuple[str, ...],
                    interval_s: float) -> bool:
        if not self._all_ready(context, devices):
            self.wait_elapsed_s += dt
            if self.wait_elapsed_s > self.settings.feedback_timeout_s:
                self._aborted(context, "readback outside +/-1% beyond timeout")
            return False
        self.wait_elapsed_s = 0.0
        self.step_elapsed_s += dt
        if self.step_elapsed_s < interval_s:
            return False
        self.step_elapsed_s = 0.0
        return True

    def _step_hv_ie(self, dt: float, context) -> None:
        if not self._tick_ready(dt, context, ("HV", "IE"),
                                self.settings.hv_ie_step_interval_s):
            return
        profile = self.settings.hv_ie_profile_kV
        while (self.profile_index < len(profile) - 1
               and all(self.target[d] >= profile[self.profile_index + 1][i]
                       for i, d in enumerate(("HV", "IE")))):
            self.profile_index += 1
        if self.profile_index == len(profile) - 1:
            self.phase = RampPhase.REPELLER
            self._set_target(context, "R", self.settings.repeller_step_kV)
            self._say(context, "HV/IE reached targets; repeller 0.1 kV")
            return
        next_hv, next_ie = profile[self.profile_index + 1]
        hv = min(self.target["HV"] + self.settings.hv_step_kV, next_hv)
        ie = min(self.target["IE"] + self.settings.ie_step_kV, next_ie)
        self._set_target(context, "HV", hv)
        self._set_target(context, "IE", ie)
        self._say(context, f"Ramping HV {hv:.1f} kV / IE {ie:.1f} kV")

    def _step_repeller(self, dt: float, context) -> None:
        if not self._tick_ready(dt, context, ("R",),
                                self.settings.repeller_step_interval_s):
            return
        if self.target["R"] >= self.settings.repeller_final_kV:
            self.phase = RampPhase.COMPLETE
            self._say(context, "HV/IE/Repeller completed, verified +/-1%")
            return
        voltage = min(self.target["R"] + self.settings.repeller_step_kV,
                      self.settings.repeller_final_kV)
        self._set_target(context, "R", voltage)
        self._say(context, f"Ramping Repeller {voltage:.1f} kV")
