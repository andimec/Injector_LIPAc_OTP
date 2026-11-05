"""Power-supply record scaling verified against topIFMIF_INJ source.

These tests verify original EPICS interface transformations, not real
FuG/MCPS dynamics or physical current draw.
"""
import pytest

from injector_otp.core.engine import SimulationContext
from injector_otp.models.catalog import DeviceCatalog
from injector_otp.models.power_supplies import PowerSupplyDevice


def catalog():
    return DeviceCatalog.from_registry("config/pv_registry_v2_0.json")


def test_ie_supply_readback_raw_register_and_engineering_units():
    device = PowerSupplyDevice("SRC:IE_PS", catalog(), {})
    ctx = SimulationContext(
        pv={
            "SRC:IE_PS:OnCmd": 1,
            "SRC:IE_PS:VSet": 25.0,
            "SRC:IE_PS:ISet": 10.0,
        },
        interlocks={"IE:ENABLE": True},
    )
    device.update(1.0, ctx)
    assert ctx.outputs["SRC:IE_PS:OnStat"][0] == 1
    assert ctx.outputs["SRC:IE_PS:IRdbk"][0] == pytest.approx(15000)
    assert ctx.outputs["SRC:IE_PS:IRdbkcalc"][0] == pytest.approx(10.0)
    assert ctx.outputs["SRC:IE_PS:Vcalcout"][0] == pytest.approx(15000)
    assert ctx.outputs["SRC:IE_PS:VRdbk"][0] == pytest.approx(600)
    assert ctx.outputs["SRC:IE_PS:VRdbkcalc"][0] == pytest.approx(1.0)


def test_hv_supply_respects_auxiliary_enable_and_fug_units():
    device = PowerSupplyDevice("LEBT:HV_PS", catalog(), {})
    ctx = SimulationContext(
        pv={
            "LEBT:HV_PS:AuxOnCmd": 1,
            "LEBT:HV_PS:HTOnCmd": 1,
            "LEBT:HV_PS:HTCmd": 100.0,
            "LEBT:HV_PS:ICmd": 250.0,
        },
        interlocks={"HV:ENABLE": True},
    )
    device.update(1.0, ctx)
    assert ctx.outputs["LEBT:HV_PS:OnStat"][0] == 1
    assert ctx.outputs["LEBT:HV_PS:CalcVHT"][0] == 100000.0
    assert ctx.outputs["LEBT:HV_PS:CalcI"][0] == pytest.approx(0.25)
    assert ctx.outputs["LEBT:HV_PS:LectVht"][0] == 1000.0
    assert ctx.outputs["LEBT:HV_PS:ScaleVHT"][0] == 1.0
    # Current-limit setpoint cannot be used as actual supply current.
    assert "LEBT:HV_PS:LectIht" not in ctx.outputs


def test_rc_ps_source_has_unresolved_current_scale_inconsistency():
    device = PowerSupplyDevice("LEBT:RC_PS", catalog(), {})
    ctx = SimulationContext(
        pv={
            "LEBT:RC_PS:ON": 1,
            "LEBT:RC_PS:ISet": 5.0,
            "LEBT:RC_PS:VSet": 1.5,
        },
        interlocks={"COOLING:READY": True},
    )
    device.update(1.0, ctx)
    assert ctx.outputs["LEBT:RC_PS:Icalcout"][0] == pytest.approx(15000)
    # Original source readback uses 1/30000 instead of 10/30000.
    assert ctx.outputs["LEBT:RC_PS:IRdbkcalc"][0] == pytest.approx(
        ctx.outputs["LEBT:RC_PS:IRdbk"][0] / 30000
    )


@pytest.mark.parametrize("prefix", ["LEBT:STH01_PS", "LEBT:STH02_PS"])
def test_horizontal_steerer_voltage_readback_ramps_and_is_not_setpoint_echo(prefix):
    device = PowerSupplyDevice(prefix, catalog(), {})
    ctx = SimulationContext(
        pv={f"{prefix}:ON": 1, f"{prefix}:VSet": 8.0, f"{prefix}:ISet": 10.0},
        interlocks={"COOLING:READY": True},
    )
    device.update(0.5, ctx)
    assert ctx.outputs[f"{prefix}:OnStat"][0] == 1
    assert ctx.outputs[f"{prefix}:VRdbkcalc"][0] == pytest.approx(0.5)
    assert ctx.outputs[f"{prefix}:VRdbkcalc"][0] != ctx.pv[f"{prefix}:VSet"]

    ctx.pv[f"{prefix}:ON"] = 0
    ctx.pv[f"{prefix}:OFF"] = 1
    device.update(0.5, ctx)
    assert ctx.outputs[f"{prefix}:OnStat"][0] == 0
    assert ctx.outputs[f"{prefix}:VRdbkcalc"][0] == pytest.approx(0.0)
