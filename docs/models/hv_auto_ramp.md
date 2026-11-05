# hv_auto_ramp.py | Arranque automático HV/IE/Repeller

**Categoría:** secuenciador de procedimiento. **No es controlador de seguridad.**
**Código:** [hv_auto_ramp.py](../../src/injector_otp/models/hv_auto_ramp.py).

## Propósito y fundamento

Reconstruye para entrenamiento la subida automática de HV, electrodo intermedio (IE) y repeller. Usa la secuencia del procedimiento **BA_D_2E9QH7 v2.0**, junto con las comprobaciones descritas en el manual LCS v4.0. Es un productor de órdenes simuladas, no ejecuta caput ni conecta al hardware.

## Estados

IDLE → HV_IE → REPELLER → COMPLETE, o ABORTED ante fallo. Los pulsos UptoHT y StopHT se detectan por flanco. Antes de empezar exige las tres señales OnStat y los permisos HV:ENABLE e IE:ENABLE. **No enciende fuentes automáticamente.**

La tabla de puntos objetivo HV/IE en kV es: (1,1), (10,5), (20,10), (30,15), (40,20), (50,25), (100,25). El camino entre puntos usa incrementos individuales de **1 kV**; cada paso espera alcanzar readbacks dentro de ±1 % y cumplir el intervalo configurado. Tras completar HV/IE, R avanza de 0.1 kV a 4.5 kV en pasos de 0.1 kV.

Las PV principales son:
- Comandos: LEBT:HV_PS:HTCmd, SRC:IE_PS:VSet, LEBT:R_PS:VSet.
- Lecturas: LEBT:HV_PS:ScaleVHT, SRC:IE_PS:VRdbkcalc, LEBT:R_PS:VRdbkcalc.
- Estado: LEBT:AUTO:Dialog y métricas hv_auto.*.

## Pseudocódigo

    al flanco UptoHT:
        si fuentes no ON o permisos no activos: ABORTED
        si correcto: phase = HV_IE; pedir 1/1 kV
    mientras phase == HV_IE:
        si permiso/estado ON perdido: ABORTED
        si readbacks fuera de tolerancia:
            acumular tiempo; abortar por timeout
        en caso contrario, tras intervalo:
            incrementar HV/IE hasta siguiente par de la tabla
        si se alcanzó 100/25 kV: phase = REPELLER
    mientras phase == REPELLER:
        esperar readback y tiempo; incrementar 0.1 kV
        al alcanzar 4.5 kV: COMPLETE
    en StopHT durante etapa activa: ABORTED

## Limitaciones críticas

El retardo entre pasos de repeller (1 s) y timeout de readback (20 s) **son supuestos de entrenamiento**. La función de aborto actual cambia estado y mensaje, pero **no implementa automáticamente una rampa de retorno a 0**. Por tanto no debe anunciarse como secuencia de apagado seguro. El chequeo de tolerancia estrictamente relativo tiene problemas potenciales cerca de cero. No reconstruye lógicas reales de disparo ni autorización PPS.

## Siguientes pasos

1. **P1 software:** protocolo explícito de aborto, congelación o descenso seguro, aprobado contra procedimiento.
2. **P1:** pruebas de pérdida de permiso, de lectura, de PS, StopHT, tolerancias y reinicio tras ABORTED.
3. **P1:** confirmar duración y tolerancias de cada etapa con operación real.
4. **P2:** introducir máquina de estados observable con reason codes y logging de pasos.
5. **P2 física:** asociar medida de HV, IE y repeller a energía de extracción y corriente de carga, sin usar ICmd como lectura real.

**Prueba:** [test_hv_auto_ramp.py](../../tests/test_hv_auto_ramp.py).
