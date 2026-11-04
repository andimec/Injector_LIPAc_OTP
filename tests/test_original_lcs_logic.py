"""Regression tests against active formulas in topIFMIF_INJ.

No EPICS network connection is required. These are traceability checks, not
tests of real PPS/PLC protection performance.
"""
import pytest

from injector_otp.models.original_lcs_logic import (
    to_analog_counts, from_analog_counts, rf_control_word,
    rf_onoff_word, rf_reset_word, rf_status_from_mot105,
    rf_atu_mode_word, reflected_power_display,
    vacuum01_pv_precondition, vacuum01_sv_precondition,
    vacuum02_sv_precondition, timing_display_ratio, physical_duty_fraction,
)


def test_ie_analogue_register_calibration_exact():
    assert to_analog_counts(25.0, 50.0) == 15000.0
    assert from_analog_counts(15000.0, 50.0) == 25.0
    assert to_analog_counts(10.0, 20.0) == 15000.0


def test_repeller_register_scales():
    assert to_analog_counts(4.5, 15.0) == 9000.0
    assert from_analog_counts(9000.0, 15.0) == 4.5


def test_bad_analog_scale_is_rejected():
    with pytest.raises(ValueError):
        to_analog_counts(1.0, 0.0)


def test_rf_command_word_matches_calc_mot02():
    # Modbus=1,CW=0,limitPR=1,filament=1,microwave=1
    word = rf_control_word(True, False, True, True, True)
    assert word == 4 + 16 + 32 + 64
    assert rf_onoff_word(True, word) == 64 + (word & 63)
    assert rf_reset_word(True, word) == ((128 | word) & 191)


def test_rf_status_bits_and_reflected_power():
    assert rf_status_from_mot105(64 + 128) == {
        "on": True, "ready": True, "defect": False
    }
    assert rf_status_from_mot105(8)["defect"]
    assert reflected_power_display(100) == 90.0
    assert rf_atu_mode_word(1) == 3


def test_vacuum_pv_precondition_matches_original_calc():
    assert vacuum01_pv_precondition(True, True, False)
    assert vacuum01_pv_precondition(False, False, True)
    assert not vacuum01_pv_precondition(False, True, False)


def test_vacuum_sv_preconditions_match_original_calc():
    assert vacuum01_sv_precondition(False, False, False, False,
                                    False, False, False, True)
    assert not vacuum01_sv_precondition(False, False, False, False,
                                        False, False, False, False)
    assert vacuum02_sv_precondition(True, True, True, True, False)
    assert vacuum02_sv_precondition(False, False, False, False, True)


def test_legacy_timing_display_is_not_physical_duty():
    assert timing_display_ratio(100.0, 5.0, False) == 20.0
    assert physical_duty_fraction(100.0, 5.0, False) == 0.05
    assert timing_display_ratio(100.0, 5.0, True) == 1.0
    assert physical_duty_fraction(100.0, 5.0, True) == 1.0
    assert timing_display_ratio(100.0, 0.0, False) is None
