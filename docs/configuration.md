# Configuration of the Injector LIPAc offline simulator

> **Baseline:** 6 November 2026, PR #11 feature branch, after PV registry V2.0, EMU and vacuum-network V1.4 integration. File paths are relative to the repository root unless otherwise specified.

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

- `config/model_parameters.yaml`: training numerical parameters, including `vacuum.stations.VAC01` / `VAC02`, time-to-target, ultimate pressure, six node volumes, conductances, pump ramp times, gas loads/velocities, MFC response, RF, HV and EMU. Most physical vacuum constants remain uncalibrated.
- `config/injector_operating_parameters.yaml`: reference values from operator procedures/manuals, not automatically enforced safety thresholds.
- `docs/original_lcs_model_logic.md`: source-derived calculations and their limitations.

## 4. Modelo de vacío configurable (V1.4)

La red se ejecuta desde `src/injector_otp/models/vacuum_network.py`, que
reemplaza las instancias aisladas de `VacuumRegionModel` en el motor
general. A diferencia del modelo histórico, VAC01/VAC02 están acopladas
por GV, y cada estación dispone de cámara (C), entrada TP (T) y línea
de respaldo (F). **NIV solamente existe físicamente en VAC01.**

La configuración por defecto **conserva** `initial_pressure_mbar: 1e-6`
en cada estación para el escenario operativo anterior. Para bombear desde
atmósfera, usar una configuración específica de escenario o la demo:

```yaml
vacuum:
  stations:
    VAC01:
      initial_pressure_mbar: 1013.25
      pumpdown:
        pumpdown_time_h: 2.0
        reference_start_pressure_mbar: 1013.25
        roughing_end_pressure_mbar: 0.05
        roughing_floor_mbar: 0.005
        roughing_time_fraction: 0.40
        target_pressure_mbar: 1.0e-6
        ultimate_pressure_mbar: 1.0e-8
```

`pumpdown_time_h` modifica las constantes efectivas del modelo, no
garantiza el instante final si hay flujos, válvulas cerradas o fallos.
`ultimate_pressure_mbar` representa el límite asintótico sin entrada
de gas y es distinto de `target_pressure_mbar`. Los dos perfiles
VAC01/VAC02 pueden configurarse de forma independiente.

La bomba TURBOVAC MAG W 2800 de VAC01 es la referencia editable para
ciertos valores: 28 800 rpm, 2400 L/s N₂ y 2100 L/s H₂ (convencional).
La velocidad para D₂/Kr en el YAML utiliza sustitutos provisionales;
las curvas reales por presión/gas, geometría y valores de VAC02 quedan
pendientes de contrastar. `max_foreline_start_mbar` es una
**guardia sintética de entrenamiento** que no pretende reproducir el PLC.

Las cargas gaseosas configuradas son:

```yaml
vacuum:
  gas_sources:
    SRC:MFCH: {species: H2, station: VAC01, delivery_fraction: 1.0}
    SRC:MFCD: {species: D2, station: VAC01, delivery_fraction: 1.0}
    LEBT:MFC: {species: Kr, station: VAC02, delivery_fraction: 1.0}
gas:
  reference_pressure_mbar: 1013.25
  reference_temperature_K: 273.15
```

La fracción de llegada a cámara y las condiciones de referencia SCCM
deben verificarse antes de usar medidas reales.

### Cargar datos medidos de presión frente a caudal

Formato CSV (`delta_pressure_mbar` representa el **incremento**
respecto a flujo cero, no presión total):

```csv
flow_sccm,delta_pressure_mbar
0,0
1,0.000001
2,0.000003
```

Ejemplo sintético. En `model_parameters.yaml`:

```yaml
vacuum:
  flow_pressure_csv:
    SRC:MFCD: "data/vacuum/d2_delta.csv"
```

La tabla solo se emplea con TP nominal, PP ON, PV/SV abiertas y se
convierte en carga gaseosa equivalente. Fuera de esa condición, el
balance utiliza SCCM convertido a throughput ideal. Una ruta relativa
al archivo se interpreta respecto del directorio de trabajo del proceso.

### Fallos externos individualizados

Los identificadores son **nombres internos de dispositivo**,
no nuevos registros EPICS. Por ejemplo:

```python
engine.control_plane.set_device_fault("LEBT:VAC01:TP", True)
engine.step()
engine.control_plane.clear_device_fault("LEBT:VAC01:TP")
```

Otros: `LEBT:VAC01:PP`, `LEBT:VAC01:SV`,
`LEBT:VAC01:PV`, `LEBT:VAC01:AIV`,
`LEBT:VAC01:NIV`, `LEBT:GV`,
`LEBT:VAC01:SGVC`, `SRC:MFCD`,
`SRC:MFCH`, `LEBT:MFC`,
`LEBT:VAC01:CHAMBER_LEAK`. Para VAC02 sustituir el prefijo,
salvo NIV que no existe. Se inyectan mediante `SimulationControlPlane`
en escenarios de entrenamiento, sin enviar comandos a un PLC real.
Al actualizar YAML se requiere **reiniciar** el proceso.

Consulta [perfil/calibración](models/vacuum_calibration.md),
[red física](models/vacuum_network.md) y
[modelo completo](vacuum_model.md).

## 5. Initial conditions

`config/simulation/default.yaml` specifies:

- `simulation.initial_state` and `simulation.timestep_s` (default 0.1 s);
- `external_conditions` for scenario setup;
- `initial_pvs` for startup values and EMU input defaults;
- `device_faults` for scenario fault flags.

Startup values are **not** proof that the real machine is ready. Configuration cannot replace dynamic model-owned readbacks or PPS logic; internally generated model outputs take precedence once the engine advances.

## 6. Native PV names and VM network configuration

Source names are unchanged: `SRC:COIL01_PS:ISet` is also the simulated IOC/Phoebus name. There is **no `OTP:` prefix or mapping**.

The intended deployment is a VM disconnected from the real LIPAc control network. Do not configure a production IOC host, CA address list, PVA beacon destination, bridged interface or VPN into LIPAc. Restrict future CA/PVA access to the loopback or dedicated offline training network. Network isolation is a necessary **deployment check**, not a feature proven by the current Python tests.

Internal runtime-only indicators: `SIM:STATE`, `SIM:TIME`. They are not source LIPAc equipment PVs.

## 7. Practical local check

```bash
python -m pip install -e ".[dev]"
pytest
python scripts/demo_vacuum_pumpdown.py --hours 2 --csv /tmp/vacuum_2h.csv
python scripts/demo_emu.py --mode emittance --synthetic-signal --out /tmp/emu_training.csv
```

This exercises **Python-only behavior**; it does not start the EPICS Soft IOC or prove Phoebus connectivity. See [architecture](architecture.md), [readback traceability](pv_readback_traceability.md) and [IOC contract](simulation_ioc_contract.md).

## 8. EMU archived-data playback

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
