#!/usr/bin/env python3
"""Auditable OPI -> V2.0 registry -> Python PV producer coverage.

No network traffic, EPICS client, hardware access or real IOC is involved.
"model_observed" means produced during the OFF-state local simulation probe,
not that all operating sequences or EPICS record-field details are verified.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WRITE_WIDGET_PARTS = (
    "textentry", "textinput", "actionbutton", "togglebutton", "pushbutton",
    "checkbox", "radio", "combo", "spinner", "slider", "thumbwheel",
    "booleanbutton", "knob", "writemessage", "byte_monitor_write",
)
SCHEMES = re.compile(r"^(?:ca|pva)://", re.IGNORECASE)
MACRO = re.compile(r"\$\([^)]*\)|\$\{[^}]*\}")
READBACK_MARKERS = (
    "Rdbk", "Rdbkcalc", "OnStat", "OffStat", "OpenStat", "CloseStat",
    "Deb1Mes", "Deb2Mes", "StsVanne", "LectVht", "ScaleVHT",
    ".RBV", ".DMOV", ".MOVN", "VhtRdbk", "VacSG", "VacPG",
    "MarcheRF", "PretRF", "PwrRef", "StmState", "InStat", "OutStat",
)


def tagname(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1].lower()


def normalize_pv(raw: str) -> str:
    """Preserve the exact EPICS record/field spelling except CA/PVA scheme."""
    return SCHEMES.sub("", raw.strip()).strip()


def pv_registry_match(pv: str, registry: set[str]) -> str:
    if MACRO.search(pv):
        return "macro_unresolved"
    if pv in registry:
        return "exact"
    # EPICS exposes the .VAL field on ordinary records even when the
    # inventory names only the base record. Never apply this to other fields.
    if pv.endswith(".VAL") and pv[:-4] in registry:
        return "implicit_VAL"
    return "missing"


def widget_role(widget_type: str, in_write_action: bool = False) -> str:
    if in_write_action or any(part in widget_type.lower().replace(" ", "") for part in WRITE_WIDGET_PARTS):
        return "potential_write"
    return "monitor_or_other"


def collect_opi_references(path: Path, root: Path) -> list[dict[str, str]]:
    """Collect explicit pv_name tags with their owning widget and action.

    Dynamic names, widget expressions and scripts are not resolved. Both
    legacy CSS BOY .opi and Phoebus .bob XML are supported.
    """
    document = ET.parse(path).getroot()
    rows: list[dict[str, str]] = []

    def visit(node: ET.Element, widget: ET.Element | None, action_write: bool) -> None:
        if tagname(node) == "widget":
            widget = node
        if tagname(node) == "action":
            kind = (node.get("type") or "").lower()
            action_write = action_write or "write" in kind or "set_pv" in kind
        if tagname(node) == "pv_name" and not any(tagname(child) == "pv_name" for child in node):
            raw = (node.text or "").strip()
            if raw:
                name = normalize_pv(raw)
                # Do not count generic macro-only placeholders as concrete PVs;
                # preserve unresolved expressions for separate review.
                if name:
                    widget_type = ""
                    widget_name = ""
                    if widget is not None:
                        widget_type = widget.get("type") or widget.get("typeId", "").split(".")[-1]
                        if not widget_type:
                            widget_type = widget.findtext("widget_type", default="") or ""
                        widget_name = widget.findtext("name", default="") or ""
                    rows.append({
                        "file": path.relative_to(root).as_posix(),
                        "generation": "legacy" if path.suffix == ".opi" else "phoebus",
                        "pv": name,
                        "widget_type": widget_type,
                        "widget_name": widget_name,
                        "role": widget_role(widget_type, action_write),
                    })
        for child in node:
            visit(child, widget, action_write)

    visit(document, None, False)
    return rows


def _find(names: set[str], prefix: str, suffixes: tuple[str, ...]) -> list[str]:
    return [prefix + suffix for suffix in suffixes if prefix + suffix in names]


def candidate_readbacks(command: str, registry: set[str]) -> list[str]:
    """Conservative, EXISTENCE-CHECKED candidate mappings.

    These are candidate relationships for review, not claims of measured
    hardware or certified EPICS links.
    """
    special = {
        "LEBT:HV_PS:HTCmd": ("LEBT:HV_PS:ScaleVHT", "LEBT:HV_PS:LectVht"),
        "LEBT:HV_PS:ICmd": ("LEBT:HV_PS:LectIht", "LEBT:HV_PS:ScaleIHT"),
        "LEBT:EMIT:MOTOR.VAL": ("LEBT:EMIT:MOTOR.RBV", "LEBT:EMIT:MOTOR.DMOV"),
        "LEBT:EMIT:MOTOR.HOMR": ("LEBT:EMIT:MOTOR.ATHM", "LEBT:EMIT:MOTOR.RBV"),
        "LEBT:CHOP_IM:StmStateSet": ("LEBT:CHOP_IM:StmState",),
        "SRC:RF_GENE:MOCmdOn": ("SRC:RF_GENE:MarcheRF", "SRC:RF_GENE:Mot105"),
        "SRC:RF_GENE:FilOnCmd": ("SRC:RF_GENE:PretRF", "SRC:RF_GENE:Mot105"),
        "SRC:RF_GENE:RfPwr": (),  # PwrRef is REFLECTED, not forward readback
    }
    if command in special:
        return [x for x in special[command] if x in registry]
    for suffix, possible in (
        (":ISet", (":IRdbkcalc", ":IRdbk")),
        (":VSet", (":VRdbkcalc", ":VRdbk")),
        (":Debit", (":Deb1Mes", ":Deb2Mes")),
        (":VmonThr", (":VmonThrRdbk",)),
        (":VmonOff", (":VmonOffRdbk",)),
        (":AcctThr", (":AcctThrRdbk",)),
        (":Softbo", (":OnOffCmd.RVAL", ":OnOffCmd")),
        (":WrtX", (":RdbkX", ":LectX")),
        (":WrtY", (":RdbkY", ":LectY")),
        (":InCmd", (":InStat",)),
        (":OutCmd", (":OutStat",)),
        (":OpenCmd", (":OpenStat", ":StsVanne")),
        (":CloseCmd", (":CloseStat",)),
        (":PPOnCmd", (":PPOnStat",)),
        (":PPOffCmd", (":PPOnStat",)),
        (":TPOnCmd", (":TPOnStat",)),
        (":TPOffCmd", (":TPOnStat",)),
        (":HTOnCmd", (":OnStat",)),
        (":HTOffCmd", (":OnStat",)),
        (":AuxOnCmd", (":AuxStat",)),
        (":AuxOffCmd", (":AuxStat",)),
        (":OnCmd", (":OnStat",)),
        (":OffCmd", (":OnStat",)),
        (":ON", (":OnStat",)),
        (":OFF", (":OnStat",)),
    ):
        if command.endswith(suffix):
            return _find(registry, command[:-len(suffix)], possible)
    for suffix in ("OpenCmd", "CloseCmd"):
        if command.endswith(suffix):
            return _find(registry, command[:-len(suffix)],
                         ("OpenStat", "CloseStat"))
    return []


def runtime_producers(repo: Path) -> dict[str, str]:
    """Observe real context.emit/publish behavior in an OFF-state time step.

    This is *not* a proof that every conditional producer is reachable.
    """
    sys.path.insert(0, str(repo / "src"))
    from injector_otp.app import build_application
    engine, _backend, _faults = build_application(
        registry_path=repo / "config/pv_registry_v2_0.json",
        model_parameters_path=repo / "config/model_parameters.yaml",
        simulation_config_path=repo / "config/simulation/default.yaml",
        runtime_overrides_path=repo / "config/pv_runtime_overrides.yaml",
    )
    engine.step()
    return {
        name: record.source
        for name, record in engine.pv_state.snapshot().items()
        if record.source not in {"registry-default", "startup-config", "engine"}
        and not record.source.startswith("python:")
    }


def _write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_report(repo: Path, include_legacy: bool = True,
                 probe_runtime: bool = True) -> dict[str, object]:
    import yaml

    registry_path = repo / "config/pv_registry_v2_0.json"
    registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
    registry = {item["name"] for item in registry_payload["pvs"]}
    overrides = yaml.safe_load((repo / "config/pv_runtime_overrides.yaml").read_text(encoding="utf-8"))
    inputs = set(overrides["inputs"])
    external = set(overrides.get("external_conditions", []))
    explicit_outputs = set(overrides.get("outputs", []))

    rows: list[dict[str, str]] = []
    parse_errors: list[dict[str, str]] = []
    files = sorted((repo / "Injector_OPI").rglob("*"))
    for path in files:
        if not path.is_file() or path.suffix not in {".bob", ".opi"}:
            continue
        if not include_legacy and path.suffix == ".opi":
            continue
        try:
            rows.extend(collect_opi_references(path, repo))
        except ET.ParseError as exc:
            parse_errors.append({"file": path.relative_to(repo).as_posix(), "error": str(exc)})
    producers = runtime_producers(repo) if probe_runtime else {}
    for row in rows:
        name = row["pv"]
        row["registry"] = pv_registry_match(name, registry)
        row["runtime_owner"] = (
            "operator_input" if name in inputs else
            "external_condition" if name in external else
            "declared_output" if name in explicit_outputs else
            "unclassified"
        )
        row["producer"] = producers.get(name, "")
        row["runtime_observation"] = (
            "model_observed" if name in producers else
            "external_scenario" if name in external else
            "not_observed_in_OFF_probe"
        )
        row["write_acl"] = (
            "allowlisted" if name in inputs else
            "NOT_ALLOWLISTED" if row["role"] == "potential_write" else "n/a"
        )

    referenced = {r["pv"] for r in rows if r["registry"] in {"exact", "implicit_VAL"}}
    pairs: list[dict[str, str]] = []
    for name in sorted(inputs):
        matches = candidate_readbacks(name, registry)
        rows_for_input = [row for row in rows if row["pv"] == name]
        modern = any(row["generation"] == "phoebus" for row in rows_for_input)
        historic = any(row["generation"] == "legacy" for row in rows_for_input)
        generated = [m for m in matches if m in producers]
        status = ("no_candidate_identified" if not matches else
                  "model_observed_in_OFF_probe" if generated else
                  "not_observed_in_OFF_probe")
        pairs.append({
            "command": name,
            "candidate_readbacks": " | ".join(matches),
            "observed_readbacks": " | ".join(generated),
            "producer_sources": " | ".join(sorted({producers[m] for m in generated})),
            "assessment": status,
            "in_phoebus": "yes" if modern else "no",
            "in_legacy_opi": "yes" if historic else "no",
        })

    unique = {r["pv"] for r in rows}
    modern_unique = {r["pv"] for r in rows if r["generation"] == "phoebus"}
    legacy_unique = {r["pv"] for r in rows if r["generation"] == "legacy"}
    missing = sorted({r["pv"] for r in rows if r["registry"] == "missing"})
    macros = sorted({r["pv"] for r in rows if r["registry"] == "macro_unresolved"})
    unallowlisted = sorted({r["pv"] for r in rows
                            if r["generation"] == "phoebus"
                            and r["role"] == "potential_write" and r["pv"] not in inputs
                            and r["registry"] == "exact"})
    unobserved_monitors = sorted({
        r["pv"] for r in rows
        if r["generation"] == "phoebus" and r["role"] == "monitor_or_other"
        and r["registry"] == "exact" and r["pv"] not in producers
        and r["pv"] not in inputs and r["pv"] not in external
        and any(marker in r["pv"] for marker in READBACK_MARKERS)
    })
    files_by_generation = Counter(r["generation"] for r in rows)
    summary = {
        "registry_total": len(registry),
        "file_count": len([p for p in files if p.is_file() and p.suffix in {".bob", ".opi"}
                           and (include_legacy or p.suffix == ".bob")]),
        "pv_occurrences": len(rows),
        "unique_references": len(unique),
        "phoebus_unique": len(modern_unique),
        "legacy_unique": len(legacy_unique),
        "modern_only": len(modern_unique - legacy_unique),
        "legacy_only": len(legacy_unique - modern_unique),
        "runtime_produced_in_OFF_probe": len(producers),
        "operator_allowlisted": len(inputs),
        "referenced_registry_unique": len(referenced),
        "missing_pvs": len(missing),
        "unresolved_macros": len(macros),
        "phoebus_potential_writes_not_allowlisted": len(unallowlisted),
        "phoebus_readback_like_not_observed_in_OFF_probe": len(unobserved_monitors),
        "parse_errors": len(parse_errors),
        "reference_occurrences_by_generation": dict(files_by_generation),
    }
    return {
        "summary": summary, "references": rows, "pairs": pairs,
        "runtime_producers": producers, "missing": missing, "macros": macros,
        "unallowlisted": unallowlisted, "unobserved_monitors": unobserved_monitors,
        "parse_errors": parse_errors,
    }


def markdown(report: dict[str, object]) -> str:
    s = report["summary"]
    lines = [
        "# Automated OPI / PV registry / Python producer audit",
        "",
        "Generated offline from the repository. **This is not a real IOC or physics validation.**",
        "An observed producer means the Python model published the PV during an initial",
        "OFF-state step. Conditional outputs and dynamic OPI expressions can be missed.",
        "Widget roles are heuristic; potential write candidates require OPI review.",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "|---|---:|",
    ]
    lines += [f"| {key.replace('_',' ')} | {val} |" for key,val in s.items()
              if isinstance(val, int)]
    groups = [
        ("Missing PV names (exact OPI expressions)", report["missing"]),
        ("Macro/dynamic PV names requiring resolution", report["macros"]),
        ("Phoebus potential write widgets not in operator allowlist", report["unallowlisted"]),
        ("Readback-like Phoebus monitors not produced in OFF-state probe", report["unobserved_monitors"]),
    ]
    for title, values in groups:
        lines.extend(["", f"## {title} ({len(values)})", ""])
        lines.extend(f"- `{v}`" for v in values[:80])
        if len(values) > 80:
            lines.append(f"- ... {len(values)-80} more; see the full CSV/JSON audit.")
    if report["parse_errors"]:
        lines.extend(["", "## XML parse errors", ""])
        lines.extend(f"- `{e['file']}`: {e['error']}" for e in report["parse_errors"])
    lines.extend([
        "", "## How to interpret gaps", "",
        "1. A PV is not a model output merely because it exists in V2.0.",
        "2. An unobserved readback might be conditionally generated; investigate its model.",
        "3. A writable widget type does not imply that every referenced PV is written.",
        "4. EPICS record fields like `MOTOR.RBV` require compatible record definitions.",
        "5. The input/readback candidate pairs are conservative naming/registry matches.",
        "6. Keep the simulator VM and all CA/PVA discovery isolated from LIPAc.",
        "",
        "See `opi_pv_references.csv`, `operator_readback_pairs.csv`, and",
        "`audit_summary.json` in the generated audit artifact.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, default=ROOT)
    p.add_argument("--output-dir", type=Path, default=ROOT / "reports" / "pv_opi_coverage")
    p.add_argument("--exclude-legacy", action="store_true")
    p.add_argument("--skip-runtime", action="store_true")
    p.add_argument("--check", action="store_true",
                   help="Fail only on XML parse errors or impossible registry/ACL references; known coverage gaps remain report-only.")
    args = p.parse_args()

    report = build_report(args.repo.resolve(), not args.exclude_legacy, not args.skip_runtime)
    dest = args.output_dir.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    _write_csv(dest / "opi_pv_references.csv", report["references"], [
        "file", "generation", "pv", "widget_type", "widget_name", "role",
        "registry", "runtime_owner", "producer", "runtime_observation", "write_acl",
    ])
    _write_csv(dest / "operator_readback_pairs.csv", report["pairs"], [
        "command", "candidate_readbacks", "observed_readbacks",
        "producer_sources", "assessment", "in_phoebus", "in_legacy_opi",
    ])
    summary_payload = {k:v for k,v in report.items()
                       if k not in {"references", "pairs"}}
    (dest / "audit_summary.json").write_text(
        json.dumps(summary_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (dest / "AUDIT.md").write_text(markdown(report), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    if args.check:
        invalid = [r["command"] for r in report["pairs"]
                   if r["command"] not in {
                       i["name"] for i in json.loads(
                           (args.repo / "config/pv_registry_v2_0.json").read_text(encoding="utf-8")
                       )["pvs"]
                   }]
        if report["parse_errors"] or invalid:
            print(f"Audit failure: {len(report['parse_errors'])} XML errors, "
                  f"{len(invalid)} unregistered allowlist PVs", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
