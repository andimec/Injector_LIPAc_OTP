from injector_otp.app import build_application
from injector_otp.core.state import InjectorState


def test_application_builds_in_safe_off_state():
    engine, pv, faults = build_application()
    assert engine.context.state == InjectorState.OFF
    assert pv.get("PPS:BEAM:InhibitStat") is False
    assert not faults.active


def test_simulation_step_is_deterministic_in_time():
    engine, pv, _ = build_application()
    engine.step()
    assert engine.context.time == 0.1
    assert pv.get("OTP:SIM_TIME") == 0.1


def test_operator_write_is_separate_from_model_publish():
    _, pv, _ = build_application()
    pv.put("SRC:COIL01_PS:ISet", 10.0)
    assert pv.get("SRC:COIL01_PS:ISet") == 10.0
    try:
        pv.put("SRC:COIL01_PS:IRdbk", 10.0)
    except PermissionError:
        pass
    else:
        raise AssertionError("Read-only PV accepted an operator write")


def test_v1_2_registry_is_exposed_only_in_simulation_namespace():
    _, pv, _ = build_application()
    assert "OTP:PPS:BEAM:InhibitStat" in pv.names()
    assert "PPS:BEAM:InhibitStat" not in pv.names()


def test_active_fault_is_visible_in_engine_context_and_snapshot():
    engine, _, faults = build_application()
    faults.inject("VACUUM_LOSS")
    engine.step()

    assert engine.context.faults == {"VACUUM_LOSS"}
    snapshot = engine.snapshot()
    assert snapshot["faults"] == ["VACUUM_LOSS"]
    assert snapshot["time"] == 0.1
