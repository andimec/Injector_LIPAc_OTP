# Prompt maestro para replicar un subsistema LIPAc con OPI, DB, motor Python y puente EPICS

**Uso:** copiar el contenido desde la sección «Prompt reutilizable» en una sesión nueva y proporcionar los archivos autorizados del subsistema elegido. Basado en la experiencia de VAC01/VAC02 del Injector OTP, 10-11-2026.

El prompt es una **especificación de trabajo**, no una autorización para conectar con la máquina real. Antes de comenzar se debe comprobar la procedencia y autorización de los archivos.

## Datos que debe aportar el responsable

- Archivo o árbol completo de OPI Phoebus \`.bob/.opi\`, incluidos widgets embebidos, macros, scripts y recursos asociados.
- Fuentes reales de IOC: archivos \`.db\`, \`st.cmd\`, substitutions \`.substitutions\`, \`.template\`, definiciones de records y, si existen y están autorizados, código de soporte de dispositivo.
- Documentos funcionales y procedimientos aprobados: máquina de estados, manual de usuario, límites, secuencia de arranque, interlocks y escenarios de fallo.
- Delimitación de seguridad: red privada, lista explícita de PV de producción prohibidas, sistemas externos PPS/MPS, servicios de archivo y rutas sin acceso a producción.
- Información de la VM: versión Debian, Podman/Quadlet, EPICS Base, Phoebus, Python, imágenes OCI, nombres de volúmenes, redes, proxy autorizado y directorios de montaje.
- Restricciones físicas: ecuaciones, parámetros medidos, unidades y rangos, hipótesis permitidas y criterios de aceptación.
- No compartir credenciales, secretos, archivos privados sin autorización ni configuraciones que expongan redes de control.

## Prompt reutilizable

\`\`\`text
Actúa como arquitecto de software científico para un gemelo digital de un
subsistema del acelerador LIPAc/IFMIF-DONES.

OBJETIVO
A partir de OPIs existentes y fuentes originales de EPICS IOC, construir un
entorno de entrenamiento TOTALMENTE AISLADO que permita utilizar las OPIs sin
conectar con el acelerador real. El proyecto debe ofrecer:
  (1) inventario y trazabilidad de PV y macros;
  (2) DB de Soft IOC fiel a los metadatos de origen;
  (3) motor de simulación Python independiente de EPICS;
  (4) puente EPICS Channel Access con permisos explícitos;
  (5) pruebas automatizadas y validación de la calidad EPICS;
  (6) despliegue reproducible Podman/Quadlet + Phoebus;
  (7) documentación y procedimiento de recuperación.

MATERIAL DE ENTRADA
Subsistema: [NOMBRE]
OPIs: [RUTA_O_ARCHIVOS]
IOC de origen: [RUTA_DB_ST_CMD_TEMPLATES]
Documentos: [PROCEDIMIENTOS_Y_MANUALES]
VM de entrenamiento: [SISTEMA, VOLUMENES, CONTENEDORES, VERSIONES]
Red aislada: [SUBRED, GATEWAY, IP_RESERVADA]
Ruta de montaje de IOC: [MONTAJE]
Restricciones de publicación: [PV_PROHIBIDAS, ACL]
Modelos/física disponibles: [DATOS, HIPOTESIS]
Otros sistemas y fuentes: [PPS, MPS, PLC, SNL, CIM, LabVIEW]

PRINCIPIOS NO NEGOCIABLES
1. No realizar ninguna lectura/escritura a controles de producción.
   Nunca ejecutar caput sobre una PV real. Empezar en modo offline.
2. Conservar exactamente nombres de PV originales para compatibilidad OPI,
   pero limitar CA/PVA a interfaces y redes privadas sin rutas a producción.
3. Python es el dueño exclusivo de la física, dinámica y estados simulados.
   El IOC publica registros y sus metadatos; las pocas fórmulas calc mantenidas
   para compatibilidad OPI se declaran con un único escritor y su procedencia.
4. No tratar fórmulas de ayuda OPI como interlocks PLC/PPS certificados.
   Separar indicadores, permisos externos, lógica de comando y protecciones.
5. No inventar el comportamiento de equipos no documentados. Para esos casos
   crear interfaces explícitas "interface-only" y anotar evidencia pendiente.
6. Conservar tipos nativos, enumeraciones, límites, unidades, precisión, alarmas,
   tiempos de escaneo, enlaces CALC/INPx/FLNK, semántica de pulsos y acceso.
7. Si faltan datos críticos, producir reporte de gaps y pruebas pendientes;
   no disfrazar datos sintéticos como mediciones ni dar por validado el modelo.
8. Nunca publicar señales PPS/MPS externas como si estuvieran verificadas;
   los permisos externos son entradas explícitas con valor seguro por defecto.

FASE A. INVENTARIO Y TRAZABILIDAD
A1. Recorrer recursivamente todos los OPIs, widgets, macros, expresiones y
    scripts. Resolver macros con sus contextos de uso, detectar PV dinámicas
    y referencias ambiguas. Guardar fuente/archivo/línea/widget.
A2. Analizar todas las DB y sus plantillas/substitutions; entender alias,
    prefijos, tipo de record, DTYP, INP/OUT/DOL, SCAN, PINI, PREC, EGU,
    LOPR/HOPR, DRVL/DRVH, alarmas, ZNAM/ONAM, CALC, INPA...INPL y FLNK.
A3. Cruzar OPI ↔ IOC y separar PV en: comandos, setpoints, readbacks,
    indicadores calc, entradas externas, señales sin productor conocido.
A4. Generar pv_manifest.csv y pv_manifest.json con:
    pv, tipo, metadata, owner, source_path, widgets, commands, quality,
    evidence, model_maturity, runtime_policy y unresolved_dependencies.
A5. Marcar PV sin origen, duplicadas, incompatibles y señales que usan
    etiquetas que no coinciden con valores numéricos; no omitirlas.

FASE B. GENERADOR DE DB PARA SIMULADOR
B1. Reconstruir DB desde un manifiesto tipado, no únicamente a partir de
    búsquedas de texto. Preservar CALC, INPA...INPL, FLNK y sus opciones NPP/NMS
    y verificar resolubilidad de todas las entradas.
B2. Diferenciar los registros del PLC original (p.ej. S7plc/I-O Intr/INP
    de direccionamiento físico) de los READBACKS escritos por Python.
B3. Para salidas modelo-owned bi/ai probadas en un IOC aislado, preparar
    DTYP="Soft Channel", SCAN="Passive", INP="0" y conservar las demás
    etiquetas, escalas y alarmas. No aplicar esta transformación a comandos,
    PPS, señales ajenas, calc, registros con enlaces reales o tipos no validados.
    Hacer piloto bi y piloto ai antes de migrar todos.
B4. Producir diff, backups y migrador idempotente; rechazar duplicados,
    enlaces inesperados, nombres ausentes y modificaciones fuera del IOC
    de entrenamiento. No tocar la DB original.
B5. Validar st.cmd, paths de carga, macros y número exacto de records.
    Evitar doble publicación y múltiples records con el mismo nombre.

FASE C. MOTOR PYTHON INDEPENDIENTE
C1. Arquitectura modular: catálogo PV, modelos de equipo, estado de simulación,
    paso de tiempo, supervisor, fallos, logs y snapshots.
C2. Escribir equations/modelos únicamente donde la evidencia lo permita.
    Separar "exact_source_formula", "procedure_based",
    "reduced_order_unvalidated" e "interface_only".
C3. Parametrizar límites, rampas, tiempos, presiones, caudales, tolerancias
    y condiciones iniciales con unidades. Registrar procedencia y versión.
C4. Configurar comandos booleanos como flanco o nivel según su semántica.
    No reinterpretar un 1500 numérico como True. El rechazo de un valor
    inválido debe quedar auditado SIN cerrar todo el motor.
C5. Modelar calidad de dato, permisos, fallos e interlocks como conceptos
    independientes. Una indicación UDF/INVALID debe provocar una política
    segura, no una autorización implícita.
C6. Definir comportamiento ante reinicios: estado inicial explícito,
    checkpoints recuperables y recuperación segura comprobada.
C7. Prohibir que el propio modelo escriba caput/caget. Debe ser ejecutable
    y testeable sin IOC/Phoebus.

FASE D. PUENTE EPICS
D1. Modo observe/read-only por defecto. Publish exclusivamente con flags
    explícitos y confinamiento verificable a subred de entrenamiento.
D2. Definir allowlist por PV y propietario; jamás publicar readbacks de
    PPS real, calcs del IOC u otros subsistemas por deducción automática.
D3. Separar entradas comandos/setpoints de salidas físicas del motor.
    Evitar ecos, replays de comandos antiguos y callbacks recolectados.
D4. Comprobar schema RTYP, DTYP, SCAN, INP, unidades y alcance antes de
    publicar; abortar si hay discrepancias críticas.
D5. Publicar valores finitos y tipados. Confirmar readback, comparar
    tolerancias numéricas y comprobar UDF/STAT/SEVR.
D6. Nunca borrar artificialmente INVALID ni escribir a STAT/SEVR/UDF
    para ocultar errores. Para el IOC Injector OTP se probó .PROC sobre
    un bi y NO solucionó el UDF INVALID heredado. No generalizar ese
    workaround; corregir procesamiento de DB.
D7. Calcular tasa, backpressure, timeout, reconexión, logging y manejo
    de fallos por PV sin reinicio total del motor.
D8. Ninguna secuencia automática publica si hay más de un writer activo.

FASE E. DEPLOYMENT Y PHOEBUS
E1. Versionar plantillas saneadas de Quadlet y referencias de imágenes OCI.
    En el caso de la VM de referencia:
      repo=/home/ifmif/Documents/Injector_LIPAc_OTP
      mount=/home/ifmif/Documents/IOCs/example_ioc_mounts
      quadlet=/etc/containers/systemd/
      network=internal, subnet=10.0.3.0/24, gateway=10.0.3.1
      ioc_ip=10.0.3.16 (confirmar localmente)
      servicios=example_ioc.service, injector_bridge.service
E2. Quadlet usa claves con "=". Una línea "IP:10.0.3.16" hizo que
    el generador rechazara example_ioc.container y no creara la unidad.
    Exigir "IP=10.0.3.16" y ejecutar podman-system-generator --dryrun.
E3. Mantener EPICS_CA_AUTO_ADDR_LIST=NO y EPICS_CA_ADDR_LIST=<IOC_IP>.
    En Phoebus settings.ini para TRAINING:
      org.phoebus.pv.ca/addr_list = <IOC_IP>
      org.phoebus.pv.ca/auto_addr_list = false
    Comprobar conectividad en PV Table antes de analizar widgets.
E4. Desplegar de forma ordenada: detener bridge, detener IOC, aplicar DB
    y backups, generar Quadlet, levantar IOC, inspeccionar IP, inspeccionar
    records, levantar bridge y verificar publicación.
E5. Documentar rollback de DB, IOC, imagen bridge y configuración Phoebus.
    No incorporar secretos o valores de producción en repositorio público.

FASE F. PRUEBAS
F1. Tests unitarios del parseo OPI/DB y manifiesto; detectar duplicados
    de PV y enlaces CALC ausentes. Ejecutar con fixtures de origen.
F2. Tests de contrato del puente: ACL, owners, digital/analógico, edge,
    reconnect, callback refs, timeouts, alarmas y valores mal tipados.
F3. Tests del motor sin EPICS: escenarios positivos, negativos, fallos,
    reinicio y persistencia. Cero llamadas a la red de producción.
F4. Smoke test CA para record types y calidad VAL/UDF/STAT/SEVR, incluyendo
    tiempo de actualización. Comparar nombres/etiquetas y valores -n.
F5. Test de Phoebus en PV Table y en OPI. Confirmar que el Host CA es el
    Soft IOC esperado y que no hay señales duplicadas.
F6. Test de transición de estados con autorizaciones reales del modelo.
    No declarar interlock funcional solo por mostrar un calc=1.
F7. Guardar trazas esperadas y obtenidas, condiciones iniciales, tiempos,
    tolerancias y versionado de imágenes/configuración.
F8. Inspeccionar CI, licencia y permisos antes de publicar.

ENTREGABLES SOLICITADOS
1. Informe de inventario PV y matriz OPI↔IOC↔modelo↔bridge↔OPI.
2. DB generadas, st.cmd, manifiesto, script generador y diffs auditables.
3. Motor Python y config YAML/JSON separados de EPICS.
4. Bridge observe/publish, allowlists y pruebas.
5. Plantillas de Quadlet y settings Phoebus solo de entrenamiento.
6. README general, documentación de arquitectura, runbook VM y troubleshooting.
7. Pruebas con salida PASS/FAIL y pendientes de validación física.
8. Prompt/plan de adaptación al siguiente subsistema.
9. Reporte de seguridad de red y calidad de señal.
10. Lista "implemented / observed in VM / pending / unsupported" sin ambigüedad.

PROCESO DE ENTREGA
- Primero: inventario, riesgos y manifiesto.
- Después: diseño tipado, modelos y DB con tests.
- Después: despliegue solo lectura y pruebas unitarias.
- Solo al final: publicación aislada con confirmación explícita,
  auditoría de alarmas y ciclo operativo.
- Nunca afirmar que un test fue ejecutado si no hay salida verificable.
- Nunca inventar archivos locales, estados del servicio ni IP actual.
- Entregar cambios en rama Git, diff revisable, instrucciones de rollback.
- Si no tienes acceso a la VM, preparar scripts y checklist de sincronización
  en lugar de afirmar que has copiado /etc/containers/systemd o db montadas.
\`\`\`

## Personalización recomendada para el siguiente sistema

Sustituir primero los campos de entrada por valores concretos. En particular, distinguir la lógica que ya aparece en la OPI de las protecciones que realmente ejecuta el controlador físico. Un PLC de seguridad, RF, electroimanes, refrigeración o EMU exige sus propios modelos y clases de alarmas; **no copiar automáticamente las hipótesis del modelo de vacío**.

Usar el documento [Runbook VM](EPICS_VM_RUNBOOK.md) como conjunto de lecciones aprendidas y el índice de [modelos](models/README.md) como ejemplo de trazabilidad y grado de madurez. Para cada subsistema nuevo, generar y revisar su propia allowlist de readbacks, mapa de comandos y lista de integraciones externas.
