# Injector LIPAc digital twin: EPICS write / readback traceability

**Scope:** Python runtime on `main` (November 2026), PV registry V2.0 (1052 references), and the explicit operator input allowlist in `config/pv_runtime_overrides.yaml`.

**Naming:** The VM is disconnected from LIPAc; Python, Soft IOC and Phoebus must use **unmodified source PV names**. `SIM:STATE` and `SIM:TIME` are the only special runtime indicators, not LIPAc PVs. There is no `OTP:` name translation.

## Reading this matrix

- **MODEL:** Python currently emits the indicated PV with `context.emit(...)` through the simulation engine.
- **DERIVED:** Python computes the monitor from setpoint(s) or other model states, not necessarily an independent sensor.
- **EXTERNAL:** The value comes from the simulated scenario/PPS/PLC environment and is **not** operator writable.
- **GAP:** The pairing has not been validated or the Python model lacks a complete generated readback. Do not invent a new PV to fill the gap.
- A readback is **not** an echo of a setpoint. Dynamics, enabling conditions, faults, limits, and conversion/calibration must be reflected.
- All rows represent model-level implementation/intent, **not** end-to-end Phoebus/Soft-IOC verification. PV presence in the registry does not prove an EPICS record is loadable.

## 1. Power supplies

The following names and generation rules are implemented in `src/injector_otp/models/power_supplies.py`, `PowerSupplyDevice.update()`, except where noted. The `DeviceCatalog.pv()` helper only emits a suffix when the exact PV is present in the V2.0 catalog.

| Writable PV (input) | Readback / monitor | Python owner | Assessment |
|---|---|---|---|
| `SRC:COIL01_PS:ISet` | `SRC:COIL01_PS:IRdbk` | `PowerSupplyDevice` | MODEL, current ramp + optional drift |
| `SRC:COIL02_PS:ISet` | `SRC:COIL02_PS:IRdbk` | same | MODEL |
| `LEBT:SOL01_PS:ISet` | `LEBT:SOL01_PS:IRdbk` | same | MODEL |
| `LEBT:SOL02_PS:ISet` | `LEBT:SOL02_PS:IRdbk` | same | MODEL |
| `LEBT:STH01_PS:ISet` | `LEBT:STH01_PS:IRdbk` | same | MODEL, conditional on registry |
| `LEBT:STH02_PS:ISet` | `LEBT:STH02_PS:IRdbk` | same | MODEL, conditional on registry |
| `LEBT:STV01_PS:ISet` | `LEBT:STV01_PS:IRdbk` | same | MODEL, conditional on registry |
| `LEBT:STV02_PS:ISet` | `LEBT:STV02_PS:IRdbk` | same | MODEL, conditional on registry |
| `SRC:IE_PS:ISet` | `SRC:IE_PS:IRdbk`, `IRdbkcalc`, `ISetRdbk`, `RdbkCalcI` | same | MODEL, raw analog vs engineering units differ |
| `SRC:IE_PS:VSet` | `SRC:IE_PS:VRdbk`, `VRdbkcalc` | same | MODEL, raw vs engineering |
| `LEBT:R_PS:ISet` | `LEBT:R_PS:IRdbk`, `IRdbkcalc` | same | MODEL, raw vs engineering |
| `LEBT:R_PS:VSet` | `LEBT:R_PS:VRdbk`, `VRdbkcalc` | same | MODEL |
| `LEBT:RC_PS:ISet` | `LEBT:RC_PS:IRdbk`, `IRdbkcalc` | same | **GAP:** known legacy scaling discrepancy; validate units |
| `LEBT:RC_PS:VSet` | `LEBT:RC_PS:VRdbk`, `VRdbkcalc` | same | MODEL, validate scaling |
| `LEBT:HV_PS:HTCmd` | `LEBT:HV_PS:LectVht`, `ScaleVHT` | same | MODEL, kV setpoint to V monitor; source `CalcVHT` is setpoint conversion, not readback |
| `LEBT:HV_PS:ICmd` | `LEBT:HV_PS:LectIht` / `ScaleIHT` | same | **GAP:** current limit is not measured load current; no artificial readback is published |
| Power-supply `ON` / `OnCmd` / `HTOnCmd` and `OFF` / `OffCmd` / `HTOffCmd` | same prefix `:OnStat` | same | MODEL, edge-triggered and interlock-dependent |
| `LEBT:HV_PS:AuxOnCmd`, `AuxOffCmd` | `LEBT:HV_PS:AuxStat` | same | MODEL |
| Power-supply `RESET` / `RstCmd` / `Reset` | same prefix `:RdyStat` | same | MODEL, resets simulated fault latch only |
| `LEBT:SOL01_PS:Rampe`, `SOL02_PS:Rampe`; coil `:Rampe` | respective `:IRdbk` rate of change | same | MODEL, manual rate is applied when positive |
| `LEBT:AUTO:UptoHT`, `StopHT` | HV/IE/repeller readbacks above | `models/hv_auto_ramp.py` `HVAutoRampSequencer` | DERIVED supervisory command; no unique readback pair |

**Caution:** never treat a raw `:IRdbk`/ `:VRdbk` Modbus analog value as an engineering-unit display when the model explicitly provides `:IRdbkcalc` / `:VRdbkcalc`. HV `:ICmd` is a current limit, not load-current measurement.

## 2. EMU motor, high-voltage plates and FACQ

| Writable PV | Python-generated counterpart | Python owner | Assessment |
|---|---|---|---|
| `LEBT:EMIT:MOTOR.VAL` | `LEBT:EMIT:MOTOR.RBV`, `.MOVN`, `.DMOV`, `.LVIO`, `.HLS`, `.LLS` | `models/emu_hardware.py:EmuMotorModel.update` | MODEL, position slew + limits |
| `LEBT:EMIT:MOTOR.HOMR` | `LEBT:EMIT:MOTOR.ATHM`, `.RBV` | same | MODEL, homing to zero on rising edge |
| `LEBT:EMIT:MOTOR.CNEN`, `LEBT:EMIT_SERV:EnaDisa` | motor status `.MOVN`, `.DMOV` and internal `emu.motor_ready` metric | `EmuMotorSupervisor`, `EmuMotorModel` | PARTIAL, no independent verified hardware enable feedback |
| `LEBT:EMIT:MOTOR.SPMG` | `.MOVN`, `.DMOV` | `EmuMotorModel` | MODEL; stop/go gate |
| motor position | `LEBT:EMIT:Position` = `-MOTOR.RBV` | `EmuMotorModel` | DERIVED, reversed sign per source DB |
| `LEBT:EMIT_PS1:Softbo` | `LEBT:EMIT_PS1:OnOffCmd`, `OnOffCmd.RVAL` | `EmuPlatePSModel` | MODEL, simulated ON state; record-field compatibility pending |
| `LEBT:EMIT_PS2:Softbo` | `LEBT:EMIT_PS2:OnOffCmd`, `OnOffCmd.RVAL` | same | MODEL |
| `LEBT:EMIT_PS1:VSet` | `LEBT:EMIT_PS1:VRdbk` | same | MODEL, bounded voltage rate |
| `LEBT:EMIT_PS2:VSet` | `LEBT:EMIT_PS2:VRdbk` | same | MODEL |
| PS1 / PS2 `:VSet` | `LEBT:EMIT:Vht` = PS1 VSet - PS2 VSet | same | DERIVED setpoint difference |
| PS1 / PS2 `:VSet` | `LEBT:EMIT:VhtRdbk` = PS1 VRdbk - PS2 VRdbk | same | DERIVED **measured** difference |
| `LEBT:EMIT:Validate` and scan actions `Actemit`, `Actscan`, `Actupper`, `Actlower` | scan progress, `.RBV`, `VhtRdbk`, `LEBT:EMIT_FC:I` | `models/emu_sequencer.py:EmuScanSequencer` | MODEL, no single dedicated homologous readback |
| `LEBT:EMIT:Pausemit` | paused sequencer state | same | **GAP:** not all state is exposed as an OPI-facing status PV |
| FACQ timing/acquisition commands | `LEBT:EMIT_FC:I` | `EmuAcquisitionModel` | PARTIAL, synthetic current; waveform realism unvalidated |

**EPICS detail:** `MOTOR.RBV`, `MOTOR.DMOV` and `OnOffCmd.RVAL` represent *fields of existing records*, not independent records to generate with literal dots in `.db` record names. Verify the Soft IOC record-field implementation and OPI bindings.

## 3. Gas, safety valves, pumping and vacuum

| Writable PV | Monitor | Python owner | Assessment |
|---|---|---|---|
| `SRC:MFCD:Debit` | `SRC:MFCD:Deb1Mes` | `models/plant.py:GasFlowController` | MODEL, first-order response |
| `SRC:MFCH:Debit` | `SRC:MFCH:Deb2Mes` | same | MODEL |
| `LEBT:MFC:Debit` | `LEBT:MFC:Deb1Mes` (if registry contains it) | same | MODEL, conditional |
| `SRC:MFCD:OpenCmd`, `SRC:MFCH:OpenCmd`, `LEBT:MFC:OpenCmd` | corresponding `:StsVanne` | same | MODEL, simulated valve-enable state |
| `SRC:SVL:D2OpenCmd`, `D2CloseCmd` | `SRC:SVL:D2OpenStat`, `D2CloseStat` | `models/plant.py:ValveDevice` | MODEL |
| `SRC:SVL:H2OpenCmd`, `H2CloseCmd` | `SRC:SVL:H2OpenStat`, `H2CloseStat` | same | MODEL |
| `LEBT:GV:OpenCmd`, `CloseCmd` | `LEBT:GV:OpenStat`, `CloseStat` | same | MODEL |
| `LEBT:VAC01:` / `VAC02:` `SV/PV/NIV/AIV` open/close commands | matching `SV/PV/NIV/AIV` `OpenStat`, `CloseStat` | `ValveDevice` | MODEL, registry-dependent concatenation |
| `LEBT:VAC01:PPOnCmd`, `PPOffCmd`; VAC02 analogs | corresponding `:PPOnStat` | `models/plant.py:VacuumRegionModel` | MODEL |
| `LEBT:VAC01:TPOnCmd`, `TPOffCmd`; VAC02 analogs | corresponding `:TPOnStat` | same | MODEL |
| gas flows, pump states, vacuum fault | `LEBT:VAC01:VacSGVC` / `VacPGVC` / `VacSGTP` / `VacPGTP`, VAC02 equivalents | `VacuumRegionModel` | MODEL, **hypothesized** pressure balance |
| vacuum model output | `LEBT:VAC01:SGVCDefStat`, VAC02 equivalent | same | DERIVED threshold indicator, not a physically calibrated gauge |
| `PPS:*:PermStat`, `PPS:BEAM:InhibitStat` | no writable echo | `config/simulation/default.yaml` external conditions | EXTERNAL; do not use OPI writes |

**Limitation:** the VM does not yet reproduce measured vacuum-network conductance, real turbo pump curves or calibrated source/MFC dynamics. Matching PV names does not validate those approximations.

## 4. RF, chopper, timing and diagnostics

| Writable PV | Readback / visible result | Python owner | Assessment |
|---|---|---|---|
| `SRC:RF_GENE:FilOnCmd` | `SRC:RF_GENE:PretRF`, `Mot105` ready bit | `models/control_devices.py:RFSystemModel` | MODEL, artificial warm-up |
| `SRC:RF_GENE:MOCmdOn` | `SRC:RF_GENE:MarcheRF`, `Mot105` ON bit | same | MODEL, interlock- and warm-up-gated |
| `SRC:RF_GENE:RfPwr` | simulated `rf.forward_W` metric; `Mot103`, `PwrRef` are **reflected**-power channels | same | **GAP:** forward power metric has no verified direct source-PV readback mapping |
| `SRC:RF_GENE:RfOffset` | no independently validated RF output PV | same | GAP, offset-gain effect is a hypothesis, default zero |
| `SRC:RF_GENE:Modbus`, `CWmdOn`, `LimitPR`, `PulseOrCW` | `CalcMot02`, `CalcOnOff`, `Mot105` | same | DERIVED control words; not all requested modes have individual status echoes |
| `SRC:RF_GENE:EnvoiRAZ` | `CalcRAZ` | same | DERIVED command encoding, not proof of external reset |
| `SRC:RF_ATU:ModeXY` | `SRC:RF_ATU:CalcModeXY` | same | DERIVED mode encoding |
| `SRC:RF_ATU:WrtX`, `WrtY` | reflected-power metric `rf.reflected_W` | same | GAP, no simulated encoder-position readback |
| `LEBT:CHOP_IM:StmStateSet` | `LEBT:CHOP_IM:StmState` | `models/chopper_cim.py:ChopperCIMModel` | MODEL, training state; not FPGA certification |
| `LEBT:CHOP_IM:VmonThr` | `LEBT:CHOP_IM:VmonThrRdbk` | same | MODEL, threshold echo (not physical transient) |
| `LEBT:CHOP_IM:AcctThr` | `LEBT:CHOP_IM:AcctThrRdbk` | same | MODEL, threshold echo |
| `LEBT:CHOP_IM:VmonOff` | `LEBT:CHOP_IM:VmonOffRdbk` | same | MODEL, but verify operator allowlist before using |
| chopper synthetic fault | `LEBT:CHOP_IM:Fbi` and `Fbi*` event snapshot | same | MODEL, synthetic trigger |
| `LEBT:FC:InCmd`, `OutCmd` | `LEBT:FC:InStat`, `OutStat` | `models/control_devices.py:PositionerModel` | MODEL |
| `LEBT:CHOP:InCmd`, `OutCmd` | `LEBT:CHOP:InStat`, `OutStat` | same | MODEL |
| `SRC:TIM:Trep`, `TPulse` | timing duty-cycle and mode metrics | `models/control_devices.py:TimingModel` | PARTIAL, not a full generator/OPI readback chain |
| Beam enable, RF, gas, HV, FC position | `LEBT:FC:I` | `models/control_devices.py:BeamDiagnosticsModel` | MODEL, qualitative synthetic current |
| calorimetry inputs / temperature readbacks | `:Tincalc`, `:Toutcalc`, `:DeltaT`, power results | `models/calorimetry.py:CalorimetryModel` | DERIVED, real thermal transport not simulated |

## 5. Critical checks to improve OPI realism

1. **Registry coverage:** confirm each row's exact PV names, field types, units, DB metadata and existence in `config/pv_registry_v2_0.json`; groups labeled conditional are not individually certified.
2. **Ownership:** confirm each OPI input is allowlisted and each monitor is simulation-owned, with no readback exposed to `put()`.
3. **Causality:** test `OnCmd -> OnStat` with missing interlocks, faults and reset; test `ISet -> IRdbk` ramp and scaling rather than immediate copying.
4. **Field access:** preserve native `record.FIELD` semantics for motor, servo and high-voltage records.
5. **Missing pairs:** prioritize measured HV load current, RF forward-power PV, RF ATU position, EMU scan state/progress, comprehensive FACQ waveforms and cooling sensor dynamics.
6. **Integration:** verify `Phoebus -> private EPICS IOC -> Python -> monitor` on an isolated VM, separately from Python unit tests.
7. **Network:** verify no route, CA broadcast, multicast/PVA discovery, bridged NIC or VPN path into LIPAc. Native PV names are safe only under that isolation assumption.

## 6. Locations

| Layer | Location |
|---|---|
| Source PV inventory | `config/pv_registry_v2_0.json` |
| Allowed OPI writes and external PVs | `config/pv_runtime_overrides.yaml` |
| Initial scenario values | `config/simulation/default.yaml` |
| PV metadata and limits | `src/injector_otp/models/catalog.py` |
| State and write permissions | `src/injector_otp/pv/state.py` |
| Simulation publishing | `src/injector_otp/core/engine.py` |
| Native-name transport | `src/injector_otp/epics/simulation_backend.py`, `bridge.py` |
| Equipment models | `src/injector_otp/models/` |
| Relevant tests | `tests/test_power_supply_scaling.py`, `test_emu_hardware.py`, `test_gas_vacuum_topology.py`, `test_chopper_cim.py`, `test_simulation_ioc.py` |

**Audit status:** this is a model-source traceability review, not proof of complete coverage of all 1052 registry references, nor a validated OPI/Soft IOC deployment. A future automated registry-to-model coverage report should count unresolved, readback-only and OPI-only references separately.
