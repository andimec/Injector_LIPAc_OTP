# vacuum_opi.py | Precondiciones para pantallas de vacío

**Categoría:** expresiones de visualización heredadas, sin dinámica.
**Código:** [vacuum_opi.py](../../src/injector_otp/models/vacuum_opi.py).

## Función en el sistema

VacuumOPIPreconditions toma estados de bombas, válvulas, medidores y forzado, y calcula las PV de **precondiciones mostradas en OPI** para VAC01/VAC02. Importa expresiones booleanas literales de [original_lcs_logic.py](original_lcs_logic.md).

Las salidas que genera, si están en catálogo, son:
- LEBT:VAC01:PVOpenPrecond y LEBT:VAC02:PVOpenPrecond.
- LEBT:VAC01:SVOpenPrecond y LEBT:VAC02:SVOpenPrecond.

La PV SVForcing puede influir en los resultados por la fórmula heredada. Este comportamiento **no debe transformarse en permiso de apertura del simulador** sin validar la semántica del PLC original.

## Fórmulas y pseudocódigo

Para la PV de ambas regiones:

    PVOpenPrecond = (TPDefStat AND PPOnStat) OR AIVOpenStat

Para la SV de VAC01:

    SV01 = ((AIVOpenStat AND NIVOpenStat)
            OR SVOpenStat
            OR (PGTPDefStat AND SGTPDefStat AND PGVCDefStat))
           AND TPDefStat
    SV01 = SV01 OR SVForcing

Para la SV de VAC02:

    SV02 = (PGTPDefStat AND SGTPDefStat AND
            PGVCDefStat AND TPSpeedStat) OR SVForcing

    en update:
        leer PV como bool, defecto False
        evaluar las tres funciones originales
        publicar únicamente resultados OPI presentes en catálogo

## Restricciones

Estos valores son compatibles con la presentación histórica; no son permisos de seguridad ni reconstrucciones verificadas de lógica Siemens. Las conversiones bool de cualquier valor no nulo pueden esconder calidad INVALID o stale. Los estados PP/TP proceden ahora de `VacuumNetworkModel` y pueden diferir de señales reales sin calibración.

## Siguientes pasos

1. **P1:** prueba de tabla de verdad para cada combinación relevante con fórmulas originales.
2. **P1:** identificar y documentar cada bit del PLC real y distinguir forzado de autorización.
3. **P2:** añadir calidad, timestamps y estado desconocido, además de verdadero/falso.
4. **P2:** correlacionar decisiones de válvulas con presión real, velocidades de TP y enclavamientos de operación, sin trasladar una fórmula de OPI al control activo.

**Prueba:** [test_original_lcs_logic.py](../../tests/test_original_lcs_logic.py). **Fuente:** plcInjector_StatusForOpi.db, según la documentación del proyecto.

## Relación con la red de vacío V1.4

El módulo mantiene **solo visualización**. La fórmula de SV02
contiene `TPSpeedStat` y aún no está reconciliada con la apertura
de SV durante bombeo primario a través de TP detenida.
`SVForcing` es una solicitud excepcional descrita por la OPI,
pero no se usa como autorización física ni se activa
automáticamente en el simulador. Solo VAC01 tiene NIV física.
El nuevo modelo [vacuum_network.py](vacuum_network.md) calcula las
presiones y estados, pero no inventa la lógica PLC ausente.
