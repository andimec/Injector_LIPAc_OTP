"""Offline reproduction of the EMU SNL v2 Fast Scan using recorded data.

This is a *replay adapter*, not a second physical plant model or an EPICS client.
It reuses emu_geometry for ROI validation and the EMU sample format;
all measured values are sourced from the archived experiment unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterator
from zoneinfo import ZoneInfo
import argparse
import json
import re
import sys
import time

from .emu_geometry import EmuGeometry, EmuROI, build_roi
from .emu_sequencer import EmuMode, EmuSample

DATA_DIRECTORY = Path(__file__).resolve().parents[1] / "Data" / "EMU"
OUTPUT_DIRECTORY = Path.cwd() / "output" / "emu"
FAST_SCAN_DEFAULT = "emit20260706-1434_optm.txt"
ROW_HEADER = "Pos(mm)"


@dataclass(frozen=True)
class ExperimentalPoint:
    motor_mm: float
    vht_set_V: float
    angle_rad: float
    current_mA: float
    vht_real_V: float


@dataclass(frozen=True)
class EmuMeasurement:
    source: Path
    source_header: tuple[str, ...]
    points: tuple[ExperimentalPoint, ...]
    energy_keV: float
    h2_status: str
    d2_status: str
    psr_V: float
    vpic_init_V: float
    vpic_end_V: float
    delta_v_V: float
    hv_points: int
    motor_upper_mm: float
    motor_lower_mm: float
    motor_step_mm: float

    @property
    def motor_rows(self) -> int:
        return 1 + sum(
            a.motor_mm != b.motor_mm for a, b in zip(self.points, self.points[1:])
        )

    def validate(self) -> EmuROI:
        """Check archived profile using the existing SNL-derived Python geometry."""
        if not self.points:
            raise ValueError("Experimental file contains no samples")
        geometry = EmuGeometry()
        to_mrad = geometry.distance_factor / self.energy_keV
        roi = build_roi(
            energy_keV=self.energy_keV,
            angle_init_mrad=self.vpic_init_V * to_mrad,
            angle_end_mrad=self.vpic_end_V * to_mrad,
            angle_delta_mrad=self.delta_v_V * to_mrad,
            border_up_mm=130.0 - self.motor_upper_mm,
            border_low_mm=130.0 - self.motor_lower_mm,
            motor_step_mm=self.motor_step_mm,
            hv_points=self.hv_points,
        )
        if abs(self.points[0].motor_mm - self.motor_upper_mm) > 0.11:
            raise ValueError("First motor position disagrees with source header")
        if abs(self.points[-1].motor_mm - self.motor_lower_mm) > 0.11:
            raise ValueError("Last motor position disagrees with source header")
        previous_position = None
        per_position = 0
        for point in self.points:
            if previous_position is None or point.motor_mm != previous_position:
                if previous_position is not None and per_position != self.hv_points + 1:
                    raise ValueError("Archived voltage points inconsistent with HVpoints")
                if previous_position is not None and abs(
                    point.motor_mm - previous_position - self.motor_step_mm
                ) > 0.11:
                    raise ValueError("Archived motor step inconsistent with header")
                per_position = 0
                previous_position = point.motor_mm
            per_position += 1
        if per_position != self.hv_points + 1:
            raise ValueError("Final motor row inconsistent with HVpoints")
        return roi

    def samples(self) -> Iterator[EmuSample]:
        """Samples compatible with the existing EmuScanSequencer data structure."""
        for row in self.points:
            yield EmuSample(
                t_s=0.0, motor_mm=row.motor_mm,
                voltage_set_V=row.vht_set_V,
                voltage_measured_V=row.vht_real_V,
                angle_rad=row.angle_rad,
                current_mA=row.current_mA, mode=EmuMode.EMITTANCE,
            )


def _field(header: str, key: str) -> str:
    match = re.search(r"\b" + re.escape(key) + r"\s*=\s*(\S+)", header)
    if match is None:
        raise ValueError(f"Missing required SNL header field: {key}")
    return match.group(1)


def load_measurement(path: str | Path) -> EmuMeasurement:
    """Parse a five-column, experimentally recorded SNL v2 measurement."""
    path = Path(path).expanduser().resolve()
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    try:
        header_end = next(i for i, line in enumerate(lines)
                          if line.strip().startswith(ROW_HEADER))
    except StopIteration as exc:
        raise ValueError("SNL header/column separator was not found") from exc
    header = tuple(lines[:header_end + 1])
    head_text = "".join(header)
    if not head_text.lstrip().startswith("processus = Emittance Measurement"):
        raise ValueError("Not a recognized EMU emittance dataset")
    points: list[ExperimentalPoint] = []
    for number, line in enumerate(lines[header_end + 1:], header_end + 2):
        if not line.strip():
            continue
        values = line.split()
        if len(values) != 5:
            raise ValueError(f"Invalid number of columns in {path.name}:{number}")
        try:
            points.append(ExperimentalPoint(*(float(value) for value in values)))
        except ValueError as exc:
            raise ValueError(f"Non-numeric point in {path.name}:{number}") from exc
    if not points:
        raise ValueError("No experimental points in EMU file")
    result = EmuMeasurement(
        source=path, source_header=header, points=tuple(points),
        energy_keV=float(_field(head_text, "Energy")),
        h2_status=_field(head_text, "H2"),
        d2_status=_field(head_text, "D2"),
        psr_V=float(_field(head_text, "PSR")),
        vpic_init_V=float(_field(head_text, "VpicInit")),
        vpic_end_V=float(_field(head_text, "VpicEnd")),
        delta_v_V=float(_field(head_text, "deltaV")),
        hv_points=int(float(_field(head_text, "HVpoints"))),
        motor_upper_mm=float(_field(head_text, "Upper")),
        motor_lower_mm=float(_field(head_text, "Lower")),
        motor_step_mm=float(_field(head_text, "Mstep")),
    )
    result.validate()
    return result


def output_filename(when: datetime) -> str:
    """Exact v2 source naming: emit%Y%m%d-%H%M_optm.txt."""
    if when.tzinfo is None:
        raise ValueError("A timezone-aware time is required")
    return when.astimezone(ZoneInfo("Asia/Tokyo")).strftime(
        "emit%Y%m%d-%H%M_optm.txt"
    )


def _updated_header(source_lines: tuple[str, ...], outpath: Path,
                    when: datetime) -> str:
    result = []
    for line in source_lines:
        if line.startswith("date "):
            result.append("date      = " + when.strftime("%a %b %d %H:%M:%S %Y") + "\n")
        elif line.startswith("file ="):
            result.append("file = " + str(outpath) + " \n")
        else:
            result.append(line)
    return "".join(result)


class EmuReplayStopped(Exception):
    """Operator set Actemit=OFF while an offline replay was running."""


def replay(measurement: EmuMeasurement, output_dir: str | Path,
           *, when: datetime | None = None, duration_s: float = 0.0,
           save: bool = True,
           should_continue: Callable[[], bool] | None = None,
           emit: Callable[[str], None] = print,
           sleep: Callable[[float], None] = time.sleep) -> Path | None:
    """Replay unchanged experimental points; write files only for Savemit=ON.

    This adapter does not connect to EPICS. The save argument represents
    LEBT:EMIT:Savemit. A future isolated PV bridge may use should_continue
    to stop when Actemit becomes OFF. With save=False, no output is created.
    """
    if duration_s < 0:
        raise ValueError("duration_s must be nonnegative")
    measurement.validate()

    target: Path | None = None
    provenance_path: Path | None = None
    part: Path | None = None
    instant: datetime | None = None
    if save:
        instant = when or datetime.now(ZoneInfo("Asia/Tokyo"))
        instant = instant.astimezone(ZoneInfo("Asia/Tokyo"))
        folder = Path(output_dir).expanduser().resolve()
        target = folder / output_filename(instant)
        provenance_path = target.with_suffix(".replay.json")
        part = target.with_name(target.name + ".partial")
        if target.exists() or provenance_path.exists() or part.exists():
            raise FileExistsError(f"EMU output already exists: {target}")
        folder.mkdir(parents=True, exist_ok=True)

    emit("EMU REPLAY [OFFLINE]: saved experimental samples, NO LIVE BEAM")
    emit("Emit: emittance measurement action received")
    emit("Emit: process started!!")
    emit(f"Recorded source = {measurement.source}")
    emit(f"Energy = {measurement.energy_keV:g} keV; D2 = {measurement.d2_status}")
    emit(f"Global voltage grid built: HVpoints = {measurement.hv_points}")
    emit(f"Data storing: {target}" if save else
         "Data storing: disabled (LEBT:EMIT:Savemit=OFF)")
    written = 0
    last_motor = None

    from contextlib import nullcontext
    try:
        with (part.open("x", encoding="utf-8", newline="")
              if part is not None else nullcontext(None)) as handle:
            if handle is not None:
                assert target is not None and instant is not None
                handle.write(_updated_header(measurement.source_header, target, instant))
            for point in measurement.points:
                if should_continue is not None and not should_continue():
                    raise EmuReplayStopped("LEBT:EMIT:Actemit=OFF")
                if last_motor is not None and point.motor_mm != last_motor:
                    if handle is not None:
                        handle.write("\n")
                    emit(f"Emit: scan {last_motor:7.1f} mm completed")
                last_motor = point.motor_mm
                emit(f"Vht = {point.vht_set_V:7.1f} ({point.vht_real_V:7.1f}) "
                     f"Pos = {point.motor_mm:6.1f} I = {point.current_mA:7.1f} "
                     f"yp = {point.angle_rad:7.4f}")
                if handle is not None:
                    handle.write(
                        f"{point.motor_mm:7.1f}  \t {point.vht_set_V:7.0f} \t "
                        f"{point.angle_rad:7.4f}  \t {point.current_mA:7.0f} \t "
                        f"{point.vht_real_V:7.0f}\n"
                    )
                    handle.flush()
                written += 1
                if duration_s:
                    sleep(duration_s / len(measurement.points))
            if handle is not None:
                handle.write("\n")
        if save:
            assert part is not None and target is not None
            assert provenance_path is not None and instant is not None
            part.rename(target)
            provenance = {
                "kind": "offline_experimental_replay",
                "live_beam": False,
                "source_file": measurement.source.name,
                "points": written,
                "motor_rows": measurement.motor_rows,
                "output_file": target.name,
                "timestamp_jst": instant.isoformat(),
                "save_pv": "LEBT:EMIT:Savemit",
                "save_value": 1,
                "data_policy": "experimental scalar samples preserved from source",
            }
            provenance_path.write_text(
                json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
            )
    except EmuReplayStopped:
        emit(f"Emit: OFF received, stopped after {written} points")
        if part is not None:
            emit(f"Emit: interrupted; partial replay retained: {part}")
        raise
    except BaseException:
        if part is not None:
            emit(f"Emit: interrupted; partial replay retained: {part}")
        raise
    if last_motor is not None:
        emit(f"Emit: scan {last_motor:7.1f} mm completed")
    emit(f"Emit: measurement completed. Processed {written} points")
    if save:
        emit(f"Output file = {target}")
        emit(f"Replay provenance = {provenance_path}")
    else:
        emit("Emit: Savemit=OFF, no TXT, JSON or partial output created")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OFFLINE EMU v2 SNL console replay")
    parser.add_argument("--source", type=Path, default=DATA_DIRECTORY / FAST_SCAN_DEFAULT)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIRECTORY)
    parser.add_argument("--duration", type=float, default=0.0,
                        help="Playback duration in seconds; 0 = immediate")
    parser.add_argument("--auto", action="store_true",
                        help="Validate and start without interactive commands")
    parser.add_argument("--save", choices=("on", "off"), default="off",
                        help="Offline Savemit setting (default: OFF)")
    parser.add_argument("--list", action="store_true",
                        help="List available archived EMU experiments")
    args = parser.parse_args(argv)
    if args.list:
        for path in sorted(DATA_DIRECTORY.glob("emit*_optm.txt")):
            print(path.name)
        return 0
    try:
        measurement = load_measurement(args.source)
    except (OSError, ValueError) as exc:
        print(f"EMU error: {exc}", file=sys.stderr)
        return 2
    print("Emit: established PV connections [LOCAL MODEL ONLY, NO CA/PVA]")
    print("Emit: waiting")
    print(f"Loaded {measurement.source.name}: "
          f"{measurement.motor_rows} positions, {len(measurement.points)} samples")
    save_enabled = args.save == "on"
    if not args.auto:
        validated = False
        print("Offline commands: validate, on, off, save on, save off, status, quit")
        while True:
            try:
                command = input("emu> ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nEmit: stopped")
                return 0
            if command == "quit":
                print("Emit: stopped")
                return 0
            if command == "status":
                state = "ROI validated, waiting for ON" if validated else "waiting"
                print(f"Emit: {state}; Savemit={'ON' if save_enabled else 'OFF'}")
            elif command in ("save on", "save off"):
                save_enabled = command == "save on"
                print(f"Emit: LEBT:EMIT:Savemit={'ON' if save_enabled else 'OFF'}")
            elif command == "off":
                print("Emit: Actemit already OFF; waiting")
            elif command == "validate":
                measurement.validate()
                validated = True
                print("Emit: validate action received. ROI validated")
            elif command == "on":
                if not validated:
                    print("Emit: press Validate before ON")
                    continue
                break
            else:
                print("Unknown command. Use validate, on, off, save on, save off, status, quit")
    else:
        print("Emit: validate action received. ROI validated")
    try:
        replay(measurement, args.output_dir, duration_s=args.duration,
               save=save_enabled)
    except (OSError, ValueError, EmuReplayStopped, KeyboardInterrupt) as exc:
        print(f"EMU replay error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
