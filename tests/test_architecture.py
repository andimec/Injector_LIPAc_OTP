from injector_otp.app import build_application
from injector_otp.core.control import SimulationControlPlane
from injector_otp.core.state import InjectorState


class ExternalInterlockAndFaultLogic:
    def evaluate(self, context, controls):
        controls.set_interlock("HV:ENABLE", context.pv.get("SIM:TEST_HV_OK", True))
        controls.set_device_fault("hv", context.pv.get("SIM:TEST_HV_FAULT", False))


def test_application_builds_in_safe_off_state():
    engine, pv, faults = build_application()
    assert engine.context.state == InjectorState.OFF
    assert pv.get("PPS:BEAM:InhibitStat") is False
    assert not faults.active


def test_simulation_step_is_deterministic_in_time():
    engine, pv, _ = build_application()
    engine.step()
    assert engine.context.time == 0.1
    assert pv.get("SIM:TIME") == 0.1


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


def test_v2_registry_is_exposed_with_native_pv_names():
    _, pv, _ = build_application()
    assert "PPS:BEAM:InhibitStat" in pv.names()
    assert "OTP:PPS:BEAM:InhibitStat" not in pv.names()


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

    pv.define("SIM:TEST_HV_OK", True, writable=True)
    pv.define("SIM:TEST_HV_FAULT", False, writable=True)

    engine.step()
    assert engine.context.interlocks["HV:ENABLE"] is True
    assert engine.context.device_faults["hv"] is False

    pv.put("SIM:TEST_HV_OK", False)
    pv.put("SIM:TEST_HV_FAULT", True)
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


def _publish_many(pv, values):
    for name, value in values.items():
        pv.publish(name, value)


def test_default_interlock_logic_is_wired_into_application():
    engine, _, _ = build_application()
    engine.step()

    assert engine.context.interlocks["HV:ENABLE"] is False
    assert engine.context.interlocks["RF:PLASMA:ENABLE"] is False
    assert engine.context.interlocks["RF:BEAM:ENABLE"] is False


def _evaluate_interlock_equations_without_plant(engine):
    """Unit-test authorization equations without advancing equipment dynamics.

    Previously these tests manually published model-owned status PVs and then
    ran engine.step(), which now correctly replaces those values with device
    model outputs. Test equations and end-to-end plant response separately.
    """
    from injector_otp.interlocks.logic import InjectorInterlockLogic

    engine.context.pv = engine.pv_state.values()
    engine.context.device_faults = dict(engine.control_plane.device_faults)
    InjectorInterlockLogic().evaluate(engine.context, engine.control_plane)
    engine.context.interlocks = dict(engine.control_plane.interlocks)


def test_hv_interlock_requires_all_documented_conditions():
    engine, pv, _ = build_application()
    values = {
        "LEBT:HV:RoomKeyA1": True,
        "LEBT:HV:RlyRmtStat": True,
        "LEBT:HV:RlyCloseStat": True,
        "LEBT:VAC01:SGVCDefStat": True,
        "SRC:IE_PS:OnStat": True,
        "INJ:WS:ResPCDefStat": True,
        "SRC:COIL01:FSDefStat": True,
        "SRC:COIL02:FSDefStat": True,
        "SRC:RF:FSDefStat": True,
        "PPS:HV:PermStat": True,
        "LEBT:HV_PS:ExtSec": True,
    }
    _publish_many(pv, values)
    _evaluate_interlock_equations_without_plant(engine)
    assert engine.context.interlocks["HV:ENABLE"] is True

    pv.publish("SRC:COIL02:FSDefStat", False)
    _evaluate_interlock_equations_without_plant(engine)
    assert engine.context.interlocks["HV:ENABLE"] is False


def test_rf_plasma_interlock_uses_d2_gas_configuration():
    engine, pv, _ = build_application()
    values = {
        "SRC:COIL01_PS:OnStat": True,
        "SRC:COIL02_PS:OnStat": True,
        "SRC:IE_PS:OnStat": True,
        "LEBT:R_PS:OnStat": True,
        "SRC:SVL:D2OpenStat": True,
        "LEBT:GE:FSFlowStat": True,
        "LEBT:GE:TSDefStat": True,
        "SRC:RF:FSDefStat": True,
        "LEBT:VAC01:SGVCDefStat": True,
        "PPS:PLSM:PermStat": True,
    }
    _publish_many(pv, values)
    _evaluate_interlock_equations_without_plant(engine)
    assert engine.context.interlocks["RF:PLASMA:ENABLE"] is True

    pv.publish("SRC:SVL:D2OpenStat", False)
    _evaluate_interlock_equations_without_plant(engine)
    assert engine.context.interlocks["RF:PLASMA:ENABLE"] is False


def test_rf_beam_interlock_requires_documented_beam_conditions():
    engine, pv, _ = build_application()
    values = {
        "LEBT:CHOP:FSDefStat": True,
        "LEBT:EMIT:FSDefStat": True,
        "LEBT:FC:FSDefStat": True,
        "LEBT:IC:FSDefStat": True,
        "LEBT:SOL01:VCFlowStat": True,
        "LEBT:SOL02:VCFlowStat": True,
        "LEBT:SOL01_PS:OnStat": True,
        "LEBT:SOL02_PS:OnStat": True,
        "SRC:RF:FSDefStat": True,
        "LEBT:GV:OpenStat": True,
        "LEBT:CHOP:InStat": True,
        "SRC:SVL:D2OpenStat": True,
        "LEBT:GE:FSFlowStat": True,
        "LEBT:GE:TSDefStat": True,
        "LEBT:HV_PS:OnStat": True,
        "SRC:IE_PS:OnStat": True,
        "LEBT:R_PS:OnStat": True,
        "PPS:CHOP:PermStat": True,
        "PPS:ACCL:PermStat": True,
        "PPS:BEAM:InhibitStat": False,
    }
    _publish_many(pv, values)
    _evaluate_interlock_equations_without_plant(engine)
    assert engine.context.interlocks["RF:BEAM:ENABLE"] is True

    pv.publish("PPS:BEAM:InhibitStat", True)
    _evaluate_interlock_equations_without_plant(engine)
    assert engine.context.interlocks["RF:BEAM:ENABLE"] is False


def test_external_device_fault_can_block_authorization_without_changing_pv_state():
    controls = SimulationControlPlane()
    engine, pv, _ = build_application(control_plane=controls)
    values = {
        "LEBT:HV:RoomKeyA1": True,
        "LEBT:HV:RlyRmtStat": True,
        "LEBT:HV:RlyCloseStat": True,
        "LEBT:VAC01:SGVCDefStat": True,
        "SRC:IE_PS:OnStat": True,
        "INJ:WS:ResPCDefStat": True,
        "SRC:COIL01:FSDefStat": True,
        "SRC:COIL02:FSDefStat": True,
        "SRC:RF:FSDefStat": True,
        "PPS:HV:PermStat": True,
        "LEBT:HV_PS:ExtSec": True,
    }
    _publish_many(pv, values)
    _evaluate_interlock_equations_without_plant(engine)
    assert engine.context.interlocks["HV:ENABLE"] is True

    controls.set_device_fault("hv", True)
    _evaluate_interlock_equations_without_plant(engine)
    assert engine.context.interlocks["HV:ENABLE"] is False
    assert pv.get("SRC:RF:FSDefStat") is True


def test_legacy_relationships_are_exposed_separately():
    engine, pv, _ = build_application()
    _publish_many(
        pv,
        {
            "LEBT:R_PS:OnStat": True,
            "LEBT:SOL01:FSDefStat": True,
            "LEBT:SOL02:FSDefStat": True,
            "LEBT:VAC01:SGVCDefStat": True,
            "LEBT:VAC02:SGVCDefStat": True,
            "LEBT:FC:InStat": True,
            "LEBT:GV:CloseStat": True,
            "LEBT:CHOP:InStat": True,
            "LEBT:CHOP_PS:OnStat": True,
        },
    )
    _evaluate_interlock_equations_without_plant(engine)

    assert engine.context.interlocks["LEGACY:MPS:FOCALIZATION:OK"] is True
    assert engine.context.interlocks["LEGACY:MPS:VACUUM:OK"] is True
    assert engine.context.interlocks["LEGACY:MPS:GV_PROTECTION"] is True
    assert engine.context.interlocks["LEGACY:MPS:CHOPPER:STATUS"] is True
