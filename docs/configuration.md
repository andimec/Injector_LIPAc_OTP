# Configuration of the Injector LIPAc offline simulator

> **Baseline:** 5 November 2026, after PV registry V2.0, EMU reconstruction and native PV-name integration. All paths are relative to the repository root.

## 1. Active and historical PV registries

- **Active default:** `config/pv_registry_v2_0.json` (1,052 PV/field references). `src/injector_otp/app.py:build_application()` loads this file unless explicitly overridden.
- **Historical archive:** `config/pv_registry_v1_2.json` (891 entries), retained for reproducibility, not the default.
- `config/pv_registry.yaml` is a historical/initial contract and **does not supersede** the reconciled V2.0 JSON.
- The V2.0 registry combines historical PV snapshot, copied EPICS DB files, original LCS audit and OPI references. Record fields and unresolved macro names require special care when generating a future IOC.

Source EPICS read/write metadata is **not** the same as model command/write ownership.

## 2. Runtime PV ownership

`config/pv_runtime_overrides.yaml` defines:

- `inputs`: approved operator-write commands/setpoints, including EMU scan parameters and motor/plate commands.
- `external_conditions`: simulated PPS/PLC/operational conditions, not operator-writable in Phoebus.
- `outputs`: selected simulation-owned readbacks/status values.

Only explicitly allowed inputs can be changed with `SimulationPVBackend.put()`. The Python engine uses `context.emit()` for readbacks and `context.request_command()` for **allowlisted** internal sequencer commands. The V2.0 registry contains many entries beyond this verified set; do not infer write permissions by name suffix alone.

## 3. Model parameters vs operating references

- `config/model_parameters.yaml`: numerical training parameters, e.g. ramp rates, gas response times, vacuum pressure balance, RF response/ATU hypotheses and EMU motor/plate/FACQ synthetic settings. These are not generally calibrated device constants.
- `config/injector_operating_parameters.yaml`: reference values from operator procedures/manuals, not automatically enforced safety thresholds.
- `docs/original_lcs_model_logic.md`: source-derived calculations and their limitations.

## 4. Initial conditions

`config/simulation/default.yaml` specifies:

- `simulation.initial_state` and `simulation.timestep_s` (default 0.1 s);
- `external_conditions` for scenario setup;
- `initial_pvs` for startup values and EMU input defaults;
- `device_faults` for scenario fault flags.

Startup values are **not** proof that the real machine is ready. Configuration cannot replace dynamic model-owned readbacks or PPS logic; internally generated model outputs take precedence once the engine advances.

## 5. Native PV names and VM network configuration

Source names are unchanged: `SRC:COIL01_PS:ISet` is also the simulated IOC/Phoebus name. There is **no `OTP:` prefix or mapping**.

The intended deployment is a VM disconnected from the real LIPAc control network. Do not configure a production IOC host, CA address list, PVA beacon destination, bridged interface or VPN into LIPAc. Restrict future CA/PVA access to the loopback or dedicated offline training network. Network isolation is a necessary **deployment check**, not a feature proven by the current Python tests.

Internal runtime-only indicators: `SIM:STATE`, `SIM:TIME`. They are not source LIPAc equipment PVs.

## 6. Practical local check

```bash
python -m pip install -e ".[dev]"
pytest
python scripts/demo_emu.py --mode emittance --synthetic-signal --out /tmp/emu_training.csv
```

This exercises **Python-only behavior**; it does not start the EPICS Soft IOC or prove Phoebus connectivity. See [architecture](architecture.md), [readback traceability](pv_readback_traceability.md) and [IOC contract](simulation_ioc_contract.md).

## 7. EMU archived-data playback

`src/injector_otp/models/emu_replay.py` is a standalone **replay adapter**.
It does not inherit the in-memory engine's synthetic FACQ signal and is
not affected by `config/model_parameters.yaml` response parameters.
Its default input is the 6 July 2026 Fast Scan in
`src/injector_otp/Data/EMU/emit20260706-1434_optm.txt` (1,395 points).
Other saved experiments can be selected with `--source`.

```bash
python3 -m injector_otp.models.emu_replay --list
python3 -m injector_otp.models.emu_replay --auto --duration 0 --output-dir output/emu
./scripts/launch_emu_snl_replay.sh --duration 180
```

Output is local `output/emu/` by default, following the
`emitYYYYMMDD-HHmm_optm.txt` convention with a `*.replay.json`
sidecar. The source archive is never overwritten. The shell launcher
sets `EPICS_CA_MAX_ARRAY_BYTES` for compatibility but does **not**
connect to a CA/PVA server. The OTP OPI **Start SNL** action executes
`Injector_OPI/Scripts/emitShell_v2.sh`; the later **Validate/ON**
buttons still need an isolated PV bridge. See
[EMU Fast Scan replay](emu_fast_scan_replay.md).
