import pytest

from injector_otp.app import build_application


def test_application_uses_v1_2_registry():
    engine, pv, _ = build_application()

    # The current snapshot is preserved as supplied by the V1.2 JSON registry.
    simulation_pvs = [name for name in pv.names() if name.startswith("OTP:")]
    assert len(simulation_pvs) == 893
    assert "OTP:DPLA:LEBT-CTransm:calc" in simulation_pvs
    assert "OTP:INJ:PLC:comStat" in simulation_pvs
    assert pv.get("OTP:STATE") == "OFF"
    assert engine.context.time == 0.0


def test_v1_2_unresolved_source_pv_is_not_operator_writable():
    _, pv, _ = build_application()

    with pytest.raises(PermissionError):
        pv.put("DPLA:LEBT-CTransm:calc", 1.0)


def test_v1_2_verified_pilot_input_is_operator_writable():
    _, pv, _ = build_application()

    pv.put("SRC:COIL01_PS:ISet", 41.6)
    assert pv.get("SRC:COIL01_PS:ISet") == 41.6
