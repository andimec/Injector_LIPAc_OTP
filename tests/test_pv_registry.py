from injector_otp.core.pv_registry import PVDirection, load_seed_registry


def test_seed_registry_contains_expected_contract():
    registry = load_seed_registry()

    assert len(registry) == 7
    assert registry.get("SRC:COIL01_PS:ISet").direction is PVDirection.SETPOINT
    assert registry.get("LEBT:FC:InStat").pbs == "04.04.03.04"
    assert registry.get("MPS:INJ:DefStat").model == "mps"
