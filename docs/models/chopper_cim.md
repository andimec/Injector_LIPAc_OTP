# chopper_cim.py | CIM y registro de fallo FBI

**Categoría:** reproducción de interfaz y escenario de fallo.
**Código:** [chopper_cim.py](../../src/injector_otp/models/chopper_cim.py).

## Qué implementa

ChopperCIMModel permite ejercitar controles y pantallas del Chopper Interlock Monitor (CIM). La enumeración visual distingue CONFIGURATION=0, PRE-ARM=1, ARMED=2, GATE OFF=3, GATE ON:RISING=4, GATE ON=5, GATE OFF:DECREASING=6, pero el modelo actual **solo cambia operativamente entre PRE_ARM y ARMED** mediante StmStateSet.

Los umbrales por defecto son hv_off=1000 V, hv_on=6000 V y acct_on=5 mA. Se reflejan desde VmonOff/VmonThr/AcctThr a las PV de readback para la OPI. No se realiza comparación física de esas señales con trazas FPGA.

Al recibir por flanco un fallo simulado FBI_TRIGGER o device_faults[chopper], el modelo enclava Fbi y guarda una instantánea de StmState, gate, Faraday cup, periodo, duración de pulso, tensión monitorizada y ACCT. El enclavamiento **no se borra simplemente pulsando PRE-ARM**. reset_exercise es una operación explícita del entrenador, no el reset del cRIO.

## Pseudocódigo

    al cambiar StmStateSet:
        si PRE_ARM: cambiar a PRE_ARM
        si ARMED y no latched: cambiar a ARMED
    copiar umbrales de configuración a monitores
    fallo_ahora = fallo sintético o fallo inyectado al chopper
    si fallo_ahora y antes_no_había_fallo y no latched:
        latched = True
        snapshot = valores visibles de la operación
        publicar Fbi* y Fbi = 1
    publicar StmState, Fbi, métricas
    reset_exercise:
        limpiar latch, snapshot y estado de ejercicio

## Qué no significa

No se ha recuperado la lógica interna de comparación por ventanas del cRIO/FPGA, el timing real de gate ni la semántica de reset de hardware. Un estado de pantalla no equivale a permiso MPS/PPS ni garantiza interrupción efectiva del haz. Los umbrales citados proceden de documentación de operación y son **referencias de interfaz**, no constantes universales de protección.

## Siguientes pasos

1. **P1:** reconstruir trazabilidad OPI → FPGA/cRIO → MPS desde fuentes y pruebas autorizadas.
2. **P1:** ensayos de disparo de ejercicio, snapshot y retención tras nuevos comandos.
3. **P2 física/tiempo:** reproducir rampas y ventanas de monitorización del chopper desde oscilogramas.
4. **P2:** distinguir fallos por HV, ACCT, gate y sincronización con códigos causales.
5. **P2 software:** timestamps y orden determinista de eventos; exportación de evidencia para formación.

**Prueba:** [test_chopper_cim.py](../../tests/test_chopper_cim.py). **Frontera:** no desplegar como función de protección real.
