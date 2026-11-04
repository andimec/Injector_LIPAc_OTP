#!/usr/bin/env python3
"""Run a self-contained EMU training scan on Debian/Linux, with no IOC.

Example:
  python scripts/demo_emu.py --mode emittance --out /tmp/emu_training.csv
  python scripts/demo_emu.py --mode wide
  python scripts/demo_emu.py --mode emittance --synthetic-signal

All PVs are Python memory objects, NOT production Channel Access names.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from injector_otp.app import build_application
from injector_otp.models.emu_beam import SyntheticPhaseSpace
from injector_otp.models.emu_sequencer import EmuMode, EmuStage


def run(mode: str, signal: bool, max_steps: int, outfile: str | None) -> int:
    engine, backend, _ = build_application()
    components = engine.models[0].components
    sequence = next(x for x in components if x.name == "emu_scan")
    if signal:
        source = next(x for x in components if x.name == "emu_facq")
        source.fixture = SyntheticPhaseSpace(
            peak_current_mA=5.0,
            mean_motor_mm=2.0,
            mean_angle_mrad=0.0,
            rms_emittance_mm_mrad=8.0,
            twiss_beta_mm_per_mrad=2.0,
        )
        print("TRAINING SYNTHETIC GAUSSIAN: not machine measurement")

    # Small deterministic scenario rather than full operational range.
    backend.put("LEBT:EMIT:Debscanl", 100.0)
    backend.put("LEBT:EMIT:Finscanl", -100.0)
    backend.put("LEBT:EMIT:Passcanl", 100.0)
    backend.put("LEBT:EMIT:Pasmotdet", 1.0)

    if mode == EmuMode.EMITTANCE.value:
        for name, value in {
            "AnglePicInit": -8.0, "AnglePicEnd": 8.0,
            "AngleDelta": 15.0, "Energy": 100.0,
            "Borderup": 129.0, "Borderlow": 127.0,
            "Nptemit": 4,
        }.items():
            backend.put("LEBT:EMIT:" + name, value)
        backend.put("LEBT:EMIT:Validate", 1)
        engine.step()
        if sequence.validated_roi is None:
            print("Cannot validate ROI:", sequence.message)
            return 2
    elif mode in (EmuMode.UPPER.value, EmuMode.LOWER.value):
        backend.put("LEBT:EMIT:Limdet", 2.0 if mode == "UPPER" else 179.0)

    command = sequence.ACTIONS[EmuMode(mode)]
    backend.put(command, 1)
    for i in range(max_steps):
        engine.step()
        if sequence.stage in (EmuStage.COMPLETE, EmuStage.ABORTED):
            break

    print(f"Mode={mode}, stage={sequence.stage.value}")
    print(f"Message={sequence.message}")
    print(f"Simulation time={engine.context.time:.3f} s")
    print(f"Samples={len(sequence.samples)} / {len(sequence.targets)}")
    if outfile:
        path = Path(outfile).expanduser()
        path.write_text(sequence.results_csv(), encoding="utf-8")
        print(f"CSV stored locally at {path}")
    if sequence.samples:
        print("First sample:", sequence.samples[0])
        print("Last sample:", sequence.samples[-1])
    if signal and mode == "EMITTANCE" and sequence.stage == EmuStage.COMPLETE:
        try:
            print("Preliminary (uncalibrated) RMS:", sequence.preliminary_emittance())
        except ValueError as err:
            print("RMS unavailable:", err)
    return 0 if sequence.stage == EmuStage.COMPLETE else 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=[x.value.lower() for x in EmuMode],
                        default="emittance")
    parser.add_argument("--synthetic-signal", action="store_true")
    parser.add_argument("--max-steps", type=int, default=2000)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    raise SystemExit(run(args.mode.upper(), args.synthetic_signal,
                         args.max_steps, args.out))


if __name__ == "__main__":
    main()
