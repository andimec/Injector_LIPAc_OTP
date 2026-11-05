"""Offline EMU playback regression tests with genuine archived EMU fixtures."""
from __future__ import annotations

from datetime import datetime
import json
from zoneinfo import ZoneInfo

import pytest

from injector_otp.models.emu_replay import (
    DATA_DIRECTORY, FAST_SCAN_DEFAULT, load_measurement,
    output_filename, replay, main,
)


def test_fast_scan_matches_2026_procedure():
    measurement = load_measurement(DATA_DIRECTORY / FAST_SCAN_DEFAULT)
    roi = measurement.validate()
    assert measurement.motor_rows == 45
    assert len(measurement.points) == 1395
    assert measurement.hv_points == 30
    assert measurement.energy_keV == 100
    assert (roi.motor_upper_mm, roi.motor_lower_mm) == (84, 172)
    assert measurement.points[0].motor_mm == 84
    assert measurement.points[-1].motor_mm == 172
    assert measurement.points[0].vht_set_V == -1172
    assert measurement.points[0].vht_real_V == -581


@pytest.mark.parametrize("filename,rows,nvolts,total", [
    ("emit20260604-1847_optm.txt", 43, 101, 4343),
    ("emit20260610-1611_optm.txt", 53, 121, 6413),
    ("emit20260706-1434_optm.txt", 45, 31, 1395),
])
def test_all_experimental_inputs_parse(filename, rows, nvolts, total):
    scan = load_measurement(DATA_DIRECTORY / filename)
    assert scan.motor_rows == rows
    assert scan.hv_points + 1 == nvolts
    assert len(scan.points) == total
    assert len(tuple(scan.samples())) == total


def test_replay_uses_original_samples_and_source_naming(tmp_path):
    source = load_measurement(DATA_DIRECTORY / FAST_SCAN_DEFAULT)
    when = datetime(2026, 11, 5, 11, 50, tzinfo=ZoneInfo("Asia/Tokyo"))
    output = replay(source, tmp_path, when=when, emit=lambda _: None)
    assert output.name == "emit20261105-1150_optm.txt"
    body = output.read_text(encoding="utf-8")
    assert "processus = Emittance Measurement vers. 2.0.0" in body
    assert "Pos(mm)" in body
    assert "emit20261105-1150_optm.txt" in body
    samples = []
    for line in body.splitlines():
        cells = line.split()
        if len(cells) == 5:
            try:
                samples.append(tuple(map(float, cells)))
            except ValueError:
                pass
    assert samples == [
        (s.motor_mm, s.vht_set_V, s.angle_rad, s.current_mA, s.vht_real_V)
        for s in source.points
    ]
    provenance = json.loads(output.with_suffix(".replay.json").read_text())
    assert provenance["live_beam"] is False
    assert provenance["points"] == 1395
    with pytest.raises(FileExistsError):
        replay(source, tmp_path, when=when, emit=lambda _: None)


def test_interactive_wait_requires_validate(tmp_path, monkeypatch, capsys):
    commands = iter(["on", "status", "validate", "on"])
    monkeypatch.setattr("builtins.input", lambda _: next(commands))
    assert main(["--source", str(DATA_DIRECTORY / FAST_SCAN_DEFAULT),
                 "--output-dir", str(tmp_path)]) == 0
    result = capsys.readouterr().out
    assert "waiting" in result
    assert "press Validate before ON" in result
    assert len(list(tmp_path.glob("emit*_optm.txt"))) == 1


def test_reject_invalid_or_incomplete_header(tmp_path):
    corrupted = tmp_path / "corrupted.txt"
    corrupted.write_text("processus = Emittance Measurement\nPos(mm) foo\n1 2 3 4 5\n")
    with pytest.raises(ValueError, match="Missing required"):
        load_measurement(corrupted)


def test_output_filename_is_jst():
    from datetime import timezone
    when = datetime(2026, 11, 5, 2, 59, tzinfo=timezone.utc)
    assert output_filename(when) == "emit20261105-1159_optm.txt"
