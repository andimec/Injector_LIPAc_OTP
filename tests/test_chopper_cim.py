"""Chopper CIM training regression tests.

Sources: Injector LCS User Manual v4.0 sections 4.4.1-4.4.4;
Injector_OPI/Chopper_IM/INJ_ChIM_Main_revMA.opi.
"""
from injector_otp.app import build_application
from injector_otp.models.chopper_cim import ChopperCIMModel, CIMState


def test_cim_2026_reference_thresholds_round_trip():
    engine, pv, _ = build_application()
    engine.step()
    assert pv.get("LEBT:CHOP_IM:VmonOffRdbk") == 1000.0
    assert pv.get("LEBT:CHOP_IM:VmonThrRdbk") == 6000.0
    assert pv.get("LEBT:CHOP_IM:AcctThrRdbk") == 5.0
    assert pv.get("LEBT:CHOP_IM:StmState") == CIMState.PRE_ARM


def test_cim_pre_arm_and_armed_follow_original_opi_values():
    engine, pv, _ = build_application()
    pv.put("LEBT:CHOP_IM:StmStateSet", 2)
    engine.step()
    assert pv.get("LEBT:CHOP_IM:StmState") == CIMState.ARMED
    pv.put("LEBT:CHOP_IM:StmStateSet", 1)
    engine.step()
    assert pv.get("LEBT:CHOP_IM:StmState") == CIMState.PRE_ARM


def test_fbi_snapshot_is_captured_only_once_and_remains_latched():
    engine, pv, faults = build_application()
    pv.put("LEBT:CHOP_IM:StmStateSet", 2)
    pv.put("SRC:TIM:Trep", 100)
    pv.put("SRC:TIM:TPulse", 5)
    pv.publish("LEBT:CHOP_IM:CurrentVmon", 7000, source="scenario_measurement")
    pv.publish("LEBT:CHOP_IM:CurrentAcct", 4.2, source="scenario_measurement")
    engine.step()
    assert pv.get("LEBT:CHOP_IM:StmState") == 2

    faults.inject("FBI_TRIGGER")
    engine.step()
    assert pv.get("LEBT:CHOP_IM:Fbi") == 1
    assert pv.get("LEBT:CHOP_IM:FbiStmState") == 2
    assert pv.get("LEBT:CHOP_IM:FbiDPeriod") == 100
    assert pv.get("LEBT:CHOP_IM:FbiDPulse") == 5
    assert pv.get("LEBT:CHOP_IM:FbiVmon") == 7000
    assert pv.get("LEBT:CHOP_IM:FbiAcct") == 4.2

    pv.publish("LEBT:CHOP_IM:CurrentVmon", 300, source="scenario_measurement")
    faults.clear("FBI_TRIGGER")
    engine.step()
    assert pv.get("LEBT:CHOP_IM:Fbi") == 1
    assert pv.get("LEBT:CHOP_IM:FbiVmon") == 7000


def test_cim_thresholds_do_not_spontaneously_reproduce_undocumented_fpga():
    engine, pv, _ = build_application()
    pv.put("LEBT:CHOP_IM:StmStateSet", 2)
    pv.publish("LEBT:CHOP_IM:CurrentVmon", 500, source="scenario_measurement")
    pv.publish("LEBT:CHOP_IM:CurrentAcct", 10, source="scenario_measurement")
    engine.step()
    assert pv.get("LEBT:CHOP_IM:Fbi") == 0
