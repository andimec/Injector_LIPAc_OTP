"""Executable safeguards for the OPI/PV coverage auditor."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "audit_opi_pv_coverage", ROOT / "scripts/audit_opi_pv_coverage.py"
)
assert SPEC is not None and SPEC.loader is not None
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def test_normalize_pv_preserves_native_names_and_record_fields():
    assert audit.normalize_pv("ca://LEBT:EMIT:MOTOR.RBV") == "LEBT:EMIT:MOTOR.RBV"
    assert audit.normalize_pv("pva://SRC:COIL01_PS:ISet") == "SRC:COIL01_PS:ISet"
    assert audit.normalize_pv("LEBT:HV_PS:OnStat") == "LEBT:HV_PS:OnStat"


def test_phoebus_expression_parsing_distinguishes_pvs_from_constants():
    assert audit.binding_pvs("='LEBT:CHOP_IM:DbgDPeriod'/1000") == [
        ("expression_reference", "LEBT:CHOP_IM:DbgDPeriod")
    ]
    assert audit.binding_pvs("=1") == [("constant_expression", "")]
    assert audit.binding_pvs("= 0.25") == [("constant_expression", "")]


def test_registry_field_and_macro_classification():
    registry = {"LEBT:EMIT:MOTOR", "LEBT:HV_PS:OnStat"}
    assert audit.pv_registry_match("LEBT:HV_PS:OnStat", registry) == "exact"
    assert audit.pv_registry_match("LEBT:EMIT:MOTOR.VAL", registry) == "implicit_VAL"
    assert audit.pv_registry_match("LEBT:EMIT:MOTOR.DMOV", registry) == "missing"
    assert audit.pv_registry_match("$(P):ISet", registry) == "macro_unresolved"


def test_xml_bob_widget_input_monitor_and_macro(tmp_path):
    opi = tmp_path / "test.bob"
    opi.write_text(
        '<display><widget type="textentry"><name>Set</name>'
        '<pv_name>ca://SRC:COIL01_PS:ISet</pv_name></widget>'
        '<widget type="textupdate"><name>Feedback</name>'
        '<pv_name>ca://SRC:COIL01_PS:IRdbk</pv_name></widget>'
        '<widget type="textupdate"><pv_name>$(P):I</pv_name></widget></display>',
        encoding="utf-8",
    )
    rows = audit.collect_opi_references(opi, tmp_path)
    assert [x["pv"] for x in rows] == [
        "SRC:COIL01_PS:ISet", "SRC:COIL01_PS:IRdbk", "$(P):I"
    ]
    assert [x["role"] for x in rows] == [
        "potential_write", "monitor_or_other", "monitor_or_other"
    ]


def test_xml_legacy_css_boy_widget(tmp_path):
    opi = tmp_path / "test.opi"
    opi.write_text(
        '<display><widget typeId="org.csstudio.opibuilder.widgets.TextInput">'
        '<name>Command</name><pv_name>LEBT:SOL01_PS:ISet</pv_name>'
        '</widget></display>',
        encoding="utf-8",
    )
    rows = audit.collect_opi_references(opi, tmp_path)
    assert len(rows) == 1
    assert rows[0]["generation"] == "legacy"
    assert rows[0]["role"] == "potential_write"


def test_candidate_pairs_only_include_existing_registry_pvs():
    registry = {
        "SRC:COIL01_PS:IRdbk", "SRC:COIL01_PS:IRdbkcalc",
        "LEBT:EMIT:MOTOR.RBV", "LEBT:EMIT:MOTOR.DMOV",
        "LEBT:HV_PS:ScaleVHT", "LEBT:HV_PS:LectVht",
    }
    assert audit.candidate_readbacks("SRC:COIL01_PS:ISet", registry) == [
        "SRC:COIL01_PS:IRdbkcalc", "SRC:COIL01_PS:IRdbk"
    ]
    assert audit.candidate_readbacks("LEBT:EMIT:MOTOR.VAL", registry) == [
        "LEBT:EMIT:MOTOR.RBV", "LEBT:EMIT:MOTOR.DMOV"
    ]
    assert audit.candidate_readbacks("LEBT:HV_PS:HTCmd", registry) == [
        "LEBT:HV_PS:ScaleVHT", "LEBT:HV_PS:LectVht"
    ]
    assert audit.candidate_readbacks("SRC:RF_GENE:RfPwr", registry) == []


def test_local_runtime_producer_provenance_is_not_inferred():
    sources = audit.runtime_producers(ROOT)
    assert sources["SRC:COIL01_PS:IRdbk"].startswith("power_supply:")
    assert sources["LEBT:EMIT:MOTOR.RBV"] == "emu_motor"


def test_real_phoebus_emu_references_are_extracted():
    file = ROOT / "Injector_OPI/emitMeasurement_v2.bob"
    refs = {row["pv"] for row in audit.collect_opi_references(file, ROOT)}
    assert "LEBT:EMIT:MOTOR.VAL" in refs
    assert "LEBT:EMIT:MOTOR.RBV" in refs


def test_report_is_reproducible_and_does_not_require_epics():
    report = audit.build_report(ROOT, probe_runtime=False)
    assert report["summary"]["registry_total"] == 1052
    assert report["summary"]["file_count"] >= 76
    assert report["summary"]["phoebus_unique"] > 0
    assert "LEBT:EMIT:MOTOR.VAL" in {r["pv"] for r in report["references"]}
    assert not report["parse_errors"]
    assert any(x["command"] == "SRC:COIL01_PS:ISet" for x in report["pairs"])
