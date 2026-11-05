# Original LIPAc LCS logic applied to the Python Digital Twin

## Provenance and scope

Primary code reference: [topIFMIF_INJ](https://github.com/andimec/topIFMIF_INJ)
at commit `3586551ce2eaede262d5cf584ab88d2d940c3a83`.

- 46 original EPICS database files indexed in `audit/original_lcs/`.
- 729 source record definitions including 71 macro-dependent records
  (724 distinct source names; 653 concrete distinct PV names).
- 101 source `CALC` formulas and 518 records with calculation/processing links.
- Every concrete original PV appears in the OTP V2.0 registry.
- `emitApp/src/emitSnlEmu_v2.st`, `emitSnlMotor.st`, and `emitSnlAlims.st`
  preserve historical EMU state machines.
- `Resources/PLC_code/` contains dated Siemens Step7 projects and 2018
  ladder PDF exports (FC10, FC11, FC20, FC23, etc.).
- `Resources/Chopper_Interlock_Module/` contains CIM LabVIEW project, FPGA
  binary and state-machine documentation.

**IMPORTANT:** This is a mixed historical software baseline, NOT evidence that
every branch/routine is deployed in the current 2026 LCS. Current Injector LCS
User Manual v4.0 and verified current machine observations take precedence for
operational status and interlock implementation. Never copy historic Siemens
protection logic as the live safety implementation without validation.

## Software boundaries

1. **EPICS input/output definitions** define name, units, limits, data type,
   access, scan and presentation.
2. **Original `calc`, `calcout`, `FLNK` and SNL sequences** show interface
   calculations, command encoding and machine operational workflows.
3. **Original PLC program** is the source for physical permission logic, valve
   actuation, platform access and protection consequences, subject to version
   verification.
4. **Physical models** must be built/calibrated from engineering parameters and
   observed data. The IOC code alone cannot yield a valid transfer function.

Every behavioural calculation is evaluated in Python, never inside the Soft IOC.

## Model-by-model logic and maturity

| Family | Original source | Python model / logic | Implemented | Still requires validation |
|---|---|---|---|---|
| Main HV 120 kV FUG | `injectorFUG_120kV.db`, StreamDevice protocol | `PowerSupplyDevice` | Reset/Aux/HT sequence, ramp, kV->V and mA->A command conversion, voltage feedback | Actual rise/fall dynamics, current draw, arc state, shutdown delays |
| IE power supply | `injectorIE_PS.db` | `PowerSupplyDevice` | ON/OFF/RESET; 30000/50 voltage and 30000/20 current register conversions | Remote/local, ready status, actual closed-loop response and limit latching |
| Electron repeller R_PS | `injectorRPS.db` | `PowerSupplyDevice` | ON/OFF/RESET; 30000/15 voltage and 30000/20 current scale | Spark interactions and dynamic recovery |
| RC_PS repeller cone | `injectorRCPS.db` | `PowerSupplyDevice` | ON/OFF; 30000/3 voltage scale | **Inconsistency**: current setpoint uses /10 but readback uses *1/30000; confirm calibration |
| Source coils C1/C2 | `injectorCOIL01/02.db` | `PowerSupplyDevice` | Pulse commands and first-order rate-limited current | Actual Modbus ramp trigger/status, magnetic B(I), fault response |
| Solenoids 1/2 | `injectorSOL01/02.db` | `PowerSupplyDevice` | Current ramp; status word: bit0=On, bit1=Off, bit2=Ready | Real status mapping, hysteresis, magnetic transfer |
| Steerers DV/DH 1/2 | `injectorSTV01/02.db`, `injectorSTH01/02.db` | `PowerSupplyDevice` | Command/readback interface, rate-limited response | Different PS families, polarity, readback gains and optics |
| H2/D2 shutoff valves | `plcInjector_Output.db`, `plcInjector_Input.db` | `ValveDevice` | Open/close command, position feedback and PPS permit input | PLC ladder-specific movement time, fault/timeout, valve interlocks |
| H2/D2 MFC | `injectorMKS_SRC_D2/H2.db`, StreamDevice protocol | `GasFlowController` | Valve command, setpoint, lag and flow readback | MKS controller behavior, local/remote, response constants, zero/span |
| LEBT MFC | `injectorMKS_LEBT.db` | `GasFlowController` (when the V2.0 prefix is present) | A provisional flow/valve-enable response, sharing the reduced-order gas model | Gas species, actual operating function, source suffix/units and calibration |
| VAC01/VAC02 pumping | `plcInjector_Input/Output.db` | `VacuumRegionModel` | Pump commands, pump state, approximate pressure evolution | Conductance, pump curves, gauge ranges, volume, valve conductance |
| Vacuum PV/SV/AIV/NIV | `plcInjector_StatusForOpi.db` | `ValveDevice` + `VacuumOPIPreconditions` | Valve positions; exact **OPI precondition displays** | Mandatory distinction from actual PLC authorization logic |
| Gate valve GV | `plcInjector_Input/Output.db` | `ValveDevice` | Open/close and external PPS permit | Actual protection logic and fail-safe travel behavior |
| RF generator | `injectorModbus_RF.db` | `RFSystemModel` + pure original helpers | Command bit packing; Mot105 bit flags; Mot103 display scaling; synthetic power ramp | Heating times, pulse behavior, mismatch maps, beam/plasma mode, response times |
| RF automatic tuning unit | `injectorModbus_RF.db` | `RFSystemModel` interface encoding | WrtX/WrtY, ModeXY/CalcModeXY | Real motor travel, reflected-power map and optimizers |
| RF analog channel | `injectorSRC_RF.db` | Interface-only | Source formulas preserved in registry | Is this legacy analog interface active in 2026? |
| Injector timing | `injectorTiming.db` | `TimingSystemModel` | Physical duty and original legacy display ratio kept separate | Pulse alignment, phase, chopper transmission, current system integration |
| HV spark suppressor | `emitApp/db/injectorHV_Spark.db` | Interface-only | Comparator/count definitions indexed | 10 ms monitor, threshold polarity, delayed inhibition and reset |
| Chopper drive | `plcInjector_Output.db` | `PositionerModel` | Insert/remove and position state | Movement time, MPS permit and thermal thresholds |
| Chopper CIM / FBI | `Resources/Chopper_Interlock_Module/` | `ChopperCIMModel` | PRE-ARM/ARMED and injected FBI event snapshot | FPGA/cRIO thresholds, time windows, latch reset state machine |
| Cooling skid | `plcInjector_Input.db` | `CoolingSkidModel` | External sensor state and injected failure | Temperatures, flow/pressure dynamics, PLC alarms and delays |
| Faraday cup / beam stop | `plcInjector_Output.db`, `emitApp/db/injectorFC/BS_Calorimetry.db` | `PositionerModel`, `BeamTransportModel`, `LegacyCalorimetryModel` | Position/synthetic signal and recovered calorimetry calculations | Calorimetric calibration, intercept geometry and precise charge collection |
| ACCT / fast acquisition | `facqApp/db`, `emitApp/db/emitIcv*` | Interface-only | PV inventory | Acquisition timing, normalization, calibration and waveforms |
| Emittance measurement unit | `emitSnlEmu_v2.st`, `emitSnlMotor.st`, `emitSnlAlims.st` | `EmuMotorModel`, `EmuPlatePSModel`, `EmuScanSequencer`, `EmuAcquisitionModel` | Wide/upper/lower and ROI scan sequences, motor and plate readbacks, synthetic FACQ event, global 4096-point grid, preliminary RMS | Current Fast/Full presets, live FACQ waveform and physical calibration; [full audit](emu_reconstruction.md) |
| FGA / RGA / diagnostics | `injectorFGA.db`, EMU and fast-acq records | Interface-only | PV inventory and equations | Sweep parameters, physics and acquisition model |
| Platform access, PPS/MPS | Siemens FC10/FC11/FC20/FC23 (historical) | `InjectorInterlockLogic` + `SimulationControlPlane` | Distinct normalized permits and faults | Validated current PLC ladder, PPS interface ownership and failure propagation |
| Plasma / extracted beam | Current operation procedures and independent physics studies | `BeamTransportModel` (qualitative) | Bounded visualization only | ECR ionization, H2/D2 kinetics, meniscus, LEBT transport, losses and emittance |

**Maturity terminology**

- `exact_legacy_equation`: original interface expression reproduced exactly.
- `reduced_order`: explicit numerical hypothesis, not calibrated against data.
- `fault_trigger_only`: only synthetic fault activation is implemented.
- `qualitative_only`: suitable for operator UI tests, not prediction.
- `interface_only`: inventory exists; model deliberately emits no artificial data.

## Verified source equations

### HV: FUG

From `injectorApp/db/injectorFUG_120kV.db`:

- `CalcVHT = HTCmd * 1000` (kV to V).
- `CalcI = ICmd / 1000` (mA to A, **current limit**, not drawn current).
- `ScaleVHT = LectVht / 1000`.
- `ScaleIHT = LectIht * 1000`.

Do not set the measured current equal to `ICmd`. The current draw must
come from a physical/load model.

### IE and repeller analogue conversion

From `injectorIE_PS.db` and `injectorRPS.db`:

- IE: `VOut = VSet * 30000 / 50`, `IOut = ISet * 30000 / 20`.
- IE readback: `VRdbkcalc = VRdbk * 50 / 30000`,
  `IRdbkcalc = IRdbk * 20 / 30000`.
- Repeller: current full scale 20 mA; voltage full scale 15 kV.

Original `RC_PS` conversion inconsistency is not silently fixed.

### RF logic

From `injectorModbus_RF.db`:

- `CalcMot02 = (Modbus<<2)|(CWmdOn<<3)|(LimitPR<<4)|(FilOnCmd<<5)|(MOCmdOn<<6)`.
- `CalcOnOff = (MOCmdOn<<6)|(CalcMot02&63)`.
- `CalcRAZ = ((EnvoiRAZ<<7)|CalcMot02)&191`.
- `MarcheRF = (Mot105&64)>>6`.
- `PretRF = (Mot105&128)>>7`.
- `DefRF = (Mot105&8)>>3`.
- `PwrRef = Mot103 * 0.9` (display conversion).
- `CalcModeXY = ModeXY|(ModeXY<<1)` because original INPA/INPB
  both reference ModeXY. Requires review against ATU protocol.

The synthetic RF forward/reflected response is **not** validated microwave
coupling physics and is kept separate from these interface equations.

### Vacuum OPI preconditions

From `plcInjector_StatusForOpi.db`:

- VAC01 / VAC02 `PVOpenPrecond = (TPDefStat & PPOnStat) | AIVOpenStat`.
- VAC01 `SVOpenPrecond = ((((AIVOpen & NIVOpen)|SVOpen)
  |(PGTPDef & SGTPDef & PGVCDef)) & TPDef) | SVForcing`.
- VAC02 `SVOpenPrecond = (PGTPDef & SGTPDef & PGVCDef & TPSpeed) | SVForcing`.

These equations are explicitly **for the OPI**, not proof of the ladder
that controls real valve opening.

### Timing (critical interpretation)

From `injectorTiming.db`:

- `Cyclut = Trep/TPulse`.
- `DutyCycle = CWmdOn ? Cyclut : 1` as originally wired when
  `B=RF_GENE:CWmdOn` and `CALC=(B)?A:C`.

**Correction note:** The source `CALC=(B)?A:C` means *CW picks Cyclut,
pulsed mode picks 1*, which is different from the usual interpretation.
The Python simulator must not reuse this expression as physical duty.
Physical duty is `min(1, TPulse/Trep)` for pulse mode or 1 for CW.
This incompatibility is deliberately flagged for review.

### EMU state machine

`emitSnlEmu_v2.st` defines a significant multi-stage sequence, including:

`connectEmit -> wait -> initMesEmit -> chkAlims -> chkFacq -> buildGrid
-> cmdMoteur -> verifMoteur -> waitAlims -> syncMesure1/2 -> actEmit`.

Additional detection branches include `initDetectUp`, `verifMoteurUp`,
`verifAlimsUp`, `scanDetectUp`, corresponding lower-scan states,
and `pause4`. The true transition graph, timeouts, ROI optimization and
motor limits have been reconstructed from `emitMotor.db` (DLLM=-3 mm, DHLM=182 mm). The executable `EmuScanSequencer` now applies these limits and bounded timeouts; see [EMU reconstruction](emu_reconstruction.md).

`emitSnlMotor.st` coordinates MaxV and servo with an external security PV.
`emitSnlAlims.st` changes a `Calcdly.ODLY` delay between 0 and 30 s
depending on power-supply on/off state.

## Inputs required for physical calibration

The source IOC code provides setpoint ranges and scaling, not validated plant dynamics.
For realistic model behaviour we still require:

- Per-device ramp/settling times, repeatability, limits and fault recovery.
- Pressure-volume-conductance/pump-speed curves for VAC01/VAC02.
- RF reflected/forward power versus stub position, gas pressure and species.
- Coil field maps `B(z,r;I1,I2)` and solenoid/steerer optics calibration.
- Siemens PLC revision currently deployed in 2026 and its safety test results.
- CIM interlock thresholds, timing window, state resets and current firmware.
- Time-series traces of start-up, CW operation, sparks and fault scenarios.
- EMU calibration, motor movement times and scanner trajectories.

The simulator runs on an **isolated VM using unchanged source PV names**. No `OTP:` prefix is applied in the runtime or planned IOC. The VM must not have network reachability to the production LIPAc system; confirm routing, CA/PVA discovery and interface binding before enabling any IOC listener. See [EPICS architecture](epics_architecture.md) and [readback traceability](pv_readback_traceability.md).
