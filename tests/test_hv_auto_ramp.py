"""Traceable Python auto-HV ramp regression tests.

Source: Injector LCS User Manual v4.0 sec. 3.5.4, BA_D_2E9QH7
v2.0 (2026) steps 8--18. Unit tests use ideal readback to isolate the
sequence from uncertain physical power-supply ramp parameters.
"""
import pytest

from injector_otp.core.engine import SimulationContext, SimulationEngine
from injector_otp.models.catalog import DeviceCatalog
from injector_otp.models.hv_auto_ramp import HVAutoRampModel, RampPhase
from injector_otp.pv.state import SimulationPVState


def build_model():
    catalog = DeviceCatalog.from_registry("config/pv_registry_v2_0.json")
    model = HVAutoRampModel(catalog)
    context = SimulationContext()
    context.interlocks = {"HV:ENABLE": True, "IE:ENABLE": True}
    context.pv = {
        "LEBT:HV_PS:OnStat": 1,
        "SRC:IE_PS:OnStat": 1,
        "LEBT:R_PS:OnStat": 1,
        "LEBT:HV_PS:ScaleVHT": 0.0,
        "SRC:IE_PS:VRdbkcalc": 0.0,
        "LEBT:R_PS:VRdbkcalc": 0.0,
        "LEBT:AUTO:UptoHT": 0,
        "LEBT:AUTO:StopHT": 0,
    }
    return model, context


def test_2026_ramp_profile_hits_hv_ie_and_repeller_milestones():
    model, context = build_model()
    context.pv["LEBT:AUTO:UptoHT"] = 1
    model.update(1.0, context)
    assert model.target["HV"] == 1.0
    assert model.target["IE"] == 1.0
    visited = set()
    for _ in range(230):
        for name, readback in model.READBACK.items():
            context.pv[readback] = model.target[name]
        model.update(1.0, context)
        visited.add((model.target["HV"], model.target["IE"]))
        if model.phase == RampPhase.COMPLETE:
            break
    assert model.phase == RampPhase.COMPLETE
    assert model.target == {"HV": 100.0, "IE": 25.0, "R": 4.5}
    for milestone in [(10.0, 5.0), (20.0, 10.0), (30.0, 15.0),
                      (40.0, 20.0), (50.0, 25.0), (100.0, 25.0)]:
        assert milestone in visited


def test_auto_ramp_requires_supplies_on_and_authorizations():
    model, context = build_model()
    context.pv["SRC:IE_PS:OnStat"] = 0
    context.pv["LEBT:AUTO:UptoHT"] = 1
    model.update(0.1, context)
    assert model.phase == RampPhase.ABORTED
    assert context.command_requests == {}


def test_auto_ramp_stop_does_not_fabricate_power_supply_shutdown():
    model, context = build_model()
    context.pv["LEBT:AUTO:UptoHT"] = 1
    model.update(0.1, context)
    context.command_requests.clear()
    context.pv["LEBT:AUTO:StopHT"] = 1
    model.update(0.1, context)
    assert model.phase == RampPhase.ABORTED
    assert context.command_requests == {}


def test_ramp_aborts_on_feedback_timeout():
    model, context = build_model()
    context.pv["LEBT:AUTO:UptoHT"] = 1
    model.update(1.0, context)
    for _ in range(25):
        model.update(1.0, context)
    assert model.phase == RampPhase.ABORTED
    assert "readback" in model.reason.lower()


def test_engine_rejects_automation_writes_to_unapproved_pv():
    state = SimulationPVState(writable_names={"TEST:CMD"})
    state.define("TEST:CMD", 0)
    state.define("TEST:READBACK", 0)
    class InvalidAutomation:
        def update(self, dt, context):
            context.request_command("TEST:READBACK", 42, "bad_sequencer")

    engine = SimulationEngine(models=[InvalidAutomation()], pv_state=state)
    with pytest.raises(PermissionError, match="non-command or unapproved"):
        engine.step()
    assert state.get("TEST:READBACK") == 0
