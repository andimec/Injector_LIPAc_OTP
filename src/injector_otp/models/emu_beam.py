"""Optional analytic beam phase-space fixture for EMU training.

An *assumed* two-dimensional Gaussian distribution (Twiss α, β, ε_rms)
generates a deterministic FC signal I(x,x'). This is neither PIC nor a
validated LIPAc beam. It can be enabled only in synthetic demonstration
scenarios and must never be mixed with genuine FACQ measurements.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp, isfinite


@dataclass(frozen=True)
class SyntheticPhaseSpace:
    peak_current_mA: float = 5.0
    mean_motor_mm: float = 80.0
    mean_angle_mrad: float = 0.0
    rms_emittance_mm_mrad: float = 30.0
    twiss_alpha: float = 0.0
    twiss_beta_mm_per_mrad: float = 3.0

    def __post_init__(self):
        if (self.peak_current_mA < 0 or self.rms_emittance_mm_mrad <= 0
                or self.twiss_beta_mm_per_mrad <= 0
                or not all(isfinite(x) for x in (
                    self.peak_current_mA, self.mean_motor_mm,
                    self.mean_angle_mrad, self.rms_emittance_mm_mrad,
                    self.twiss_alpha, self.twiss_beta_mm_per_mrad,
                ))):
            raise ValueError("Invalid synthetic EMU phase-space parameters")

    def current_mA(self, motor_mm: float, angle_mrad: float) -> float:
        """Positive Twiss Gaussian in motor-coordinate / observed angle."""
        xx = motor_mm - self.mean_motor_mm
        aa = angle_mrad - self.mean_angle_mrad
        beta = self.twiss_beta_mm_per_mrad
        alpha = self.twiss_alpha
        gamma = (1 + alpha*alpha) / beta
        action = (gamma*xx*xx + 2*alpha*xx*aa + beta*aa*aa)
        return self.peak_current_mA * exp(
            -max(0.0, action) / (2*self.rms_emittance_mm_mrad)
        )
