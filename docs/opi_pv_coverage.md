# OPI-to-PV coverage and Python readback producer audit

**Implementation:** `scripts/audit_opi_pv_coverage.py` and `tests/test_opi_pv_coverage.py`. This audit is offline, non-invasive and uses the current `config/pv_registry_v2_0.json`, `config/pv_runtime_overrides.yaml`, `Injector_OPI/` and the actual in-process simulation engine.

## Run locally

```bash
python -m pip install -e ".[dev]"
python scripts/audit_opi_pv_coverage.py --check --output-dir reports/pv_opi_coverage
pytest tests/test_opi_pv_coverage.py
```

The default run processes both Phoebus (`.bob`) and historical CSS BOY (`.opi`) files. For the active-only review:

```bash
python scripts/audit_opi_pv_coverage.py --exclude-legacy --output-dir reports/phoebus_only
```

The GitHub Actions `tests` workflow runs the auditor and uploads the four files as an artifact named `pv-opi-coverage`. Coverage deficiencies are **reported**, not hidden or used to fail otherwise valid model tests. The `--check` mode fails on malformed OPI XML or missing allowlisted registry entries.

## Report outputs

| File | Purpose |
|---|---|
| `opi_pv_references.csv` | Every explicit PV occurrence: source OPI, widget, XML role heuristic, registry membership, Python owner if observed, ACL |
| `operator_readback_pairs.csv` | Every allowlisted command/setpoint and conservative candidate readback(s), plus observed generator sources |
| `audit_summary.json` | Machine-readable metrics and lists of missing names, macros, possible unauthorized widgets and unobserved monitor candidates |
| `AUDIT.md` | Human-readable summary and prioritized gaps; counts recalculated for every run |

## Definition of coverage

The audit differentiates these distinct concepts:

1. **OPI referenced.** An explicit `pv_name` appears in a Phoebus or CSS BOY XML widget. Embedded scripts, formula-generated PVs, unexpanded macros and dynamically loaded child displays may require manual inspection.
2. **Registry resolved.** The reference matches a V2.0 entry, or has the implicit `.VAL` field of a base record. Other `record.FIELD` references are not automatically assumed to exist.
3. **Write authorization.** `config/pv_runtime_overrides.yaml` explicitly enables a PV for operator input; the XML widget type is only a **potential write** classifier.
4. **Model observed.** The Python model actually publishes the PV during the initial OFF-state simulation step, with `PVValue.source` identifying its generator. **An absent observation is not proof that no conditional generator exists.**
5. **Readback pairing.** Candidate pairs are created from explicit mappings and name suffixes, **only if the readback exists in V2.0**. A same-name echo is not accepted as a physical response.
6. **Functional validity.** Tests must demonstrate command-to-readback behavior with ramps, faults and time delays. This audit is a prerequisite, **not** a substitute.
7. **Deployment validity.** EPICS 7, field-compatible Soft IOC records, Phoebus monitors, scan rates, alarm semantics and network isolation remain separate acceptance criteria.

## Important interpretation cases

- **HV:** `LEBT:HV_PS:ICmd` is a current **limit**, not a readback of actual HV load current. The audit does not falsely pair it with measured current.
- **EMU:** `LEBT:EMIT:MOTOR.VAL` pairs with record fields `.RBV` and `.DMOV`. An IOC must implement them as compatible EPICS record fields, not arbitrary standalone record names. The plate setpoints have separate dynamic `VRdbk` outputs.
- **RF:** `SRC:RF_GENE:PwrRef` is **reflected** RF power, not a direct monitor of `RfPwr`. Forward power lacks a confirmed source-PV mapping.
- **IE, R_PS and RC_PS:** Source registers and engineering-unit `IRdbkcalc`/`VRdbkcalc` are distinct. RC_PS has a known unresolved current scale discrepancy.
- **Vacuum and gas:** Dynamic readbacks are reduced-order training hypotheses, not calibrated gas conductance/pump behavior.
- **PPS/MPS:** External protection conditions are not writable from Phoebus, and training responses do not certify safety functions.

## Prioritization

Resolve missing **concrete Phoebus** PV names first. Review **potential writes not in the Python allowlist**, then investigate **readback-like monitors not observed in the OFF probe**, then review legacy-only names and macros. For each high-priority PV, check the actual OPI control, its source DB record/field, model ownership, units, engineering limits, scan time, and control transition.

**No `OTP:` name transformation is used.** Native LIPAc names are safe in this project only because the future VM/Soft IOC must be isolated from the production network. The audit uses no Channel Access or PVAccess endpoint.

Related: [architecture](architecture.md), [runtime contract](pv_runtime_contract.md), [readback matrix](pv_readback_traceability.md), [EPICS integration](epics_architecture.md).
