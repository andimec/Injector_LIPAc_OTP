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
from math import exp, isfinite, sqrt
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
        # Pumping does not produce gas when a node is already below its floor.
        p[gas] = (p[gas] if p[gas] < floor
                  else max(0.0, floor + (p[gas] - floor) * decay))



def _pumped_pair(
    a: dict[str, float], va: float, b: dict[str, float], vb: float,
    conductance_l_s: float, speed_l_s: float, dt: float, species: str,
    throughput_mbar_l_s: float = 0.0, floor_mbar: float = 0.0,
) -> None:
    """Exact two-node solution for SV conductance and turbo throughput.

    V_a dP_a/dt = Q - C(P_a - P_b)
    V_b dP_b/dt = C(P_a - P_b) - S(P_b - floor).

    Using a stable 2x2 matrix exponential avoids the time-step-dependent
    effective pumping speed of a split conductance/pump solver. The
    constant incoming throughput is applied to the chamber node.
    """
    if min(va, vb) <= 0 or min(conductance_l_s, speed_l_s) <= 0:
        raise ValueError("Volumes, conductance and pumping speed must be positive")
    if throughput_mbar_l_s < 0 or floor_mbar < 0:
        raise ValueError("Throughput and pressure floor must be nonnegative")
    g = conductance_l_s
    s = speed_l_s
    aa, bb = -g / va, g / va
    cc, dd = g / vb, -(g + s) / vb
    mid = (aa + dd) / 2.0
    gap = sqrt(((aa - dd) / 2.0)**2 + bb * cc)
    lam_plus, lam_minus = mid + gap, mid - gap
    divisor = lam_plus - lam_minus
    e_plus, e_minus = exp(min(0.0, lam_plus * dt)), exp(min(0.0, lam_minus * dt))
    m11 = (e_plus * (aa - lam_minus) + e_minus * (lam_plus - aa)) / divisor
    m12 = bb * (e_plus - e_minus) / divisor
    m21 = cc * (e_plus - e_minus) / divisor
    m22 = (e_plus * (dd - lam_minus) + e_minus * (lam_plus - dd)) / divisor
    # Steady state: P_b = floor + Q/S; P_a = P_b + Q/C.
    pb_eq = floor_mbar + throughput_mbar_l_s / s
    pa_eq = pb_eq + throughput_mbar_l_s / g
    pa0, pb0 = a[species] - pa_eq, b[species] - pb_eq
    a[species] = max(0.0, pa_eq + m11 * pa0 + m12 * pb0)
    b[species] = max(0.0, pb_eq + m21 * pa0 + m22 * pb0)


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
            # The chamber starts at the pressure supplied by its external
            # vacuum system. This is an INITIAL condition, not a permanent
            # clamp: real simulated gas loads, open valves and leaks can
            # subsequently change chamber pressure.
            chamber_initial = float(station_cfg.get(
                "chamber_initial_pressure_mbar", initial))
            if chamber_initial < 0 or not isfinite(chamber_initial):
                raise ValueError(f"Invalid chamber initial pressure for {short}")
            pressure = {v: {gas: ((chamber_initial if v == "C" else initial)
                                   if gas == "residual" else 0.0)
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

    def _apply_sources(self, station: VacuumStation, context) -> dict[str, float]:
        """Compute chamber throughputs for this step (mbar L/s).

        The optional measured curve is converted to an equivalent chamber
        gas throughput using Q = P_delta / (1/S + 1/C). This calibrates
        the steady-state pressure without overwriting simulated gauges.
        """
        settings = self.settings
        defaults = {
            "SRC:MFCH": {"species": "H2", "station": "VAC01"},
            "SRC:MFCD": {"species": "D2", "station": "VAC01"},
            "LEBT:MFC": {"species": "Kr", "station": "VAC02"},
        }
        sources = settings.get("gas_sources", defaults)
        gas_cfg = self.params.get("gas", {})
        temperature = float(station.config.get("temperature_K", 293.15))
        speeds = station.config.get("gas_pumping_speed_l_s", {
            "H2": 2100.0, "D2": 2100.0, "Kr": 2400.0, "N2": 2400.0})
        conductance = float(station.config.get("sv_conductance_l_s", 10000.0))
        nominal_turbo = (station.tp.running and station.tp.speed_fraction >= 0.999999
                         and station.pp.running
                         and self._is_open(context, f"{station.prefix}:PV")
                         and self._is_open(context, f"{station.prefix}:SV"))
        loads: dict[str, float] = {}
        for prefix, source in sources.items():
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
            physical_q = sccm_to_throughput(
                flow,
                reference_pressure_mbar=float(
                    gas_cfg.get("reference_pressure_mbar", 1013.25)),
                reference_temperature_K=float(
                    gas_cfg.get("reference_temperature_K", 273.15)),
                gas_temperature_K=temperature)
            equivalent_q = physical_q
            if nominal_turbo and prefix in self.curves:
                target_delta = self.curves[prefix].value(flow)
                s = float(speeds.get(species, 2400.0))
                if min(s, conductance) <= 0:
                    raise ValueError("Measured calibration requires S and C > 0")
                equivalent_q = target_delta / (1.0 / s + 1.0 / conductance)
            loads[species] = loads.get(species, 0.0) + equivalent_q
            context.metrics[f"{prefix}.throughput_mbar_l_s"] = physical_q
            context.metrics[f"{prefix}.effective_load_mbar_l_s"] = equivalent_q
        return loads

    def _evolve_station(self, station: VacuumStation, dt: float, context) -> None:
        p, cfg, prof = station.prefix, station.config, station.profile
        C, T, F = (station.pressure[v] for v in ("C", "T", "F"))
        vc, vt, vf = (station.volume_l(v) for v in ("C", "T", "F"))
        pp = station.pp.running and not station.pp.fault
        tp_speed = station.tp.speed_fraction if not station.tp.fault else 0.0
        pv = self._is_open(context, f"{p}:PV")
        sv = self._is_open(context, f"{p}:SV")

        gas_loads = self._apply_sources(station, context)
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
            # AIV admits atmosphere on the TP inlet side. It must work even
            # with TP stopped and both PV and SV closed.
            _vent(T, dt, float(cfg.get(
                "aiv_vent_tau_s", cfg.get("vent_tau_s", 120.0))), ambient)
        if bool(context.pv.get(f"{p}:LTVOpenStat", False)):
            _vent(F, dt, float(cfg.get("vent_tau_s", 120.0)), ambient)

        s_sv = float(cfg.get("sv_conductance_l_s", 10000.0))
        if s_sv < 0:
            raise ValueError("SV conductance must be nonnegative")
        turbo_active = pp and pv and tp_speed >= 0.01
        if turbo_active and sv and s_sv > 0:
            # Coupled C/T evolution, stable even with fast TP and large C_SV.
            background_speed = (vc + vt) / prof.turbo_tau_s * tp_speed
            _pumped_pair(C, vc, T, vt, s_sv, background_speed, dt,
                         "residual", floor_mbar=prof.ultimate_pressure_mbar)
            speeds = cfg.get("gas_pumping_speed_l_s", {
                "H2": 2100.0, "D2": 2100.0, "Kr": 2400.0, "N2": 2400.0})
            for gas in ("H2", "D2", "Kr", "N2"):
                speed = float(speeds.get(gas, 2400.0)) * tp_speed
                if speed < 0:
                    raise ValueError("Gas pumping speed must be nonnegative")
                if speed > 0:
                    _pumped_pair(C, vc, T, vt, s_sv, speed, dt, gas,
                                 throughput_mbar_l_s=gas_loads.get(gas, 0.0))
                else:
                    C[gas] += gas_loads.get(gas, 0.0) * dt / vc
        else:
            # No pump connected to C: injected gases accumulate locally.
            for gas, q in gas_loads.items():
                C[gas] += q * dt / vc
            if sv:
                _equalize(C, vc, T, vt, s_sv, dt)
            if turbo_active:
                # SV closed. Turbo can still evacuate its own inlet.
                _pump(T, vt, (vc + vt) / prof.turbo_tau_s * tp_speed, dt,
                      floor_mbar=prof.ultimate_pressure_mbar,
                      species="residual")
                speeds = cfg.get("gas_pumping_speed_l_s", {
                    "H2": 2100.0, "D2": 2100.0, "Kr": 2400.0, "N2": 2400.0})
                for gas in ("H2", "D2", "Kr", "N2"):
                    _pump(T, vt, float(speeds.get(gas, 2400.0))*tp_speed,
                          dt, species=gas)
            elif pv:
                # Stopped-TP equalization is only possible with PV open.
                # With PV closed the TP inlet is isolated from the foreline.
                _equalize(T, vt, F, vf,
                          float(cfg.get("stopped_tp_conductance_l_s", 10000.0)),
                          dt)
        # Configurable training leak of the sealed inlet. Interpret "1 %"
        # as a time-normalized rate (per hour), never as 1 % per model step.
        # An open AIV instead uses the atmospheric vent branch above.
        isolated_rise_pct = float(cfg.get(
            "isolated_tp_pressure_rise_percent_per_hour", 0.0))
        if not isfinite(isolated_rise_pct) or isolated_rise_pct < 0:
            raise ValueError("isolated TP pressure rise must be >= 0 %/h")
        if (isolated_rise_pct > 0 and not station.tp.running
                and not pv and not sv
                and not self._is_open(context, f"{p}:AIV")):
            growth = exp((dt / 3600.0) *
                         __import__("math").log1p(isolated_rise_pct / 100.0))
            for gas in COMPONENTS:
                T[gas] *= growth
        if pp and pv:
            effective_rough_speed = (vc + vt + vf) / prof.roughing_tau_s
            _pump(F, vf, effective_rough_speed, dt,
                  floor_mbar=prof.roughing_floor_mbar)

    def _publish(self, station: VacuumStation, context) -> None:
        p = station.prefix
        for suffix, volume in (("PGVC", "C"), ("SGVC", "C"),
                               ("PGTP", "T"), ("SGTP", "T")):
            gauge = station.gauges[suffix]
            gauge.fault = bool(context.device_faults.get(gauge.name, False))
            reading = station.total(volume)
            # The exposed numeric PV is an ideal pressure surrogate,
            # including out-of-range values. The range flag is diagnostic
            # only and does NOT pretend that a real Pirani/Penning gauge
            # remains calibrated outside its measurement interval.
            kind = "pirani" if suffix.startswith("PG") else "penning"
            nominal_bounds = ((1.0e-4, float(self.settings.get(
                "atmospheric_pressure_mbar", 1013.25)))
                if kind == "pirani" else (1.0e-8, 1.0e-4))
            gauge_cfg = self.settings.get("gauge_ranges_mbar", {}).get(kind, {})
            low = float(gauge_cfg.get("min", nominal_bounds[0]))
            high = float(gauge_cfg.get("max", nominal_bounds[1]))
            if not (0 < low <= high and isfinite(low) and isfinite(high)):
                raise ValueError(f"Invalid {kind} gauge range: {low}, {high}")
            context.metrics[f"{gauge.name}.in_range"] = float(low <= reading <= high)
            context.metrics[f"{gauge.name}.actual_pressure_mbar"] = reading
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
