"""Checks for the offline Python engine launcher."""
import json

import pytest

from injector_otp import runner


def test_runner_finite_steps_and_snapshot(tmp_path, capsys):
    output = tmp_path / "engine-snapshot.json"
    code = runner.main([
        "--steps", "3", "--fast", "--report-every", "1",
        "--snapshot", str(output),
    ])
    assert code == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["kind"] == "offline_in_memory_simulation"
    assert data["steps"] == 3
    assert data["dt_s"] == pytest.approx(0.1)
    assert data["engine"]["time"] == pytest.approx(0.3)
    assert "LEBT:HV_PS:HTCmd" in data["engine"]["pv"]
    text = capsys.readouterr().out
    assert "No EPICS CA/PVA" in text
    assert "steps=3" in text


@pytest.mark.parametrize("arguments", [
    ["--steps", "-1"],
    ["--fast"],
    ["--report-every", "0"],
])
def test_runner_rejects_invalid_arguments(arguments):
    with pytest.raises(SystemExit) as error:
        runner.main(arguments)
    assert error.value.code == 2
