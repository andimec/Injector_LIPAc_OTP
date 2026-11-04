"""Pure translations of documented, active original LCS record equations.

Source: https://github.com/andimec/topIFMIF_INJ (main branch).
These functions implement *interface representation* and HMI-precondition
equations. They must not be confused with hardware PPS/PLC safety logic.
All actuator dynamics, state machines and safety validation live in Python.
"""
from __future__ import annotations


def clamp_register(value: float, lower: float = 0.0, upper: float = 30000.0) -> float:
    """Clamp a simulated unsigned analogue register to its documented range."""
    return max(lower, min(upper, value))


def to_analog_counts(engineering: float, full_scale: float, counts: float = 30000.0) -> float:
    """Engineering signal -> analog register, CALC=(A*30000)/full_scale.

    IE and repeller use 30,000 full-scale counts in original .db files.
    """
    if full_scale <= 0 or counts <= 0:
        raise ValueError("full_scale and counts must be positive")
    return engineering * counts / full_scale


def from_analog_counts(raw: float, full_scale: float, counts: float = 30000.0) -> float:
    """Analogue register -> engineering signal, CALC=(A*full_scale)/30000."""
    if full_scale <= 0 or counts <= 0:
        raise ValueError("full_scale and counts must be positive")
    return raw * full_scale / counts


def rf_control_word(modbus: bool, cw: bool, limit_reflection: bool,
                    filament: bool, microwave: bool) -> int:
    """SRC:RF_GENE:CalcMot02: A<<2|B<<3|C<<4|D<<5|E<<6."""
    return ((int(modbus) << 2) | (int(cw) << 3)
            | (int(limit_reflection) << 4) | (int(filament) << 5)
            | (int(microwave) << 6))


def rf_onoff_word(microwave: bool, control_word: int) -> int:
    """SRC:RF_GENE:CalcOnOff: (A<<6)|(B&63)."""
    return (int(microwave) << 6) | (control_word & 63)


def rf_reset_word(reset: bool, control_word: int) -> int:
    """SRC:RF_GENE:CalcRAZ: ((reset<<7)|control_word)&191."""
    return ((int(reset) << 7) | control_word) & 191


def rf_status_from_mot105(word: int) -> dict[str, bool]:
    """Reported RF status: on=bit6, ready=bit7, defect=bit3."""
    return {
        "on": bool(int(word) & 64),
        "ready": bool(int(word) & 128),
        "defect": bool(int(word) & 8),
    }


def reflected_power_display(mot103: float) -> float:
    """Original SRC:RF_GENE:PwrRef display conversion: Mot103 * 0.9."""
    return float(mot103) * 0.9


def rf_atu_mode_word(mode_xy: int) -> int:
    """Exact original CalcModeXY=(A|(B<<1)), INPA=INPB=ModeXY.

    This apparently duplicates ModeXY into bit1. Keep source behaviour,
    but classify this as an interface encoding, not a physical model.
    """
    return int(mode_xy) | (int(mode_xy) << 1)


def vacuum01_pv_precondition(tp_def: bool, pp_on: bool,
                             aiv_open: bool) -> bool:
    """Original PLC StatusForOpi: PVOpenPrecond=(A&B)|C."""
    return (tp_def and pp_on) or aiv_open


def vacuum01_sv_precondition(aiv: bool, niv: bool, tp_def: bool,
                             sv_open: bool, pgtp_def: bool,
                             sgtp_def: bool, pgvc_def: bool,
                             forcing: bool) -> bool:
    """Original PLC StatusForOpi VAC01: ((((A&B)|D)|(E&F&G))&C)|H."""
    return ((((aiv and niv) or sv_open)
             or (pgtp_def and sgtp_def and pgvc_def))
            and tp_def) or forcing


def vacuum02_sv_precondition(pgtp_def: bool, sgtp_def: bool,
                             pgvc_def: bool, tp_speed: bool,
                             forcing: bool) -> bool:
    """Original PLC StatusForOpi VAC02: (A&B&C&D)|E."""
    return (pgtp_def and sgtp_def and pgvc_def and tp_speed) or forcing


def timing_display_ratio(period_ms: float, pulse_ms: float,
                         rf_cw: bool) -> float | None:
    """Original Cyclut=Trep/TPulse and DutyCycle=(B)?A:C (C=1).

    NB: The published source formula is INVERSE to physical duty fraction!
    This is retained only for compatibility with legacy displays.
    """
    # Original CALC=(B)?A:C, B=RF_GENE:CWmdOn, A=Cyclut, C=1.
    # Therefore CW selects Trep/TPulse, pulse mode selects 1.
    if not rf_cw:
        return 1.0
    if pulse_ms <= 0:
        return None
    return period_ms / pulse_ms


def physical_duty_fraction(period_ms: float, pulse_ms: float,
                           cw: bool) -> float:
    """Actual beam pulse duration / period, independent of legacy display."""
    if cw:
        return 1.0
    if period_ms <= 0:
        return 0.0
    return max(0.0, min(1.0, pulse_ms / period_ms))
