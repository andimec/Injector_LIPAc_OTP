"""End-to-end EMU operation from Python PV state without EPICS.

These are state/command and source-geometry tests; synthetic FACQ ticks do
NOT imply real beam physics or acquisition accuracy.
"""
import pytest

from injector_otp.app import build_application
from injector_otp.models.emu_sequencer import EmuStage, EmuMode


def emu(engine):
    return next(x for x in engine.models[0].components if x.name == "emu_scan")


def ready_engine():
    engine, pv, faults = build_application()
    assert pv.get("LEBT:EMIT:ExtSec")
    return engine, pv, faults


def tick_until(engine, condition, maximum=1000):
    for _ in range(maximum):
        engine.step()
        if condition():
            return True
    return False


def configure_roi(pv):
    pv.put("LEBT:EMIT:AnglePicInit", -8.0)
    pv.put("LEBT:EMIT:AnglePicEnd", 8.0)
    pv.put("LEBT:EMIT:AngleDelta", 15.0)
    pv.put("LEBT:EMIT:Energy", 100.0)
    pv.put("LEBT:EMIT:Borderup", 129.0)
    pv.put("LEBT:EMIT:Borderlow", 127.0)
    pv.put("LEBT:EMIT:Nptemit", 4)
    pv.put("LEBT:EMIT:Pasmotdet", 1.0)
    pv.put("LEBT:EMIT:Validate", 1)


def test_model_and_pv_field_aliases_exist():
    engine, pv, _ = ready_engine()
    assert pv.get("LEBT:EMIT:MOTOR.DMOV") == 0
    assert pv.get("LEBT:EMIT_PS1:OnOffCmd.RVAL") == 0
    assert any(x.name == "emu_motor" for x in engine.models[0].components)
    assert any(x.name == "emu_plates" for x in engine.models[0].components)


def test_validate_emittance_geometry_and_complete_small_scan():
    engine, pv, _ = ready_engine()
    configure_roi(pv)
    engine.step()
    assert pv.get("LEBT:EMIT:Validate") == 0
    assert pv.get("LEBT:EMIT:Upper") == pytest.approx(1.0)
    assert pv.get("LEBT:EMIT:Lower") == pytest.approx(3.0)
    assert pv.get("LEBT:EMIT:Vstep") > 0
    assert pv.get("LEBT:EMIT:Vpic") < 0

    pv.put("LEBT:EMIT:Actemit", 1)
    assert tick_until(engine, lambda: emu(engine).stage in {
        EmuStage.COMPLETE, EmuStage.ABORTED
    }, maximum=1200)
    assert emu(engine).stage == EmuStage.COMPLETE, emu(engine).message
    assert len(emu(engine).samples) > 5
    assert emu(engine).samples[0].mode == EmuMode.EMITTANCE
    assert [s.motor_mm for s in emu(engine).samples] == sorted(
        [s.motor_mm for s in emu(engine).samples]
    )
    assert pv.get("LEBT:EMIT:Actemit") == 0
    assert pv.get("LEBT:EMIT_PS1:VSet") == 0
    assert pv.get("LEBT:EMIT_PS2:VSet") == 0


def test_emittance_scan_requires_validation_and_preserves_motor_safety():
    engine, pv, _ = ready_engine()
    pv.put("LEBT:EMIT:Actemit", 1)
    engine.step()
    assert emu(engine).stage == EmuStage.ABORTED
    assert pv.get("LEBT:EMIT:Actemit") == 0
    assert pv.get("LEBT:EMIT:MOTOR.VAL") == 0


def test_emu_emergency_external_safety_blocks_movement():
    engine, pv, _ = ready_engine()
    pv.publish("LEBT:EMIT:ExtSec", False)
    pv.put("LEBT:EMIT:Actscan", 1)
    engine.step()
    assert emu(engine).stage == EmuStage.ABORTED
    assert pv.get("LEBT:EMIT_PS1:VSet") == 0


def test_wide_scan_reconstructs_source_plate_voltage_difference():
    engine, pv, _ = ready_engine()
    pv.put("LEBT:EMIT:Debscanl", 100.0)
    pv.put("LEBT:EMIT:Finscanl", -100.0)
    pv.put("LEBT:EMIT:Passcanl", 100.0)
    pv.put("LEBT:EMIT:Actscan", 1)
    assert tick_until(engine, lambda: emu(engine).stage in {
        EmuStage.COMPLETE, EmuStage.ABORTED
    }, maximum=350)
    assert emu(engine).stage == EmuStage.COMPLETE, emu(engine).message
    assert [x.voltage_set_V for x in emu(engine).samples] == [
        200.0, 0.0, -200.0
    ]


def test_pause_freezes_scan_progress_then_resumes():
    engine, pv, _ = ready_engine()
    pv.put("LEBT:EMIT:Debscanl", 200.0)
    pv.put("LEBT:EMIT:Finscanl", -200.0)
    pv.put("LEBT:EMIT:Passcanl", 100.0)
    pv.put("LEBT:EMIT:Actscan", 1)
    assert tick_until(engine, lambda: emu(engine).stage == EmuStage.WAIT_ACQUISITION, 180)
    pv.put("LEBT:EMIT:Pausemit", 1)
    engine.step()
    assert emu(engine).stage == EmuStage.PAUSED
    before = len(emu(engine).samples)
    for _ in range(30):
        engine.step()
    assert len(emu(engine).samples) == before
    pv.put("LEBT:EMIT:Pausemit", 0)
    assert tick_until(engine, lambda: emu(engine).stage == EmuStage.COMPLETE, 300)
    assert len(emu(engine).samples) == 5


def test_fault_during_active_emu_scan_aborts_and_removes_plate_setpoints():
    engine, pv, _ = ready_engine()
    pv.put("LEBT:EMIT:Debscanl", 100)
    pv.put("LEBT:EMIT:Finscanl", -100)
    pv.put("LEBT:EMIT:Passcanl", 100)
    pv.put("LEBT:EMIT:Actscan", 1)
    engine.step()
    engine.control_plane.set_device_fault("emu_motor", True)
    engine.step()
    assert emu(engine).stage == EmuStage.ABORTED
    assert pv.get("LEBT:EMIT_PS1:VSet") == 0
    assert pv.get("LEBT:EMIT_PS2:VSet") == 0
