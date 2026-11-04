from injector_otp.core.pv_registry import PVDirection, load_seed_registry
from injector_otp.core.pv_registry_loader import load_v1_2_registry


def test_seed_registry_contains_expected_contract():
    registry = load_seed_registry()

    assert len(registry) == 7
    assert registry.get("SRC:COIL01_PS:ISet").direction is PVDirection.SETPOINT
    assert registry.get("LEBT:FC:InStat").pbs == "04.04.03.04"
    assert registry.get("MPS:INJ:DefStat").model == "mps"


def test_v1_2_read_write_metadata_is_not_mistaken_for_operator_ownership():
    registry = load_v1_2_registry()
    definition = registry.get("SRC:COIL01_PS:ISet")

    # The V1.2 source access flags alone do not define Digital Twin semantics.
    # Runtime ownership is supplied by the explicit override layer.
    assert definition.direction is PVDirection.UNRESOLVED
