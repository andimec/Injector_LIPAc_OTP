import pytest

from injector_otp.epics.contract import SimulationIOCContract
from injector_otp.epics.simulation_backend import SimulationPVBackend
from injector_otp.pv.state import SimulationPVState


def test_simulation_namespace_is_explicit():
    backend = SimulationPVBackend()
    backend.define("LEBT:TEST", 1.0, writable=True)

    assert backend.names() == ["OTP:LEBT:TEST"]
    assert backend.get("LEBT:TEST") == 1.0


def test_operator_write_stays_inside_simulation_namespace():
    backend = SimulationPVBackend()
    backend.define("LEBT:TEST", 1.0, writable=True)

    backend.put("LEBT:TEST", 2.0)

    assert backend.get("OTP:LEBT:TEST") == 2.0


def test_production_source_name_is_mapped_to_simulation_namespace():
    assert (
        SimulationIOCContract.simulation_name("SRC:COIL01_PS:ISet")
        == "OTP:SRC:COIL01_PS:ISet"
    )


def test_non_simulation_name_cannot_bypass_contract():
    with pytest.raises(PermissionError):
        SimulationIOCContract.require_simulation_namespace("LEBT:TEST")


def test_simulation_state_rejects_unresolved_external_write():
    state = SimulationPVState()
    state.define("PPS:HV:PermStat", False)

    with pytest.raises(PermissionError):
        state.put("PPS:HV:PermStat", True)


def test_simulation_state_accepts_only_explicit_inputs():
    state = SimulationPVState(writable_names={"SRC:COIL01_PS:ISet"})
    state.define("SRC:COIL01_PS:ISet", 0.0)
    state.define("SRC:COIL01_PS:IRdbk", 0.0)

    state.put("SRC:COIL01_PS:ISet", 41.6)
    assert state.get("SRC:COIL01_PS:ISet") == 41.6

    with pytest.raises(PermissionError):
        state.put("SRC:COIL01_PS:IRdbk", 41.6)


def test_simulation_state_outputs_are_published_by_python():
    state = SimulationPVState()
    state.define("SRC:COIL01_PS:IRdbk", 0.0)

    state.publish("SRC:COIL01_PS:IRdbk", 12.3, source="coil01_model")

    record = state.record("SRC:COIL01_PS:IRdbk")
    assert record.value == 12.3
    assert record.source == "coil01_model"
    assert record.timestamp > 0
