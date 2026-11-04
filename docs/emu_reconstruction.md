# EMU digital twin: SNL reconstruction (first executable baseline)

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
  `BA_D_2E98YT v1.0`. These three specialized manuals were **not provided
  in full** for this implementation, so their specifications were not invented.
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

The manual's operator terms **Fast Scan** and **Full Scan** are not yet
reliably mapped to distinct SNL `Actemit` parameter profiles. They must
be resolved from the 2026 optimized EMU procedure or actual OPI script,
rather than fabricated. Both can later reuse this general ROI sequencer
with a validated configuration profile.

### Acquisition and results

The original SNL waits on an event flag synchronized to `EMIT_FC:I`:
`sync iFaisc flagFaisc` / `efTestAndClear(flagFaisc)`.
It stores per-sample position, commanded VHT, angle, collected current
and measured VHT. Optional waveforms are saved to a hardcoded path in the
source; the Python model has no filesystem side effects and returns a CSV
string through `EmuScanSequencer.results_csv()`.

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
new records named `*.DMOV` or `*.RVAL`. All future network-visible PVs
must remain isolated in the `OTP:` namespace.

The existing `db/emitApp/db/` still contains copied `calc` records.
They must not execute competing EMU calculations in the final thin IOC.

### Current acceptance tests

- `test_emu_geometry.py`: geometry, sentinel validation and global grid.
- `test_emu_sequences.py`: full ROI, wide scan, both edge searches,
  stop, pause, loss of safety, motor hold and synthetic timeout.
- `test_emu_analysis.py`: Gaussian training fixture, CSV and Twiss/RMS.
- Existing `test_simulation_config.py` / `test_architecture.py`:
  operator ACL and computed-PV ownership.

All tests operate in-process; no FIBUS6, Debian 13, EPICS 7, VM I/O,
live hardware or OPC server is contacted.

## Questions to close with the machine team

Before claiming quantitative and operational equivalence, obtain the
EMU manuals **2E7XBQ**, **22BCRE v2.1** and **2E98YT v1.0**; current
motor/servo speed and homing calibration, field/polarity of plate supplies,
the real `ExtSec` PLC channel, PS1/PS2 turn-on/ramp traces, FACQ
event/waveform acquisition rules and the validated Fast/Full presets.
