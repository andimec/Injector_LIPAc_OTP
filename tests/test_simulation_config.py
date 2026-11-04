from injector_otp.app import build_application
from injector_otp.config.loader import load_simulation_config
from injector_otp.core.state import InjectorState

def test_default_simulation_config_is_loaded():
    config = load_simulation_config()
    assert config.initial_state == "OFF"
    assert config.timestep_s == 0.1
    assert config.initial_pvs["LEBT:HV:RoomKeyA1"] is True
    assert config.initial_pvs["PPS:BEAM:InhibitStat"] is False

def test_startup_config_initializes_external_conditions_without_overriding_calculated_outputs():
    engine, pv, _ = build_application()
    assert engine.context.state == InjectorState.OFF
    assert pv.get("LEBT:HV:RoomKeyA1") is True
    assert pv.get("LEBT:VAC01:SGVCDefStat") is True
    engine.step()
    assert engine.context.interlocks["HV:ENABLE"] is False
    assert pv.get("PPS:HV:PermStat") is True

def test_startup_config_rejects_unknown_pv():
    import tempfile
    from pathlib import Path
    bad = "simulation:\n  initial_state: OFF\ninitial_pvs:\n  DOES_NOT_EXIST: true\n"
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "bad.yaml"
        path.write_text(bad, encoding="utf-8")
        try:
            build_application(simulation_config_path=path)
        except ValueError as exc:
            assert "not present in the PV registry" in str(exc)
        else:
            raise AssertionError("Unknown startup PV was accepted")