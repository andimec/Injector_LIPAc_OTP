# emu_geometry.py | Geometría del Allison scanner y malla ROI

**Categoría:** relaciones geométricas derivadas de SNL v2.
**Código:** [emu_geometry.py](../../src/injector_otp/models/emu_geometry.py).

## Visión física

El sistema EMU es un Allison scanner: una cabeza móvil con rendijas, placas de deflexión y una copa de Faraday. Cada posición del motor y cada tensión aplicada seleccionan una región del espacio de fases transversal. **La geometría convierte el ángulo de referencia en tensión; no calcula trayectorias completas ni emittance por sí sola.**

## EmuGeometry: relación ángulo-tensión

Parámetros por defecto en metros: separación entrada→placas 0.010, longitud de placas 0.090, tramo placas→salida 0.002 y separación entre placas 0.009.

Se forma un factor geométrico:

    F = [(L + 2*b)*L] / [4*d*(a + L + b)]
    VHT [V] = angulo [mrad] * energia [keV] / F
    angulo [rad] = F * VHT [V] / (1000 * energia [keV])

Los nombres y unidades siguen las expresiones extraídas de emitSnlEmu_v2.st. En el modelo se exige energía positiva y finita. VHT es la **diferencia entre placas** y no la orden individual de PS1 o PS2.

## build_roi: de la OPI a la malla global

Los parámetros upper/lower, motor step, energy, angle peak init/end, angle delta y HVpoints definen la exploración. La implementación invierte las coordenadas de pantalla mediante:

    motor_upper = 130 - border_up
    motor_lower = 130 - border_low

Se convierten a V los picos inicial y final y la anchura angular. Se interpola linealmente el centro de la ventana de tensión según la posición de motor: Vpic(x) = pendiente*x + intercepto. La ventana de cada fila se centra en ese Vpic y tiene anchura deltaV.

Para que posiciones vecinas sean comparables en el análisis ROOT, se crea **una única malla global de tensión**. La tensión pedida se redondea al índice más cercano y se recorre la malla en orden descendente. El extremo final de malla se fija a hi para limitar deriva de coma flotante.

## Pseudocódigo

    validar números finitos, límites y sentinelas ±9999
    calcular factor geométrico F
    convertir ángulos (mrad) a VHT (V)
    transformar coordenadas OPI a motor (130 - border)
    calcular pendiente e intercepto de Vpic(x)
    construir malla VHT global, con paso deltaV / HVpoints
    para cada posición x:
        calcular inicio/fin de ventana local
        redondear ambos límites a índices de malla
        devolver secuencia descendente de tensiones

## Riesgos y mejoras

La aproximación es geométrica de primer orden: no incluye fringe fields, ancho de rendija, aceptación angular finita, ni variación del campo entre placas. El valor 130 y las dimensiones son del software fuente: deben contrastarse con metrología y la convención real de coordenadas. Los límites admitidos están protegidos por guardas de software, no por PLC.

1. **P1:** pruebas de inversión ángulo↔voltaje, extremos de ROI, signos y casos de malla límite.
2. **P1:** verificación geométrica contra escaneos Fast/Full experimentales.
3. **P2 física:** simular campo eléctrico de placas con bordes, ray tracing y función de respuesta del Allison.
4. **P2:** incorporar errores de alineación y calibración de energía y posición.

**Prueba:** [test_emu_geometry.py](../../tests/test_emu_geometry.py). **Complemento:** [reconstrucción EMU](../emu_reconstruction.md).
