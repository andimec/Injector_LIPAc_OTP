# emu_replay.py | Reproducción de mediciones EMU archivadas

**Categoría:** adaptador de datos experimentales. **No es un modelo físico adicional.**
**Código:** [emu_replay.py](../../src/injector_otp/models/emu_replay.py).

## Qué problema resuelve

Permite reproducir en consola mediciones EMU SNL v2 archivadas (formato emit*_optm.txt) sin haz ni conexión a EPICS. Conserva los valores escalares experimentales de cinco columnas: posición motor, VHT solicitado, ángulo, corriente y VHT medido. Este mecanismo es **independiente** del EmuAcquisitionModel sintético y del motor de física reducido.

## Flujo de implementación

**load_measurement** identifica la cabecera, lee los campos de configuración y exige exactamente cinco columnas numéricas. EmuMeasurement.validate reconstruye la ROI con [emu_geometry.py](emu_geometry.md) y compara la primera/última posición, paso del motor y número de valores VHT por fila. En este formato, cada fila del motor tiene **hv_points + 1** muestras, no necesariamente hv_points.

**replay** recorre los puntos archivados, anuncia el estado en terminal y, opcionalmente, reparte su presentación en una duración solicitada. Esa duración es una **animación temporal**, no la cadencia original de adquisición. Si Save está desactivado, **no crea archivos ni directorios**. Si Save está activo, crea un TXT compatible y un JSON de procedencia con nombre, fecha JST, archivo fuente, puntos y política de datos. Usa un archivo .partial mientras está escribiendo, que se conserva si hay interrupción.

El comando interactivo ofrece validate, on, off, save on/off, status y quit. El modo automático evita introducir comandos manuales. **El comando off en el prompt previo a la ejecución no interrumpe una reproducción ya iniciada**; en la API Python existe should_continue para una futura integración.

## Pseudocódigo

    medida = leer archivo TXT experimental
    exigir cabecera, cinco columnas y consistencia geométrica
    si operador eligió Savemit=OFF:
        destino = None; no crear carpeta
    si Savemit=ON:
        comprobar que no exista salida
        abrir archivo .partial y preparar JSON de procedencia
    para cada punto archivado:
        si should_continue informa OFF: interrumpir
        imprimir muestra real sin modificar valores
        opcionalmente dormir para animar
        si guardar: añadir fila a .partial
    si guardar y terminó:
        renombrar .partial a TXT
        crear JSON de procedencia
    devolver ruta de salida o None

## Ejecución offline

    python3 -m injector_otp.models.emu_replay --list
    python3 -m injector_otp.models.emu_replay --auto --save off
    python3 -m injector_otp.models.emu_replay --auto --save on --output-dir output/emu
    ./scripts/launch_emu_snl_replay.sh --duration 180

El launcher/OPI de entrenamiento muestra una terminal, pero los botones Phoebus Validate/ON y el checkbox Save **todavía no envían PV al replay**. Las opciones de terminal son un sustituto explícito y local.

## Limitaciones y hoja de ruta

1. **P1:** puente local de solo entrenamiento OPI → PV autorizada → replay, sin red de producción.
2. **P1:** timestamps por muestra, CRC/hash de fuente, verificación de integridad y controles de duplicados.
3. **P1:** pruebas Save OFF sin efectos secundarios, interrupción y retención del .partial.
4. **P2:** representación gráfica y comparación con mediciones originales; no modificar datos de origen.
5. **P2:** soporte de waveforms reales solo cuando existan archivos de adquisición asociados. No reconstruir formas de onda a partir de promedios.

**Prueba:** [test_emu_replay.py](../../tests/test_emu_replay.py). **Guía:** [emu_fast_scan_replay.md](../emu_fast_scan_replay.md).
