import json

import pytest

from injector_otp.core.pv_registry_loader import load_registry


def test_v1_2_registry_loads_all_source_entries(tmp_path):
    payload = {
        "schema_version": "1.2",
        "pvs": [
            {
                "name": "TEST:MON",
                "source_data": {
                    "epics_type": "time_double",
                    "read_access": True,
                    "write_access": False,
                },
            },
            {
                "name": "TEST:CMD",
                "source_data": {
                    "epics_type": "time_enum",
                    "read_access": True,
                    "write_access": True,
                },
            },
        ],
    }
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    registry = load_registry(path)

    assert len(registry) == 2
    assert registry.get("TEST:MON").type == "number"
    assert registry.get("TEST:CMD").type == "enum"


def test_missing_registry_file_is_reported():
    with pytest.raises(FileNotFoundError):
        load_registry("does-not-exist.json")
