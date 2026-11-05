# emu_beam.py | Haz gaussiano sintético

**Categoría:** fixture analítica para pruebas, no simulación de un haz LIPAc.
**Código:** [emu_beam.py](../../src/injector_otp/models/emu_beam.py).

## Propósito

Una prueba del scanner necesita una señal I(x,x') reproducible incluso sin haz. SyntheticPhaseSpace define una gaussiana bidimensional en coordenadas de **posición motor mm** y **ángulo mrad**, caracterizada por corriente máxima, centro, emittance RMS supuesta y parámetros Twiss alfa/beta.

## Modelo matemático

Definimos X=x−x_c y A=x'−x'_c, beta>0, epsilon>0 y gamma=(1+alfa²)/beta. El modelo devuelve:

    J = gamma*X² + 2*alfa*X*A + beta*A²
    I(X,A) = I_pico * exp(-J / (2*epsilon))

Los valores por defecto son demostrativos: pico 5 mA, centro 80 mm/0 mrad, epsilon 30 mm·mrad, alfa 0 y beta 3 mm/mrad. El objeto valida finitud de entradas, epsilon>0, beta>0 y pico no negativo.

Esta forma es útil para obtener una elipse gaussiana y comprobar reconstrucción. No implica que el haz de deuterones/protones del inyector sea realmente gaussiano ni que la lectura de copa sea exactamente la intensidad local de esa distribución.

## Pseudocódigo

    crear fixture con pico, centro, epsilon, alfa y beta
    validar parámetros positivos y finitos
    para un punto (x, ángulo):
        X = x - centro_x
        A = ángulo - centro_angulo
        gamma = (1 + alfa*alfa) / beta
        J = gamma*X² + 2*alfa*X*A + beta*A²
        devolver pico * exp(-J/(2*epsilon))

## Qué falta físicamente

No hay extracción de plasma, menisco, cola no gaussiana, aberraciones, espacio de carga, ruido de copa, mezcla D+/D2+/D3+, aceptación de rendija, filtro temporal o calibración de la intensidad. El modelo puede dar una curva aparentemente perfecta que **no demuestra exactitud física**.

## Próximas mejoras

1. **P1:** regresión analítica de momentos Twiss sobre una malla suficientemente fina.
2. **P1:** asegurar que el fixture solo pueda activarse con una etiqueta synthetic y no se mezcle con datos reales de FACQ.
3. **P2:** introducir múltiples poblaciones, halos, ruido configurable, offset y regiones sin señal.
4. **P2 física:** convolucionar distribución con transmisión/aceptación del Allison scanner.
5. **P3:** incorporar distribuciones exportadas de PIC/LEBT o medidas calibradas con trazabilidad.

**Prueba asociada:** [test_emu_analysis.py](../../tests/test_emu_analysis.py), y modo synthetic de [test_emu_hardware.py](../../tests/test_emu_hardware.py).
