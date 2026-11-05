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
    output = replay(source, tmp_path, when=when, save=True, emit=lambda _: None)
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
        replay(source, tmp_path, when=when, save=True, emit=lambda _: None)


def test_interactive_wait_requires_validate(tmp_path, monkeypatch, capsys):
    commands = iter(["on", "status", "save on", "validate", "on"])
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


def test_otp_opi_start_snl_invokes_python_replay():
    """The existing Phoebus button keeps using the same OTP shell entrypoint."""
    root = DATA_DIRECTORY.parents[3]
    opi = (root / "Injector_OPI" / "emitMeasurement_v2.bob").read_text()
    wrapper = (root / "Injector_OPI" / "Scripts" / "emitShell_v2.sh").read_text()
    launcher = (root / "scripts" / "launch_emu_snl_replay.sh").read_text()
    assert "/bin/bash Scripts/emitShell_v2.sh" in opi
    assert "launch_emu_snl_replay.sh" in wrapper
    assert "python3 -m injector_otp.models.emu_replay" in launcher
    assert "emitSnlEmu_v2 -s" not in wrapper



def test_savemit_off_runs_all_samples_without_creating_output(tmp_path):
    from injector_otp.models.emu_replay import replay
    source = load_measurement(DATA_DIRECTORY / FAST_SCAN_DEFAULT)
    folder = tmp_path / "no-output"
    messages = []
    result = replay(source, folder, save=False, emit=messages.append)
    assert result is None
    assert not folder.exists()
    assert sum(msg.startswith("Vht =") for msg in messages) == 1395
    assert any("Savemit=OFF" in msg for msg in messages)


def test_cli_default_savemit_off_runs_without_any_file(tmp_path, capsys):
    folder = tmp_path / "no-output"
    rc = main(["--auto", "--source", str(DATA_DIRECTORY / FAST_SCAN_DEFAULT),
               "--output-dir", str(folder)])
    assert rc == 0
    assert not folder.exists()
    assert "no TXT, JSON or partial output created" in capsys.readouterr().out


def test_cli_explicit_save_on_creates_file(tmp_path, capsys):
    rc = main(["--auto", "--save", "on",
               "--source", str(DATA_DIRECTORY / FAST_SCAN_DEFAULT),
               "--output-dir", str(tmp_path)])
    assert rc == 0
    assert len(list(tmp_path.glob("emit*_optm.txt"))) == 1
    assert len(list(tmp_path.glob("*.replay.json"))) == 1


def test_replay_stops_on_actemit_off_without_saving(tmp_path):
    from injector_otp.models.emu_replay import EmuReplayStopped, replay
    source = load_measurement(DATA_DIRECTORY / FAST_SCAN_DEFAULT)
    folder = tmp_path / "stopped"
    count = 0
    def on_state():
        nonlocal count
        count += 1
        return count <= 10
    observed = []
    with pytest.raises(EmuReplayStopped):
        replay(source, folder, save=False,
               should_continue=on_state, emit=observed.append)
    assert not folder.exists()
    assert sum(msg.startswith("Vht =") for msg in observed) == 10


def test_replay_stops_with_partial_if_save_enabled(tmp_path):
    from injector_otp.models.emu_replay import EmuReplayStopped, replay
    source = load_measurement(DATA_DIRECTORY / FAST_SCAN_DEFAULT)
    count = 0
    def is_on():
        nonlocal count
        count += 1
        return count <= 3
    with pytest.raises(EmuReplayStopped):
        replay(source, tmp_path, save=True,
               should_continue=is_on, emit=lambda _: None)
    assert len(list(tmp_path.glob("*.partial"))) == 1
    assert not list(tmp_path.glob("emit*_optm.txt"))
    assert not list(tmp_path.glob("*.replay.json"))


def test_otp_opi_control_pvs_and_widget_types():
    import xml.etree.ElementTree as ET
    root = DATA_DIRECTORY.parents[3]
    opi = ET.parse(root / "Injector_OPI" / "emitMeasurement_v2.bob")
    controls = {}
    for widget in opi.iter("widget"):
        pv = widget.findtext("pv_name", default="")
        if pv.startswith("ca://LEBT:EMIT:") and pv.split(":")[-1] in {
            "Validate", "Actemit", "Savemit"
        }:
            controls.setdefault(pv, set()).add(widget.attrib["type"])
    assert "bool_button" in controls["ca://LEBT:EMIT:Validate"]
    assert "choice" in controls["ca://LEBT:EMIT:Actemit"]
    assert "led" in controls["ca://LEBT:EMIT:Actemit"]
    assert "checkbox" in controls["ca://LEBT:EMIT:Savemit"]
