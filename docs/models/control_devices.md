# control_devices.py | RF, timing, actuadores y haz

**Categoría:** mixta. Parte de lógica exacta del LCS, parte de dinámica de entrenamiento.
**Código:** [control_devices.py](../../src/injector_otp/models/control_devices.py).

## Modelos existentes

### RFSystemModel

Espera warmup_s con FilOnCmd, exige autorización RF:PLASMA:ENABLE o RF:BEAM:ENABLE y ausencia de fallo. La potencia directa sigue una respuesta de primer orden, con tiempo característico power_tau_s:

    P_f(t+dt) = P_f(t) + (P_obj - P_f(t)) * (1 - exp(-dt/tau))

P_obj = max(0, RfPwr + rf_offset_effect_gain × RfOffset), solo si RF está activa. El valor por defecto de rf_offset_effect_gain es **0**, porque el efecto físico de ese registro no está caracterizado. La fracción de potencia reflejada se estima mediante una distancia en el plano de posiciones ATU (WrtX, WrtY), respecto al punto de referencia, y se limita a 0.95. Esta correlación es ilustrativa, **no una impedancia de plasma medida**. Los bits de control y estado provienen de original_lcs_logic.py.

### PositionerModel

Actúa ante flancos de InCmd/OutCmd y publica InStat/OutStat inmediatamente. Es binario, sin tiempo de inserción, carrera, atasco o límites físicos.

### TimingSystemModel

Calcula duty físico desde TPulse/Trep y modo CW de RF_GENE; conserva además las expresiones Cyclut/DutyCycle históricas para pantallas. El duty histórico no debe alimentar el haz.

### BeamTransportModel

Produce una señal cualitativa limitada por RF, caudal D2, HV y BEAM:ENABLE. La escala depende de raíz cuadrada de potencia RF, caudal relativo y tensión relativa; solo muestra señal FC si está insertada y multiplica por duty físico. **No simula plasma ECR, extracción, menisco ni óptica LEBT**.

### InterfaceOnlyModel

No modifica PV. Declara explícitamente una familia todavía sin modelo.

## Pseudocódigo principal

    comprobar autorización, fallos y calentamiento RF
    avanzar potencia RF con filtro exponencial de primer orden
    estimar reflexión con distancia ATU y publicar bits LCS
    detectar flancos de posición de FC, BS y CHOP
    calcular duty físico y valores de pantalla
    si hay RF, D2, HV, autorización y FC insertada:
        señal_FC = corriente_nominal * factores_cualitativos * duty
    en otro caso: señal_FC = 0

## Limitaciones y evolución

1. **P1:** ajustar warmup, tau y potencia real con series temporales Pforward/Preflected y estados Modbus.
2. **P1:** implementar límites, retrasos, atascos e incoherencias comando/readback de posicionadores.
3. **P2 física RF:** caracterización de adaptación de impedancias, reflexión compleja y respuesta al plasma.
4. **P2 física haz:** modelo de extracción y transmisión dependiente de solenoides/steerers y especie H2/D2; comparar FC, BS y ACCT.
5. **P2 software:** tipos y calidad de dato, alarmas y observabilidad de fallos intermitentes.

Los parámetros se encuentran en [model_parameters.yaml](../../config/model_parameters.yaml). **Pruebas relacionadas:** [test_original_lcs_logic.py](../../tests/test_original_lcs_logic.py), [test_architecture.py](../../tests/test_architecture.py).
