# Injector_LIPAc_OTP

LIPAc Injector Operator Training Platform (OTP) and Digital Twin.

## Purpose

This repository provides an offline, non-invasive Digital Twin of the LIPAc
Injector for operator training, procedure validation, fault injection,
logging/replay, and Phoebus/EPICS integration without commanding the real
machine.

## Core architectural principle

**Python owns the Injector behaviour. EPICS exposes the behaviour.**

The Soft IOC is deliberately a thin interface layer. It owns the EPICS
representation of PVs, transport, access and monitoring, but it does not own
Injector physics, equipment dynamics, interlocks, MPS/PPS causal logic, fault
propagation, ramp algorithms, or the Injector state machine.

    PHOEBUS
       |
     CA/PVA
       |
    SOFT IOC
       |
    EPICS bridge
       |
    PYTHON ENGINE
       |
       +-- PV State
       +-- Models
       +-- Interlocks
       +-- Faults
       +-- State machine

The Python runtime can run without EPICS or Phoebus. The EPICS implementation
is an adapter around the simulation-owned PV state.

## Modelo de vacío configurable VAC01/VAC02 (implementación V1.4)

Esta rama incorpora un **modelo Python de red de vacío** en
[`src/injector_otp/models/vacuum_network.py`](src/injector_otp/models/vacuum_network.py)
con seis nodos físicos aproximados (`C`: cámara, `T`: entrada de TP,
`F`: línea de respaldo, para **VAC01** y **VAC02**) acoplados por
`LEBT:GV`. El cálculo sustituye a los dos `VacuumRegionModel`
independientes en `InjectorModel`. El módulo histórico sigue en `plant.py`
solo para compatibilidad con pruebas.

- **VAC01:** bombas primaria PP y turbomolecular TP, válvulas PV/SV/AIV/NIV,
  estado de LTV y sensores PGVC/SGVC/PGTP/SGTP.
- **VAC02:** estación simplificada con PP, TP, PV/SV/AIV/LTV y cuatro
  sensores. **No existe NIV02 física**, aunque el archivo DB original
  contenga comandos `LEBT:VAC02:NIV*`; no se modela, no recibe comandos
  del runtime ni se simula su venteo. La cámara RF queda fuera del alcance.
- **GV:** permite intercambio de gas entre cámaras si está abierta;
  `PPS:GV:OpenPermStat` sigue siendo una autorización externa.
- **Gas:** H₂ (`SRC:MFCH`) y D₂ (`SRC:MFCD`) a VAC01; Kr
  (`LEBT:MFC`) a VAC02. Caudal SCCM → throughput de gas;
  se mantienen presiones parciales idealizadas de residual/H₂/D₂/Kr/N₂.
- **Fallos específicos:** PP, TP, válvulas, sensores, MFC y fugas,
  inyectables a través de `SimulationControlPlane.set_device_fault()`.

### Ajustar el tiempo y la presión del bombeo

Editar [`config/model_parameters.yaml`](config/model_parameters.yaml)
y reiniciar el motor para aplicar cambios:

```yaml
vacuum:
  stations:
    VAC01:
      initial_pressure_mbar: 1013.25  # escenario desde atmósfera
      pumpdown:
        pumpdown_time_h: 2.0          # valor de referencia: 1, 2 o 3 h
        target_pressure_mbar: 1.0e-6  # presión objetivo
        ultimate_pressure_mbar: 1.0e-8 # límite asintótico, sin entrada de gas
```

`pumpdown_time_h` calibra **constantes efectivas de bombeo**, no un
temporizador que garantice alcanzar la presión indicada. El tiempo
efectivo cambia con los estados de PP/TP, SV/PV, rampas, fugas y caudales.
La configuración distribuida comienza a `1e-6` mbar para no modificar
el escenario por defecto del motor; el ejemplo de arriba inicia un
**ensayo independiente** desde atmósfera.

Prueba sin EPICS y exporta trazas en CSV:

```bash
python scripts/demo_vacuum_pumpdown.py --hours 1 --csv /tmp/vacuum_1h.csv
python scripts/demo_vacuum_pumpdown.py --hours 2 --csv /tmp/vacuum_2h.csv
python scripts/demo_vacuum_pumpdown.py --hours 3 --csv /tmp/vacuum_3h.csv
pytest -q tests/test_vacuum_network.py tests/test_gas_vacuum_topology.py
```

Se pueden aportar **curvas reales** de incremento de presión frente a
caudal en CSV (`flow_sccm,delta_pressure_mbar`) mediante la clave
`vacuum.flow_pressure_csv` por MFC. Estas curvas solo se aplican en
la condición de TP nominal y con bombeo habilitado, como carga gaseosa
equivalente; no son lecturas medidas generadas por el simulador.

**Limitaciones:** los volúmenes, conductancias, fracciones de llegada del
gas a las cámaras, curvas de TP y calibraciones de vacuómetros aún
requieren datos de LIPAc. Los parámetros de la TURBOVAC MAG W 2800 son
una referencia editable; las cifras sustitutivas de D₂/Kr no están
validadas. `SVForcing` sigue siendo una fórmula de **visualización**
de la OPI, no un bypass de la lógica de seguridad ni una orden
automática de apertura. El 70 % de velocidad durante la parada de VAC01
es una **métrica**, no un cierre automático de PV.

Documentación: [modelo de vacío y límites](docs/vacuum_model.md),
[calibración y datos medidos](docs/models/vacuum_calibration.md),
[red física y fallos](docs/models/vacuum_network.md) y
[configuración detallada](docs/configuration.md).

## Iniciar el motor Python en la máquina virtual (Debian)

**El motor y el IOC son procesos diferentes.** `src/injector_otp/app.py` contiene la función `build_application()`, pero `python3 -m injector_otp.app` ejecuta **solo un paso** y termina. El iniciador del motor continuo es ahora [`scripts/start_injector_engine.sh`](scripts/start_injector_engine.sh). El proceso sigue siendo **exclusivamente local y en memoria**, sin conexión CA/PVA a Phoebus ni al Soft IOC.

### Directorios de la VM

Las rutas proporcionadas para la instalación son:

| Componente | Ubicación |
|---|---|
| Raíz de proyectos | `/home/ifmif/Documents/` |
| Repositorio del motor | `/home/ifmif/Documents/Injector_LIPAc_OTP/` **si está clonado ahí** |
| Archivos `*.db` del Soft IOC | `/home/ifmif/Documents/IOCs/example_ioc_mounts/db/` |
| Phoebus v5.0 | `/home/ifmif/Documents/lipac-phoebus/bin/lipac-phoebus.exe` |
| OPIs del inyector | `/home/ifmif/Documents/lipac-integrated-opi-injector-phoebus5/LIPAc/L1-SystemExpert/Injector/` |
| Scripts de la OPI | `/home/ifmif/Documents/lipac-integrated-opi-injector-phoebus5/LIPAc/L1-SystemExpert/Injector/Scripts/` |
| Script EMU usado en la VM | `/home/ifmif/Documents/lipac-integrated-opi-injector-phoebus5/LIPAc/L1-SystemExpert/Injector/Scripts/emitShell_V2.sh` |

La ruta del repositorio es una **ubicación de instalación propuesta**, no una carpeta que se haya verificado en la VM. Si lo has clonado en otro directorio, utiliza esa carpeta como raíz del proyecto. El script lanzador detecta la raíz de su propia copia y puede invocarse desde cualquier directorio.

### 1. Preparar la instalación una sola vez

En la terminal de la VM, si **todavía no existe** la copia del repositorio en la ubicación propuesta:

```bash
cd /home/ifmif/Documents
git clone https://github.com/andimec/Injector_LIPAc_OTP.git
```

Después, entrando en el repositorio ya existente o recién clonado:

```bash
cd /home/ifmif/Documents/Injector_LIPAc_OTP
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

Se requiere Python 3.10 o posterior y el módulo `venv` (en Debian, normalmente `python3-venv`). Si ya tienes una copia, **no la clones otra vez**; actualiza la rama correspondiente cuando proceda. El lanzador usa `.venv/bin/python` si existe; también permite seleccionar otro intérprete con la variable `PYTHON`.

### 2. Arranque continuo del motor

```bash
cd /home/ifmif/Documents/Injector_LIPAc_OTP
./scripts/start_injector_engine.sh
```

También se puede ejecutar con la ruta absoluta desde otra carpeta:

```bash
/home/ifmif/Documents/Injector_LIPAc_OTP/scripts/start_injector_engine.sh
```

El iniciador sitúa el directorio de trabajo en la raíz del repositorio, carga la configuración `config/simulation/default.yaml`, construye `SimulationEngine` + `InjectorModel`, y ejecuta continuamente `engine.step()`. Por defecto el paso es **0.1 s** con espera de reloj real, y se imprime un resumen cada **50 pasos**. Se detiene pulsando **Ctrl+C**.

Alternativamente, desde la raíz del proyecto:

```bash
.venv/bin/python -m injector_otp.runner
```

**Importante:** el estado inicial es `OFF`, conforme al YAML. Que el contador de tiempo avance no implica que se haya encendido el haz ni que se haya comunicado un comando a equipos reales.

### 3. Prueba rápida y diagnóstico

Para simular exactamente **100 pasos** sin esperar en tiempo real, equivalentes a **10 s** de tiempo de simulación con la configuración por defecto:

```bash
cd /home/ifmif/Documents/Injector_LIPAc_OTP
./scripts/start_injector_engine.sh --steps 100 --fast --snapshot /tmp/injector-otp-state.json
```

El archivo JSON opcional contiene el tiempo, estado y valores de las PV **en memoria**. `--fast` se permite solo con `--steps` positivo para evitar un bucle sin límite a máxima velocidad. Otras opciones:

```bash
./scripts/start_injector_engine.sh --help
./scripts/start_injector_engine.sh --steps 200 --report-every 10
```

Sin `--snapshot` no se escribe ningún archivo de estado. Para revisar las pruebas del repositorio:

```bash
.venv/bin/python -m pytest -q
```

### 4. Diferencia entre Python, IOC y Phoebus

```text
Phoebus v5.0: .../lipac-phoebus/bin/lipac-phoebus.exe
   |
   | CA/PVA (todavía NO integrado con el motor Python)
   v
Soft IOC: .../IOCs/example_ioc_mounts/db/*.db
   |
   | puente de entrada/salida EPICS (todavía pendiente)
   v
Python: scripts/start_injector_engine.sh
   |
   +-- SimulationEngine -> InjectorModel
   +-- interlocks, faults y estado de PV en memoria
```

**Arrancar Python no arranca el IOC, no carga los `*.db`, no abre Phoebus y no crea PV consultables mediante `caget`/`pvget`.** `SimulationPVBackend` y `LocalPVBridge` son adaptadores en memoria. El puente CA/PVA, la publicación de readbacks al IOC y la recepción de órdenes de las OPI requieren una implementación posterior.

Los `*.db` deben mantener los nombres originales de PV. Antes de ponerlos en servicio hay que eliminar o desactivar cálculos históricos que compitan con las salidas Python. La máquina de entrenamiento **debe estar aislada de la red EPICS de producción**. Si se utiliza el Soft IOC bajo contenedores, su configuración de servicios en `/etc/containers/systemd/` también es independiente de este lanzador.

### 5. EMU: script de emitancia de la OPI frente al motor global

La instalación Phoebus de la VM utiliza el script indicado `.../Injector/Scripts/emitShell_V2.sh`. **No es el iniciador del motor Python completo.** En este repositorio hay una copia para entrenamiento llamada [`Injector_OPI/Scripts/emitShell_v2.sh`](Injector_OPI/Scripts/emitShell_v2.sh) que invoca [`scripts/launch_emu_snl_replay.sh`](scripts/launch_emu_snl_replay.sh). Este último abre `emu_replay.py` en `xterm`, usando **datos experimentales archivados**, no nuevas adquisiciones ni el reloj global de simulación.

**Atención a Linux y las mayúsculas:** `emitShell_V2.sh` (en la VM) y `emitShell_v2.sh` (en el repositorio) no son el mismo nombre. Tampoco son necesariamente el mismo contenido. Antes de modificar o usar el script externo, examínalo:

```bash
sed -n '1,160p' /home/ifmif/Documents/lipac-integrated-opi-injector-phoebus5/LIPAc/L1-SystemExpert/Injector/Scripts/emitShell_V2.sh
```

Para ejecutar el **replay offline** desde el repositorio:

```bash
cd /home/ifmif/Documents/Injector_LIPAc_OTP
./scripts/launch_emu_snl_replay.sh --duration 180
```

Requiere `xterm` y sesión X11. Sin escritorio gráfico:

```bash
.venv/bin/python -m injector_otp.models.emu_replay --auto --save off
```

El replay todavía **no está conectado** a los botones Validate/ON/Save de Phoebus mediante EPICS. Se debe distinguir entre ejecutar el motor general, ejecutar el replay de EMU y lanzar la OPI. Véase [EMU replay](docs/emu_fast_scan_replay.md).

**Verificación pendiente en la VM:** no hemos comprobado directamente la ubicación real del clone, la ejecutabilidad de `lipac-phoebus.exe`, el contenido de `emitShell_V2.sh`, el estado del contenedor IOC ni el aislamiento de red. Las rutas indicadas proceden de la organización de la VM facilitada para esta guía.

## Package layout

- src/injector_otp/core: simulation clock, state machine and engine.
- src/injector_otp/pv: authoritative simulation PV state and runtime ownership
  contract. This package has no EPICS dependency.
- src/injector_otp/models: subsystem models and composition; `vacuum_network.py` owns the coupled VAC01/VAC02 pressure calculations and `vacuum_calibration.py` holds configurable pumpdown/CSV utilities.
- src/injector_otp/epics: transport contracts and adapters between Python PV
  state and the future simulation Soft IOC.
- src/injector_otp/faults: deterministic fault definitions and injection manager.
- src/injector_otp/interlocks: documented Injector authorization chains and
  complementary legacy PPS/MPS relationships.
- src/injector_otp/app.py: application composition and simulation bootstrap.
- config/pv_registry_v2_0.json: active reconciled registry (1052 PV references,
  including six EMU SNL interfaces), sourced from historic PV snapshot,
  original DB definitions and current OPIs.
- config/pv_registry_v1_2.json: preserved historical September 2026 snapshot
  (891 entries); not used by the default application bootstrap.
- config/pv_runtime_overrides.yaml: explicitly verified runtime ownership
  overrides for the pilot.
- config/model_parameters.yaml: editable vacuum pumpdown targets, final pressure, gas species and training parameters.
- config/simulation/default.yaml: startup conditions only.
- tests/: architecture, registry, state and simulation tests, including `test_vacuum_network.py`.
- docs/: architecture, runtime contract, interlock and configuration design.

## PV registry and runtime ownership

The active V2.0 registry contains 1052 PV references; the historical V1.2
snapshot contains 891 unique entries.

The source EPICS read/write flags do not uniquely determine Digital Twin
semantics. A read/write PV may be writable for implementation reasons while
being a monitor, status or calculated value from the simulation perspective.

Therefore:

1. The V2.0 registry defines the active PV inventory and source metadata.
2. Runtime overrides define only verified pilot inputs.
3. Unresolved PVs remain unresolved until their semantics are documented.
4. SimulationPVState is the source of truth for simulation values.

## Ownership rules

Operator inputs are commands and setpoints.

Simulation outputs are readbacks, equipment status and calculated values.

Configuration provides initial conditions only.

A simulation-owned PV cannot be written by an operator through the Python
runtime.

## Safety boundary

This repository is a training/simulation platform. It must never write to
production LIPAc control PVs.

The isolated virtual machine exposes the **original LIPAc PV names unchanged**.
For example, `LEBT:HV_PS:OnStat` remains `LEBT:HV_PS:OnStat` in
Python, the simulation Soft IOC and Phoebus. No `OTP:` renaming is applied.

**Deployment boundary:** the VM must have no connection or route to the LIPAc
production control network. CA/PVA interfaces must bind only to the isolated
VM or training-only network. Network isolation does not replace the Python
command allowlist, which prevents operator writes to readback and safety
signals. Never attach this unqualified naming scheme to the production LAN.

See [write/readback traceability](docs/pv_readback_traceability.md).

## Interlock logic

The Simulation Engine includes the documented Injector interlock layer through
InjectorInterlockLogic.

The interlock layer is intentionally external to physical subsystem models.
It reads observed PV states and writes normalized authorization signals into
SimulationControlPlane using:

    True  = authorized / allowed
    False = blocked

The implementation integrates the available documentation rather than
classifying one source as valid and another as invalid:

- current Injector LCS User Manual v4.0 supplies current HVPS, IEPS, RF-for-Plasma
  and RF-for-Beam authorization paths;
- PLC maintenance documentation supplies complementary historical Boolean
  relationships;
- V2.0 PV registry supplies reconciled concrete PV names;
- ambiguous protection equations remain open rather than invented.

The LCS manual states that PPS/MPS OPI information is for monitoring and
diagnostic purposes and that actual protection functions are implemented by
hardware protection systems. The OTP therefore models observable
authorization/protection behaviour for training; it is not a replacement for
real PPS/MPS hardware.

Detailed design decisions and source traceability are documented in
docs/interlocks.md and docs/pv_runtime_contract.md.

## EMU: SNL v2 simulation and experimental Fast Scan replay

The EMU provides **two distinct offline workflows**:

- **Python device/state models:** `emu_geometry.py`, `emu_hardware.py`,
  `emu_sequencer.py`, `emu_beam.py`, and `emu_analysis.py` reproduce
  SNL-derived geometry, the motor/plate/FACQ *training* responses, the scan
  sequence, and provisional RMS diagnostics. Acquisition is synthetic by
  default, not a calibrated beam measurement.
- **Recorded-data replay:** `emu_replay.py` reads the 2026 experimental
  five-column `_optm.txt` files, prints the saved samples in `xterm`,
  and generates a compatible `emitYYYYMMDD-HHmm_optm.txt` result with
  an additional `*.replay.json` provenance file **only when
  `LEBT:EMIT:Savemit=ON`**. With Save OFF, the full console replay runs
  without creating any result file. This adapter does not
  publish EPICS PVs, run the physical model or fabricate waveforms.

The archived **Fast Scan** (6 July 2026) has **45 motor positions × 31
voltage points = 1,395 samples**. Its operator parameters are upper 46 mm,
lower -42 mm, step 2 mm, 100 keV (D+), angle peaks -37/+45 mrad, angular
width 20 mrad, and 30 HV intervals. A Full Scan reference uses upper 60 mm,
lower -44 mm, step 2 mm, 0/0 mrad, angular width 100 mrad and 120 HV
intervals. The Python sequencer uses a generic ROI scan; it does not yet
offer named Fast/Full preset selection.

The OTP OPI `Injector_OPI/emitMeasurement_v2.bob` retains its **Start SNL**
action, calling `Injector_OPI/Scripts/emitShell_v2.sh`. That **training
copy** now opens the Python replay in xterm. It initially shows **waiting**,
then accepts `validate` and `on` typed in the terminal. The actual
Phoebus **Validate/ON** controls are not yet connected to this process
through the EPICS bridge. Do not install the OTP script on LIPAc.

```bash
python3 -m pip install -e ".[dev]"
# Synthetic internal model
python scripts/demo_emu.py --mode emittance --synthetic-signal --out /tmp/emu_training.csv
# Recorded Fast Scan with xterm on a local X11 desktop (about 3 minutes).
# Type "save on" to enable file output, then "validate" and "on".
# Without save on, only the console is displayed.
./scripts/launch_emu_snl_replay.sh --duration 180
# Immediate headless reproduction WITH output + provenance
python3 -m injector_otp.models.emu_replay --auto --save on --output-dir output/emu
# Immediate headless reproduction WITHOUT creating files
python3 -m injector_otp.models.emu_replay --auto --save off
# Regression checks
pytest tests/test_emu_replay.py tests/test_emu_sequences.py tests/test_emu_geometry.py
```

Documentation: [Fast Scan experimental replay](docs/emu_fast_scan_replay.md),
[SNL v2 reconstruction](docs/emu_reconstruction.md),
[model inventory](src/injector_otp/models/README.md),
[technical documentation index](docs/README.md).

**Boundary:** Neither path contacts production LIPAc CA/PVA endpoints;
the future Soft IOC must be isolated. CI tests do not validate xterm
rendering, OPI-to-PV connectivity or calibrated machine physics.

The source SNL v2 forces `Savemit` from 0 to 1 when measurement begins.
That legacy behavior is **intentionally not reproduced** in the OTP:
`Savemit=OFF` must mean no output files. The Python sequencer accepts
`Validate=1` as a rising-edge trigger, `Actemit=ON` to start and
`Actemit=OFF` to abort; it latches `Savemit` at scan start, without
writing to disk itself. A local storage/EPICS bridge is still required for
**OPI checkbox -> file creation**; the console's `save on/off` is an
explicit offline stand-in, not an active CA connection.
