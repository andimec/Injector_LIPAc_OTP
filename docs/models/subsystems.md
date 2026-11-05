# subsystems.py | Estructura heredada sin dinámica

**Categoría:** andamiaje antiguo. **Estado:** placeholders sin modelo físico activo.
**Código:** [subsystems.py](../../src/injector_otp/models/subsystems.py).

## Qué hay en este archivo

Contiene las clases SourceModel, VacuumModel, MagnetModel, HVModel, RFModel, ChopperModel, DiagnosticsModel, CoolingModel, MPSModel y PPSModel. Cada una define un nombre y una actualización que únicamente llama a la validación del paso temporal de SubsystemModel.

No se deben confundir con los equipos operativos compuestos en [injector.py](injector.md). Por ejemplo, el vacío con presión y bombeo simplificados está en [plant.py](plant.md), y los magnetos en [power_supplies.py](power_supplies.md). La presencia de una clase MPSModel/PPSModel **no implica simulación del sistema real de protección**.

## Pseudocódigo actual

    clase VacuumModel hereda SubsystemModel
        name = "vacuum"
        update(dt, context):
            comprobar dt >= 0
            no modificar presión, comandos ni PV

    idem para Source, Magnet, HV, RF, Chopper,
    Diagnostics, Cooling, MPS y PPS

## Motivo de conservarlo

Puede resultar útil como inventario histórico para aplicaciones antiguas, pero genera riesgo de confundir cobertura nominal con implementación real. El sistema actual utiliza componentes de mayor detalle y, donde no hay ley comprobada, InterfaceOnlyModel.

## Próximos pasos

1. **P1:** identificar cualquier importación activa y crear una prueba de que estas clases no publican telemetría.
2. **P1:** señalizar explícitamente deprecated o retirar las clases cuando se confirme que no existen consumidores.
3. **P2:** sustituir la taxonomía duplicada por un registro de capacidades y madurez por subsistema.
4. **Condición previa a añadir física:** definir fuentes, estados observables, ecuaciones, parámetros, casos de prueba y un responsable de salida PV.

**Criterio de aceptación:** ninguna pantalla ni reporte tratará estos placeholders como un modelo validado.
