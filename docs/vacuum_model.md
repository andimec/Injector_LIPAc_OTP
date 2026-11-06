# Red de vacío LIPAc V1.4. Modelo Python configurable (borrador de validación)

Este módulo es **solo para simulación aislada y entrenamiento**. No implementa
interlocks Siemens ni sustituye manuales OEM o procedimientos LIPAc aprobados.
Los valores de volumes, conductancias, tiempos de respuesta y fracciones de
entrega de gas son hipótesis editables, no resultados experimentales.

## Arquitectura

- `VAC01`: volumen C de cámara de fuente, T en entrada de TP, F de respaldo;
  PP, TP, PV, SV, AIV, NIV y la lectura de LTV.
- `VAC02`: misma topología **sin NIV física**; cámara RF queda fuera del alcance.
- `LEBT:GV`: intercambia masa entre C1 y C2 solo si el estado de apertura es
  verdadero. La autorización `PPS:GV:OpenPermStat` sigue en `ValveDevice`.
- `SRC:MFCH`: H2 -> VAC01; `SRC:MFCD`: D2 -> VAC01;
  `LEBT:MFC`: Kr -> VAC02.
- Una sola clase `VacuumNetworkModel` genera las lecturas de vacío y estado de
  bombas; las válvulas y MFC existentes se ejecutan antes.
- El viejo `VacuumRegionModel` se conserva solamente para compatibilidad de
  pruebas legadas. **No participa en el InjectorModel operativo**.

Se modelan presiones parciales `residual, H2, D2, Kr, N2` en tres volúmenes
por estación. Las transferencias por SV, GV y por una TP detenida usan
intercambio conservativo por conductancia. La evacuación usa velocidades de
bombeo efectivas y un perfil de descenso de presión configurado.
Las señales `VacPGVC`, `VacSGVC`, `VacPGTP`, `VacSGTP` representan la
**presión total ideal** del volumen correspondiente, sin correcciones de
sensibilidad por gas ni efectos de rango del sensor.

## 1. Control práctico del tiempo de bombeo

Editar `config/model_parameters.yaml`:

```yaml
vacuum:
  stations:
    VAC01:
      initial_pressure_mbar: 1013.25 # arranque desde atmósfera
      pumpdown:
        pumpdown_time_h: 1.0         # o 2.0 o 3.0
        reference_start_pressure_mbar: 1013.25
        roughing_end_pressure_mbar: 0.05
        roughing_floor_mbar: 0.005
        roughing_time_fraction: 0.40
        target_pressure_mbar: 1.0e-6
        ultimate_pressure_mbar: 1.0e-8
```

Se deriva una constante de tiempo por fase:

```text
tau_rough = 3600 * hours * fraction /
            ln((P_ref-P_rough_floor)/(P_rough_end-P_rough_floor))
tau_turbo = 3600 * hours * (1-fraction) /
            ln((P_rough_end-P_ultimate)/(P_target-P_ultimate))
```

Esto calibra el **descenso libre de gas bajo la secuencia de referencia**.
Los tiempos de arranque de PP/TP, el retraso del operador, el estado de
PV/SV, el flujo de gas y las limitaciones de conductancia alteran el instante
real al que se alcanza la presión objetivo. No se fuerza artificialmente la
presión al cumplirse un temporizador.

`target_pressure_mbar` es la presión deseada al tiempo de referencia.
`ultimate_pressure_mbar` es el suelo asintótico sin gas: no son la misma
variable. No confundir el criterio de IV602 < 1e-6 mbar (transferencia a
procedimientos de operación del inyector) con el umbral OEM de arranque TP.

El fichero conserva `initial_pressure_mbar: 1e-6` en las estaciones por
compatibilidad con el escenario operacional existente. Cambiarlo explícitamente
a `1013.25` para simular bombeo desde atmósfera. Cambios en YAML requieren
reiniciar el motor.

## 2. Modelo de bomba

La bomba TP de referencia VAC01 es **Leybold TURBOVAC MAG W 2800**,
con perfil editable. Los datos de catálogo convencionales usados son:

- 28 800 rpm nominales.
- 2 400 L/s N2 y 2 100 L/s H2.
- Presión de respaldo máxima N2 refrigerada por agua: 3 mbar.

`tp_acceleration_s: 600` representa el límite de catálogo, no un transitorio
medido; `tp_deceleration_s: 600` es solo una hipótesis. D2 utiliza
provisionalmente la velocidad H2, y Kr la de N2; **ambas sustituciones
deben calibrarse**. El modelo comprueba, como guardia sintética de entrenamiento,
PP encendida, PV abierta y presión de respaldo por debajo del límite
configurado antes de aceptar `TPOnCmd`. No afirma reflejar el PLC real.

Con TP detenida el bombeo primario se transmite a través del volumen F y la
conductancia de la TP parada, siempre que PV y SV estén abiertas.
La condición de 70% de velocidad durante parada se expone como métrica
`LEBT:VAC01:TP.speed_70_percent_or_less`, no como PV EPICS inventada.
No se automatiza ninguna maniobra del procedimiento.

## 3. MFC y cargas de gas

Caudales existentes publicados en SCCM:
`SRC:MFCH:Deb2Mes`, `SRC:MFCD:Deb1Mes`, `LEBT:MFC:Deb1Mes`.
Se convierten en throughput mediante:

```text
Q_g [mbar L/s] = flow_sccm * (1e-3 L/cm3) / (60 s/min)
                  * P_std[mbar] * T_gas[K] / T_std[K]
```

La masa molar NO se utiliza en la ecuación de aumento de presión ideal,
pero sí sería necesaria para expresar el caudal másico en kg/s. Ajustar
`gas.reference_pressure_mbar` y `gas.reference_temperature_K` a las
condiciones reales de referencia de los controladores, así como sus
`delivery_fraction`, que NO están verificadas para la geometría de fuente.
La velocidad efectiva de cada especie es también configurable.

Para datos medidos, crear un CSV con columnas:

```csv
flow_sccm,delta_pressure_mbar
0,0
1,0.000001
2,0.000003
```

**Ejemplo sintético únicamente, no datos de LIPAc.** Los valores deben
representar incremento de presión en cámara respecto al estado a caudal cero,
a bombeo constante, con idéntico gas y corrección de calibración.
Luego configurar:

```yaml
vacuum:
  flow_pressure_csv:
    SRC:MFCD: "data/vacuum/d2_measured_delta_pressure.csv"
```

La interpolación es lineal y fuera del rango mantiene la última medida.
Cuando TP está nominal, se convierte el incremento experimental de presión
en una **carga efectiva de gas** según
`Q_cal = P_delta / (1/S_gas + 1/C_SV)`; el balance acoplado de
C/T se integra mediante la solución exacta del sistema lineal de dos nodos.
Esto ajusta la presión estacionaria sin escribir directamente el sensor.
Las curvas siguen siendo **un prototipo provisional** con hipótesis de
aditividad entre especies; las futuras campañas deberán incorporar
dependencia cruzada, estados de bombas, rangos de presión y presión de
respaldo, además de un tratamiento distinto de flujo viscoso y molecular.
Si el archivo falta, se produce un error deliberado al inicializar, en lugar
de inventar datos.

## 4. Fallos por dispositivo

No se necesita crear una PV de fallo para cada equipo. Se utiliza el contrato
actual del motor `SimulationControlPlane.set_device_fault()` y
`context.device_faults`. Cada equipo simulado conserva un indicador interno:

- `LEBT:VAC01:PP`: PP no arranca o se detiene.
- `LEBT:VAC01:TP`: TP se desconecta y desacelera.
- `LEBT:VAC01:SV`, `...:PV`, `...:AIV`, `...:NIV`:
  el actuador conserva su última posición (fallo tipo stuck).
- `LEBT:GV`: su actuador conserva la última posición.
- `SRC:MFCD`, `SRC:MFCH`, `LEBT:MFC`: flujo controlado cae a cero
  con el tiempo de respuesta configurado.
- `LEBT:VAC01:PGVC`, `...:SGVC`, `...:PGTP`, `...:SGTP`:
  lectura congelada, `*DefStat=0` (error).
- `LEBT:VAC01:CHAMBER_LEAK`: añade fuga al volumen de cámara.

Se puede afectar VAC02 cambiando el prefijo. Ejemplo en una simulación
Python, **no en la red de EPICS de producción**:

```python
engine.control_plane.set_device_fault("LEBT:VAC01:TP", True)
engine.step()
engine.control_plane.clear_device_fault("LEBT:VAC01:TP")
```

El atributo `fault` de cada bomba/sensor, y `state.fault` en cada
válvula/MFC, permite construir procedimientos externos de fallos. El nivel
actual usa fallos binarios; características como fuga progresiva en asiento,
ruido de sensor o atasco parcial quedan para una ampliación posterior.

## 5. Límites y validaciones pendientes

1. Volúmenes de los seis nodos y conductancias en función de presión/gas.
2. Curvas OEM verificadas y equipos PP/TP reales de las dos estaciones.
3. Rangos Pirani/Penning y correcciones para mezclas H2, D2, Kr, N2.
4. Lógica Siemens de permisos SV durante bombeo primario (VAC02 en especial).
5. Ubicación y PV de IV602; no se equipara automáticamente a VacSGVC.
6. Secuencia específica de VAC02 y cámara RF fuera de alcance.
7. Validar datos MFC de gas real, condiciones SCCM, transporte desde fuente.
8. Obtener series temporales de presión, flujo y estado de válvulas para ajuste.
9. Red de ventilación NIV/AIV/LTV con regulación de presión y sobrepresión
   real. El venteo actual usa una constante de tiempo y atmósfera nominal.

**Este módulo no conecta con los IOC reales.** Las órdenes EPICS siguen siendo
operador-propiedad, los readbacks siguen siendo propiedad del motor Python,
y `SVForcing` solo se representa como condición visual del OPI, no como
permiso físico no validado.
