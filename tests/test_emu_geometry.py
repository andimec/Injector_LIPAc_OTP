"""EMU source-geometry and December-2025 VHT-grid reconstruction tests."""
from math import isclose
import pytest

from injector_otp.models.emu_geometry import EmuGeometry, build_roi


def baseline(**overrides):
    values = dict(energy_keV=100.0, angle_init_mrad=-8,
                  angle_end_mrad=8, angle_delta_mrad=15,
                  border_up_mm=129, border_low_mm=127,
                  motor_step_mm=1.0, hv_points=4)
    values.update(overrides)
    return build_roi(**values)


def test_exact_original_emu_geometry_constants():
    g = EmuGeometry()
    expect = ((0.09 + 2*0.002)*0.09) / (
        4*0.009*(0.01 + 0.09 + 0.002))
    assert g.distance_factor == pytest.approx(expect)
    assert g.angle_mrad_to_vht(8, 100) == pytest.approx(800/expect)
    assert g.vht_to_angle_rad(800/expect, 100) == pytest.approx(0.008)


def test_validation_border_and_plate_voltage_symmetry():
    roi = baseline()
    assert roi.motor_upper_mm == 1.0
    assert roi.motor_lower_mm == 3.0
    assert roi.vpic_end_V == pytest.approx(-roi.vpic_init_V)
    assert roi.start_voltage_V == pytest.approx(
        roi.vpic_init_V + roi.delta_v_V/2
    )
    assert roi.end_voltage_V == pytest.approx(
        roi.vpic_init_V - roi.delta_v_V/2
    )
    assert roi.half_plate_step_V == pytest.approx(roi.delta_v_V/8)


def test_global_vht_grid_is_bounded_and_snaps_descending():
    roi = baseline(hv_points=10)
    assert 2 <= len(roi.grid) <= 4096
    assert roi.grid[0] == pytest.approx(
        roi.vpic_init_V - roi.delta_v_V/2
    )
    assert roi.grid[-1] == pytest.approx(
        roi.vpic_end_V + roi.delta_v_V/2
    )
    points = roi.snapped_voltages(roi.motor_upper_mm)
    assert len(points) > 1
    assert all(a >= b for a, b in zip(points, points[1:]))


@pytest.mark.parametrize("bad", [
    {"angle_init_mrad": -9999},
    {"angle_end_mrad": 9999},
    {"border_up_mm": 40, "border_low_mm": 120},
    {"motor_step_mm": 0},
    {"angle_delta_mrad": 0},
    {"energy_keV": 0},
    {"hv_points": 0},
    {"hv_points": 5000},
])
def test_invalid_emu_roi_is_rejected_without_division_by_zero(bad):
    with pytest.raises(ValueError):
        baseline(**bad)
