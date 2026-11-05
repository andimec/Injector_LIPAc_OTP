# EMU v2 Fast Scan: offline xterm replay

## Scope and boundaries

This utility reproduces the **console display and original 5-column data
file** of the EMU SNL v2 measurement using historical experimental samples.
It is an **offline replay**, not a new beam measurement, EPICS CA/PVA client,
motor/voltage controller, or a calibrated physical model. No accelerator
hardware is accessed. The adapter imports the existing SNL-derived Python
geometry (`emu_geometry.py`) and EmuSample (`emu_sequencer.py`) instead
of creating a competing beam-physics model.

Source references:
* Uploaded `emitSnlEmu_v2.st`: `state wait` creates the filename and
  header, `state syncMesure2` logs motor, voltage, current and angle.
* BA_D_2E98YT v1.0, steps 22–31 (Fast Scan), 42–45 (Start SNL,
  Validate, Save), 50 (ON; result file).
* BA_D_22BCRE v2.0 pp. 3–5 (ROI, hvpoints, file naming); BA_D_22BCRE
  v2.1 pp. 5–7 (fixed voltage grid and SNL state flow).

## Archived experiments

| Archived file | Profile | Motor rows | Points/row | Total |
|---|---|---:|---:|---:|
| `emit20260706-1434_optm.txt` | Fast ROI | 45 | 31 | 1,395 |
| `emit20260604-1847_optm.txt` | Full-coverage variant | 43 | 101 | 4,343 |
| `emit20260610-1611_optm.txt` | Full Scan reference | 53 | 121 | 6,413 |

The July 6 Fast Scan recording gives `Upper=84`, `Lower=172` motor
coordinates and `Mstep=2`. The operator coordinates are therefore
`upper=46 mm`, `lower=-42 mm` because the SNL computes
`motor=130-border`. `Energy=100 keV`, peak angles approximately
-37 and +45 mrad, delta 20 mrad and `HVpoints=30`. These are the
documented Fast Scan settings.

The fifth experimental column (`V1-V2(V)-real`) can differ substantially
from the commanded second column (`V1-V2(V)-set`). Both recorded
numbers are preserved, without assumed calibration corrections.

## Run on Debian/Linux

Install Python 3.10+ and `xterm`, from repository root:

~~~bash
python3 -m pip install -e .
./scripts/launch_emu_snl_replay.sh --duration 180
~~~

The `Start SNL` action opens a 110x60 terminal and enters
**waiting**. In this version type `validate` and then `on`
in the terminal. `--duration 180` spreads the default 1,395 points
over roughly three minutes, matching the procedure's order of magnitude.
Use `--duration 0` (default) for immediate testing.

Without an X11 server:

~~~bash
python3 -m injector_otp.models.emu_replay --list
python3 -m injector_otp.models.emu_replay --auto --duration 0 \
  --source src/injector_otp/Data/EMU/emit20260706-1434_optm.txt \
  --output-dir output/emu
~~~

The launcher sets `EPICS_CA_MAX_ARRAY_BYTES=10485760` for script
compatibility but **does not use EPICS**. Unlike the original
`ps | grep xterm` guard, an unrelated xterm does not block its launch.

## Start SNL, Validate and ON are separate steps

The original operational procedure separates starting the sequencer,
validating the ROI settings and starting measurement. The OTP implements
the same order **in the standalone console**: `Start SNL` launches the
Python process and prints `Emit: waiting`; `validate` checks the
archived profile; `on` starts a time-scaled printing of saved samples.

The actual Phoebus buttons for Validate and ON still write their own
source PVs and are **not connected to this standalone replay**.
The file reader imports the existing ROI geometry and `EmuSample`
structure, but does not call the in-memory simulation's state machine,
publish FC current PVs or write plate/motor commands.

## Output fidelity

The original SNL filename convention is retained:

~~~text
emitYYYYMMDD-HHmm_optm.txt
~~~

Dates use the `Asia/Tokyo` timezone. Files go to `output/emu`
by default or the explicitly configured `--output-dir` in the
**isolated training filesystem**. Do not set a real acquisition directory.

The output retains the legacy header and five numeric columns.
Only the run's `date` and `file` header lines are updated.
A separate `*.replay.json` sidecar identifies the archived input,
number of samples, and `live_beam: false`, preventing confusion
with a new measurement. Same-minute file collisions are never
overwritten. Interrupted acquisitions remain as `*.partial`.
The original archived files are never modified.

Historical scalar data contain **no full FACQ waveform array**.
Consequently, this adapter does not fabricate an `IwfGraph/Xwf`
waveform export. That extension requires genuine waveform recordings.

## OPI Start SNL wiring and remaining integration

In the OTP repository, `Injector_OPI/emitMeasurement_v2.bob` already
runs `/bin/bash Scripts/emitShell_v2.sh` for the **Start SNL** button.
The OTP implementation replaces only its **training repository copy** of `emitShell_v2.sh` with
a path-independent launcher for the offline Python xterm replay. The OPI
must be launched with `Injector_OPI` as its working directory (as for
other relative Phoebus scripts). This edit must **never** be copied over
the real LIPAc installation. Starting the replay from the OPI button is wired via a shell command,
but actual Phoebus launch behavior on the Debian VM has not been
confirmed and no PV bridge is supplied.

The manual `validate` / `on` console inputs currently stand in
for the corresponding OPI action buttons. To control the scan via Phoebus/CSS,
a separate local bridge must route `LEBT:EMIT:Validate`,
`LEBT:EMIT:Actemit`, `LEBT:EMIT:Savemit`, `Pausemit`
and readback PVs to the Python engine in the **isolated OTP IOC**.
This work must not alter the original LIPAc OPI or publish training
values onto the production network. The true Python
`EmuScanSequencer` and hardware models are already in the repository
for that later integration.

### Acceptance checklist

1. The three archived files are discoverable and their headers validate.
2. The default Fast Scan yields 45 motor rows and 1,395 samples.
3. The terminal waits for Validate followed by ON.
4. The generated `_optm.txt` retains each original 5-column sample.
5. Replay provenance is recorded separately; existing data is not overwritten.
6. No live IOC access, actual hardware commands or production OPI edits occur.

## Regression tests and rollout checklist

Run `pytest tests/test_emu_replay.py`. GitHub Actions tests validate the
three archived datasets, the default Fast Scan count and geometry,
recorded columns, console Validate/ON ordering, source-compatible
filename/header, provenance and no-overwrite handling. Tests also
check the command path from the OTP OPI to the shell launcher.

For a manual Debian/X11 check, launch the training OPI
`Injector_OPI/emitMeasurement_v2.bob` with the `Injector_OPI/`
working directory, click **Start SNL**, check `Emit: waiting`,
type `validate` followed by `on`, then inspect `output/emu/`.
The actual GUI working directory must be verified; CI cannot check X11.

**Not yet implemented:** OPI Validate/ON/Pause/Save PV event handling
within xterm, local EPICS IOC readback publication, replayed FACQ
waveform arrays and connection to production. Output files are replay
artifacts, **not new beam measurements**.
