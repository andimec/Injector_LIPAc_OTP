# emu_sequencer.py | Secuencia de medida EMU

**Categoría:** reconstrucción de SNL v2 con protecciones adicionales de entrenamiento.
**Código:** [emu_sequencer.py](../../src/injector_otp/models/emu_sequencer.py).

## Objetivo

Ordena al motor y a las placas una serie de posiciones/tensiones, espera a que cada una llegue al readback solicitado y toma una muestra cuando aparece un evento FACQ nuevo. Admite cuatro modos: **EMITTANCE** (ROI), **WIDE** (barrido de tensión), **UPPER** y **LOWER** (detección de borde). Los modos no son cuatro representaciones físicas diferentes del haz, sino trayectorias de exploración de la instrumentación.

## Estados y transición

IDLE → WAIT_MOTOR_ENABLE → WAIT_PLATES_ENABLE → WAIT_MOTOR → WAIT_PLATES → WAIT_ACQUISITION → siguiente objetivo o COMPLETE.

PAUSED suspende el avance desde cualquier espera y permite reanudar; ABORTED se alcanza por pérdida de autorización externa, OFF, fallo de motor/placas, acción incompatible o timeout. Las guardas y esperas acotadas son **extensiones de entrenamiento** frente al SNL original.

### Cómo prepara un barrido EMITTANCE

Validate llama a [build_roi](emu_geometry.md). Rechaza entradas no finitas, rangos/sentinelas incorrectos y trayectorias fuera del recorrido motor. Se generan posiciones cada Pasmotdet y para cada fila se eligen tensiones sobre la malla global. Los extremos se incluyen incluso si no son múltiplos exactos del paso. El número total se limita por max_targets.

Los modos WIDE/UPPER/LOWER usan Debscanl, Finscanl y Passcanl para barrido de placas, junto con un motor fijo o movimiento de detección. La tensión individual de cada placa es ±VHT/2. Los contadores históricos Nptscanl/Nptdet son fórmulas de OPI, no necesariamente el número real de puntos ejecutados.

### Cómo toma cada muestra

Se comprueba MOTOR.RBV próximo al objetivo, MOVN=0 y DMOV=1. Después PS1/PS2 deben estar cerca de ±VHT/2, según tolerancias absoluta y relativa. Al recibir un **emu.facq_sample_id distinto del anterior**, guarda tiempo, posición, tensión solicitada, diferencia medida, ángulo calculado y corriente FC.

**Matiz importante:** actualmente el ángulo almacenado se calcula desde la **tensión solicitada**, no desde VhtRdbk, aunque el archivo conserve ambas tensiones. Es una simplificación que debe quedar explícita al interpretar datos.

## Pseudocódigo

    cuando Validate sube:
        construir y guardar ROI; publicar parámetros o error
    cuando Actemit/Actscan/Actupper/Actlower sube:
        comprobar ExtSec/FSDefStat y validar trayectoria
        guardar Savemit solo si modo EMITTANCE
        solicitar habilitar motor y placas
    para cada (posición, VHT):
        pedir MOTOR.VAL, PS1=VHT/2 y PS2=-VHT/2
        esperar motor listo; si excede timeout: abortar
        esperar placas listas; si excede timeout: abortar
        esperar id de muestra FACQ nuevo; si timeout: abortar
        agregar muestra y avanzar índice
    al terminar:
        COMPLETE, solicitar Act*=0
        en EMITTANCE devolver placas y motor a cero
    al abortar:
        ABORTED, solicitar placas a 0 y mantener motor en lectura actual

## Ejemplo de operación del simulador

Para representar el Fast Scan documentado, configurar las PV de emittance con upper=46, lower=-42, motor step=2, energy=100 keV, angle peak init=-37 mrad, angle peak end=45 mrad, angle delta=20 mrad, HVpoints=30. Emitir primero el flanco Validate y después Actemit=ON **con los permisos externos simulados activos**. El algoritmo genera los objetivos, espera readbacks de motor/placas y consume un evento FACQ por punto. Savemit=OFF no solicita almacenamiento; Savemit=ON solo guarda el indicador de autorización para un futuro adaptador. Las 1.395 muestras del archivo real no aparecen mágicamente en esta simulación, porque pertenecen al replay separado.

## Alcance y mejoras

El secuenciador **no escribe archivos**. Solo mantiene samples y save_requested; results_csv devuelve texto, y preliminary_emittance invoca el estimador RMS sin corrección. El modo Fast/Full del procedimiento de julio de 2026 se expresa mediante parámetros, **todavía no hay presets con esos nombres**. El hecho de tener event id no sustituye la adquisición ICV108 real. Pausa/aborto debe contrastarse con riesgos y secuencias originales.

1. **P1:** presets Fast/Full explícitos con versiones, parámetros y tests de puntos.
2. **P1:** auditoría de cancelación, retorno a posición segura y tensiones tras todos los fallos.
3. **P1:** usar quality/timestamp por muestra y comprobar consistencia VSet vs VRdbk.
4. **P2:** almacenamiento separado autorizado por Savemit, conectado al IOC de entrenamiento.
5. **P2 física:** integrar función de aceptación del scanner y parámetros de resolución reales.

**Pruebas:** [test_emu_sequences.py](../../tests/test_emu_sequences.py) y [test_emu_geometry.py](../../tests/test_emu_geometry.py). **Procedimiento:** BA_D_2E98YT v1.0.
