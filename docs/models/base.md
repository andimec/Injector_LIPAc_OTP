# base.py | Contrato común de los modelos

**Categoría:** infraestructura. **Fidelidad:** contrato de software, sin física.
**Código:** [base.py](../../src/injector_otp/models/base.py).

## Para entenderlo

Todos los componentes necesitan una forma común de expresar estado y de comprobar que el paso temporal es válido. Este archivo define **ModelState** (enabled, fault) y **SubsystemModel**. No representa ningún componente material del inyector. Los modelos heredan de él para disponer de una interfaz mínima.

## Qué implementa realmente

- **ModelState:** dos indicadores internos, activado y fallo.
- **update(dt):** comprueba que dt no sea negativo. No cambia variables físicas.
- **interlock_ok(context, name, default):** lee una autorización ya calculada por otra capa.
- **in_fault(context, device):** consulta fallos inyectados por el escenario.

**Decisión de diseño:** una clase de equipo no debe inventar el funcionamiento del PPS/MPS. Las protecciones están separadas del comportamiento físico y se observan a través de SimulationContext.

## Pseudocódigo

    crear Modelo:
        state = {enabled: True, fault: False}
    en cada actualización(dt, context):
        si dt < 0: rechazar valor
        el modelo hijo evalúa sus propias ecuaciones
    para consultar autorización:
        devolver context.interlocks[nombre] si existe; en otro caso usar default
    para consultar fallo:
        devolver context.device_faults[equipo] o False

## Límites actuales

No existe comprobación global de unidades, un ciclo de vida formal (initialize, reset, shutdown) ni contrato tipado único para todas las salidas. Los modelos hijos pueden exponer diferentes firmas de actualización, aunque los modelos instanciados por InjectorModel aceptan contexto.

## Próximos pasos

1. **Software, P1:** unificar firma de update, reset y snapshot con Protocol y pruebas de conformidad.
2. **Software, P1:** eliminar permisos por defecto permisivos en los puntos críticos. La capa que calcula interlocks debe definir explícitamente cada autorización.
3. **Software, P2:** incorporar metadatos de fidelidad, procedencia, unidades y versión de cada estado.
4. **Validación:** probar dt negativo, fallos externos, ausencia de autorizaciones y compatibilidad con [core/engine.py](../../src/injector_otp/core/engine.py).

**Criterio de aceptación:** un nuevo modelo se puede registrar sin añadir acceso EPICS y sin redefinir la política de seguridad.

## Contrato de fallos por equipo en VAC01/VAC02

`SimulationControlPlane.set_device_fault(device_id, True)` permite
afectar dispositivos individuales de la red de vacío:
`LEBT:VAC01:PP`, `LEBT:VAC01:TP`, `LEBT:VAC01:SV`,
`LEBT:GV`, `LEBT:VAC01:SGVC`, `SRC:MFCD`, etc.
`ValveDevice` y `GasFlowController` mantienen `state.fault`,
mientras que `VacuumPump` y `VacuumGauge` exponen `fault`.
Los identificadores no son nuevas PV de producción ni
protecciones de Siemens. Véase [red de vacío](vacuum_network.md).
