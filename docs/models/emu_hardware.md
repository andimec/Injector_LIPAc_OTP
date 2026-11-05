# emu_hardware.py | Motor, placas y adquisición sintética

**Categoría:** dinámica de actuadores de entrenamiento y adaptación SNL.
**Código:** [emu_hardware.py](../../src/injector_otp/models/emu_hardware.py).

## Qué contiene

Cuatro modelos distintos con un fin común: producir readbacks creíbles para ejercitar el secuenciador EMU. Ninguno controla un equipo real.

### 1. EmuMotorSupervisor

Reproduce tres etapas de habilitación MaxV/servo/Refresh y la secuencia inversa de deshabilitación, con retardo de 1 s por etapa por defecto. Requiere ExtSec y FSDefStat activos y ausencia de fallo EMU. La comprobación explícita de ExtSec es un **endurecimiento conservador del simulador**, no una afirmación sobre la implementación del PLC. Las solicitudes se realizan mediante context.request_command y ACL.

### 2. EmuMotorModel

Un motor unidimensional se mueve hacia MOTOR.VAL a velocidad máxima rate_mm_s, con tolerancia y límites configurados. Solo se mueve con MOTOR.CNEN, servo habilitado, guardas externos sanos, SPMG en Go y destino dentro de límites. HOMR, al detectar flanco, fija destino cero. Publica RBV, MOVN, DMOV, ATHM y flags de límites. La PV LEBT:EMIT:Position mantiene la **convención de signo negativa** respecto a MOTOR.RBV usada por la DB original.

### 3. EmuPlatePSModel

Cada placa responde a Softbo y a su VSet con velocidad máxima plate_rate_V_s. Si hay fallo emu_plates, se apaga. Publica VRdbk y comandos/status; calcula:

    Vht = PS1.VSet - PS2.VSet
    VhtRdbk = PS1.VRdbk - PS2.VRdbk

La propiedad Calcdly.ODLY=30 cuando está apagada reproduce la expresión del LCS; **no significa** que exista un retardo físico de apagado de 30 s.

### 4. EmuAcquisitionModel

Genera eventos temporales en intervalos synthetic_period_s, incrementando emu.facq_sample_id. Sin fixture, puede reutilizar una PV de corriente disponible; con fixture explícitamente activada, calcula un pulso gaussiano desde [emu_beam.py](emu_beam.md). No representa una tarjeta ICV108/178 de alta velocidad ni guarda la forma de onda real.

## Pseudocódigo

    supervisor:
        si enable y seguros activos:
            habilitar MAXV -> servo -> refresh
        si disable o seguridad perdida:
            deshabilitar servo -> refresh -> MAXV
    motor:
        leer destino y home; comprobar límites y enable
        acercar posición al destino en velocidad * dt
        publicar movimiento, posición y fin de movimiento
    placas:
        si Softbo: activar según retardo configurado
        acercar cada tensión a su setpoint
        publicar diferencia comandada y medida
    FACQ:
        cuando transcurre el período sintético:
            generar nuevo id de muestra
            si fixture activo: evaluar gaussiana x,x'
            publicar corriente (sintética o de entrada local)

## Limitaciones y próximas mejoras

1. **P1:** medir velocidad real, tiempos de servo, final de carrera, homing, latencia PS y precisión de readback.
2. **P1:** añadir sensores con fallos stuck/noisy, variación de voltaje y timeout observable.
3. **P1:** distinguir muestras nuevas de valores estáticos; el event id no prueba que se adquirió una waveform física.
4. **P2:** modelo de controlador MAXv con aceleración, backlash, límites suaves/duros y servo-fault.
5. **P2 física:** circuito/electrostática de placas y filtro del sistema de adquisición, integración de ventana de medición y ruido calibrado.

**Prueba:** [test_emu_hardware.py](../../tests/test_emu_hardware.py). **Fuente:** emitSnlMotor.st, emitSnlAlims.st, emitMotor.db y tarjetas ICV.
