# Procedimiento de aceptación: VAC01/VAC02

### Lecturas, sin escribir

`PPOnStat`, `PVOpenStat`, `TPOnStat`, `TPSpeedStat`, `TPDefStat`,
`SVOpenPrecond`, `SVOpenStat` y las correspondientes `.UDF`, `.STAT`, `.SEVR`.

### Secuencia observable de VAC01, sin atribuir semántica PLC

1. PP recibe orden: `PPOnStat=1` y calidad aceptable.
2. PV abre: `PVOpenStat=1` con `PVOpenPrecond=1` previamente confirmado.
3. TP recibe pulso: `TPOnStat=1` cuando PP encendida, PV abierta y presión
   de la línea de respaldo calculada por Python <=3 mbar (hipótesis de entrenamiento).
4. Aceleración: `TPSpeedStat=0` durante la rampa configurada, luego `1`
   aproximadamente 600 s después del arranque simulado, sin reinicios ni fallos.
5. SV: `SVOpenPrecond` calculado y alarmas válidas. **La fórmula VAC01 no
   contiene `TPSpeedStat`**, por tanto puede conceder permiso antes de completar
   la rampa; la fórmula VAC02 sí depende de `TPSpeedStat`. No identificar
   ninguna de las dos fórmulas OPI con la protección certificada del PLC.
6. `ValveDevice` en la versión actual **no aplica** `PVOpenPrecond` ni
   `SVOpenPrecond` como guarda de apertura. Antes de afirmar que el
   enclavamiento es efectivo, implementar y probar esas guardas con manejo
   fail-closed de valores y alarmas no válidas.

### Criterios de aceptación de calidad

- `.UDF=0`, `.STAT` distinto de `UDF`, `.SEVR` distinto de `INVALID`.
- No se modifican nunca `.STAT`, `.SEVR` ni `.UDF` manualmente.
- `.PROC` puede usarse únicamente tras verificar que no hay enlaces físicos,
  ni escrituras de dispositivo que cambien `VAL`.
- Registros `calc` se actualizan por sus entradas (no forzar `VAL`).
- Los eventos de pérdida de conexión o reinicio del motor invalidan la
  continuidad física; una prueba de aceleración exige un ciclo continuo.
