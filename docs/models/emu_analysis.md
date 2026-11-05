# emu_analysis.py | Emittance RMS y parámetros Twiss

**Categoría:** análisis de muestras, no simulador del haz.
**Código:** [emu_analysis.py](../../src/injector_otp/models/emu_analysis.py).

## Qué calcula

A partir de parejas (posición motor, ángulo, corriente) calcula segundos momentos ponderados por corriente **positiva**, emittance geométrica RMS y parámetros de Twiss. Las entradas siguen las unidades x en mm, angle en rad (convertido a mrad internamente), I en mA.

Para cada punto i se usa un peso w_i=max(0,I_i) y se descartan pesos nulos. Se necesitan al menos cuatro puntos válidos. Definimos las medias ponderadas de x y a=x' en mrad y:

    Sxx = suma[w_i*(x_i-media_x)^2] / suma[w_i]
    Saa = suma[w_i*(a_i-media_a)^2] / suma[w_i]
    Sxa = suma[w_i*(x_i-media_x)*(a_i-media_a)] / suma[w_i]
    epsilon_rms = sqrt(max(0, Sxx*Saa - Sxa^2))
    alfa = -Sxa / epsilon_rms
    beta = Sxx / epsilon_rms
    gamma = Saa / epsilon_rms

Si epsilon es cero se rechaza matriz de covarianza singular. samples_to_csv devuelve texto con columnas de resultados, sin escribir disco ni acceder a EPICS.

## Pseudocódigo

    convertir todos los samples: x mm, angle rad -> mrad, w=max(I,0)
    filtrar pesos > 0; exigir cuatro puntos y suma de pesos positiva
    medias = promedios ponderados x y ángulo
    calcular Sxx, Saa y Sxa
    epsilon = sqrt(Sxx*Saa - Sxa^2)
    si epsilon <= 0: error de covarianza singular
    alfa, beta, gamma = relaciones de Twiss
    devolver resultado y número de muestras utilizadas

## Limitaciones que afectan al resultado

El estimador asume **área de celda constante** en la malla x,x'. En un escaneo ROI optimizado, la distribución de puntos puede no ser uniforme. No realiza resta de línea base, selección de especie, corrección de eficiencia, resolución instrumental, error de lectura angular, factor de integración espacial, tratamiento estadístico ni normalización relativista. La geometría emplea **coordenadas del motor**; para comparar con emittance de máquina debe verificarse origen y signo.

Por tanto las cifras son **diagnósticas preliminares**, no emittance normalizada ni un resultado de aceptación de haz.

## Siguientes pasos

1. **P1:** pesos explícitos por área ΔxΔx' y rechazo de muestras inexistentes; diferenciar ceros sintéticos de zonas no exploradas.
2. **P1:** propagación de incertidumbre y estudios de sensibilidad al umbral de corriente y línea base.
3. **P2:** reconstrucción de mezcla de especies, calibración copa y función de transmisión del Allison.
4. **P2:** comparar con ROOT/herramientas de análisis históricas sobre los mismos registros.
5. **P3:** informe de emittance geométrica y normalizada con energía, especie y convención de unidades explícitas.

**Prueba:** [test_emu_analysis.py](../../tests/test_emu_analysis.py). **Relacionado:** [emu_geometry.md](emu_geometry.md).
