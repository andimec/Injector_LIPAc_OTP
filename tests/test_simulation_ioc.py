import pytest

from injector_otp.epics.contract import SimulationIOCContract
from injector_otp.epics.simulation_backend import SimulationPVBackend
from injector_otp.epics.bridge import LocalPVBridge
from injector_otp.pv.state import SimulationPVState


def test_native_names_are_preserved():
    backend = SimulationPVBackend()
    backend.define("LEBT:TEST", 1.0, writable=True)
    assert backend.names() == ["LEBT:TEST"]
    assert backend.get("LEBT:TEST") == 1.0
    assert SimulationIOCContract.simulation_name("SRC:COIL01_PS:ISet") == "SRC:COIL01_PS:ISet"


def test_operator_write_uses_native_name_and_allowlist():
    backend = SimulationPVBackend()
    backend.define("LEBT:TEST", 1.0, writable=True)
    backend.put("LEBT:TEST", 2.0)
    assert backend.get("LEBT:TEST") == 2.0


def test_no_namespace_requirement():
    SimulationIOCContract.require_simulation_namespace("LEBT:TEST")
    with pytest.raises(ValueError):
        SimulationIOCContract.require_simulation_namespace("")


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


def test_local_bridge_does_not_rewrite_names():
    state = SimulationPVState()
    state.define("LEBT:SOL01_PS:IRdbk", 0.0)
    bridge = LocalPVBridge(state)
    bridge.push_outputs({"LEBT:SOL01_PS:IRdbk": 12.0})
    assert bridge.pull_inputs()["LEBT:SOL01_PS:IRdbk"] == 12.0


def test_simulation_state_outputs_are_published_by_python():
    state = SimulationPVState()
    state.define("SRC:COIL01_PS:IRdbk", 0.0)
    state.publish("SRC:COIL01_PS:IRdbk", 12.3, source="coil01_model")
    record = state.record("SRC:COIL01_PS:IRdbk")
    assert record.value == 12.3
    assert record.source == "coil01_model"
    assert record.timestamp > 0
