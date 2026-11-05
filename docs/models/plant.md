# plant.py | Gases, válvulas, vacío y refrigeración

**Categoría:** modelos de proceso reducidos para entrenamiento.
**Código:** [plant.py](../../src/injector_otp/models/plant.py). **Parámetros:** [model_parameters.yaml](../../config/model_parameters.yaml).

## Qué representa

El módulo aporta estados y una respuesta temporal comprensible para equipos de vacío y gas. No pretende resolver una red de conductancias moleculares ni un circuito termohidráulico.

### ValveDevice

Detecta **flancos de subida** de OpenCmd/CloseCmd, mantiene opened y publica OpenStat/CloseStat. En las válvulas con permit_pv, solo permite abrir cuando esa PV está activa. El cierre no requiere permiso. Los nombres de algunas PV de VAC se forman sin separador entre válvula y sufijo, a diferencia de otros equipos. El modelo no reproduce tiempos de carrera, válvulas atascadas ni toda la lógica del PLC.

### GasFlowController

El caudal de un MFC responde al setpoint Debit solo cuando está habilitado y se cumple la condición de válvula. Su dinámica es:

    q(t+dt) = q(t) + (q_obj - q(t)) * (1 - exp(-dt/tau_gas))

Los MFC SRC:MFCD y SRC:MFCH dependen respectivamente de las válvulas de D2 y H2. LEBT:MFC representa una alimentación auxiliar independiente de esas válvulas de fuente. Se publican Deb1Mes/Deb2Mes y StsVanne si existen en catálogo.

### VacuumRegionModel

Para VAC01 y VAC02 calcula, con integración Euler y presión mínima p_base:

    dp/dt = fuga + Kgas * suma_caudales - bombeo * (p - p_base) / tau
            + entrada_fallo
    p_siguiente = max(p_base, p_actual + dt * dp/dt)

Se usa bombeo si PP o TP están activadas. VAC01 recibe q de SRC:MFCD/MFCH; VAC02 de LEBT:MFC. No se supone conductancia entre ambas regiones. Los sensores de presión disponibles reciben un valor común simplificado. SGVCDefStat compara con el umbral configurado.

### CoolingSkidModel

No resuelve balances térmicos: observa INJ:WS:ResPCDefStat, lo fuerza a cero ante fallo sintético de refrigeración y publica una métrica cooling.healthy.

## Pseudocódigo combinado

    leer órdenes de válvulas y actualizar estado binario
    si válvula de gas y MFC habilitados:
        filtrar caudal hacia Debit
    si no:
        filtrar caudal hacia cero
    para cada región VAC:
        leer caudales que le corresponden
        comprobar estado PP/TP
        calcular fuente de gas + fugas - extracción + fallo
        integrar presión y actualizar indicadores
    actualizar estado externo de refrigeración

## Precisión y riesgos

Los valores de Kgas, tau, fuga, vacío base y respuesta MFC son **hipótesis**, no curvas de equipo. Para dt comparable o superior a tau, Euler puede generar errores numéricos importantes. Los sensores reales no necesariamente comparten presión. Las PV OPI de precondición **no prueban** permisos efectivos del PLC.

## Mejoras priorizadas

1. **P1 software:** proteger dt/tau, modelar fallo de sensor, comando bloqueado, retardo de válvula y consistencia de readbacks.
2. **P1 medición:** ajustar tau de MFC y caída/subida de presión con registros de transitorios reales.
3. **P2 física:** construir red de nodos con volumen V, conductancia C y velocidad de bombeo S(p), gases H2/D2 y estados de GV.
4. **P2 física:** diferenciar lecturas de ion gauges, Pirani y vacuómetros por rango, calibración y ruido.
5. **P3:** añadir circuito térmico del skid con masa térmica, caudal, temperatura y alarmas.

**Pruebas:** [test_gas_vacuum_topology.py](../../tests/test_gas_vacuum_topology.py), [test_architecture.py](../../tests/test_architecture.py). **Criterio de aceptación:** evolución estable de presión, caudales correctos por región y fallos reproducibles.
