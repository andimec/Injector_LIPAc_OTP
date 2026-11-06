# injector.py | Composición del gemelo digital

**Categoría:** orquestación. **Fidelidad:** orden de ejecución y cobertura de modelos.
**Código:** [injector.py](../../src/injector_otp/models/injector.py).

## Qué hace

**InjectorModel** agrupa todos los modelos de equipos en una sola unidad actualizable. Añade componentes según la presencia de PV en DeviceCatalog, conserva un mapa de madurez y publica observables agregados de haz, HV, RF y vacío. No resuelve por sí mismo ecuaciones del plasma.

La secuencia de registro sigue dependencias causales y no períodos SCAN de EPICS:

1. Refrigeración → válvulas → MFC → **red de vacío única VAC01/VAC02** → fórmulas de precondición OPI.
2. Secuenciador de HV → fuentes de alimentación → timing → posicionadores → CIM → RF.
3. Haz cualitativo → calorimetría → motor, placas, adquisición y secuenciador EMU.
4. Resto de familias → InterfaceOnlyModel, que no fabrica readbacks.

## Pseudocódigo

    iniciar InjectorModel(catalog, parameters):
        para cada grupo que tenga PV:
            añadir modelo concreto y etiqueta de madurez
        añadir placeholders para familias restantes
    update(dt, context):
        verificar dt >= 0 y estado del agregado
        si agregado deshabilitado o en fallo: no avanzar
        para modelo en orden de dependencias:
            modelo.update(dt, context)
        leer métricas calculadas y exponer resumen del inyector

## Decisiones importantes

El propio InjectorModel no llama a caput/caget. Las PV de salida se registran con context.emit; las solicitudes de cambios de comandos con context.request_command. Es el [motor](../../src/injector_otp/core/engine.py) el que comprueba permisos antes de publicar.

**Punto de atención:** el orden de familias es fijo. La red de vacío incluye integración acoplada de C/T y GV en su propia clase; los acoplamientos RF/plasma con otras familias no se resuelven iterativamente. Además, no todas las familias reciben dinámica real: el mapa model_coverage es una declaración de madurez, no un certificado.

## Siguientes pasos

1. **P1:** introducir comprobación automática de escritores únicos por PV y grafo de dependencias.
2. **P1:** registrar inventario de estados y cobertura observada en cada ciclo de simulación.
3. **P2:** separar integradores multirrate para procesos rápidos (RF/EMU) y lentos (vacío/refrigeración).
4. **P2 física:** iteración acoplada RF → plasma → corriente → carga térmica, solo tras incorporar modelos y datos contrastados.
5. **Validación:** casos end-to-end con escenario nominal, fallo de vacío, pérdida de habilitación y secuencias EMU.

**Prueba:** [test_architecture.py](../../tests/test_architecture.py). **Límite:** no ejecutar con red EPICS de producción.

## Integración VAC01/VAC02 V1.4

Se eliminó la doble instancia de `VacuumRegionModel` del motor activo.
`InjectorModel` crea los MFC y actuadores `ValveDevice`, **omite
NIV02** por inexistencia física y agrega una instancia de
`VacuumNetworkModel`. Esta produce las lecturas de presión y estados
de PP/TP de ambas estaciones. Los estados de sensores, bombas y
fallos se gestionan en la red. `VacuumOPIPreconditions` se ejecuta
después y solo publica las fórmulas de visualización originales.
Ni `SVForcing` ni el cruce de 70% de TP son comandos automáticos.

Parámetros: [configuración](../configuration.md),
[red de vacío](vacuum_network.md),
[calibración](vacuum_calibration.md).
Prueba: [test_vacuum_network.py](../../tests/test_vacuum_network.py).
