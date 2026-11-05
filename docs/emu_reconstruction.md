# EMU digital twin: SNL v2 reconstruction and recorded-data replay

**Status:** executable Python training model; **not** a validated EMU
plant model, live EPICS IOC or protection implementation.

## Reproducible source baseline

- [Original SNL `emitSnlEmu_v2.st`](https://github.com/andimec/topIFMIF_INJ/blob/3586551ce2eaede262d5cf584ab88d2d940c3a83/emitApp/src/emitSnlEmu_v2.st)
  (source includes changes dated Dec 2025 / Feb 2026).
- [`emitSnlMotor.st`](https://github.com/andimec/topIFMIF_INJ/blob/3586551ce2eaede262d5cf584ab88d2d940c3a83/emitApp/src/emitSnlMotor.st)
  and [`emitSnlAlims.st`](https://github.com/andimec/topIFMIF_INJ/blob/3586551ce2eaede262d5cf584ab88d2d940c3a83/emitApp/src/emitSnlAlims.st).
- `emitApp/db/emitProcess.db`, `emitMotor.db`, `emitServo.db`,
  `emitIcv196.db`, `emitIcv150.db` and `emitIcv714.db`.
- Current Phoebus `Injector_OPI/emu*.bob`, `emitMeasurement_v2.bob`.
- **Injector LCS User Manual v4.0**, 01-Oct-2026, EMU section (Fast Scan /
  Full Scan, positioning and acquisition). Additional source procedures cited
  by that manual: `EMU_LIPAC_User_Manual (2E7XBQ v1.0)`,
  `EMU_Optimization_Maintenance_Manual (22BCRE v2.1)` and
  `BA_D_2E98YT v1.0`. These EMU references, the optimization report and
  the original `emitSnlEmu_v2.st` source were subsequently available for
  the Fast/Full operator settings and the recorded-data replay. This
  does not validate hardware calibration.
- Motor field semantics: [EPICS motorRecord reference](https://github.com/epics-modules/motor/blob/master/docs/motorRecord.html)
  explains that `DMOV` and `MOVN` are independent (DMOV completion does
  not equal simply `not MOVN`).

## Source reconstruction

The actual SNL has 27 named EMU states:

```text
connectEmit -> wait
wait -> initMesEmit -> chkAlims -> chkFacq -> buildGrid
     -> cmdMoteur -> verifMoteur -> waitAlims -> syncMesure2
     -> actEmit -> (voltage step -> waitAlims, or motor row -> cmdMoteur)
     -> wait
wait -> scanLarge -> verifAlimsSL -> syncScanLarge -> scanLarge
wait -> initDetectUp -> incMoteur -> verifMoteurUp
     -> verifAlimsUp -> syncDetectUp -> scanDetectUp -> incMoteur
wait -> initDetectLow -> decMoteur -> verifMoteurLow
     -> verifAlimsLow -> syncDetectLow -> scanDetectLow -> decMoteur
wait -> actValidate -> wait
cmdMoteur -> pause4 -> actEmit
```

The Python runtime retains the operative sequence while consolidating
internal phases into explicit bounded state transitions:

```text
IDLE -> WAIT_MOTOR_ENABLE -> WAIT_PLATES_ENABLE
     -> WAIT_MOTOR -> WAIT_PLATES -> WAIT_ACQUISITION
     -> (next VHT target / next motor position) -> COMPLETE
any active stage -> PAUSED -> previous stage
any active stage -> ABORTED (fault, stop, lost external safety, timeout)
```

### Motor and power-supply blocks

| Hardware | Source controls | Python readback / outcome |
|---|---|---|
| MAXv motor | `MOTOR.CNEN`, `MOTOR.VAL`, `MOTOR.HOMR`, `MOTOR.SPMG` | `MOTOR.RBV`, `MOVN`, `DMOV`, `ATHM`, `HLS`, `LLS`, `LVIO`, `Position` |
| Servo | `EMIT_SERV:EnaDisa`, `Refresh` | motor authorization, no fake servo status |
| Plate PS1/2 | `EMIT_PS*:Softbo`, `VSet` | `OnOffCmd`, `OnOffCmd.RVAL`, `VRdbk`, `Calcdly.ODLY` |
| Acquisition | `EMIT_FC:I` event, `FACQ` timing | deterministic training sample event, no fake 10k-sample waveform |

The original `emitSnlMotor.st` sequences enabling MAXv, enabling servo and
refreshing status in 1-second stages; disabling reverses that sequence.
The script declares `ExtSec` but does **not** explicitly gate the SNL
transitions on it. Python **conservatively gates** enable and movement using
`LEBT:EMIT:ExtSec` plus `FSDefStat`. That design decision is an OTP safety
rule, pending confirmation of the deployed PLC/servo wiring.

`emitSnlAlims.st` sets `Calcdly.ODLY=0 s` when each supply is ON and
`30 s` otherwise. This is **a record processing delay setting**, not
evidence of an actual 30-second HV rise time.

The motor's source `DHLM=182 mm`, `DLLM=-3 mm` and absolute arrival
tolerance 0.01 mm are retained. A nominal motor speed (20 mm/s) and plate
slew rate (10000 V/s) are explicit, changeable training hypotheses.

### Emittance geometry

The SNL calculates a geometric factor

```text
D = (LP + 2*LFSP)*LP / [4*GP*(LFEP + LP + LFSP)]
LFEP = 0.010 m
LP   = 0.090 m
LFSP = 0.002 m
GP   = 0.009 m
```

With angles in mrad and beam energy in keV:

```text
VpicInit = AnglePicInit * Energy / D
VpicEnd  = AnglePicEnd  * Energy / D
DeltaV   = AngleDelta   * Energy / D
Vstart   = VpicInit + DeltaV/2
Vend     = VpicInit - DeltaV/2
Vstep    = DeltaV / (2*Nptemit)

Upper = 130 - Borderup
Lower = 130 - Borderlow

Vpic(motor_position) = slope * motor_position + intercept
slope = (VpicEnd - VpicInit)/(Lower - Upper)
intercept = VpicEnd - slope*Lower
```

The global `VHT=V1-V2` grid has at most **4096 points**, with spacing
`dVHT=2*Vstep`. Each motor position scans the interval centered on
`Vpic(motor_position)`, snapped to this global grid, high voltage to low
voltage. Plate commands are `V1=VHT/2`, `V2=-VHT/2`.

`Position=-MOTOR.RBV` is retained for original graph compatibility.
This is not silently reinterpreted as the external physical slit coordinate.
Actual plate field maps and slit transmission require calibration.

### Four operations

| Original input PV | Training action |
|---|---|
| `Actemit` | Validated optimized ROI emittance scan, motor rows plus plate voltage bins |
| `Actscan` | Wide voltage scan at current motor position; source PS1=V, PS2=-V |
| `Actupper` | Increment motor from 0 mm toward `Limdet`, wide scan at each position |
| `Actlower` | Decrement motor from 180 mm toward `Limdet`, wide scan at each position |
| `Validate` | Check peak angles, borders, positive energy/steps, 4096-bin limit and travel |

Fast Scan and Full Scan are two operator parameter profiles for the same
`Actemit` emittance measurement action, rather than different
`EmuMode` enum values. Their **documented parameter sets** are now
available and can be compared with the archived experiments. The
in-memory `EmuScanSequencer` still takes generic ROI inputs; it does not
yet implement a named Fast/Full profile selector.

### Fast/Full settings and comparison with archived 2026 measurements

| Parameter | Fast Scan, steps 22–30 | Full Scan, steps 32–40 |
|---|---:|---:|
| OPI upper / lower (mm) | 46 / -42 | 60 / -44 |
| Motor step (mm) | 2 | 2 |
| Beam energy D+ (keV) | 100 | 100 |
| Peak angle init / end (mrad) | -37 / +45 | 0 / 0 |
| Angle delta (mrad) | 20 | 100 |
| HVpoints (voltage intervals) | 30 | 120 |
| Approximate run time | 3 min | 10 min |

The procedure specifies 50 keV for proton beams. The SNL transforms OPI
border coordinates to motor position by `motor = 130 - border`.

Archived test data:
- `emit20260706-1434_optm.txt`: **Fast Scan** reference, 45 motor rows
  (84–172 mm) × 31 points = **1,395** samples.
- `emit20260610-1611_optm.txt`: **Full Scan** reference, 53 rows
  (70–174 mm) × 121 points = **6,413** samples.
- `emit20260604-1847_optm.txt`: full-coverage *variant*, 43 rows
  (90–174 mm) × 101 points = **4,343** samples; not identical to
  the procedural Full Scan defaults.

The archived signals and format validate the replay parser. They do
**not** validate the reduced-order motor dynamics, plate transients or
beam physics. The console workflow is described in
[Fast Scan experimental replay](emu_fast_scan_replay.md).

### Acquisition and results

The original SNL waits on an event flag synchronized to `EMIT_FC:I`:
`sync iFaisc flagFaisc` / `efTestAndClear(flagFaisc)`.
It stores per-sample position, commanded VHT, angle, collected current
and measured VHT. Optional waveforms are saved to a hardcoded path in the
source; the *in-memory sequencer* has no filesystem side effects and
returns CSV through `EmuScanSequencer.results_csv()`. A **separate**
`models/emu_replay.py` adapter validates archived headers with
`emu_geometry.build_roi()`, creates compatible `EmuSample` objects,
prints historical measurements in xterm and writes legacy five-column
`emitYYYYMMDD-HHmm_optm.txt` files plus `*.replay.json` provenance.
It does not run `build_application()`, drive PVs, or generate a new beam
distribution. Set and measured VHT columns remain separate.

An explicit *synthetic scalar FACQ clock* is enabled for training,
`config/model_parameters.yaml -> emu.facq.synthetic_period_s`.
This **does not model sampling at kSamples/s** or a real oscilloscope/
fast-acquisition trigger. Real FACQ data must arrive through a future
dedicated adapter. A Gaussian 2D beam profile can be enabled under
`emu.facq.synthetic_phase_space.enabled=true` to exercise the scan and
verify reconstruction, but is **off by default**.

`EmuScanSequencer.preliminary_emittance()` calculates current-weighted
second moments, ε_rms, α, β and γ in motor-position/mm and angle/mrad
coordinates. These are **uncorrected illustrative values**, not an
experimentally qualified normalized emittance. Optical acceptance,
detector calibration, integration weights and backgrounds are pending.

### Identified original-code hazards and corrective differences

1. Original `actValidate` checks `AnglePicInit==-9999` but the
   original `emitProcess.db` initializes `AnglePicInit` at **+9999**.
   The simulator rejects either sign sentinel and invalid numeric values.
2. Several SNL guards compute `consHT1/lectHT1` or
   `ecrPosition/lectPosition` without a safe zero-denominator branch.
   Python uses bounded absolute/relative errors and timeouts.
3. Source wide scan checks `consHT1==finScan`; Python safely includes the
   endpoint even if step size does not divide the span exactly.
4. `Actemit` is a binary output record, yet SNL writes `Actemit=2`
   at measurement end. The simulator uses documented zero (OFF) instead.
5. The original `pause4` is entered from `cmdMoteur` only. The simulator
   supports pause in any active waiting stage, as an explicit training
   extension. Timeout clocks are frozen during pause.
6. Original event-flag and motor-wait states may wait indefinitely. The
   simulator applies bounded motor/supply/FACQ waits.
7. The original stop handling does not always ensure plates are at 0 V.
   The simulator zeros both plate setpoints and holds motor readback after
   abort. This is an OTP exercise safeguard, **not live machine protection**.
8. The actual motor record can produce a `DMOV` 1/0/1 monitor pulse,
   including for zero-displacement commands. Our simplified position model
   reproduces stable `MOVN` and `DMOV` states but not that full EPICS
   event waveform. It must be addressed by the EPICS bridge.

### PV registry and Soft IOC compatibility

V2.0 contains **1,052 concrete PV and field references** after 6 extra
EMU SNL references were added (1,046 before the EMU pass). The six are
`ExtSec`, `MOTOR.DMOV`, two `OnOffCmd.RVAL` and two
`Calcdly.ODLY`. `Vpic` was already present.

The Python model uses those names as logical interfaces. For a true
EPICS 7 IOC, `MOTOR.DMOV` and `OnOffCmd.RVAL` are *record field*
references, not independent base record names. Their implementation
requires a field-compatible server/mapping rather than blindly creating
new records named `*.DMOV` or `*.RVAL`. The eventual Soft IOC must expose **the same original LIPAc PV names** on a VM isolated from the production network; there is no `OTP:` prefix.

The existing `db/emitApp/db/` still contains copied `calc` records.
They must not execute competing EMU calculations in the final thin IOC.

### Current naming and maturity

The Python `SimulationPVBackend` and `LocalPVBridge` preserve native PV names, e.g. `LEBT:EMIT_PS1:VSet` and `LEBT:EMIT_PS1:VRdbk`. The source records with fields such as `MOTOR.DMOV` and `OnOffCmd.RVAL` must be implemented as **record fields**, not ad hoc names of independent EPICS records. Only a private VM/training network is permitted. The current code does not implement a networked Soft IOC or validate its record-field semantics.

Read the [write/readback traceability matrix](pv_readback_traceability.md) for the OPI-facing EMU commands and model-generated monitor ownership.

### Current acceptance tests

- `test_emu_geometry.py`: geometry, sentinel validation and global grid.
- `test_emu_sequences.py`: full ROI, wide scan, both edge searches,
  stop, pause, loss of safety, motor hold and synthetic timeout.
- `test_emu_analysis.py`: Gaussian training fixture, CSV and Twiss/RMS.
- `test_emu_replay.py`: experimental sample counts, geometry, replay
  ordering, original five-column format, provenance, collision guard,
  and repository Start SNL script wiring.
- Existing `test_simulation_config.py` / `test_architecture.py`:
  operator ACL and computed-PV ownership.

All tests run **offline** and do not contact the live IOC. The
experimental replay tests also write local temporary files and inspect
the OPI script link; they do **not** prove xterm rendering or the
Phoebus-to-EPICS-bridge operation on Debian.

## Questions to close with the machine team

The supplied EMU references **2E7XBQ**, **22BCRE v2.1**, **2E98YT v1.0** and the 2026 optimization test report are available for documentary comparison. The optimized EMU user/maintenance material describes ROI acquisition, a global voltage grid and optional waveform logging. However, **having the manuals is not the same as validating the simulator against real acquisition**. Still obtain current motor/servo speed and homing calibration, plate polarity/field traces, the actual `ExtSec` PLC mapping, PS1/PS2 turn-on/ramp traces, FACQ timing/waveform datasets and confirmation of deployed OPI presets. The **documented** Fast/Full reference parameters are recorded above; automated selection and real OPI-button integration in the OTP remain pending.

## Start SNL deployment boundary

The OTP `Injector_OPI/emitMeasurement_v2.bob` executes
`/bin/bash Scripts/emitShell_v2.sh` when the operator clicks **Start
SNL**. In the repository's **training copy**, that shell entrypoint
starts `scripts/launch_emu_snl_replay.sh` and Python in xterm. The
standalone replay waits for the operator to type `validate` and `on`
at the terminal. The OPI's own `LEBT:EMIT:Validate` and
`LEBT:EMIT:Actemit` buttons do **not yet send data to the xterm process**;
that requires a separate bridge to the isolated Soft IOC.

Do not deploy the modified script on the real LIPAc workstation or
route the native-name training PVs to the machine's CA network.

## Operator PV: Validate, Actemit and Savemit

The training OPI defines **three distinct controls**:

1. `LEBT:EMIT:Validate` is a boolean push/toggle command; the Python
   sequencer validates the ROI on a rising edge and resets it to zero.
2. `LEBT:EMIT:Actemit` is an ON/OFF choice: ON starts only after
   validation, and OFF aborts the running sequence.
3. `LEBT:EMIT:Savemit` is a checkbox: the current ON/OFF value is
   latched as `EmuScanSequencer.save_requested` when Actemit starts.
   The runtime also exposes `emu.scan_save_requested` in local
   metrics. It does **not** silently change Savemit from 0 to 1.

This intentionally differs from legacy `emitSnlEmu_v2.st`, which
explicitly forced Save ON at the start of a measurement. The OTP
implements the operator's requested OFF = no new files policy.

The in-memory motor/scan model has **no filesystem side effects**;
`save_requested` is a contract for the future persistence bridge.
Meanwhile the standalone `emu_replay.py` honors the same binary
meaning via a local `--save on/off` parameter or interactive
`save on/off` console command, OFF by default. It cannot read
Phoebus PVs until the isolated IOC integration is completed.
