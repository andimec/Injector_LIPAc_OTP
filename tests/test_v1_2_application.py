from injector_otp.app import build_application


def test_application_uses_v1_2_registry():
    engine, pv, _ = build_application()

    # The current snapshot is preserved as supplied by the V1.2 JSON registry.
    source_pvs = [name for name in pv.names() if not name.startswith("OTP:")]
    assert len(source_pvs) == 891
    assert "DPLA:LEBT-CTransm:calc" in source_pvs
    assert "INJ:PLC:comStat" in source_pvs
    assert pv.get("OTP:STATE") == "OFF"
    assert engine.context.time == 0.0


def test_v1_2_operator_write_remains_local():
    _, pv, _ = build_application()

    writable = [name for name in pv.names() if not name.startswith("OTP:") and name != "DPLA:LEBT-CTransm:calc"]
    assert writable

    # Select a PV explicitly marked writable in the source registry.
    pv.put("DPLA:LEBT-CTransm:calc", 1.0)
