# Documentación técnica del gemelo digital del inyector LIPAc

**Estado de referencia:** 5 de noviembre de 2026. Incluye modelos Python de EMU y reproducción offline de los registros experimentales Fast/Full Scan. Los botones Validate/ON por EPICS siguen pendientes. Este índice describe el **estado del código**, no constituye una validación del funcionamiento físico ni del control de seguridad de LIPAc.

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
| [original_lcs_model_logic.md](original_lcs_model_logic.md) | Procedencia de cálculos de DB/SNL/PLC históricos y madurez de modelos |
| [interlocks.md](interlocks.md) | Autorizaciones implementadas, relaciones PLC históricas y límites de PPS/MPS |
| [emu_reconstruction.md](emu_reconstruction.md) | Geometría SNL v2, motor, placas, FACQ sintético, estados y parámetros Fast/Full |
| [emu_fast_scan_replay.md](emu_fast_scan_replay.md) | Datos experimentales archivados, reproducción en xterm, formato SNL y conexión Start SNL |

## Hechos de implementación que gobiernan todo el conjunto

- **PVs:** `config/pv_registry_v2_0.json` es el registro por defecto (1.052 referencias PV/campos). `config/pv_registry_v1_2.json` (891 entradas) es histórico.
- **Nombres:** se preservan nombres originales `SRC:...`, `LEBT:...`, `PPS:...` en Python y en el futuro IOC. No se exige `OTP:`. `SIM:STATE` y `SIM:TIME` son indicadores internos, no PV de equipo.
- **Responsabilidades:** Python genera la dinámica y readbacks; el IOC previsto será una capa de transporte. Los `calc` históricos de `db/` no deben competir con cálculos Python.
- **Aislamiento:** el entorno previsto es una VM sin ninguna conectividad o descubrimiento EPICS hacia LIPAc. Esta condición debe verificarse al desplegarla; las pruebas Python no la demuestran.
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
