# plant.py | Válvulas, MFC, refrigeración y clase legacy de vacío

**Código:** [plant.py](../../src/injector_otp/models/plant.py).
**Fidelidad:** dinámica reducida de entrenamiento. **Estado V1.4:** la red de
presión activa se ha trasladado a [vacuum_network.py](vacuum_network.md).

## ValveDevice

Lee flancos de `OpenCmd/CloseCmd` y emite `OpenStat/CloseStat` cuando
existen en el catálogo. Un `permit_pv`, si está configurado, condiciona
la apertura. Los prefijos de vacío concatenan directamente el sufijo,
por ejemplo `LEBT:VAC01:SVOpenCmd`.

Un fallo interno `state.fault` se toma de
`context.device_faults["LEBT:VAC01:SV"]` (o identificador correspondiente):
el actuador **congela su última posición**. No se simulan recorridos
intermedios, fuga de asiento, tiempo de actuación ni PLC real. Se crea
NIV solo en VAC01. GV es `LEBT:GV` y su permiso externo de apertura
procede de `PPS:GV:OpenPermStat`.

## GasFlowController

Los caudales responden en SCCM mediante:

```text
q(t+dt) = q(t) + (q_set-q(t))*(1-exp(-dt/gas.response_tau_s))
```

`SRC:MFCH` (H₂) y `SRC:MFCD` (D₂) exigen la válvula de seguridad
de la fuente correspondiente; `LEBT:MFC` suministra Kr auxiliar.
Se publican `Deb1Mes`, `Deb2Mes` y `StsVanne` si existen.
El modelo de vacío usa `<prefix>.flow_sccm` para convertir a
throughput. Los flags `context.device_faults["SRC:MFCD"]`,
`"SRC:MFCH"` o `"LEBT:MFC"` reducen a cero el caudal objetivo
con la constante de respuesta. No se modela calibración MKS real.

## CoolingSkidModel

El skid observa `INJ:WS:ResPCDefStat`, reproduce un fallo sintético
de refrigeración y expone `cooling.healthy`; no integra ecuaciones
de flujo de agua o temperatura.

## VacuumRegionModel: histórico, NO usado en ejecución principal

La clase antigua integra una presión por estación:

```text
dp/dt = leak + Kgas*flow_sccm - (p-floor)/pumping_tau
```

Se conserva **solo por compatibilidad con tests anteriores**. Las claves
legacy `gas_coupling_mbar_s_per_sccm` y `pumping_tau_s` de
`config/model_parameters.yaml` **no gobiernan** VAC01/VAC02 en
`InjectorModel`. No debe registrarse simultáneamente con
`VacuumNetworkModel`, porque competiría por las mismas PV de presión
y bombas.

La red nueva dispone de seis nodos C/T/F, conecta las cámaras por GV,
reproduce el bombeo primario a través de TP detenida, inyección
H₂/D₂/Kr, presión parcial, bombeo configurado por tiempo y
presión última, y fallos individuales. Véase
[red de vacío](vacuum_network.md) y
[calibración](vacuum_calibration.md).

## Pruebas y límites

```bash
pytest -q tests/test_gas_vacuum_topology.py tests/test_vacuum_network.py
```

Estas pruebas de software no validan el PLC Siemens, bombas Leybold,
conductancias reales ni medidas de presión de LIPAc.
Pendiente calibrar respuesta MFC, válvulas, sensores y equipos.
