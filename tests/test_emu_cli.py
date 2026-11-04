"""Smoke-test the offline Debian/Linux EMU training entrypoint."""
import subprocess
import sys


def test_emu_demo_completes_without_epics_network():
    completed = subprocess.run(
        [sys.executable, "scripts/demo_emu.py", "--mode", "emittance",
         "--synthetic-signal", "--max-steps", "300"],
        capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "stage=COMPLETE" in completed.stdout
    assert "TRAINING SYNTHETIC GAUSSIAN" in completed.stdout
