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

## Measured repository baseline, 5 November 2026

Validated by [GitHub Actions run 41948528635](https://github.com/andimec/Injector_LIPAc_OTP/actions/runs/41948528635). **101 Python tests passed**. The report contains:

| Observable | Result |
|---|---:|
| Phoebus .bob screens / legacy .opi screens | 37 / 39 |
| Explicit references including duplicate widget occurrences | 1,963 |
| Distinct concrete/dynamic references across both sets | 539 |
| Distinct Phoebus PV references | 522 |
| Concrete references matching the V2.0 inventory | 538 |
| PVs absent from V2.0 after resolving calculated expression syntax | **0** |
| Unresolved macro expressions | 1, `$(pv_name)` |
| Operator input PVs in explicit allowlist | 157 |
| Signals published by Python in the initial OFF-state step | 146 |
| Phoebus potential-write references outside allowlist | 73, **not automatically safe to enable** |
| Readback-like monitors not observed in the OFF step | 72 |
| Of which MPS/PPS external bitfield references | 65 |
| Of which preinitialized scenario status monitors | 1 |
| **Remaining equipment readback candidates** | **6** |

The original three "missing PVs" reported during development were `='LEBT:CHOP_IM:DbgDPeriod'/1000`, `='LEBT:CHOP_IM:DbgDPulse'/1000` and `=1`. These are Phoebus expressions, **not absent EPICS records**. The parser now extracts the two underlying source PVs and excludes numeric constants from the PV inventory.

### Six OPI equipment monitors requiring explicit engineering review

| OPI monitor | Likely implementation location | Resolution needed |
|---|---|---|
| `LEBT:CHOP_PS:OnStat` | `models/power_supplies.py` or dedicated chopper PS model | Check actual source command and status mapping; CHOP_PS is not currently in the dynamic PS prefix list |
| `LEBT:EMIT:OutStat` | `models/control_devices.py` / `emu_hardware.py` | Identify actual mechanical position feedback rather than assuming it follows a command |
| `LEBT:EMIT_PSR:VRdbk` | `models/emu_hardware.py` | Add the EMU electron-repeller power-supply path after confirming the source DB, units and enabling behavior |
| `LEBT:STV01_PS:IRdbkcalc` | `models/power_supplies.py` | Source DB contains `CALC=(A*B)/C`; do not equate raw and engineering values until scale factors are verified |
| `LEBT:VAC01:LTVOpenStat` | `models/plant.py` / external scenario | Determine whether the status is derived from a modeled valve or external PLC status |
| `LEBT:VAC02:LTVOpenStat` | `models/plant.py` / external scenario | Same validation for VAC02 |

**One real improvement completed:** `LEBT:STH01_PS:VRdbkcalc` and `LEBT:STH02_PS:VRdbkcalc` are now generated by `PowerSupplyDevice.update()` using a reduced-order, rate-limited voltage state. The original DBs identify them as measured-voltage analog input records in volts. Their actual hardware calibration remains unverified. The unit tests verify ramp behavior and shutdown; these are **training** readbacks rather than experimentally calibrated voltmeters.

The **65 MPS/PPS bitfields** are deliberately separated from ordinary equipment gaps. They must be treated as external protection/scenario signals or be modeled using verified protection logic; copying guessed equipment states into them would create a misleading representation of machine protection.

For the **73 possible OPI writes**, first inspect the EMU `MOTOR.*` engineering fields and `LEBT:CHOP_PS:VSet`. Some widgets are editable, but that does not imply those PVs should be writable from the current operator simulation interface. Keep them blocked until their meaning, range, ownership and generator are reviewed.

**Artifact:** [download the complete four-file audit (CSV/JSON/Markdown)](https://github.com/andimec/Injector_LIPAc_OTP/actions/runs/41948528635/artifacts/13379582136).

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
