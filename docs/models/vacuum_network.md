# vacuum_network.py | Red de vacío acoplada VAC01 y VAC02

**Implementación:** [`vacuum_network.py`](../../src/injector_otp/models/vacuum_network.py)  
**Integración:** [`injector.py`](../../src/injector_otp/models/injector.py)  
**Configuración:** [`model_parameters.yaml`](../../config/model_parameters.yaml)  
**Ámbito:** simulación Python aislada; V1.4, 6 de noviembre de 2026.  
**Madurez:** modelo dinámico reducido, **no calibrado** con mediciones de LIPAc.

## Función y diferencia respecto a la versión anterior

`VacuumNetworkModel` es el **único productor de lecturas de vacío y estado
de bombas** en el `InjectorModel`. Reemplaza en tiempo de ejecución a
las instancias separadas de `VacuumRegionModel` de `plant.py`, que se
conserva como código histórico para pruebas independientes. La nueva red
no asigna una sola presión a todos los sensores.

Cada estación comprende tres volúmenes con estados de presión parcial:

| Nodo | Función | Lecturas EPICS |
|---|---|---|
| `C1`, `C2` | Cámara VAC01 o VAC02 | `VacPGVC`, `VacSGVC` |
| `T1`, `T2` | Entrada de la turbomolecular, entre SV y TP | `VacPGTP`, `VacSGTP` |
| `F1`, `F2` | Respaldo de TP, conexión hacia PP por PV | Métrica interna, sin PV original específica identificada |

La conexión `C1 <-> C2` existe **solo con GV abierta**, con
conductancia configurable; no es conexión directa entre TP/F de las
estaciones. `LEBT:GV` permanece como dispositivo `ValveDevice`,
con `PPS:GV:OpenPermStat` procedente de condiciones externas.

## Topología física y alcance

```text
 H2 / D2 -> [C1] ---- GV ---- [C2] <- Kr (LEBT:MFC)
              |                   |
             SV1                 SV2
              |                   |
             [T1]                [T2]
              |  AIV1             |  AIV2
            TP1                 TP2
              |                   |
             [F1]                [F2]
              |  LTV1             |  LTV2
             PV1                 PV2
              |                   |
             PP1                 PP2
       NIV1 -> C1        (no existe NIV2)
```

La topología dibujada es funcional y **no representa dimensiones**.
VAC01 recibe H₂/D₂ de la fuente, VAC02 el Kr auxiliar. La transmisión
de H₂/D₂ desde la cámara ECR hasta C1 se simplifica mediante
`delivery_fraction` configurable; por defecto 1.0 es una hipótesis, no
un coeficiente medido. La cámara de RF asociada a VAC02 queda fuera del
alcance físico de este modelo.

NIV solo existe en VAC01. Los comandos históricos
`LEBT:VAC02:NIVOpenCmd` y `NIVCloseCmd` pueden seguir presentes en
las DB originales, pero el runtime de esta rama **no crea NIV02** y
los ha excluido de la lista activa de comandos escribibles.

LTV tiene estados heredados de lectura en la OPI, pero en esta versión no
se ha identificado un par de comandos de accionamiento para crear su
`ValveDevice`. El modelo puede consumir `LTVOpenStat` como condición
externa de venteo del nodo F. Esto **no supone** reconstruir el controlador
automático real de LTV.

## Estados físicos y ecuaciones

Las presiones se almacenan por nodo y especie
`residual, H2, D2, Kr, N2`. La presión total ideal es la suma
de las parciales. En forma reducida:

```text
V_C dP_C,g/dt = Q_MFC,g + Q_fuga,g + Q_GV,g - Q_SV,g
V_T dP_T,g/dt = Q_SV,g + Q_AIV,g - Q_TP,g
V_F dP_F,g/dt = Q_TP,g + Q_LTV,g - Q_PP,g
```

En régimen de conductancia, se usa intercambio conservativo entre
nodos; para SV con TP activa y PP disponible existe una solución
analítica de **dos nodos acoplados C/T**, con conductancia y velocidad
efectiva. Se evita que el resultado dependa artificialmente del paso
temporal cuando C/S son grandes. El modelo mantiene un balance
de presiones parciales, **no resuelve** en general flujos compresibles,
transiciones viscosa/molecular, gases químicamente reactivos ni
dependencias de conductancia con la presión.

Con **TP detenida**, T y F se conectan a través de
`stopped_tp_conductance_l_s`; SV abierta, PV abierta y PP funcionando
permiten el bombeo primario de cámara a través de la TP inmóvil.
Cuando TP está girando, su eficacia efectiva combina la conductancia
de SV, velocidad de la bomba y velocidad fraccionaria.

El modelo de bomba residual tiene un suelo asintótico de presión.
No crea deliberadamente gas al bombear un nodo que ya estaba por
debajo del suelo. Los flujos externos sí pueden provocar una presión
final superior a `ultimate_pressure_mbar`.

## Máquina de equipos y señales

- `PPOnCmd/PPOffCmd` -> `PPOnStat`; `TPOnCmd/TPOffCmd` ->
  `TPOnStat` y `TPSpeedStat`.
- `TP.speed_fraction`: estado numérico interno de 0 a 1, con
  `tp_acceleration_s` y `tp_deceleration_s` editables.
- `TP.speed_70_percent_or_less`: **métrica** de parada para VAC01;
  no crea un comando `PVCloseCmd`.
- La aceptación sintética de `TPOnCmd` exige PP encendida, PV abierta
  y presión F por debajo de `max_foreline_start_mbar`. **No es una
  reconstrucción de las condiciones reales del PLC.**
- `PGVC/SGVC/PGTP/SGTP` publican presión total ideal de su nodo;
  no incorporan rango efectivo del instrumento, gases de calibración
  ni correcciones Pirani/Penning.
- `*DefStat` de vacuómetros indica fallo **de dispositivo** en el
  modelo V1.4, no `P < umbral`. El indicador TP `TPDefStat` se
  publica en función del fallo sintético de TP.
- Las precondiciones `PVOpenPrecond` / `SVOpenPrecond` las calcula
  `vacuum_opi.py` por compatibilidad. La fórmula de `SVForcing`
  **no autoriza acciones** en el modelo ni sustituye la lógica del PLC.

Métricas útiles en `context.metrics`:

```text
LEBT:VAC01.pressure_mbar
LEBT:VAC01.inlet_pressure_mbar
LEBT:VAC01.foreline_pressure_mbar
LEBT:VAC01.partial_D2_mbar
LEBT:VAC01.partial_H2_mbar
LEBT:VAC01.partial_Kr_mbar
LEBT:VAC01.partial_N2_mbar
LEBT:VAC01:TP.speed_fraction
LEBT:VAC01:TP.speed_70_percent_or_less
```

VAC02 utiliza prefijo equivalente. Los PV se emiten solo si existen
en el catálogo de PV activo. Las métricas internas no son PV
de equipamiento publicadas por defecto.

## Fallos asignables por equipo

Se utiliza el mecanismo ya existente
`engine.control_plane.set_device_fault(device_id, True)`.
El motor sincroniza los fallos con `context.device_faults`; las clases
`VacuumPump` y `VacuumGauge` exponen `.fault`, las clases
`ValveDevice` y `GasFlowController` exponen `.state.fault`.

| Identificador para VAC01 | Respuesta del entrenamiento |
|---|---|
| `LEBT:VAC01:PP` | La bomba primaria se detiene/no arranca |
| `LEBT:VAC01:TP` | Se detiene la orden de funcionamiento y desacelera |
| `LEBT:VAC01:PV`, `SV`, `AIV`, `NIV` | Actuador congelado en su posición previa |
| `LEBT:VAC01:PGVC`, `SGVC`, `PGTP`, `SGTP` | Lectura anterior retenida y `DefStat = 0` |
| `LEBT:VAC01:CHAMBER_LEAK` | Carga de fuga añadida a C1 |
| `LEBT:GV` | GV queda bloqueada en su posición previa |
| `SRC:MFCD`, `SRC:MFCH`, `LEBT:MFC` | Caudal controlado decae a cero |

VAC02 admite los equivalentes excepto NIV. Para un fallo de un
sensor antes de la primera lectura no existe dato anterior fiable;
esta limitación no debe confundirse con una medida válida.

```python
engine.control_plane.set_device_fault("LEBT:VAC01:TP", True)
engine.step()
engine.control_plane.clear_device_fault("LEBT:VAC01:TP")
```

La semántica de cada fallo es una hipótesis de **entrenamiento binario**,
no necesariamente el modo de fallo del componente real.
La implementación no automatiza recuperación de GV, SV, PV ni apertura
de emergencia, ni permite que `SVForcing` anule protecciones.

## Verificación, extensiones y límites

```bash
pytest -q tests/test_vacuum_network.py tests/test_gas_vacuum_topology.py
python scripts/demo_vacuum_pumpdown.py --hours 2 --csv /tmp/vacuum_2h.csv
```

La demo arranca desde atmósfera, supone autorización previa de SV y
genera CSV **sintético**. No controla el inyector ni reproduce PLC.

Pendiente validar: volúmenes, conductancias C(P,gas), velocidades de
bombeo S(P,gas), temperatura, límites de respaldo y criterios de
arranque TP, respuesta de PP, tiempos de válvulas, dinámica de NIV/AIV
y LTV, calibración y rango de sensores, lectura IV602 y semántica
de permisos SV02 durante el bombeo primario. Véanse
[modelo completo](../vacuum_model.md),
[calibración](vacuum_calibration.md),
[procedencia LCS](../original_lcs_model_logic.md) y
[PV readbacks](../pv_readback_traceability.md).
