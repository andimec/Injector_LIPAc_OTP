# Documentación técnica del gemelo digital del inyector LIPAc

> **Actualización de integración, 10-11-2026:** el IOC y el puente CA de vacío se han ensayado en la VM aislada; los 39 readbacks digitales auditados tienen `UDF=0` y `STAT/SEVR=NO_ALARM`. Permanecen pendientes la validación de los 11 analógicos, la prueba completa de secuencia y la sincronización final de archivos operativos del host con Git. Las secciones anteriores que describen el Soft IOC como «futuro» son antecedentes de diseño, no el estado completo de la VM.

**Documentos prioritarios:** [Runbook de la VM, errores y recuperación](EPICS_VM_RUNBOOK.md) · [Prompt de réplica para otros subsistemas](SUBSYSTEM_REPLICATION_PROMPT.md).


**Estado de referencia:** 6 de noviembre de 2026, rama de desarrollo del modelo configurable de vacío (PR #11), además de EMU y su reproducción offline Fast/Full. Los botones Validate/ON por EPICS siguen pendientes. Esta documentación describe el **código de entrenamiento**, no valida los equipos, los permisos PLC ni el funcionamiento físico de LIPAc.

**Guías explicativas de los 20 módulos Python:** [índice de modelos, lógica, pseudocódigo y próximos pasos](models/README.md).

## Cómo leer la documentación

| Documento | Contenido y alcance |
|---|---|
| [architecture.md](architecture.md) | Arquitectura vigente, módulos Python, estados de implementación y tareas pendientes |
| [configuration.md](configuration.md) | Registro PV activo V2.0, parámetros, propiedad de entradas y condiciones iniciales |
| [opi_pv_coverage.md](opi_pv_coverage.md) | Auditoría automática de OPIs, cobertura del registro V2.0 y productores Python; exporta CSV/JSON |
| [pv_readback_traceability.md](pv_readback_traceability.md) | Mapeo de PV de escritura/readback, responsables Python, conversiones y lagunas identificadas |
| [pv_runtime_contract.md](pv_runtime_contract.md) | Control de propiedad y permisos de PV, secuencia de simulación, límites del runtime |
| [epics_architecture.md](epics_architecture.md) | Diseño Phoebus ↔ Soft IOC ↔ puente ↔ Python. El despliegue real sigue pendiente |
| [simulation_ioc_contract.md](simulation_ioc_contract.md) | Contrato del adaptador local, nombres originales y requisitos de red aislada |
| [modeling_baseline.md](modeling_baseline.md) | Modelo físico reducido, dependencias y parámetros orientativos |
| [vacuum_model.md](vacuum_model.md) | Modelo VAC01/VAC02 V1.4: topología, parámetros de bombeo, MFC, fallos y límites |
| [models/vacuum_network.md](models/vacuum_network.md) | Detalle del balance de presión por seis nodos, bombas, GV, NIV y señales EPICS |
| [models/vacuum_calibration.md](models/vacuum_calibration.md) | Ajuste de 1/2/3 h, presión objetivo/última, conversión SCCM y CSV experimentales |
| [original_lcs_model_logic.md](original_lcs_model_logic.md) | Procedencia de cálculos de DB/SNL/PLC históricos y madurez de modelos |
| [interlocks.md](interlocks.md) | Autorizaciones implementadas, relaciones PLC históricas y límites de PPS/MPS |
| [emu_reconstruction.md](emu_reconstruction.md) | Geometría SNL v2, motor, placas, FACQ sintético, estados y parámetros Fast/Full |
| [emu_fast_scan_replay.md](emu_fast_scan_replay.md) | Datos experimentales archivados, reproducción en xterm, formato SNL y conexión Start SNL |

## Hechos de implementación que gobiernan todo el conjunto

- **PVs:** `config/pv_registry_v2_0.json` es el registro por defecto (1.052 referencias PV/campos). `config/pv_registry_v1_2.json` (891 entradas) es histórico.
- **Nombres:** se preservan nombres originales `SRC:...`, `LEBT:...`, `PPS:...` en Python y en el futuro IOC. No se exige `OTP:`. `SIM:STATE` y `SIM:TIME` son indicadores internos, no PV de equipo.
- **Responsabilidades:** Python genera la dinámica y readbacks; el IOC previsto será una capa de transporte. Los `calc` históricos de `db/` no deben competir con cálculos Python.
- **Aislamiento:** el entorno previsto es una VM sin ninguna conectividad o descubrimiento EPICS hacia LIPAc. Esta condición debe verificarse al desplegarla; las pruebas Python no la demuestran.
- **Red de vacío:** `VacuumNetworkModel` sustituye a los dos `VacuumRegionModel` del `InjectorModel`; seis nodos C/T/F conectados por GV, H₂/D₂/Kr, NIV solo en VAC01 y fallo individual por dispositivo. El modelo antiguo persiste únicamente como clase histórica de compatibilidad.
- **Validación:** las pruebas unitarias verifican implementaciones de Python. Un IOC EPICS 7 con Phoebus, la fidelidad de campos EPICS y los parámetros físicos calibrados aún no se han verificado extremo a extremo.
- **Protecciones:** PPS/MPS reales son externos. Las señales de autorización del simulador sirven para entrenamiento, no para protección de maquinaria real.

## Fuentes y trazabilidad

Las bases de datos copiadas se conservan bajo `db/`. La comparación del registro está en `audit/registry_v2/`, y la recuperación de definiciones originales en `audit/original_lcs/`. Las OPIs relevantes están en `Injector_OPI/`. La documentación operativa externa y los manuales de EMU complementan estas fuentes; no sustituyen una verificación de versiones y ensayos con el sistema real.

## Siguiente criterio de aceptación

Antes de declarar funcional el entorno integrado, comprobar de forma reproducible: aislamiento de red de la VM; generación y carga de registros EPICS con sus campos; correspondencia de PV OPI con el registro V2.0; permisos `put`; respuesta de lectura bajo rampas/fallos; suscripción CA/PVA; y consistencia de los resultados de EMU.

## EMU: estado de implementación

La OPI de entrenamiento `Injector_OPI/emitMeasurement_v2.bob` mantiene el
botón **Start SNL**, que abre la terminal Python mediante
`Injector_OPI/Scripts/emitShell_v2.sh`. El programa espera las órdenes
`validate` y `on` en la terminal; **los botones de Phoebus no están
conectados al reproductor mediante PVs**. La ejecución gráfica en Debian
todavía requiere verificación local.

El archivo Fast Scan de julio de 2026 contiene 1.395 puntos (45 posiciones
por 31 tensiones). Los otros dos conjuntos tienen 4.343 y 6.413 puntos.
La salida es `emitYYYYMMDD-HHmm_optm.txt` junto a una trazabilidad
`*.replay.json`, dentro de `output/emu/`. No representa una adquisición
nueva de haz ni incluye los waveforms originales de FACQ.

Detalles: [reproducción experimental](emu_fast_scan_replay.md) y
[reconstrucción SNL](emu_reconstruction.md).

## EMU: significado de las tres PV de operador

- `LEBT:EMIT:Validate`: botón booleano. El secuenciador detecta el
  flanco de subida, valida la región y devuelve el comando a 0.
- `LEBT:EMIT:Actemit`: selector ON/OFF. ON inicia la medida una vez
  validada; OFF interrumpe una secuencia activa.
- `LEBT:EMIT:Savemit`: checkbox. ON autoriza producir el archivo
  experimental de cinco columnas y el JSON de procedencia. OFF significa
  **solo representación en terminal**, sin archivos nuevos.

El SNL antiguo reactivaba `Savemit` de forma automática; el OTP no lo
hace. El modelo Python lee la selección, pero la reproducción actual es
independiente del IOC: la terminal permite `save on` / `save off`
y el comando headless `--save on|off` (por defecto OFF). Todavía falta
un puente EPICS aislado para que los tres controles de la OPI actúen
directamente sobre esa terminal. Ver
[emu_fast_scan_replay.md](emu_fast_scan_replay.md).

## Ejecución rápida del bombeo (solo Python)

```bash
python scripts/demo_vacuum_pumpdown.py --hours 1 --csv /tmp/vacuum_1h.csv
python scripts/demo_vacuum_pumpdown.py --hours 2 --csv /tmp/vacuum_2h.csv
python scripts/demo_vacuum_pumpdown.py --hours 3 --csv /tmp/vacuum_3h.csv
pytest -q tests/test_vacuum_network.py
```

Los tiempos son **referencias configurables**, no una predicción validada de la
puesta en vacío real. Los CSV generados contienen trazas sintéticas. Para
incorporar mediciones en la simulación véase [calibración](models/vacuum_calibration.md).
