"""Regression against original FC/BS/IC EPICS calculation chains."""
import pytest

from injector_otp.core.engine import SimulationContext
from injector_otp.models.catalog import DeviceCatalog
from injector_otp.models.calorimetry import (
    LegacyCalorimetryModel, legacy_current, legacy_delta_t
)


def test_original_fc_temperature_and_current_chain():
    model = LegacyCalorimetryModel(DeviceCatalog.from_registry("config/pv_registry_v2_0.json"))
    context = SimulationContext(pv={
        "LEBT:FC:TinRdbk": 2.0,
        "LEBT:FC:ToutRdbk": 2.1,
        "LEBT:FC:Comp": 0.1,
        "LEBT:HV_PS:HTCmd": 100.0,
        "SRC:TIM:DutyCycle": 1.0,
        "LEBT:FC:InStat": 1,
        "LEBT:EMIT_FC:I": 20.0,
    })
    model.update(0.1, context)
    assert context.outputs["LEBT:FC:Tincalc"][0] == 10.0
    assert context.outputs["LEBT:FC:Toutcalc"][0] == pytest.approx(10.5)
    assert context.outputs["LEBT:FC:DeltaT"][0] == pytest.approx(0.4)
    expected = ((40.0 / 60.0) * 4186.8 * 0.4) / 100.0
    assert context.outputs["LEBT:FC:ICalc"][0] == pytest.approx(expected)


def test_legacy_bs_uses_fc_inlet_temperature_by_source_definition():
    model = LegacyCalorimetryModel(DeviceCatalog.from_registry("config/pv_registry_v2_0.json"))
    context = SimulationContext(pv={
        "LEBT:FC:TinRdbk": 2.0,
        "LEBT:FC:ToutRdbk": 2.2,
        "LEBT:BS:TinRdbk": 1.8,
        "LEBT:BS:ToutRdbk": 2.2,
        "LEBT:HV_PS:HTCmd": 100.0,
        "SRC:TIM:DutyCycle": 1.0,
    })
    model.update(0.1, context)
    assert context.outputs["LEBT:BS:DeltaT"][0] == pytest.approx(1.0)
    assert context.outputs["LEBT:BS:DeltaT2"][0] == pytest.approx(2.0)


def test_original_ic_uses_fixed_320_over_60_and_100_scale():
    model = LegacyCalorimetryModel(DeviceCatalog.from_registry("config/pv_registry_v2_0.json"))
    context = SimulationContext(pv={
        "LEBT:FC:TinRdbk": 2.0,
        "LEBT:FC:ToutRdbk": 2.1,
        "LEBT:IC:TinRdbk": 2.0,
        "LEBT:IC:ToutRdbk": 2.1,
    })
    model.update(0.1, context)
    expected = ((320.0 / 60.0) * 4186.8 * 0.5) / 100.0
    assert context.outputs["LEBT:IC:Icalc"][0] == pytest.approx(expected)


def test_no_dangerous_division_by_zero_or_invalid_unmeasured_readback():
    model = LegacyCalorimetryModel(DeviceCatalog.from_registry("config/pv_registry_v2_0.json"))
    context = SimulationContext(pv={
        "LEBT:FC:TinRdbk": 0,
        "LEBT:FC:ToutRdbk": 1,
        "LEBT:HV_PS:HTCmd": 0,
    })
    model.update(0.1, context)
    assert "LEBT:FC:ICalc" not in context.outputs
    assert legacy_current(1.0, 40.0, 0.0) is None
    assert legacy_delta_t(2.0, 2.1, 0.1) == pytest.approx(0.4)
