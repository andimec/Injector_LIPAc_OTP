"""Uncalibrated EMU phase-space fixture and RMS-moment tests."""
from dataclasses import dataclass
import pytest

from injector_otp.models.emu_analysis import rms_emittance, samples_to_csv
from injector_otp.models.emu_beam import SyntheticPhaseSpace
from injector_otp.models.emu_hardware import EmuAcquisitionModel
from injector_otp.models.catalog import DeviceCatalog
from injector_otp.core.engine import SimulationContext
from injector_otp.models.emu_sequencer import EmuMode


@dataclass
class Sample:
    motor_mm: float
    angle_rad: float
    current_mA: float
    voltage_set_V: float = 0.0
    voltage_measured_V: float = 0.0
    t_s: float = 0.0
    mode: EmuMode = EmuMode.EMITTANCE


def test_uncorrected_rms_emittance_of_symmetric_four_point_distribution():
    samples = [
        Sample(x, a / 1000.0, 1.0)
        for x in (-1, 1)
        for a in (-2, 2)
    ]
    result = rms_emittance(samples)
    assert result.samples_used == 4
    assert result.sigma_motor_mm == pytest.approx(1)
    assert result.sigma_angle_mrad == pytest.approx(2)
    assert result.emittance_rms_mm_mrad == pytest.approx(2)
    assert result.twiss_alpha == pytest.approx(0)
    assert result.twiss_beta_mm_per_mrad == pytest.approx(0.5)
    assert result.twiss_gamma_mrad_per_mm == pytest.approx(2)


def test_rms_requires_nonzero_signal_and_two_dimensional_spread():
    with pytest.raises(ValueError):
        rms_emittance([Sample(0, 0, 0)] * 10)
    with pytest.raises(ValueError, match="singular"):
        rms_emittance([Sample(x, 0, 1) for x in range(4)])


def test_synthetic_gaussian_is_positive_and_peaked_at_configured_center():
    f = SyntheticPhaseSpace(
        peak_current_mA=7, mean_motor_mm=80,
        mean_angle_mrad=2, rms_emittance_mm_mrad=30,
    )
    assert f.current_mA(80, 2) == pytest.approx(7)
    assert f.current_mA(70, 2) < 7
    assert f.current_mA(80, 12) < 7
    with pytest.raises(ValueError):
        SyntheticPhaseSpace(rms_emittance_mm_mrad=0)


def test_csv_has_original_source_columns_without_writing_files():
    s = Sample(3, 0.002, 5, 200, 201, 10)
    csv = samples_to_csv([s])
    assert csv.startswith("motor_mm,vht_set_V,angle_rad,current_mA,vht_measured_V")
    assert "3.000000,200.000000,0.002000000,5.000000000,201.000000" in csv


def test_opt_in_gaussian_facq_generates_deterministic_scalar_and_event():
    cat=DeviceCatalog.from_registry("config/pv_registry_v2_0.json")
    model=EmuAcquisitionModel(cat, {
        "synthetic_enabled": True,
        "synthetic_period_s": 0.1,
        "synthetic_phase_space": {
            "enabled": True,
            "peak_current_mA": 7,
            "mean_motor_mm": 80,
            "mean_angle_mrad": 0,
        },
    })
    ctx=SimulationContext(
        pv={"LEBT:EMIT:Energy": 100},
        metrics={"emu.motor_position_mm": 80, "emu.VhtRdbk": 0},
    )
    model.update(0.1, ctx)
    assert ctx.outputs["LEBT:EMIT_FC:I"][0] == pytest.approx(7)
    assert ctx.metrics["emu.facq_sample_id"] == 1.0
