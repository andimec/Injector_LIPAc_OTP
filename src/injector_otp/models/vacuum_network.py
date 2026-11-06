"""Reduced-order, fault-injectable VAC01/VAC02 vacuum network.

OFFLINE TRAINING MODEL, not Leybold firmware or PLC safety implementation.
Three volumes per station: chamber C, turbo inlet T, foreline F. VAC01
has NIV; VAC02 deliberately has NO physical NIV. The source MFCs inject
H2/D2 to VAC01; auxiliary LEBT MFC injects Kr to VAC02.

The configured pumpdown duration calibrates an effective residual-gas
pumpdown trajectory. Manufacturer N2/H2 nominal pumping speeds enter the
gas-throughput response separately. Unknown conductances, gas delivery
fractions and gauge gas corrections remain training assumptions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import exp, isfinite
from pathlib import Path

from .base import SubsystemModel
from .catalog import DeviceCatalog
from .vacuum_calibration import FlowPressureCurve, PumpdownProfile, sccm_to_throughput


COMPONENTS = ("residual", "H2", "D2", "Kr", "N2")


@dataclass
class VacuumPump:
    """Independent device status for external fault procedures."""
    name: str
    running: bool = False
    fault: bool = False
    speed_fraction: float = 0.0


@dataclass
class VacuumGauge:
    name: str
    fault: bool = False
    last_value_mbar: float | None = None


@dataclass
class VacuumStation:
    prefix: str
    config: dict
    profile: PumpdownProfile
    pressure: dict[str, dict[str, float]]
    pp: VacuumPump
    tp: VacuumPump
    gauges: dict[str, VacuumGauge] = field(default_factory=dict)

    def total(self, volume: str) -> float:
        return sum(self.pressure[volume].values())

    def volume_l(self, volume: str) -> float:
        return float(self.config.get("volumes_l", {}).get(
            volume, {"C": 180.0, "T": 30.0, "F": 20.0}[volume]))


def _equalize(
    a: dict[str, float], va: float, b: dict[str, float], vb: float,
    conductance_l_s: float, dt: float,
) -> None:
    """Conservative finite-volume exchange, exact for two well-mixed nodes."""
    if conductance_l_s <= 0:
        return
    fraction = -__import__("math").expm1(-conductance_l_s * (1 / va + 1 / vb) * dt)
    for species in COMPONENTS:
        avg = (va * a[species] + vb * b[species]) / (va + vb)
        pa, pb = a[species], b[species]
        a[species] = max(0.0, pa + fraction * (avg - pa))
        b[species] = max(0.0, pb + fraction * (avg - pb))


def _pump(p: dict[str, float], volume_l: float, speed_l_s: float,
          dt: float, floor_mbar: float = 0.0, species: str | None = None) -> None:
    if speed_l_s <= 0:
        return
    decay = exp(-min(700.0, speed_l_s * dt / volume_l))
    keys = [species] if species is not None else list(COMPONENTS)
    for gas in keys:
        floor = floor_mbar if gas == "residual" else 0.0
        p[gas] = max(0.0, floor + (p[gas] - floor) * decay)


def _vent(p: dict[str, float], dt: float, tau_s: float,
          atmospheric_pressure_mbar: float) -> None:
    """Controlled ideal N2 admission; never pressurizes above atmosphere."""
    if tau_s <= 0:
        raise ValueError("Venting time constant must be positive")
    current = sum(p.values())
    target = atmospheric_pressure_mbar
    difference = (target - current) * (-__import__("math").expm1(-dt / tau_s))
    if difference >= 0:
        p["N2"] += difference
    elif current > 0:
        factor = max(0.0, (current + difference) / current)
        for species in COMPONENTS:
            p[species] *= factor


class VacuumNetworkModel(SubsystemModel):
    """Single writer for all vacuum pump and gauge PV readbacks."""

    name = "vacuum_network"

    def __init__(self, catalog: DeviceCatalog, params: dict) -> None:
        super().__init__()
        self.catalog = catalog
        self.params = params
        settings = params.get("vacuum", {})
        self.settings = settings
        self._previous_commands: dict[str, bool] = {}
        self.stations: dict[str, VacuumStation] = {}
        self.curves: dict[str, FlowPressureCurve] = {}

        for short in ("VAC01", "VAC02"):
            station_cfg = dict(settings.get("stations", {}).get(short, {}))
            profile = PumpdownProfile(**station_cfg.get("pumpdown", {}))
            initial = float(station_cfg.get(
                "initial_pressure_mbar", settings.get("initial_pressure_mbar", 1e-6)))
            if initial < 0 or not isfinite(initial):
                raise ValueError(f"Invalid initial pressure for {short}")
            for volume in ("C", "T", "F"):
                if float(station_cfg.get("volumes_l", {}).get(
                        volume, {"C": 180, "T": 30, "F": 20}[volume])) <= 0:
                    raise ValueError("Vacuum volumes must be positive")
            prefix = f"LEBT:{short}"
            pressure = {v: {gas: (initial if gas == "residual" else 0.0)
                             for gas in COMPONENTS} for v in ("C", "T", "F")}
            self.stations[short] = VacuumStation(
                prefix, station_cfg, profile, pressure,
                VacuumPump(f"{prefix}:PP"), VacuumPump(f"{prefix}:TP"),
                {key: VacuumGauge(f"{prefix}:{key}")
                 for key in ("PGVC", "SGVC", "PGTP", "SGTP")})
        for source, file_path in settings.get("flow_pressure_csv", {}).items():
            self.curves[source] = FlowPressureCurve.from_csv(Path(file_path))

    def _edge(self, context, name: str) -> bool:
        current = bool(context.pv.get(name, 0))
        past = self._previous_commands.get(name, False)
        self._previous_commands[name] = current
        return current and not past

    def _is_open(self, context, prefix: str) -> bool:
        return bool(context.metrics.get(f"{prefix}.open", 0.0))

    def _emit(self, context, name: str, value: object) -> None:
        if self.catalog.has(name):
            context.emit(name, value, "vacuum_network")

    def _pump_commands(self, station: VacuumStation, dt: float, context) -> None:
        p = station.prefix
        pp, tp = station.pp, station.tp
        pp.fault = bool(context.device_faults.get(pp.name, False))
        tp.fault = bool(context.device_faults.get(tp.name, False))
        pp_on = self._edge(context, f"{p}:PPOnCmd")
        pp_off = self._edge(context, f"{p}:PPOffCmd")
        tp_on = self._edge(context, f"{p}:TPOnCmd")
        tp_off = self._edge(context, f"{p}:TPOffCmd")
        if pp_off or pp.fault:
            pp.running = False
        elif pp_on:
            pp.running = True
        if tp_off or tp.fault:
            tp.running = False
        elif tp_on:
            # Physical training guard only, NOT a claim about Siemens PLC.
            max_foreline = float(station.config.get("max_foreline_start_mbar", 3.0))
            if (pp.running and self._is_open(context, f"{p}:PV")
                    and station.total("F") <= max_foreline):
                tp.running = True
        runup = float(station.config.get("tp_acceleration_s", 600.0))
        rundown = float(station.config.get("tp_deceleration_s", 600.0))
        if min(runup, rundown) <= 0:
            raise ValueError("TP ramp times must be positive")
        increment = dt / (runup if tp.running else rundown)
        tp.speed_fraction = max(0.0, min(1.0, tp.speed_fraction
                              + (increment if tp.running else -increment)))
        nominal = tp.speed_fraction >= 0.999999 and not tp.fault
        self._emit(context, f"{p}:PPOnStat", int(pp.running))
        self._emit(context, f"{p}:TPOnStat", int(tp.running))
        self._emit(context, f"{p}:TPSpeedStat", int(nominal))
        self._emit(context, f"{p}:TPDefStat", int(not tp.fault))
        context.metrics[f"{p}:TP.speed_fraction"] = tp.speed_fraction
        context.metrics[f"{p}:PP.fault"] = float(pp.fault)
        context.metrics[f"{p}:TP.fault"] = float(tp.fault)
        context.metrics[f"{p}:TP.speed_70_percent_or_less"] = float(
            not tp.running and 0.0 < tp.speed_fraction <= 0.70)

    def _apply_sources(self, station: VacuumStation, dt: float, context) -> None:
        cfg = self.settings
        default_sources = {
            "SRC:MFCH": {"species": "H2", "station": "VAC01"},
            "SRC:MFCD": {"species": "D2", "station": "VAC01"},
            "LEBT:MFC": {"species": "Kr", "station": "VAC02"},
        }
        source_cfg = cfg.get("gas_sources", default_sources)
        gas_cfg = self.params.get("gas", {})
        reference_temperature = float(gas_cfg.get("reference_temperature_K", 273.15))
        reference_pressure = float(gas_cfg.get("reference_pressure_mbar", 1013.25))
        temperature = float(station.config.get("temperature_K", 293.15))
        turbo_ready = (station.tp.running and station.tp.speed_fraction >= 0.999999
                       and station.pp.running
                       and self._is_open(context, f"{station.prefix}:PV")
                       and self._is_open(context, f"{station.prefix}:SV"))
        for prefix, source in source_cfg.items():
            if source.get("station") != station.prefix.split(":")[-1]:
                continue
            species = source["species"]
            if species not in COMPONENTS or species == "residual":
                raise ValueError(f"Unsupported MFC gas species {species}")
            flow = max(0.0, float(context.metrics.get(f"{prefix}.flow_sccm", 0.0)))
            fraction = float(source.get("delivery_fraction", 1.0))
            if not 0 <= fraction <= 1:
                raise ValueError("delivery_fraction must lie within [0,1]")
            flow *= fraction
            if prefix in self.curves and turbo_ready:
                # Equilibrium data are pressure *increments* above no-flow.
                target = self.curves[prefix].value(flow)
                tau = float(station.config.get("flow_response_tau_s", 5.0))
                if tau <= 0:
                    raise ValueError("flow_response_tau_s must be positive")
                current = station.pressure["C"][species]
                station.pressure["C"][species] = (
                    target + (current - target) * exp(-dt / tau))
            else:
                q = sccm_to_throughput(
                    flow, reference_pressure_mbar=reference_pressure,
                    reference_temperature_K=reference_temperature,
                    gas_temperature_K=temperature)
                station.pressure["C"][species] += q * dt / station.volume_l("C")
            context.metrics[f"{prefix}.throughput_mbar_l_s"] = sccm_to_throughput(
                flow, reference_pressure_mbar=reference_pressure,
                reference_temperature_K=reference_temperature,
                gas_temperature_K=temperature)

    def _evolve_station(self, station: VacuumStation, dt: float, context) -> None:
        p, cfg, prof = station.prefix, station.config, station.profile
        C, T, F = (station.pressure[v] for v in ("C", "T", "F"))
        vc, vt, vf = (station.volume_l(v) for v in ("C", "T", "F"))
        pp = station.pp.running and not station.pp.fault
        tp_speed = station.tp.speed_fraction if not station.tp.fault else 0.0
        pv = self._is_open(context, f"{p}:PV")
        sv = self._is_open(context, f"{p}:SV")

        self._apply_sources(station, dt, context)
        leak = float(cfg.get("leak_throughput_mbar_l_s", 0.0))
        if leak < 0:
            raise ValueError("Leak throughput must be nonnegative")
        if (context.device_faults.get(f"{p}:CHAMBER_LEAK", False)
                or "VACUUM_LOSS" in context.faults):
            leak += float(cfg.get("fault_leak_throughput_mbar_l_s", 1e-3))
        C["residual"] += leak * dt / vc

        ambient = float(self.settings.get("atmospheric_pressure_mbar", 1013.25))
        if p == "LEBT:VAC01" and self._is_open(context, f"{p}:NIV"):
            _vent(C, dt, float(cfg.get("vent_tau_s", 120.0)), ambient)
        if self._is_open(context, f"{p}:AIV"):
            _vent(T, dt, float(cfg.get("vent_tau_s", 120.0)), ambient)
        if bool(context.pv.get(f"{p}:LTVOpenStat", False)):
            _vent(F, dt, float(cfg.get("vent_tau_s", 120.0)), ambient)

        if sv:
            _equalize(C, vc, T, vt,
                      float(cfg.get("sv_conductance_l_s", 10000.0)), dt)
        if tp_speed <= 0.0:
            _equalize(T, vt, F, vf,
                      float(cfg.get("stopped_tp_conductance_l_s", 10000.0)), dt)

        if pp and pv:
            # Effective PP speed derived from configured roughing time.
            effective_rough_speed = (vc + vt + vf) / prof.roughing_tau_s
            _pump(F, vf, effective_rough_speed, dt,
                  floor_mbar=prof.roughing_floor_mbar)
        if pp and pv and tp_speed > 0:
            # Slow residual pumpdown reflects uncalibrated chamber outgassing,
            # not the OEM 2400 L/s nominal throughput.
            effective_turbo_speed = (vc + vt) / prof.turbo_tau_s * tp_speed
            _pump(T, vt, effective_turbo_speed, dt,
                  floor_mbar=prof.ultimate_pressure_mbar, species="residual")
            speeds = cfg.get("gas_pumping_speed_l_s",
                             {"H2": 2100.0, "D2": 2100.0,
                              "Kr": 2400.0, "N2": 2400.0})
            for gas in ("H2", "D2", "Kr", "N2"):
                speed = float(speeds.get(gas, 2400.0))
                if speed < 0:
                    raise ValueError("Pumping speed must be nonnegative")
                _pump(T, vt, speed * tp_speed, dt, species=gas)

        # Additional diffusion after pumping: avoid a full-tick C/T lag.
        if sv:
            _equalize(C, vc, T, vt,
                      float(cfg.get("sv_conductance_l_s", 10000.0)), dt)

    def _publish(self, station: VacuumStation, context) -> None:
        p = station.prefix
        for suffix, volume in (("PGVC", "C"), ("SGVC", "C"),
                               ("PGTP", "T"), ("SGTP", "T")):
            gauge = station.gauges[suffix]
            gauge.fault = bool(context.device_faults.get(gauge.name, False))
            reading = station.total(volume)
            if not gauge.fault:
                gauge.last_value_mbar = reading
            elif gauge.last_value_mbar is not None:
                reading = gauge.last_value_mbar
            self._emit(context, f"{p}:Vac{suffix}", reading)
            self._emit(context, f"{p}:{suffix}DefStat", int(not gauge.fault))
            context.metrics[f"{gauge.name}.fault"] = float(gauge.fault)
        for volume, label in (("C", "pressure_mbar"),
                              ("T", "inlet_pressure_mbar"),
                              ("F", "foreline_pressure_mbar")):
            context.metrics[f"{p}.{label}"] = station.total(volume)
        for gas in COMPONENTS:
            context.metrics[f"{p}.partial_{gas}_mbar"] = station.pressure["C"][gas]

    def update(self, dt: float, context) -> None:
        super().update(dt)
        for station in self.stations.values():
            self._pump_commands(station, dt, context)
        for station in self.stations.values():
            self._evolve_station(station, dt, context)
        if self._is_open(context, "LEBT:GV"):
            a, b = self.stations["VAC01"], self.stations["VAC02"]
            _equalize(a.pressure["C"], a.volume_l("C"),
                      b.pressure["C"], b.volume_l("C"),
                      float(self.settings.get("gv_conductance_l_s", 500.0)), dt)
        for station in self.stations.values():
            self._publish(station, context)
