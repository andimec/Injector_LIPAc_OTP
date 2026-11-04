import pytest

from injector_otp.app import build_application
from injector_otp.core.pv_registry_loader import load_v1_2_registry, load_v2_0_registry


def test_application_defaults_to_reconciled_v2_registry():
    engine, pv, _ = build_application()

    # V2.0 is the union of snapshot, standalone DB and current OPI references.
    assert len(load_v2_0_registry()) == 1052
    assert len(pv.names()) == 1054   # 1052 Injector/SNL PV references + two OTP runtime PVs
    assert "DPLA:LEBT-CTransm:calc" in pv.names()
    assert "INJ:PLC:comStat" in pv.names()
    assert pv.get("SIM:STATE") == "OFF"
    assert engine.context.time == 0.0


def test_v1_2_snapshot_is_still_available_unchanged():
    assert len(load_v1_2_registry()) == 891


def test_v2_unresolved_source_pv_is_not_operator_writable():
    _, pv, _ = build_application()

    with pytest.raises(PermissionError):
        pv.put("DPLA:LEBT-CTransm:calc", 1.0)


def test_v2_verified_pilot_input_is_operator_writable():
    _, pv, _ = build_application()

    pv.put("SRC:COIL01_PS:ISet", 41.6)
    assert pv.get("SRC:COIL01_PS:ISet") == 41.6


def test_pps_external_condition_is_not_operator_writable():
    _, pv, _ = build_application()

    with pytest.raises(PermissionError):
        pv.put("PPS:HV:PermStat", False)
