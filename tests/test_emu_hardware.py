"""EMU motor/plate equipment response and bounded wait regressions."""
from injector_otp.core.engine import SimulationContext
from injector_otp.models.catalog import DeviceCatalog
from injector_otp.models.emu_hardware import EmuMotorModel, EmuPlatePSModel
from injector_otp.models.emu_sequencer import (
    EmuScanSequencer, EmuSequenceSettings, EmuStage, EmuMode, EmuTarget
)


def catalog():
    return DeviceCatalog.from_registry("config/pv_registry_v2_0.json")


def test_motor_soft_limit_does_not_move_to_invalid_target():
    model=EmuMotorModel(catalog(), {"rate_mm_s": 20})
    ctx=SimulationContext(pv={
        "LEBT:EMIT:MOTOR.VAL": 200,
        "LEBT:EMIT:MOTOR.CNEN": "Enable",
        "LEBT:EMIT_SERV:EnaDisa": 1,
        "LEBT:EMIT:ExtSec": 1,
        "LEBT:EMIT:FSDefStat": 1,
        "LEBT:EMIT:MOTOR.SPMG": "Go",
    })
    model.update(1, ctx)
    assert model.position_mm == 0
    assert ctx.outputs["LEBT:EMIT:MOTOR.LVIO"][0] == 1
    assert ctx.outputs["LEBT:EMIT:MOTOR.DMOV"][0] == 0
    assert ctx.outputs["LEBT:EMIT:MOTOR.MOVN"][0] == 0


def test_motor_status_and_position_polarity_from_original_db():
    model=EmuMotorModel(catalog(), {"rate_mm_s": 10})
    ctx=SimulationContext(pv={
        "LEBT:EMIT:MOTOR.VAL": 5,
        "LEBT:EMIT:MOTOR.CNEN": "Enable",
        "LEBT:EMIT_SERV:EnaDisa": 1,
        "LEBT:EMIT:ExtSec": 1,
        "LEBT:EMIT:FSDefStat": 1,
        "LEBT:EMIT:MOTOR.SPMG": "Go",
    })
    model.update(0.1, ctx)
    assert ctx.outputs["LEBT:EMIT:MOTOR.MOVN"][0] == 1
    assert ctx.outputs["LEBT:EMIT:MOTOR.DMOV"][0] == 0
    assert ctx.outputs["LEBT:EMIT:Position"][0] == -1.0
    model.update(0.5, ctx)
    assert ctx.outputs["LEBT:EMIT:MOTOR.RBV"][0] == 5.0
    assert ctx.outputs["LEBT:EMIT:MOTOR.DMOV"][0] == 1


def test_two_plate_readbacks_and_original_vht_setpoint_equation():
    model=EmuPlatePSModel(catalog(), {"plate_rate_V_s": 1000})
    ctx=SimulationContext(pv={
        "LEBT:EMIT_PS1:Softbo": 1, "LEBT:EMIT_PS2:Softbo": 1,
        "LEBT:EMIT_PS1:VSet": 200, "LEBT:EMIT_PS2:VSet": -200,
    })
    model.update(0.1,ctx)
    assert ctx.outputs["LEBT:EMIT_PS1:OnOffCmd.RVAL"][0] == 1
    assert ctx.outputs["LEBT:EMIT:Vht"][0] == 400
    assert ctx.outputs["LEBT:EMIT:VhtRdbk"][0] == 200


def test_missing_fast_acquisition_event_times_out_instead_of_waiting_forever():
    model=EmuScanSequencer(
        catalog(), EmuSequenceSettings(acquisition_timeout_s=0.2)
    )
    model.mode=EmuMode.WIDE
    model.stage=EmuStage.WAIT_ACQUISITION
    model.targets=[EmuTarget(0,0)]
    ctx=SimulationContext(pv={
        "LEBT:EMIT:Actscan": 1,
        "LEBT:EMIT:ExtSec": 1,
        "LEBT:EMIT:FSDefStat": 1,
        "LEBT:EMIT:MOTOR.RBV": 0,
    })
    for _ in range(3):
        model.update(0.1,ctx)
    assert model.stage == EmuStage.ABORTED
    assert ctx.command_requests["LEBT:EMIT_PS1:VSet"][0] == 0
