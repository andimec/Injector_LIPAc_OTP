"""Configurable vacuum calibration. All pressures are absolute mbar.

The pumpdown hours are an *effective training calibration* for a reference
sequence, NOT an OEM pump curve or a guarantee under arbitrary gas loads.
SCCM uses explicitly configured reference temperature and pressure.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from math import log
from pathlib import Path


def sccm_to_throughput(
    flow_sccm: float, *, reference_pressure_mbar: float = 1013.25,
    reference_temperature_K: float = 273.15, gas_temperature_K: float = 293.15,
) -> float:
    """Return gas throughput in mbar L/s at the chamber temperature."""
    if min(reference_pressure_mbar, reference_temperature_K, gas_temperature_K) <= 0:
        raise ValueError("Pressures and temperatures must be positive")
    if flow_sccm < 0:
        raise ValueError("Flow must not be negative")
    return (flow_sccm * 1e-3 / 60.0 * reference_pressure_mbar
            * gas_temperature_K / reference_temperature_K)


@dataclass(frozen=True)
class PumpdownProfile:
    pumpdown_time_h: float = 2.0
    reference_start_pressure_mbar: float = 1013.25
    roughing_end_pressure_mbar: float = 0.05
    roughing_floor_mbar: float = 0.005
    roughing_time_fraction: float = 0.40
    target_pressure_mbar: float = 1e-6
    ultimate_pressure_mbar: float = 1e-8

    def __post_init__(self) -> None:
        if not 0 < self.roughing_time_fraction < 1:
            raise ValueError("roughing_time_fraction must lie between zero and one")
        if self.pumpdown_time_h <= 0:
            raise ValueError("pumpdown_time_h must be positive")
        if not (self.reference_start_pressure_mbar > self.roughing_end_pressure_mbar
                > self.roughing_floor_mbar > 0):
            raise ValueError("Expected start > roughing_end > roughing_floor > 0")
        if not (self.roughing_end_pressure_mbar > self.target_pressure_mbar
                > self.ultimate_pressure_mbar > 0):
            raise ValueError("Expected roughing_end > target > ultimate > 0")

    @property
    def roughing_tau_s(self) -> float:
        return (3600 * self.pumpdown_time_h * self.roughing_time_fraction
                / log((self.reference_start_pressure_mbar - self.roughing_floor_mbar)
                      / (self.roughing_end_pressure_mbar - self.roughing_floor_mbar)))

    @property
    def turbo_tau_s(self) -> float:
        return (3600 * self.pumpdown_time_h * (1 - self.roughing_time_fraction)
                / log((self.roughing_end_pressure_mbar - self.ultimate_pressure_mbar)
                      / (self.target_pressure_mbar - self.ultimate_pressure_mbar)))


class FlowPressureCurve:
    """Measured EXTRA pressure at fixed pumping configuration versus one MFC.

    CSV columns: flow_sccm,delta_pressure_mbar. Data must already have been
    baseline-subtracted and measured with the same gas and gauge calibration.
    This is a 1D approximation; mixtures are not empirically cross-calibrated.
    """

    def __init__(self, points: list[tuple[float, float]]) -> None:
        if not points or any(x < 0 or y < 0 for x, y in points):
            raise ValueError("Curve requires nonnegative data")
        self.points = sorted((float(x), float(y)) for x, y in points)
        if any(b[0] <= a[0] for a, b in zip(self.points, self.points[1:])):
            raise ValueError("Flow-pressure data must use unique flow values")

    @classmethod
    def from_csv(cls, path: str | Path) -> "FlowPressureCurve":
        with Path(path).open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            required = {"flow_sccm", "delta_pressure_mbar"}
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise ValueError(f"CSV must contain {sorted(required)}")
            return cls([(float(r["flow_sccm"]), float(r["delta_pressure_mbar"]))
                        for r in reader])

    def value(self, flow_sccm: float) -> float:
        if flow_sccm < 0:
            raise ValueError("Flow must not be negative")
        if flow_sccm <= self.points[0][0]:
            return self.points[0][1]
        for (x0, y0), (x1, y1) in zip(self.points, self.points[1:]):
            if flow_sccm <= x1:
                return y0 + (y1 - y0) * (flow_sccm - x0) / (x1 - x0)
        return self.points[-1][1]
