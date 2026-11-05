# catalog.py | Inventario y contrato de las PV

**Categoría:** interfaz. **Fidelidad:** metadatos de registros reconstruidos, no dinámica.
**Código:** [catalog.py](../../src/injector_otp/models/catalog.py).

## Para entenderlo

El catálogo permite saber qué PV existen y qué dice el registro V2.0 sobre ellas. El hecho de encontrar una PV **no demuestra** que exista una señal operativa o un equipo conectado. El catálogo aporta nombres, campos EPICS, origen y asignación funcional a otros modelos.

## Implementación

**DevicePV** conserva name, record_type, fields, subsystem y source. **DeviceCatalog.from_registry** lee [pv_registry_v2_0.json](../../config/pv_registry_v2_0.json); entre varias definiciones DB prefiere una que no sea solo inferida de OPI. Si no hay registro DB, clasifica el origen como opi o snapshot.

Las funciones has, get, pv(prefix, suffixes), names y subsystems permiten descubrir PV y agruparlas. **clamp(name, value)** limita únicamente cuando los campos DRVL y DRVH existen, son numéricos y forman un intervalo coherente. No usa HOPR/LOPR como límites de orden.

## Pseudocódigo

    abrir registro JSON
    para cada entrada PV:
        elegir definición DB no inferida, si existe
        guardar nombre, tipo, campos, subsistema y procedencia
    consultar(prefix, candidatos):
        devolver primera PV exacta presente
    limitar(name, valor):
        límites = campos DRVL, DRVH
        si ambos válidos: devolver max(DRVL, min(DRVH, valor))
        si no: devolver valor sin cambiar

## Limitaciones y riesgos

- El catálogo combina hallazgos históricos; puede contener definiciones redundantes, ambiguas o sin productor.
- Una PV read/write de EPICS no equivale automáticamente a un comando autorizado del OTP.
- Si faltan límites DRVL/DRVH, clamp no protege frente a órdenes fuera de rango.
- La autorización efectiva de escritura se administra fuera del catálogo, en [pv_runtime_overrides.yaml](../../config/pv_runtime_overrides.yaml) y SimulationPVState.

## Siguientes mejoras

1. **P1:** auditar todas las PV modeladas con relación comando → readback, tipo, EGU, límites y origen concreto de DB/OPI.
2. **P1:** añadir comprobador de conflictos entre productores y entre límites de varias fuentes.
3. **P2:** generar fichas automáticas de PV y cobertura por subsistema.
4. **P2:** validación de schema JSON y comprobación de tipos y unidades en tiempo de ejecución.

**Pruebas:** [test_pv_registry.py](../../tests/test_pv_registry.py), [test_pv_registry_v1_2.py](../../tests/test_pv_registry_v1_2.py) y [test_architecture.py](../../tests/test_architecture.py).
