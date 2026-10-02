import pytest

from injector_otp.epics.contract import SimulationIOCContract
from injector_otp.epics.simulation_backend import SimulationPVBackend


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
