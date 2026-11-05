# LIPAc Injector Python device models (OTP)

This directory contains all simulation and original-LCS equation implementations.
**No model calls caput/caget, writes an EPICS database, or communicates with
a real accelerator.** The thin EPICS IOC is a transport/interface boundary.

## Evidence and version precedence

1. Injector LCS User Manual **v4.0, 01-Oct-2026**: operating modes, security
   boundaries, CHOP_IM states and gas/vacuum topology.
2. **BA_D_2E9QH7 v2.0, 09-Jul-2026**: CW start-up task numbers, HV/IE/Repeller
   target sequence, RF operating points and current/ramp settings.
3. [topIFMIF_INJ](https://github.com/andimec/topIFMIF_INJ), commit
   `3586551ce2eaede262d5cf584ab88d2d940c3a83`: EPICS `CALC`,
   register scales, limits, SNL state machines and historical device wiring.
4. Available PLC-ladder and LabVIEW CIM artifacts are **historical**. Their
   current deployment status and protection semantics have not been verified.
5. Unverified dynamic parameters in `config/model_parameters.yaml` are
   training assumptions only.

## Model inventory

| Python module | Family | Implemented fidelity | Important limitation |
|---|---|---|---|
| `catalog.py` | all registered PVs | interface contract and metadata | PV presence does not imply live hardware |
| `original_lcs_logic.py` | LCS legacy calculations | exact source expressions | not a physical model |
| `power_supplies.py` | Coils C1/C2, solenoids, steerers, HV, IE, R, RC | source scaling + rate-limited response | transfer functions uncalibrated |
| `hv_auto_ramp.py` | automatic HV/IE/Repeller startup | 2026 procedure-based command sequence | feedback timeouts and repeller dwell are provisional |
| `chopper_cim.py` | CIM | actual OPI PRE-ARM/ARMED commands, manual thresholds, FBI snapshots | FPGA trigger logic and reset not reconstructed |
| `control_devices.py` | RF, ATU, timing, FC, chopper positions, beam | exact RF bits + qualitative dynamics | ECR plasma/transport not yet solved |
| `plant.py` | H2/D2 valves, source & LEBT MFC, VAC01/02 pumps and pressures | source topology + empirical equations | pumping curves and conductances uncalibrated |
| `vacuum_opi.py` | VAC01/02 PV/SV help preconditions | exact OPI formulas | NOT PLC valve actuation authorization |
| `calorimetry.py` | FC, BS, IC | exact source CALC/FLNK equations | input sensor calibration and physical duty remain uncertain |
| `emu_geometry.py` | EMU plate geometry and global grid | exact SNL geometrical equations | slit field/acceptance uncalibrated |
| `emu_hardware.py` | EMU MaxV/servo, PS1/2 and FACQ | SNL timing and training actuator response | speed, delays, acquisition synthetic |
| `emu_sequencer.py` | EMU wide/edge/ROI scans | 2026 source transitions and verified sample guards | documented Fast/Full profiles identified; named preset selection not implemented |
| `emu_beam.py`, `emu_analysis.py` | optional beam fixture and RMS diagnostics | analytic second moments, opt-in Gaussian toy | not validated phase-space measurement |
| `emu_replay.py` | recorded experimental EMU scans | validates archived geometry, displays five-column samples, exports legacy TXT and provenance | standalone file replay; no EPICS PV bridge, live acquisition or waveform arrays |
| `injector.py` | model composition | physical/logic execution ordering | other instrument families are still interface-only |
| `subsystems.py` | older framework stubs | legacy scaffolding | not source-validated |

## Separation of commands and readbacks

`SimulationContext.emit()` produces **model-owned output** PVs.
`SimulationContext.request_command()` is for Python sequencers to change a
**pre-authorized operator-setpoint/command** PV. The engine calls
`SimulationPVState.put()` only if the PV appears in the strict
`config/pv_runtime_overrides.yaml` input list.

There is one in-memory authoritative writer per PV. Reconstructed source
equations publish output PVs; original `CALC` records must be excluded from
the **eventual** EPICS 7 Soft IOC to avoid competing calculations.

The current `db/` folder still contains historical records with `calc`/
`calcout` types; those are **not ready for direct loading as the final dumb
IOC**. The live IOC generation/bridge and Debian 13 systemd deployment remain
separate integration work; no production CA/PVA endpoints are used.

## Numerical assumptions and units

- `LEBT:HV_PS:HTCmd` in kV; `CalcVHT` in V. The supply's `ICmd` is
  a current **limit**, not a measured load current.
- IE and repeller voltage/current hardware register scaling use original
  full scales of 30000 counts.
- Original RC_PS current readback `IRdbkcalc` differs in scale from the
  command-side `Icalcout` (1 versus 10). This discrepancy is retained.
- Source `SRC:RF_GENE:RfPwr` and `RfOffset` are separate Modbus settings.
  No unverified additive offset is applied by default.
- `SRC:TIM:DutyCycle` is reproduced for OPI compatibility from original
  EPICS calculation; `context.metrics["timing.duty_cycle"]` carries the
  physically meaningful pulse width divided by period.
- Calorimetric PV results are original **legacy calculation outputs** and
  should not be interpreted as validated beam power.
- VAC01 uses H2/D2 source injection; VAC02 uses separate auxiliary LEBT
  PR4000B flow. No cross-region conductance is assumed yet.

## Regression tests

- `tests/test_original_lcs_logic.py`: record equations, RF bitmap, timing.
- `tests/test_hv_auto_ramp.py`: documented HV sequence and failsafe abort.
- `tests/test_chopper_cim.py`: CIM state, thresholds and injected FBI snapshot.
- `tests/test_gas_vacuum_topology.py`: gas injection topology.
- `tests/test_calorimetry.py`: original FC/BS/IC equations.
- `tests/test_power_supply_scaling.py`: original FuG and MCPS conversions.
- `tests/test_architecture.py`: authorization separate from actuator physics.
- `tests/test_emu_replay.py`: experimental Fast/Full sample counts, export compatibility, provenance, interactive sequence and Start SNL script.

The GitHub Actions test pipeline checks Python simulation determinism and
record-level equations. **It does not certify the live PLC, FPGA, OPI runtime,
or beam physics.**

## EMU instructions

See [full EMU reconstruction](../../../docs/emu_reconstruction.md) for state
transitions, original SNL equations, source inconsistencies, operator PVs and
remaining calibration. Local demo with no EPICS network:

```bash
python -m pip install -e .
python scripts/demo_emu.py --mode emittance --synthetic-signal --out /tmp/emu_training.csv
```

This command runs only an in-memory Python simulation and never connects to
real Injector PVs.

### Experimental SNL v2 playback

A separate **offline** application replays the actual 2026 EMU experiment
archives. From the repository root:

```bash
./scripts/launch_emu_snl_replay.sh --duration 180
# Without a display:
python3 -m injector_otp.models.emu_replay --auto --save on --output-dir output/emu
# Console only, do not create output directory or files:
python3 -m injector_otp.models.emu_replay --auto --save off
```

The OTP OPI `Start SNL` button uses
`Injector_OPI/Scripts/emitShell_v2.sh`, which invokes this local launcher.
`Validate` and `ON` are **manual terminal commands**, not yet connected
to OPI PV writes. These recorded samples do not enter the in-memory
`EmuAcquisitionModel`; the experimental replay and synthetic scan are
intentionally separate. See
[Fast Scan replay](../../../docs/emu_fast_scan_replay.md).

### EMU Save control

The OPI boolean `Validate` initiates ROI checking, the ON/OFF
`Actemit` selector starts/aborts the sequencer and the `Savemit`
checkbox is latched as `EmuScanSequencer.save_requested` on starting
a scan. The sequencer does not perform direct disk writes and does
not force the checkbox to ON (unlike the original SNL).
The standalone replay honors Save OFF with **zero output file
creation**, and Save ON with SNL TXT + JSON provenance. To set
the standalone choice, use `save on` or `save off` before
`validate` and `on`, or `--save on/off` for headless runs.
Real OPI-to-Python PV delivery is a separate pending integration.
