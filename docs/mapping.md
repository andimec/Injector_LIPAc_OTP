# Restaure solo las entradas INP del `calc`, sin cambiar la fórmula original

Las cuatro fórmulas y los 19 enlaces se han cotejado con el repositorio original `andimec/topIFMIF_INJ`, archivo `plcInjectorApp/db/plcInjector_StatusForOpi.db`.

## VAC01 PV
`(A&B)|C`
- A `LEBT:VAC01:TPDefStat`
- B `LEBT:VAC01:PPOnStat`
- C `LEBT:VAC01:AIVOpenStat`

## VAC01 SV
`((((A&B)|D)|(E&F&G))&C)|H`
- A `LEBT:VAC01:AIVOpenStat`
- B `LEBT:VAC01:NIVOpenStat`
- C `LEBT:VAC01:TPDefStat`
- D `LEBT:VAC01:SVOpenStat`
- E `LEBT:VAC01:PGTPDefStat`
- F `LEBT:VAC01:SGTPDefStat`
- G `LEBT:VAC01:PGVCDefStat`
- H `LEBT:VAC:SVForcing`

## VAC02 PV
`(A&B)|C`
- A `LEBT:VAC02:TPDefStat`
- B `LEBT:VAC02:PPOnStat`
- C `LEBT:VAC02:AIVOpenStat`

## VAC02 SV
`(A&B&C&D)|E`
- A `LEBT:VAC02:PGTPDefStat`
- B `LEBT:VAC02:SGTPDefStat`
- C `LEBT:VAC02:PGVCDefStat`
- D `LEBT:VAC02:TPSpeedStat`
- E `LEBT:VAC:SVForcing`

**Limitaciones:** el resultado calc es una precondición de OPI, no necesariamente un interlock PLC completo. No aplicar esta lógica a un sistema real sin validación del PLC y la documentación de seguridad.
