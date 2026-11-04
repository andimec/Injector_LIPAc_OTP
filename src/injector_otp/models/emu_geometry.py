"""EMU angle-to-voltage geometry and December-2025 global ROI grid.

Directly translated from topIFMIF_INJ/emitApp/src/emitSnlEmu_v2.st,
lines 199-243 and 875-936, 1023-1040 and 1074-1096.
Units: Energy keV, angles mrad, plate potential V, position mm.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import floor, isfinite


@dataclass(frozen=True)
class EmuGeometry:
    gap_inlet_to_plate_m: float = 0.01
    plate_length_m: float = 0.09
    gap_plate_to_exit_m: float = 0.002
    plate_spacing_m: float = 0.009

    @property
    def distance_factor(self) -> float:
        return ((self.plate_length_m + 2 * self.gap_plate_to_exit_m)
                * self.plate_length_m / (
                    4 * self.plate_spacing_m
                    * (self.gap_inlet_to_plate_m + self.plate_length_m
                       + self.gap_plate_to_exit_m)
                ))

    def angle_mrad_to_vht(self, angle_mrad: float, energy_keV: float) -> float:
        if energy_keV <= 0 or not isfinite(energy_keV):
            raise ValueError("EMU beam energy must be positive and finite")
        return angle_mrad * energy_keV / self.distance_factor

    def vht_to_angle_rad(self, vht_V: float, energy_keV: float) -> float:
        if energy_keV <= 0 or not isfinite(energy_keV):
            raise ValueError("EMU beam energy must be positive and finite")
        return self.distance_factor * vht_V / (energy_keV * 1000.0)


@dataclass(frozen=True)
class EmuROI:
    """Validated 2026 SNL emittance measurement setup."""

    energy_keV: float
    motor_upper_mm: float
    motor_lower_mm: float
    motor_step_mm: float
    vpic_init_V: float
    vpic_end_V: float
    delta_v_V: float
    start_voltage_V: float
    end_voltage_V: float
    half_plate_step_V: float
    slope_V_per_mm: float
    intercept_V: float
    grid: tuple[float, ...]

    def vpic_at(self, motor_position_mm: float) -> float:
        return self.slope_V_per_mm * motor_position_mm + self.intercept_V

    def snapped_voltages(self, motor_position_mm: float) -> tuple[float, ...]:
        """Nearest global voltage grid index, descending like SNL idxCur--."""
        start = self.vpic_at(motor_position_mm) + self.delta_v_V / 2
        end = self.vpic_at(motor_position_mm) - self.delta_v_V / 2
        step = self.grid[1] - self.grid[0]
        def index(v: float) -> int:
            # Original integer cast (int)(r + .5) and clamp.
            k = int((v - self.grid[0]) / step + 0.5)
            return max(0, min(len(self.grid) - 1, k))
        a, b = index(start), index(end)
        if b > a:
            a, b = b, a
        return tuple(self.grid[i] for i in range(a, b - 1, -1))


def build_roi(*, energy_keV: float, angle_init_mrad: float,
              angle_end_mrad: float, angle_delta_mrad: float,
              border_up_mm: float, border_low_mm: float,
              motor_step_mm: float, hv_points: int,
              geometry: EmuGeometry | None = None,
              max_grid: int = 4096) -> EmuROI:
    """SNL actValidate + buildVHTGrid, with guards against zero divisions.

    The source checks borderUp>borderLow, and inverts physical display
    coordinates with motor=130-border. No unverified geometry is introduced.
    """
    g = geometry or EmuGeometry()
    values = (energy_keV, angle_init_mrad, angle_end_mrad,
              angle_delta_mrad, border_up_mm, border_low_mm, motor_step_mm)
    if not all(isfinite(v) for v in values):
        raise ValueError("EMU ROI parameters must be finite")
    if angle_init_mrad == -9999 or angle_end_mrad == 9999:
        raise ValueError("Replace the source unset-angle sentinel before Validate")
    if border_up_mm <= border_low_mm:
        raise ValueError("Borderup must be greater than Borderlow")
    if motor_step_mm <= 0 or angle_delta_mrad <= 0 or energy_keV <= 0:
        raise ValueError("Motor step, angular width and energy must be positive")
    if not 1 <= hv_points <= max_grid:
        raise ValueError("Invalid number of voltage sample points")
    u, l = 130.0 - border_up_mm, 130.0 - border_low_mm
    if l <= u:
        raise ValueError("SNL motor must travel from upper to lower")
    vi = g.angle_mrad_to_vht(angle_init_mrad, energy_keV)
    ve = g.angle_mrad_to_vht(angle_end_mrad, energy_keV)
    dv = g.angle_mrad_to_vht(angle_delta_mrad, energy_keV)
    step = dv / hv_points
    lo, hi = sorted((vi - dv / 2, ve + dv / 2))
    if step <= 0:
        raise ValueError("Global VHT grid requires positive step")
    n = floor((hi - lo) / step + 0.5) + 1
    if n < 2 or n > max_grid:
        raise ValueError(f"Global VHT grid needs {n} points; limit {max_grid}")
    grid = [lo + i * step for i in range(n)]
    grid[-1] = hi  # source implementation pins its last point to max
    slope = (ve - vi) / (l - u)
    intercept = ve - slope * l
    return EmuROI(
        energy_keV=energy_keV,
        motor_upper_mm=u, motor_lower_mm=l, motor_step_mm=motor_step_mm,
        vpic_init_V=vi, vpic_end_V=ve, delta_v_V=dv,
        start_voltage_V=vi + dv / 2, end_voltage_V=vi - dv / 2,
        half_plate_step_V=dv / (2 * hv_points),
        slope_V_per_mm=slope, intercept_V=intercept, grid=tuple(grid),
    )
