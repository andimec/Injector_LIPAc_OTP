# Guía de modelos del Injector LIPAc OTP

**Alcance:** los 20 módulos con código Python bajo [src/injector_otp/models](../../src/injector_otp/models/), excluyendo __init__.py, que es solo el inicializador del paquete. **Fecha de revisión:** 06-11-2026, propuesta de red de vacío V1.4.

Esta documentación está orientada a lectores que conocen el inyector, pero no necesariamente el código. Cada página contesta: **qué problema representa, de dónde procede la lógica, cómo se ejecuta, qué NO reproduce y qué se debe mejorar a continuación**. El README de [modelos de origen](../../src/injector_otp/models/README.md) y la [arquitectura](../architecture.md) explican el marco global.

## Cómo interpretar la madurez

- **Lógica heredada:** ecuación/codificación reproducida desde DB, SNL u OPI. No equivale a calibración de un proceso real.
- **Procedimiento reconstruido:** secuencia de comandos/estados inspirada en procedimiento validado documentalmente; no controla equipos reales.
- **Modelo reducido:** respuesta matemática pensada para ejercitar OPIs, aún sin ajuste experimental.
- **Fixture sintético:** señal de prueba fabricada explícitamente para demostrar software.
- **Adaptador de archivo:** procesa registros existentes sin simular un equipo.

## Índice: cada modelo con su función y mejora clave

| Módulo | Tipo / lógica principal | Principal mejora pendiente |
|---|---|---|
| [base.py](base.md) | Contrato base, fallos y autorizaciones externas | API de ciclo de vida, typing y test de conformidad |
| [catalog.py](catalog.md) | Inventario y campos de PV DB/OPI | Límites, procedencia y conflictos entre productores |
| [injector.py](injector.md) | Composición causal y mapa de madurez | Grafo de dependencias, propiedad de PV, multirrate |
| [original_lcs_logic.py](original_lcs_logic.md) | Conversiones, máscaras RF, fórmulas de OPI/timing | Verificación de escalas y tablas de verdad |
| [subsystems.py](subsystems.md) | Clases heredadas sin comportamiento | Retirar/aislar stubs para evitar falsa cobertura |
| [plant.py](plant.md) | Válvulas, MFC y refrigeración; `VacuumRegionModel` antiguo solo para pruebas | Carrera de válvulas, calibrar respuesta y fallos |
| [vacuum_network.py](vacuum_network.md) | Seis nodos de presión VAC01/VAC02, PP/TP, GV, gases y fallos | Conductancias, velocidad S(P,gas), calibración y SV real |
| [vacuum_calibration.py](vacuum_calibration.md) | Perfiles de bombeo y curvas CSV presión/caudal, conversión SCCM | Validar ajuste con transitorios medidos |
| [vacuum_opi.py](vacuum_opi.md) | Precondiciones de pantalla de vacío | PLC fuente y calidad del dato, sin autorización activa |
| [power_supplies.py](power_supplies.md) | Rampas y readbacks de magnetos/HV/IE/R/RC | Caracterización dinámica y escalas por equipo |
| [hv_auto_ramp.py](hv_auto_ramp.md) | Máquina de estados de arranque HV/IE/R | Política de aborto/retorno seguro y verificación real |
| [control_devices.py](control_devices.md) | RF, ATU, timing, posicionadores y haz cualitativo | Identificación RF y transporte/óptica del haz |
| [chopper_cim.py](chopper_cim.md) | PRE-ARM/ARMED, umbrales, snapshot FBI simulado | Validación de lógica cRIO/FPGA y ventanas |
| [calorimetry.py](calorimetry.md) | Fórmulas heredadas FC/BS/IC | Balance físico térmico, calibración y duty real |
| [emu_geometry.py](emu_geometry.md) | Allison, conversión ángulo-VHT y malla ROI | Geometría real, fringing y aceptación de rendijas |
| [emu_hardware.py](emu_hardware.md) | Motor/servo, placas y evento FACQ sintético | Tiempos de equipo y adquisición con waveforms |
| [emu_sequencer.py](emu_sequencer.md) | Barridos EMITTANCE/WIDE/UPPER/LOWER | Presets Fast/Full y validación de abortos |
| [emu_beam.py](emu_beam.md) | Distribución gaussiana Twiss de laboratorio | Halos, especies y función de respuesta del scanner |
| [emu_analysis.py](emu_analysis.md) | Momentos RMS y parámetros Twiss sin corrección | Pesos de malla, baseline y comparación con ROOT |
| [emu_replay.py](emu_replay.md) | Replay offline de archivos EMU de cinco columnas | Puente Phoebus local, timestamps y waveforms reales |

## Flujo de ejecución del OTP

    Scenario/Config + registro PV V2.0
                   |
              SimulationEngine
                   |
          Autorizaciones y fallos externos
                   |
              InjectorModel
                   |
    +--------------+-------------------+
    |              |                   |
    MFC + red     PS/HV/RF/haz       EMU hardware
    |              |                   |
    monitores     readbacks         EMU sequencer
    +--------------+-------------------+
                   |
      context.emit / request_command
                   |
        SimulationPVState (ACL)
                   |
         futuro puente EPICS aislado

**emu_replay.py es una vía aparte.** Lee registros experimentales de archivo y no recibe muestras del EmuAcquisitionModel ni de la red CA/PVA.

## Hoja de ruta transversal

| Prioridad | Trabajo concreto | Evidencia mínima de aceptación |
|---|---|---|
| **P1. Contrato y seguridad del OTP** | Un propietario por salida PV, lista de comandos permitidos, red aislada, fallos y abortos reproducibles | Tests sin producción, fallo por comando no permitido, registros de eventos y tests de abortos |
| **P1. Datos de calibración** | Medir transitorios y factores de escala de PS, MFC, vacío, RF y EMU | Curvas de entrada/salida con incertidumbre, fecha, configuración y trazabilidad |
| **P1. EMU operativo** | Presets Fast/Full y conexión de botones Phoebus a Python mediante Soft IOC aislado | Secuencias equivalentes, Save OFF sin archivos y readbacks observables |
| **P2. Modelado físico** | Calibración de la red de conductancias ya implementada, S(P,gas), RL de bobinas, RF/impedancia y óptica LEBT | Ecuaciones verificables, parámetros medidos, comparación independiente con datos |
| **P2. Diagnósticos** | Calorimetría física, scanner Allison y cálculo RMS con pesos/correcciones | Comparación con señales/calorimetría y herramientas de análisis existentes |
| **P3. Física cinética avanzada** | ECR, menisco de extracción y especies, cuando la plataforma tenga datos adecuados | Validación separada y documentación de rango de aplicabilidad |

## Reglas para mejorar un modelo

1. **Primero una evidencia:** archivo DB/SNL/OPI, procedimiento, prueba de banco o serie temporal. Registrar versión y el dato que justifica cada ecuación.
2. **Separar entradas de salidas:** comandos y setpoints son *operator-owned*, readbacks y cálculos son *model-owned*. Los modelos nunca deben publicar directamente una orden EPICS de producción.
3. **Anotar unidades:** no equiparar cuentas analógicas, voltios, kV, mA, sccm o magnitudes derivadas.
4. **Definir comportamiento anómalo:** pérdida de permisos, fallos, saturación, stale data, pausa y timeout.
5. **Demostrar validación:** pruebas unitarias, pruebas de integración, escenario nominal y escenario de fallo; distinguir lo simulado de lo experimental.
6. **Actualizar la ficha:** ecuaciones, pseudocódigo, parámetros, limitaciones, clase de fidelidad y tareas siguientes.

## Comprobaciones locales

    python3 -m pip install -e ".[dev]"
    pytest -q
    pytest tests/test_emu_geometry.py tests/test_emu_sequences.py tests/test_emu_replay.py
    pytest tests/test_hv_auto_ramp.py tests/test_gas_vacuum_topology.py tests/test_vacuum_network.py

Las pruebas de Python no prueban fidelidad del haz, funcionamiento del PLC/cRIO ni comunicación Phoebus ↔ EPICS. Para ello hacen falta ensayos independientes y una VM **sin ruta a la red de control de LIPAc**.

## Fuentes y documentos de apoyo

- [README general](../../README.md), [arquitectura EPICS](../epics_architecture.md), [contrato de PV](../pv_runtime_contract.md), [lógica original](../original_lcs_model_logic.md).
- [Modelo de vacío V1.4](../vacuum_model.md), [red de seis volúmenes](vacuum_network.md) y [calibración](vacuum_calibration.md).
- [EMU reconstrucción SNL](../emu_reconstruction.md) y [replay experimental](../emu_fast_scan_replay.md).
- Documentación operativa base citada por el proyecto: Injector LCS User Manual v4.0 (01-10-2026); BA_D_2E9QH7 v2.0 (09-07-2026); BA_D_2E2GU7 v1.0; BA_D_2E98YT v1.0; BA_D_22BCRE v2.1; y manual EMU BA_D_2EAHXV v1.0. El código fuente y los datos se deben usar como evidencia de implementación concreta, no las guías como validación experimental.

> **Regla fundamental:** reproducir una interfaz y generar una señal plausible no es lo mismo que haber validado un gemelo físico del acelerador.
