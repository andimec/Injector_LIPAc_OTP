"""Physics/control contracts for configurable vacuum network V1.

Tests are deterministic offline training checks, not pump qualification.
"""
from __future__ import annotations

import math

import pytest

from injector_otp.core.engine import SimulationContext
from injector_otp.models.catalog import DeviceCatalog
from injector_otp.models.injector import InjectorModel
from injector_otp.models.plant import GasFlowController, ValveDevice
from injector_otp.models.vacuum_calibration import (
    FlowPressureCurve, PumpdownProfile, sccm_to_throughput,
)
from injector_otp.models.vacuum_network import VacuumNetworkModel


def catalog():
    return DeviceCatalog.from_registry("config/pv_registry_v2_0.json")


def params(*, duration_h=2.0, initial_01=1e-6):
    return {"vacuum": {
        "atmospheric_pressure_mbar": 1013.25,
        "stations": {
            "VAC01": {"initial_pressure_mbar": initial_01,
                      "tp_acceleration_s": 1.0,
                      "pumpdown": {"pumpdown_time_h": duration_h}},
            "VAC02": {"initial_pressure_mbar": 1e-6},
        },
    }}


def valves(station="VAC01"):
    p = f"LEBT:{station}"
    return {f"{p}:PV.open": 1, f"{p}:SV.open": 1}


def test_pumpdown_profile_hours_scale_time_constants():
    one = PumpdownProfile(pumpdown_time_h=1)
    two = PumpdownProfile(pumpdown_time_h=2)
    three = PumpdownProfile(pumpdown_time_h=3)
    assert two.roughing_tau_s == pytest.approx(2 * one.roughing_tau_s)
    assert three.turbo_tau_s == pytest.approx(3 * one.turbo_tau_s)
    assert one.ultimate_pressure_mbar < one.target_pressure_mbar


def test_invalid_pumpdown_settings_are_rejected():
    with pytest.raises(ValueError):
        PumpdownProfile(pumpdown_time_h=0)
    with pytest.raises(ValueError):
        PumpdownProfile(ultimate_pressure_mbar=1e-4)


def test_faster_profile_reaches_lower_pressure_at_same_elapsed_time():
    pressures = []
    for hours in (1.0, 3.0):
        model = VacuumNetworkModel(catalog(), params(
            duration_h=hours, initial_01=1013.25))
        ctx = SimulationContext(
            pv={"LEBT:VAC01:PPOnCmd": 1},
            metrics=valves())
        # PP evacuates through a stopped turbo with PV and SV open.
        for _ in range(1800):
            model.update(1.0, ctx)
        pressures.append(ctx.metrics["LEBT:VAC01.pressure_mbar"])
    assert pressures[0] < pressures[1]
    assert pressures[0] < 0.05


def test_pp_does_not_pump_isolated_chamber():
    model = VacuumNetworkModel(catalog(), params(initial_01=100.0))
    ctx = SimulationContext(
        pv={"LEBT:VAC01:PPOnCmd": 1},
        metrics={"LEBT:VAC01:PV.open": 1, "LEBT:VAC01:SV.open": 0})
    for _ in range(200):
        model.update(1.0, ctx)
    assert ctx.metrics["LEBT:VAC01.pressure_mbar"] == pytest.approx(100.0)


def test_turbo_speed_crosses_seventy_percent_on_shutdown():
    model = VacuumNetworkModel(catalog(), params())
    p = "LEBT:VAC01"
    ctx = SimulationContext(pv={f"{p}:PPOnCmd": 1, f"{p}:TPOnCmd": 1},
                            metrics=valves())
    model.update(1.0, ctx)
    assert ctx.pv[f"{p}:TPSpeedStat"] == 1
    ctx.pv[f"{p}:TPOffCmd"] = 1
    model.update(0.31, ctx)
    assert model.stations["VAC01"].tp.speed_fraction == pytest.approx(1-0.31/600)
    # Override ramp duration to test actual 70% indicator.
    model.stations["VAC01"].config["tp_deceleration_s"] = 1.0
    ctx.pv[f"{p}:TPOffCmd"] = 0
    model.update(0.1, ctx)
    model.update(0.3, ctx)
    assert 0 < model.stations["VAC01"].tp.speed_fraction <= 0.70
    assert ctx.metrics[f"{p}:TP.speed_70_percent_or_less"] == 1.0


def test_gv_exchanges_gas_and_isolates_when_closed():
    model = VacuumNetworkModel(catalog(), params(initial_01=1e-6))
    model.stations["VAC02"].pressure["C"]["residual"] = 1.0
    ctx = SimulationContext()
    model.update(1.0, ctx)
    assert ctx.metrics["LEBT:VAC01.pressure_mbar"] == pytest.approx(1e-6)
    ctx.metrics["LEBT:GV.open"] = 1
    model.update(1.0, ctx)
    assert ctx.metrics["LEBT:VAC01.pressure_mbar"] > 0.1
    assert ctx.metrics["LEBT:VAC02.pressure_mbar"] < 1.0


def test_niv_is_only_physical_on_vac01():
    model = VacuumNetworkModel(catalog(), params())
    ctx = SimulationContext(metrics={"LEBT:VAC02:NIV.open": 1,
                                     "LEBT:VAC01:NIV.open": 1})
    model.update(10.0, ctx)
    assert model.stations["VAC01"].total("C") > 1.0
    assert model.stations["VAC02"].total("C") == pytest.approx(1e-6)
    combined = InjectorModel(catalog(), params())
    assert all(component.name != "LEBT:VAC02:NIV"
               for component in combined.components)


def test_species_flow_affects_correct_station_without_pp():
    model = VacuumNetworkModel(catalog(), params())
    ctx = SimulationContext(metrics={
        "SRC:MFCD.flow_sccm": 2.0,
        "SRC:MFCH.flow_sccm": 0.0,
        "LEBT:MFC.flow_sccm": 0.0,
    })
    model.update(1.0, ctx)
    assert ctx.metrics["LEBT:VAC01.partial_D2_mbar"] > 0
    assert ctx.metrics["LEBT:VAC01.pressure_mbar"] > 1e-6
    assert ctx.metrics["LEBT:VAC02.pressure_mbar"] == pytest.approx(1e-6)


def test_sccm_is_molar_throughput_not_same_mass_for_all_species():
    q = sccm_to_throughput(1, gas_temperature_K=273.15)
    assert q == pytest.approx(0.0168875, rel=1e-5)
    assert sccm_to_throughput(2) == pytest.approx(
        2 * sccm_to_throughput(1))
    with pytest.raises(ValueError):
        sccm_to_throughput(-1)


def test_measured_flow_pressure_csv_is_configurable(tmp_path):
    csv_file = tmp_path / "d2.csv"
    csv_file.write_text(
        "flow_sccm,delta_pressure_mbar\n"
        "0,0\n1,0.000001\n3,0.000005\n",
        encoding="utf-8")
    curve = FlowPressureCurve.from_csv(csv_file)
    assert curve.value(2) == pytest.approx(3e-6)
    assert curve.value(8) == pytest.approx(5e-6)
    settings = params()
    settings["vacuum"]["flow_pressure_csv"] = {"SRC:MFCD": str(csv_file)}
    model = VacuumNetworkModel(catalog(), settings)
    assert "SRC:MFCD" in model.curves


def test_specific_faults_do_not_disable_every_station():
    model = VacuumNetworkModel(catalog(), params())
    ctx = SimulationContext(
        pv={"LEBT:VAC01:PPOnCmd": 1, "LEBT:VAC02:PPOnCmd": 1},
        metrics={**valves("VAC01"), **valves("VAC02")},
        device_faults={"LEBT:VAC01:PP": True, "LEBT:VAC01:SGVC": True})
    model.update(1.0, ctx)
    assert model.stations["VAC01"].pp.fault
    assert ctx.pv["LEBT:VAC01:PPOnStat"] == 0
    assert ctx.pv["LEBT:VAC01:SGVCDefStat"] == 0
    assert ctx.pv["LEBT:VAC02:PPOnStat"] == 1
    assert ctx.pv["LEBT:VAC02:SGVCDefStat"] == 1


def test_valve_fault_freezes_position_and_mfc_fault_zeros_flow():
    c = catalog()
    valve = ValveDevice("LEBT:VAC01:SV", c)
    ctx = SimulationContext(pv={"LEBT:VAC01:SVOpenCmd": 1},
                            device_faults={"LEBT:VAC01:SV": True})
    valve.update(0.1, ctx)
    assert not valve.valve.opened
    assert valve.state.fault
    valve2 = ValveDevice("LEBT:VAC01:PV", c)
    ctx2 = SimulationContext(pv={"LEBT:VAC01:PVOpenCmd": 1})
    valve2.update(0.1, ctx2)
    assert valve2.valve.opened
    ctx2.device_faults["LEBT:VAC01:PV"] = True
    ctx2.pv["LEBT:VAC01:PVCloseCmd"] = 1
    valve2.update(0.1, ctx2)
    assert valve2.valve.opened  # stuck open on injected fault
    mfc = GasFlowController("LEBT:MFC", None, c,
                            {"gas": {"response_tau_s": 0.01}})
    ctx3 = SimulationContext(pv={"LEBT:MFC:OpenCmd": 1,
                                  "LEBT:MFC:Debit": 2},
                             device_faults={"LEBT:MFC": True})
    mfc.update(1.0, ctx3)
    assert mfc.state.fault and ctx3.metrics["LEBT:MFC.flow_sccm"] == 0.0
