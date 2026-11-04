"""Gas/vacuum architecture tests grounded in Injector LCS Manual v4.0.

Section 3.2 documents a separate PR4000B for LEBT auxiliary injection,
distinct from source H2 and D2. These tests verify *model topology*,
not quantitative vacuum pressure calibration.
"""
from injector_otp.core.engine import SimulationContext
from injector_otp.models.catalog import DeviceCatalog
from injector_otp.models.plant import GasFlowController, VacuumRegionModel


def _catalog():
    return DeviceCatalog.from_registry("config/pv_registry_v2_0.json")


def test_auxiliary_lebt_mfc_has_independent_valve_and_flow_readback():
    model = GasFlowController("LEBT:MFC", None, _catalog(), {"gas": {"response_tau_s": 0.2}})
    context = SimulationContext(
        pv={"LEBT:MFC:OpenCmd": 1, "LEBT:MFC:Debit": 2.0}
    )
    model.update(1.0, context)
    assert context.metrics["LEBT:MFC.flow_sccm"] > 1.9
    assert context.outputs["LEBT:MFC:Deb1Mes"][0] > 1.9


def test_source_flow_affects_vac01_not_lebt_auxiliary_vac02():
    cat = _catalog()
    settings = {"vacuum": {
        "initial_pressure_mbar": 1e-6,
        "leak_rate_mbar_s": 0,
        "gas_coupling_mbar_s_per_sccm": 1e-6,
        "flow_sources": {
            "LEBT:VAC01": ["SRC:MFCD", "SRC:MFCH"],
            "LEBT:VAC02": ["LEBT:MFC"],
        }
    }}
    context = SimulationContext(
        metrics={"SRC:MFCD.flow_sccm": 2.0, "LEBT:MFC.flow_sccm": 0.0}
    )
    vac1 = VacuumRegionModel("LEBT:VAC01", cat, settings)
    vac2 = VacuumRegionModel("LEBT:VAC02", cat, settings)
    vac1.update(1.0, context)
    vac2.update(1.0, context)
    assert vac1.pressure_mbar > vac2.pressure_mbar


def test_chopper_state_db_type_supports_opi_armed_value_two():
    definition = _catalog().get("LEBT:CHOP_IM:StmState")
    assert definition.record_type == "longin"
