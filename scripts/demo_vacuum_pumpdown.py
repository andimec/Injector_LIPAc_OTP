#!/usr/bin/env python3
"""Offline pumpdown demonstration, with NO EPICS, IOC or PLC connection.

Examples:
  python scripts/demo_vacuum_pumpdown.py --hours 1 --csv /tmp/pumpdown.csv
  python scripts/demo_vacuum_pumpdown.py --hours 3
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import yaml

from injector_otp.core.engine import SimulationContext
from injector_otp.models.catalog import DeviceCatalog
from injector_otp.models.plant import ValveDevice
from injector_otp.models.vacuum_network import VacuumNetworkModel


def run(*, config: Path, station: str, hours: float | None,
        start_pressure: float, dt: float, limit_hours: float,
        output_csv: Path | None = None) -> tuple[float | None, float]:
    if min(start_pressure, dt, limit_hours) <= 0:
        raise ValueError("Pressure, timestep and time limit must be positive")
    params = yaml.safe_load(config.read_text(encoding="utf-8"))
    settings = params.setdefault("vacuum", {})
    station_config = settings.setdefault("stations", {}).setdefault(station, {})
    station_config["initial_pressure_mbar"] = start_pressure
    profile_config = station_config.setdefault("pumpdown", {})
    if hours is not None:
        if hours <= 0:
            raise ValueError("--hours must be positive")
        profile_config["pumpdown_time_h"] = hours

    catalog = DeviceCatalog.from_registry("config/pv_registry_v2_0.json")
    model = VacuumNetworkModel(catalog, params)
    prefix = f"LEBT:{station}"
    pv_name = lambda suffix: f"{prefix}:{suffix}"
    valves = [ValveDevice(f"{prefix}:PV", catalog),
              ValveDevice(f"{prefix}:SV", catalog)]

    ctx = SimulationContext(pv={
        pv_name("PPOnCmd"): 1,
        pv_name("PVOpenCmd"): 1,
        pv_name("SVOpenCmd"): 1,
        pv_name("TPOnCmd"): 0,
    })
    target = model.stations[station].profile.target_pressure_mbar
    roughing_end = model.stations[station].profile.roughing_end_pressure_mbar
    started_tp = False
    reached = None
    rows = []
    n = int(limit_hours * 3600 / dt)
    for k in range(n + 1):
        for valve in valves:
            valve.update(dt, ctx)
        if not started_tp and model.stations[station].total("C") <= roughing_end:
            started_tp = True
            ctx.pv[pv_name("TPOnCmd")] = 1
        model.update(dt, ctx)
        time_s = (k + 1) * dt
        pressure = ctx.metrics[f"{prefix}.pressure_mbar"]
        if k == 0 or k % max(1, int(10 / dt)) == 0 or pressure <= target:
            rows.append({
                "time_s": round(time_s, 6),
                "chamber_mbar": pressure,
                "turbo_inlet_mbar": ctx.metrics[f"{prefix}.inlet_pressure_mbar"],
                "foreline_mbar": ctx.metrics[f"{prefix}.foreline_pressure_mbar"],
                "tp_speed_fraction": ctx.metrics[f"{prefix}:TP.speed_fraction"],
                "pp_on": int(model.stations[station].pp.running),
                "tp_on": int(model.stations[station].tp.running),
            })
        if pressure <= target:
            reached = time_s
            break

    if output_csv is not None:
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        with output_csv.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    return reached, ctx.metrics[f"{prefix}.pressure_mbar"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path,
                        default=Path("config/model_parameters.yaml"))
    parser.add_argument("--station", choices=("VAC01", "VAC02"),
                        default="VAC01")
    parser.add_argument("--hours", type=float,
                        help="Override the configured reference pumpdown hours")
    parser.add_argument("--initial-pressure", type=float,
                        default=1013.25, help="Starting absolute chamber pressure mbar")
    parser.add_argument("--dt", type=float, default=1.0,
                        help="Simulation step in seconds, default 1")
    parser.add_argument("--limit-hours", type=float, default=10.0)
    parser.add_argument("--csv", type=Path,
                        help="Optional pressure time-series CSV output path")
    args = parser.parse_args()
    print("OFFLINE synthetic training simulation. SV commands assume prior",
          "authorization; NO live EPICS or PLC link.")
    reached, final = run(
        config=args.config, station=args.station, hours=args.hours,
        start_pressure=args.initial_pressure, dt=args.dt,
        limit_hours=args.limit_hours, output_csv=args.csv)
    if reached is None:
        print(f"{args.station}: target NOT attained; last P={final:.4e} mbar")
        return 1
    print(f"{args.station}: target reached at {reached:.0f} s "
          f"({reached/3600:.3f} h); P={final:.4e} mbar")
    if args.csv:
        print(f"Saved synthetic pressures to {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
