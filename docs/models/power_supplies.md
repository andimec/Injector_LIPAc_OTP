# power_supplies.py | Fuentes de alimentación

**Categoría:** dinámica reducida y conversiones LCS.
**Código:** [power_supplies.py](../../src/injector_otp/models/power_supplies.py).

## Cobertura

Una instancia PowerSupplyDevice representa cada equipo enumerado en POWER_SUPPLY_PREFIXES: bobinas de fuente C1/C2, solenoides SOL01/02, steerers STH/STV, HV principal, IE, repeller R y RC. Cada instancia conserva powered, auxiliary, ready, fault_latched, corriente y tensión. **No simula electrónica de potencia internamente.**

## Lógica y ecuaciones

- Los comandos RESET, ON, OFF y auxiliares se detectan por **flanco**, no por nivel permanente.
- Una falta inyectada enclava fault_latched. Se requiere un reset sin fallo presente para liberarla.
- HV necesita su auxiliar habilitado y HV:ENABLE. IE usa IE:ENABLE. El resto usa COOLING:READY.
- El setpoint se recorta a DRVL/DRVH cuando ambos límites existen en el catálogo.
- La corriente/tensión avanza hacia el objetivo con una rampa limitada:

    cambio_max = max(0, velocidad) * dt
    y_siguiente = y_actual + limitar(y_objetivo - y_actual,
                                      -cambio_max, +cambio_max)

- Para corriente, una PV Rampe positiva sustituye la velocidad configurada. No se interpreta como un modelo de inductancia L/R.
- Para IE, R y RC, las escalas analógicas se convierten a registros y valores de ingeniería. La escala original de lectura de corriente en RC (1) difiere de la escala del comando (10); **se preserva y se advierte**.
- Para HV, HTCmd está en kV, CalcVHT y LectVht en V. ICmd es **límite de corriente**, no lectura de carga. El modelo no fabrica LectIht desde ICmd.

## Pseudocódigo

    para cada fuente:
        comprobar fallos; bloquear hasta reset si persisten
        procesar flancos de comandos y auxiliar
        obtener permiso externo por familia
        si falta permiso o hay fallo: powered = False
        leer y limitar setpoints según DRVL/DRVH
        aplicar rampa hacia setpoint si ON, o hacia 0 si OFF
        convertir cuentas analógicas donde proceda
        publicar OnStat, RdyStat y readbacks compatibles
        publicar métricas separadas de comando y medida

## Qué no está resuelto

No hay sobrecorriente real, disparos, disipación, histéresis magnética, tolerancias instrumentales, ondulación ni transferencia HV a energía del haz. El fallo MAGNET_DRIFT aplica una pérdida simplificada del 5 % en lectura de bobinas, no deriva magnética física. Ciertas salidas de este archivo reproducen **convenciones de registros**, no magnitudes medidas calibradas.

## Hoja de ruta

1. **P1:** campañas de escalones de comando/readback y rampas de cada familia, con timestamps.
2. **P1:** tablas de límites de operación, resolución, factor de escala, estado OFF y fallo/RESET por equipo.
3. **P2 física:** incorporar respuesta RL en bobinas, circuito de control y saturaciones cuando haya datos; transformar corriente a campo mediante FEMM o mapas medidos.
4. **P2:** modelar HV/IE/repeller con tolerancia, retardo, corriente de carga y trips independientes.
5. **P2 software:** detectar discrepancia persistente command/readback, calidad de PV y tiempos máximos.

**Pruebas:** [test_power_supply_scaling.py](../../tests/test_power_supply_scaling.py), [test_architecture.py](../../tests/test_architecture.py). **Parámetros:** [config/model_parameters.yaml](../../config/model_parameters.yaml).
