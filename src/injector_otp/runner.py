"""Offline Injector Python simulation clock (not an EPICS or Phoebus server)."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .app import build_application


def _print_status(engine, steps: int) -> None:
    context = engine.context
    vacuum = float(context.metrics.get("LEBT:VAC01.pressure_mbar", 0.0))
    rf = float(context.metrics.get("rf.forward_W", 0.0))
    beam = float(context.metrics.get("beam.current_mA", 0.0))
    print(
        f"[engine] steps={steps} sim_time={context.time:.1f}s "
        f"state={context.state.value} "
        f"vac01={vacuum:.3e} mbar rf={rf:.1f} W beam={beam:.1f} mA",
        flush=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the isolated, in-memory Injector Python model clock."
    )
    parser.add_argument(
        "--steps", type=int, default=0,
        help="Number of simulation steps. Default 0 = until Ctrl+C.",
    )
    parser.add_argument(
        "--fast", action="store_true",
        help="Run finite steps without real-time waiting (requires --steps > 0).",
    )
    parser.add_argument(
        "--report-every", type=int, default=50,
        help="Print status every N steps, as well as at first and final step.",
    )
    parser.add_argument(
        "--snapshot", type=Path,
        help="Optional JSON snapshot saved only on clean exit/Ctrl+C.",
    )
    args = parser.parse_args(argv)
    if args.steps < 0:
        parser.error("--steps must be >= 0")
    if args.report_every < 1:
        parser.error("--report-every must be >= 1")
    if args.fast and args.steps == 0:
        parser.error("--fast requires a finite --steps value")

    engine, _, _ = build_application()
    print(
        "[engine] OFFLINE PYTHON SIMULATION ONLY. No EPICS CA/PVA, "
        "no Soft IOC, no production equipment.",
        flush=True,
    )
    print(
        f"[engine] dt={engine.dt:g}s; "
        f"{'unlimited' if args.steps == 0 else args.steps} steps; "
        f"{'fast' if args.fast else 'wall-clock paced'}",
        flush=True,
    )

    steps = 0
    deadline = time.monotonic()
    try:
        while args.steps == 0 or steps < args.steps:
            engine.step()
            steps += 1
            if (steps == 1 or steps % args.report_every == 0
                    or (args.steps > 0 and steps == args.steps)):
                _print_status(engine, steps)

            if not args.fast:
                deadline += engine.dt
                remaining = deadline - time.monotonic()
                if remaining > 0:
                    time.sleep(remaining)
                elif -remaining > engine.dt:
                    deadline = time.monotonic()
    except KeyboardInterrupt:
        print("\n[engine] Ctrl+C received; stopping simulation clock.", flush=True)

    if args.snapshot is not None:
        output = args.snapshot.expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "kind": "offline_in_memory_simulation",
            "steps": steps,
            "dt_s": engine.dt,
            "engine": engine.snapshot(),
        }
        output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8")
        print(f"[engine] snapshot: {output}", flush=True)

    print(f"[engine] stopped after {steps} steps ({engine.context.time:.1f} s simulated).",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
