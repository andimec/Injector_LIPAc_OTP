# calorimetry.py | Calorimetría heredada FC, BS e IC

**Categoría:** reproducción exacta de cálculos DB con calibración pendiente.
**Código:** [calorimetry.py](../../src/injector_otp/models/calorimetry.py).

## Interpretación

LegacyCalorimetryModel permite que las PV calculadas originalmente por EPICS sigan teniendo productor dentro de Python. **No es un modelo termohidráulico validado.** Reproduce expresiones de los registros injectorFC_Calorimetry.db, injectorBS_Calorimetry.db e injectorIC_Calorimetry.db.

## Relaciones utilizadas

Las temperaturas se calculan desde las tensiones de lectura:

    Tin_calc = 5 * TinRdbk
    Tout_calc = 5 * ToutRdbk
    DeltaT = Tout_calc - Tin_calc - Comp

La corriente aparente se calcula con la forma histórica:

    Icalc = (mass_flow / 60) * 4186.8 * DeltaT / voltage * duty_factor

Si la tensión de entrada es cero, legacy_current devuelve None y **no emite una corriente calculada**. La función no atribuye unidades nuevas al parámetro mass_flow: conserva la interpretación de la DB original.

Comportamientos específicos:
- FC usa flujo fijo 40, HTCmd y SRC:TIM:DutyCycle de origen, más comp.
- BS calcula DeltaT respecto a **Tin de FC**. Además publica DeltaT2/Icalc2 usando su propio Tin.
- IC también usa Tin de FC, flujo fijo 320 y divisor fijo 100.
- La eficiencia IRendement se calcula como 100 × Icalc / lectura de corriente pertinente. En FC es cero si InStat no está activo.
- Una lectura de TinRdbk igual a cero se considera no disponible para no fingir medición válida.

## Pseudocódigo

    leer temperaturas FC, BS, IC solo si hay entradas no nulas
    convertir sensores usando factor 5
    si FC disponible:
        calcular DeltaT, ICalc y rendimiento
    para BS e IC, si FC y dispositivo tienen datos:
        tomar Tin_FC como referencia histórica
        calcular DeltaT, Icalc, eficiencia
        si BS: calcular DeltaT2 e Icalc2 locales
    si tensión o lectura de referencia es cero:
        no publicar resultado indeterminado

## Advertencias de física

El factor duty histórico puede **no representar la fracción física del pulso**. El calor específico 4186.8 y los caudales son parámetros de la expresión histórica, no evidencia de calibración. Un cero puede ser físicamente válido y el código actual lo trata como dato ausente. No se consideran inercia térmica, distribución de potencia, pérdidas ni sensor offset.

## Mejora incremental

1. **P1:** documentar unidades y rango calibrado de cada transductor, flujo real, tensión y duty.
2. **P1:** introducir señales de calidad para distinguir 0 válido de muestra no recibida.
3. **P2 física:** ecuación de balance P = m_punto × cp(T) × ΔT, con pérdidas, retardo térmico y duty físico correctamente definido.
4. **P2:** incertidumbre propagada y comparación con medida eléctrica/ACCT del haz.
5. **P2 software:** no sustituir cálculos históricos sin una comparación de regresión por PV.

**Prueba:** [test_calorimetry.py](../../tests/test_calorimetry.py).
