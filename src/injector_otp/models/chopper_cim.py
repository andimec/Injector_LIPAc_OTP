"""CIM training model, deliberately distinct from cRIO/FPGA protection logic.

Evidence:
- Injector LCS User Manual v4.0 (2026), sections 4.4.1--4.4.4:
  PRE-ARM / ARMED operator states, 1000 V off, 6000 V on, 5 mA ACCT
  reference thresholds and captured FBI event fields.
- Injector_OPI/Chopper_IM/INJ_ChIM_Main_revMA.opi:
  StmStateSet=1 for PRE-ARM and =2 for ARMED. Display enumeration:
  0 CONFIGURATION, 1 PRE-ARM, 2 ARMED, 3 GATE OFF,
  4 GATE ON:RISING, 5 GATE ON, 6 GATE OFF:DECREASING.

The cRIO/FPGA comparison windows and real-world fault reset semantics are
NOT available in text form. This model does not invent those algorithms.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from .base import SubsystemModel
from .catalog import DeviceCatalog


class CIMState(IntEnum):
    CONFIGURATION = 0
    PRE_ARM = 1
    ARMED = 2
    GATE_OFF = 3
    GATE_ON_RISING = 4
    GATE_ON = 5
    GATE_OFF_DECREASING = 6


@dataclass(frozen=True)
class CIMThresholds:
    hv_off_V: float = 1000.0
    hv_on_V: float = 6000.0
    acct_on_mA: float = 5.0


class ChopperCIMModel(SubsystemModel):
    """Operator state, threshold readbacks, explicit FBI and event snapshot."""

    name = "chopper_im"

    def __init__(self, catalog: DeviceCatalog, thresholds: CIMThresholds | None = None):
        super().__init__()
        self.catalog = catalog
        self.thresholds = thresholds or CIMThresholds()
        self.operational_state = CIMState.PRE_ARM
        self.latched = False
        self._last_command: int | None = None
        self._was_triggering = False
        self.snapshot: dict[str, float | int] = {}

    def _name(self, suffix: str) -> str:
        return f"LEBT:CHOP_IM:{suffix}"

    def _read(self, context, suffix: str, default=0):
        return context.pv.get(self._name(suffix), default)

    def _emit(self, context, suffix: str, value: object) -> None:
        pv = self._name(suffix)
        if self.catalog.has(pv):
            context.emit(pv, value, "chopper_cim_training")

    def update(self, dt: float, context) -> None:
        super().update(dt)
        cmd = int(self._read(context, "StmStateSet", 0) or 0)
        # OPI button actions write a level, not a pulse. Apply on changes,
        # without automatically clearing a previously captured FBI.
        if cmd != self._last_command:
            if cmd == CIMState.PRE_ARM:
                self.operational_state = CIMState.PRE_ARM
            elif cmd == CIMState.ARMED and not self.latched:
                self.operational_state = CIMState.ARMED
            self._last_command = cmd

        # Threshold setpoint values are initialized in the scenario YAML.
        # They are not physical/FPGA comparisons yet.
        off = float(self._read(context, "VmonOff", self.thresholds.hv_off_V))
        on = float(self._read(context, "VmonThr", self.thresholds.hv_on_V))
        acct = float(self._read(context, "AcctThr", self.thresholds.acct_on_mA))
        self._emit(context, "VmonOffRdbk", off)
        self._emit(context, "VmonThrRdbk", on)
        self._emit(context, "AcctThrRdbk", acct)

        triggering = bool(
            "FBI_TRIGGER" in context.faults
            or context.device_faults.get("chopper", False)
        )
        if triggering and not self._was_triggering and not self.latched:
            self.latched = True
            self.snapshot = {
                "FbiStmState": int(self.operational_state),
                "FbiCGate": int(bool(self._read(context, "DbgChop", 0))),
                "FbiFaraday": int(bool(context.pv.get("LEBT:FC:InStat", 0))),
                "FbiDPeriod": float(context.pv.get("SRC:TIM:Trep", 0) or 0),
                "FbiDPulse": float(context.pv.get("SRC:TIM:TPulse", 0) or 0),
                "FbiVmon": float(self._read(context, "CurrentVmon", 0)),
                "FbiAcct": float(self._read(context, "CurrentAcct", 0)),
            }
            for suffix, value in self.snapshot.items():
                self._emit(context, suffix, value)
        self._was_triggering = triggering

        self._emit(context, "StmState", int(self.operational_state))
        self._emit(context, "Fbi", int(self.latched))
        # These are exercise status metrics, not overrides of external PPS.
        context.metrics["chopper.fbi"] = float(self.latched)
        context.metrics["chopper.state"] = float(self.operational_state)
        context.metrics["chopper.threshold_off_V"] = off
        context.metrics["chopper.threshold_on_V"] = on
        context.metrics["chopper.threshold_acct_mA"] = acct

    def reset_exercise(self) -> None:
        """Explicit trainer reset, NEVER a proxy for undocumented FPGA reset."""
        self.latched = False
        self.snapshot.clear()
        self.operational_state = CIMState.PRE_ARM
        self._was_triggering = False
        self._last_command = None
