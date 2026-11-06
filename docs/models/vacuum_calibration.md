# vacuum_calibration.py | Perfil configurable y datos experimentales

**Código:** [`vacuum_calibration.py`](../../src/injector_otp/models/vacuum_calibration.py)  
**Configuración:** [`model_parameters.yaml`](../../config/model_parameters.yaml)  
**Prueba ejecutable:** [`demo_vacuum_pumpdown.py`](../../scripts/demo_vacuum_pumpdown.py)  
**Madurez:** parametrización de entrenamiento, sin ajuste experimental.

## Objetivo

Separar la predicción basada en balances de gas de los valores que
queremos **ajustar** para un escenario de referencia: tiempo efectivo
de bombeo, presión objetivo a dicho tiempo y presión última asintótica.
Permite disponer de perfiles de 1, 2 o 3 horas y, posteriormente,
sustituir las hipótesis por datos registrados de LIPAc.

**No** es un controlador que fuerza `P(t)` a una curva o instante fijo.
Es una calibración de constantes temporales del modelo. Si las válvulas
están cerradas, falla PP/TP, el gas entra o la temperatura/volúmenes
cambian, la presión y el tiempo resultantes cambian también.

## 1. Parámetros y unidades

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

| Clave | Unidades | Semántica |
|---|---|---|
| `initial_pressure_mbar` | mbar | Presión física inicial de la simulación |
| `pumpdown_time_h` | h | Duración total de referencia para calibrar el perfil |
| `reference_start_pressure_mbar` | mbar | Presión inicial de referencia para cálculo de constante de roughing |
| `roughing_end_pressure_mbar` | mbar | Presión de referencia para pasar de fase primaria a turbo en la demo |
| `roughing_floor_mbar` | mbar | Suelo asintótico de fase primaria |
| `roughing_time_fraction` | adimensional | Parte de duración de referencia asignada a fase primaria |
| `target_pressure_mbar` | mbar | Presión deseada en tiempo de referencia, **no** límite último |
| `ultimate_pressure_mbar` | mbar | Límite asintótico nominal del bombeo de gas residual |

Validación de parámetros: horas positivas,
`0 < roughing_time_fraction < 1`;
`P_ref > P_rough_end > P_rough_floor > 0`;
`P_rough_end > P_target > P_ultimate > 0`.
Valores inválidos provocan `ValueError`.

El perfil de VAC02 es **independiente** del de VAC01, de forma que
podemos asignar tiempos y presiones diferentes. La cámara RF vinculada
a VAC02 no está incluida en el modelo físico actual.

## 2. Calibración de constantes temporales

El perfil utiliza dos constantes:

```text
tau_rough = 3600 * pumpdown_time_h * roughing_time_fraction /
            ln((P_ref - roughing_floor)/(roughing_end - roughing_floor))

tau_turbo = 3600 * pumpdown_time_h * (1 - roughing_time_fraction) /
            ln((roughing_end - ultimate)/(target - ultimate))
```

La fase primaria utiliza velocidad de bombeo efectiva ligada a
`tau_rough`; en alto vacío el bombeo residual se asocia a
`tau_turbo`. Las características concretas de la red de volúmenes,
conductancia por TP detenida, apertura SV/PV y tiempo de aceleración de
TP modifican la presión alcanzada respecto al perfil de referencia.

**Importante:** el valor `max_foreline_start_mbar` es una guardia
sintética independiente, no deriva de `target_pressure_mbar`.
Igualmente, el criterio de procedimiento `IV602 < 1e-6 mbar`
no equivale al umbral de arranque de la MAG W 2800.

## 3. Conversión de los tres MFC

`SRC:MFCH` -> H₂ en VAC01; `SRC:MFCD` -> D₂ en VAC01;
`LEBT:MFC` -> Kr en VAC02.

El caudal de los MFC se expresa en SCCM. Al convertirlo en
carga de gas para la ecuación de presión:

```text
Q_g [mbar L/s] = flow_sccm * 0.001 L/cm³ / 60 s/min
                 * P_ref[mbar] * T_g[K] / T_ref[K]
```

Los valores por defecto son
`gas.reference_pressure_mbar = 1013.25` y
`gas.reference_temperature_K = 273.15`.
**Se deben verificar** las condiciones reales de calibración del
controlador y factores de corrección por especie antes de usar
datos de operación. Las `delivery_fraction` también son ajustables
y requieren estudio del camino desde la fuente ECR.

El throughput de gas se calcula por especie; a igualdad de SCCM
corregidos, las masas de H₂, D₂ y Kr son distintas, pero la carga
molar ideal equivalente se basa en PVT. El transporte y velocidad de
bombeo sí dependen del gas.

## 4. Calibración futura mediante curvas reales

Formato CSV permitido:

```csv
flow_sccm,delta_pressure_mbar
0,0
1,0.000001
2,0.000003
```

**Valores ilustrativos, no medidas LIPAc.** La columna
`delta_pressure_mbar` debe contener presión adicional en la cámara
respecto a flujo cero, con mismo gas, estado de bombas, temperatura y
configuración de válvulas. La medida real debe acompañarse de metadatos
de procedencia externos: fecha, sensor, calibración, configuración,
estado SV/PV/GV, presión de respaldo, temperatura, flujo real y errores.

Colocar un archivo de medidas, por ejemplo
`data/vacuum/d2_delta.csv`, y configurar:

```yaml
vacuum:
  flow_pressure_csv:
    SRC:MFCD: "data/vacuum/d2_delta.csv"
```

**En la V1.4** las tablas se cargan al iniciar Python, exigen
columnas exactas, caudales únicos y valores no negativos.
`FlowPressureCurve.value()` interpola linealmente en el intervalo
medido y **satura** a los valores extremos fuera del rango: no
extrapola linealmente.

Solo en el régimen de **TP nominal, PP ON, PV abierta y SV abierta**
se usa el dato experimental para construir una carga efectiva,
sin sustituir directamente el valor publicado del vacuómetro:

```text
Q_effective = delta_pressure / (1 / S_species + 1 / C_SV)
```

Fuera de esa condición el sistema utiliza el flujo físico
SCCM -> throughput ideal. Los datos de varias especies se suman como
aproximación; **no** se ha calibrado una interacción entre flujos
o una familia de curvas multivariable.

El archivo CSV se resuelve como ruta normal del proceso Python; para
rutas relativas, ejecutar desde la raíz del repositorio, tal como
hace el lanzador estándar. La ruta del CSV es dato de configuración
del entrenamiento, no proviene de EPICS.

## 5. Ejecución y comparación de escenarios

```bash
python -m pip install -e ".[dev]"
python scripts/demo_vacuum_pumpdown.py --hours 1 --csv /tmp/vacuum_1h.csv
python scripts/demo_vacuum_pumpdown.py --hours 2 --csv /tmp/vacuum_2h.csv
python scripts/demo_vacuum_pumpdown.py --hours 3 --csv /tmp/vacuum_3h.csv
pytest -q tests/test_vacuum_network.py
```

La demo usa presión inicial atmosférica para el ejemplo, sin alterar
el valor predeterminado del motor general, que es `1e-6 mbar`.
Arranca PP, abre conceptualmente PV/SV con autorización **supuesta**
y arranca TP cuando la presión de cámara alcanza
`roughing_end_pressure_mbar`. Exporta la presión de cámara, entrada
de turbo, respaldo y velocidad de la bomba por tiempo. No inicia
Phoebus, un IOC ni ningún equipo real.

El ensayo automatizado de PR #11 verificó `138 passed` en la
revisión inicial del código. Esa evidencia acredita comportamiento
de software para los escenarios probados, **no fidelidad física**.

## 6. Plan de calibración experimental

1. Identificar modelo exacto de TP/PP y registrar curvas OEM por especie.
2. Medir volúmenes efectivos de cámaras, T/F y conductancias de SV/GV/TP parada.
3. Registrar bombeo primario con SV/PV abiertas, desde presión conocida.
4. Registrar aceleración, presión de respaldo y transición a alto vacío.
5. Registrar presión estable y transitoria a caudales independientes de
   H₂, D₂ y Kr, con corrección de los MFC y del sensor utilizado.
6. Ajustar simultáneamente tiempos, suelo y cargas gaseosas con unidades;
   reservar datos independientes para validación, no solo ajuste.
7. Documentar incertidumbres y rangos de uso del perfil resultante.

Véanse [red física](vacuum_network.md),
[modelo principal](../vacuum_model.md) y
[condiciones de operación del inyector](../modeling_baseline.md).
