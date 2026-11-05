# original_lcs_logic.py | Traducción de ecuaciones originales

**Categoría:** lógica heredada. **Fidelidad:** expresiones DB/OPI reproducidas, no física de planta.
**Código:** [original_lcs_logic.py](../../src/injector_otp/models/original_lcs_logic.py).

## Objetivo

Permitir que la simulación produzca determinados valores exactamente como los registros CALC o representaciones históricas del LCS. **Reproducir una fórmula no significa demostrar que ese valor tenga el significado físico esperado.**

## Fórmulas implementadas

- Conversión de señales analógicas: raw = ingeniería × 30000 / escala, y la inversa. clamp_register recorta el registro a [0, 30000] por defecto.
- RF: máscaras de bits para CalcMot02, CalcOnOff, CalcRAZ; decodificación de Mot105 (on, ready, defect).
- Potencia reflejada mostrada: PwrRef = 0.9 × Mot103.
- ATU: CalcModeXY = ModeXY OR (ModeXY desplazado un bit). Se mantiene la expresión de origen, aunque parezca redundante.
- VAC01/02: expresiones booleanas de PVOpenPrecond y SVOpenPrecond para **visualización OPI**. No autorizan por sí solas abrir válvulas.
- Temporización: timing_display_ratio reproduce una razón histórica Trep/TPulse condicionada por CW; physical_duty_fraction calcula la fracción física TPulse/Trep para pulso, o 1 para CW.

## Pseudocódigo

    para una salida derivada:
        leer los operandos originales
        aplicar literalmente la expresión registrada
        publicar solo como monitor de compatibilidad
    para calcular duty físico:
        si CW: duty = 1
        si Trep <= 0: duty = 0
        si pulso: duty = limitar(TPulse / Trep, 0, 1)
    nunca usar fórmulas OPI como sustituto del PLC/PPS/MPS

## Advertencias

La salida histórica DutyCycle puede no coincidir con la fracción temporal del haz. Tampoco el valor RF PwrRef prueba la validez de la estimación de reflexión usada por RFSystemModel. Las conversiones mantienen los factores originales, incluso si existe una incoherencia de escalas. El origen es [topIFMIF_INJ](https://github.com/andimec/topIFMIF_INJ), commit 3586551ce2eaede262d5cf584ab88d2d940c3a83, según el inventario del repositorio.

## Hoja de ruta

1. **P1:** tabla fuente → PV → fórmula → versión → prueba de regresión para cada expresión.
2. **P1:** marcar formalmente qué salidas son solo HMI, y bloquear su uso como interlock o medida física validada.
3. **P2:** contrastar escalas con registros históricos y ensayos instrumentales.
4. **P2:** automatizar pruebas de equivalencia numérica frente a los CALC originales.

**Prueba principal:** [test_original_lcs_logic.py](../../tests/test_original_lcs_logic.py).
