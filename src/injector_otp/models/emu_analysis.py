"""First-principles *analysis* of EMU phase-space samples, not a beam solver.

The source EMU SNL logs motor position, VHT and beam current. Its angular
conversion comes from emu_geometry.py. This module computes uncorrected RMS
emittance and Twiss moments from positive sampled currents.

To compare with machine measurements, raw waveforms require calibrated
baseline subtraction, slit acceptance, detector gain, angular and spatial
integration weights, and a verified position coordinate convention.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Iterable, Protocol


class PhaseSpaceSample(Protocol):
    motor_mm: float
    angle_rad: float
    current_mA: float


@dataclass(frozen=True)
class EmuEmittanceResult:
    samples_used: int
    total_weight_mA: float
    mean_motor_mm: float
    mean_angle_mrad: float
    sigma_motor_mm: float
    sigma_angle_mrad: float
    covariance_mm_mrad: float
    emittance_rms_mm_mrad: float
    twiss_alpha: float
    twiss_beta_mm_per_mrad: float
    twiss_gamma_mrad_per_mm: float


def rms_emittance(samples: Iterable[PhaseSpaceSample]) -> EmuEmittanceResult:
    """Uncorrected current-weighted 2D second moments.

    Constant cell-area assumption is valid only for an equally spaced x,x'
    grid. The optimized SNL ROI may have non-uniform coverage, so results
    from that mode are *diagnostic estimates*, not calibrated emittance.
    """
    data = [(float(s.motor_mm), float(s.angle_rad) * 1000.0,
             max(0.0, float(s.current_mA))) for s in samples]
    valid = [(x, a, w) for x, a, w in data if w > 0]
    if len(valid) < 4:
        raise ValueError("At least four nonzero EMU current samples are required")
    weight = sum(w for _, _, w in valid)
    if weight <= 0:
        raise ValueError("Total measured current must be positive")
    mean_x = sum(x * w for x, _, w in valid) / weight
    mean_a = sum(a * w for _, a, w in valid) / weight
    xx = sum(w*(x-mean_x)**2 for x, _, w in valid)/weight
    aa = sum(w*(a-mean_a)**2 for _, a, w in valid)/weight
    xa = sum(w*(x-mean_x)*(a-mean_a) for x, a, w in valid)/weight
    epsilon = sqrt(max(0.0, xx*aa-xa*xa))
    if epsilon <= 0:
        raise ValueError("EMU phase-space covariance is singular")
    return EmuEmittanceResult(
        samples_used=len(valid), total_weight_mA=weight,
        mean_motor_mm=mean_x, mean_angle_mrad=mean_a,
        sigma_motor_mm=sqrt(xx), sigma_angle_mrad=sqrt(aa),
        covariance_mm_mrad=xa, emittance_rms_mm_mrad=epsilon,
        twiss_alpha=-xa/epsilon,
        twiss_beta_mm_per_mrad=xx/epsilon,
        twiss_gamma_mrad_per_mm=aa/epsilon,
    )


def samples_to_csv(samples: Iterable) -> str:
    """Export the columns of original SNL emit*_optm files as CSV text.

    No path or hardware I/O occurs here. A future separate storage adapter
    may persist the returned text to a configured directory.
    """
    lines=["motor_mm,vht_set_V,angle_rad,current_mA,vht_measured_V,time_s,mode"]
    for s in samples:
        lines.append(
            f"{s.motor_mm:.6f},{s.voltage_set_V:.6f},{s.angle_rad:.9f},"
            f"{s.current_mA:.9f},{s.voltage_measured_V:.6f},{s.t_s:.6f},{s.mode.value}"
        )
    return "\n".join(lines) + "\n"
