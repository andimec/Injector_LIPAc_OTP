from injector_otp.app import build_application
from injector_otp.core.control import SimulationControlPlane
from injector_otp.core.state import InjectorState


class ExternalInterlockAndFaultLogic:
    def evaluate(self, context, controls):
        controls.set_interlock("HV:ENABLE", context.pv.get("OTP:TEST_HV_OK", True))
        controls.set_device_fault("hv", context.pv.get("OTP:TEST_HV_FAULT", False))


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


def test_external_logic_controls_interlocks_and_device_faults():
    engine, pv, _ = build_application()
    engine.logic.append(ExternalInterlockAndFaultLogic())

    pv.define("OTP:TEST_HV_OK", True, writable=True)
    pv.define("OTP:TEST_HV_FAULT", False, writable=True)

    engine.step()
    assert engine.context.interlocks["HV:ENABLE"] is True
    assert engine.context.device_faults["hv"] is False

    pv.put("OTP:TEST_HV_OK", False)
    pv.put("OTP:TEST_HV_FAULT", True)
    engine.step()

    assert engine.context.interlocks["HV:ENABLE"] is False
    assert engine.context.device_faults["hv"] is True
    assert engine.snapshot()["interlocks"]["HV:ENABLE"] is False
    assert engine.snapshot()["device_faults"]["hv"] is True


def test_control_plane_is_independent_from_fault_manager():
    controls = SimulationControlPlane()
    controls.set_interlock("RF:ENABLE", False)
    controls.set_device_fault("rf", True)

    assert controls.interlock_ok("RF:ENABLE") is False
    assert controls.device_in_fault("rf") is True
    controls.clear_device_fault("rf")
    assert controls.device_in_fault("rf") is False
