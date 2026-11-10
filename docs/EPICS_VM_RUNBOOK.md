# Runbook de la VM: Phoebus, EPICS, Podman y gemelo digital del inyector

**Fecha de referencia:** 10 de noviembre de 2026. **Ámbito:** VM Debian de entrenamiento del Injector LIPAc. Este documento recoge observaciones reales de las pruebas de VAC01/VAC02 y distingue hechos verificados, configuración de referencia y tareas pendientes.

> **Límite de seguridad.** Solo utilizar en una red de simulación aislada, sin rutas ni descubrimiento EPICS hacia controles reales de LIPAc. Los nombres de PV se preservan literalmente, por lo que conectar un IOC de entrenamiento a una red de producción supone riesgo de colisión. Ninguna fórmula de OPI aquí descrita constituye un interlock Siemens/PPS certificado.

## 1. Estado de implementación y verificaciones

| Elemento | Evidencia / resultado | Situación |
|---|---|---|
| Modelo de red VAC01/VAC02 | \`src/injector_otp/models/vacuum_network.py\` | Modelo reducido, no calibrado |
| Puente CA integral | Ejecución local de \`injector_otp.epics.vacuum_full_bridge\` en \`injector_bridge.service\` | Comprobado en VM. Los archivos de despliegue deben versionarse y contrastarse con la VM |
| Cálculos de precondiciones | Cuatro \`calc\` con enlaces \`INPA...INPH\` recuperados del DB original | Reparación ejecutada en DB montada |
| Readbacks digitales | \`UNHEALTHY=0 of 39\` con \`scripts/audit_vacuum_readbacks.py --scope bi\` | **Validado en VM** |
| Readbacks analógicos | 11 \`ai\`; piloto \`LEBT:VAC01:VacSGVC\` identificado mediante dry-run | **No se ha comunicado validación completa** |
| Dirección estática | \`10.0.3.16\` propuesta en Quadlet | No se ha comunicado todavía la verificación posterior al último reinicio |
| Ciclo completo PP/PV/TP/SV | TP pudo arrancar y publicar \`TPOnStat=1\` | Secuencia completa no validada; permiso de válvula no aplicado por completo |
| Reinicios del motor | Excepción por valor booleano 1500 y \`Restart=always\` | Causa conocida; falta política de recuperación |

## 2. Rutas, procesos y red de esta VM

| Recurso | Ubicación / valor |
|---|---|
| Usuario Debian | \`ifmif\` |
| Clon Git | \`/home/ifmif/Documents/Injector_LIPAc_OTP\` |
| Volumen de IOC | \`/home/ifmif/Documents/IOCs/example_ioc_mounts\` |
| Arranque EPICS | \`.../example_ioc_mounts/st.cmd\` |
| Bases de datos activas | \`.../example_ioc_mounts/db/\` |
| Quadlet IOC | \`/etc/containers/systemd/example_ioc.container\` |
| Quadlet puente | \`/etc/containers/systemd/injector_bridge.container\` |
| Quadlet red | \`/etc/containers/systemd/internal.network\` |
| Servicio IOC | \`example_ioc.service\` |
| Servicio Python | \`injector_bridge.service\` |
| Contenedor IOC | \`systemd-example_ioc\` |
| Contenedor Python | \`injector-ca-bridge\` |
| Podman observado | \`5.4.2\` |
| Red \`internal\` | Bridge Podman, \`10.0.3.0/24\`, gateway \`10.0.3.1\`, DNS habilitado |
| IP de referencia IOC | \`10.0.3.16\`, siempre confirmar después de reinicio |
| Proxy de construcción | \`http://cproxy.iferc.local:8080\`, solo si lo requiere el entorno |
| OPIs Phoebus externas | \`/home/ifmif/Documents/lipac-integrated-opi-injector-phoebus5/LIPAc/L1-SystemExpert/Injector/\` |

Los archivos reales de \`/etc/containers/systemd/\` son **estado del host**. GitHub no lee ni actualiza automáticamente estos archivos. Se deben comparar con las plantillas versionadas y evitar subir contraseñas, credenciales, archivos de alarmas corporativas o rutas de red sensibles adicionales.

### Quadlet IOC

Referencia basada en la configuración observada:

\`\`\`ini
[Unit]
Description=Example IOC with external db

[Container]
Image=ghcr.io/ifmif/lipac-uber-ioc
Network=internal.network
IP=10.0.3.16
PodmanArgs=-it
User=1000
ReadOnly=true
Volume=/data/example_ioc/%H/%N:/data
Environment=EPICS_IOCSH_HISTFILE=/data/iocsh_history
Volume=/home/ifmif/Documents/IOCs/example_ioc_mounts/st.cmd:/opt/uber_ioc/boot/st.cmd
Volume=/home/ifmif/Documents/IOCs/example_ioc_mounts/db:/opt/uber_ioc/db

[Service]
Restart=always
ExecStartPre=mkdir -p /data/example_ioc/%H/%N/

[Install]
WantedBy=default.target
\`\`\`

**Error reproducido:** escribir \`IP:10.0.3.16\` en lugar de \`IP=10.0.3.16\` provoca \`Unit example_ioc.service not found\`; el generador lo explicó con \`not a key-value pair\`. Comprobar siempre las unidades generadas:

\`\`\`bash
sudo podman network inspect internal
sudo /usr/lib/systemd/system-generators/podman-system-generator --dryrun 2>&1
sudo systemctl daemon-reload
sudo systemctl status example_ioc.service --no-pager
sudo podman inspect systemd-example_ioc \
  --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'
\`\`\`

La dirección es persistente **solo si se ha comprobado después del reinicio** y continúa libre en esa subred. No recrear la red \`internal\` sin comprobar su definición \`internal.network\`.

### Variables EPICS en la terminal

\`\`\`bash
export EPICS_CA_AUTO_ADDR_LIST=NO
export EPICS_CA_ADDR_LIST=10.0.3.16
cainfo LEBT:VAC01:TPOnStat
caget -n LEBT:VAC01:TPOnStat LEBT:VAC01:TPSpeedStat
\`\`\`

Después de una interrupción o migración, confirmar el servidor y la IP mediante \`cainfo\`; no asumir que la configuración del shell es heredada por procesos Java ya abiertos.

### Phoebus: archivo settings de la instancia **de entrenamiento**

Añadir bajo \`Data sources\` al archivo \`settings.ini\` que efectivamente utiliza Phoebus:

\`\`\`properties
org.phoebus.pv.ca/addr_list = 10.0.3.16
org.phoebus.pv.ca/auto_addr_list = false
\`\`\`

Cerrar y volver a abrir Phoebus. Verificar en PV Table mediante \`ca://LEBT:VAC01:PPOnStat\`. Si \`caget\` ve \`On\` pero la OPI ve \`Off\`, distinguir fallo del cliente CA de macros/rules/widgets de la pantalla. No modificar el \`settings.ini\` compartido de producción.

## 3. Inventario, generación y enlaces de base de datos

**Fuente doble:** (1) referencias PV reales usadas por las OPIs \`.bob/.opi\`; (2) DB de origen \`topIFMIF_INJ\`. Reconstruir registros \`ai/ao/bi/bo/calc\` conservando nombres, \`ZNAM/ONAM\`, \`EGU\`, \`PREC\`, límites, alarmas y metadatos. No tratar todos los registros como booleanos.

**Error observado:** el generador de DB conservó \`CALC\` pero omitió \`INPA...INPH\` en las cuatro precondiciones. Se restauraron los enlaces originales desde \`topIFMIF_INJ/plcInjectorApp/db/plcInjector_StatusForOpi.db\`:

| Registro calc | Fórmula | Enlaces necesarios |
|---|---|---|
| \`LEBT:VAC01:PVOpenPrecond\` | \`(A&B)|C\` | A TPDefStat, B PPOnStat, C AIVOpenStat |
| \`LEBT:VAC01:SVOpenPrecond\` | \`((((A&B)|D)|(E&F&G))&C)|H\` | A AIVOpenStat, B NIVOpenStat, C TPDefStat, D SVOpenStat, E PGTPDefStat, F SGTPDefStat, G PGVCDefStat, H \`LEBT:VAC:SVForcing\` |
| \`LEBT:VAC02:PVOpenPrecond\` | \`(A&B)|C\` | A TPDefStat, B PPOnStat, C AIVOpenStat |
| \`LEBT:VAC02:SVOpenPrecond\` | \`(A&B&C&D)|E\` | A PGTPDefStat, B SGTPDefStat, C PGVCDefStat, D TPSpeedStat, E \`LEBT:VAC:SVForcing\` |

Los sufijos sin prefijo de la tabla corresponden a la estación indicada. \`SCAN=1 second\` se conserva para estos \`calc\`.

\`\`\`bash
DB=$HOME/Documents/IOCs/example_ioc_mounts/db/plcInjectorApp/db/plcInjector_StatusForOpi.db
python3 scripts/restore_vacuum_calc_links.py "$DB"
# Solo con IOC de entrenamiento y tras inspeccionar el diff:
python3 scripts/restore_vacuum_calc_links.py "$DB" \
  --apply --confirm-training-ioc
caget LEBT:VAC01:PVOpenPrecond.CALC \
      LEBT:VAC01:PVOpenPrecond.INPA \
      LEBT:VAC01:PVOpenPrecond.INPB \
      LEBT:VAC01:PVOpenPrecond.INPC
\`\`\`

Los enlaces CA \`NPP NMS\` no propagan severidades a los cálculos. Las precondiciones de pantalla no sustituyen la lógica PLC y no garantizan enclavamientos efectivos en \`ValveDevice\`.

## 4. Error UDF INVALID y normalización de 39 bi / 11 ai

**Observación antes de la corrección:**

\`\`\`text
LEBT:VAC01:TPOnStat.VAL   Off
LEBT:VAC01:TPOnStat.UDF   0
LEBT:VAC01:TPOnStat.STAT  UDF
LEBT:VAC01:TPOnStat.SEVR  INVALID
\`\`\`

Las lecturas \`bi\` tenían \`DTYP=Injector Soft Channel\`, \`SCAN=I/O Intr\`, \`PINI=NO\` e \`INP\` vacío. Python escribía \`VAL\` mediante Channel Access, pero los registros seguían comunicando calidad inválida. Se probó de forma controlada \`.PROC=1\` y **no eliminó la alarma**. No usar el antiguo modo \`process-stale-udf\` para este IOC.

**Solución ensayada con éxito para readbacks digitales de entrenamiento:**

\`\`\`epics
record(bi, "LEBT:VAC01:TPOnStat") {
    field(DTYP, "Soft Channel")
    field(SCAN, "Passive")
    field(PINI, "NO")
    field(INP, "0")
    field(ZNAM, "Off")
    field(ONAM, "On")
}
\`\`\`

El script \`migrate_vacuum_readbacks.py\` selecciona **50 salidas pertenecientes a Python**, 39 \`bi\` y 11 \`ai\`. Rechaza enlaces inesperados, duplicados y cambios fuera del montaje del IOC. No modifica comandos, PV externas PPS o \`calc\`.

\`\`\`bash
cd ~/Documents/Injector_LIPAc_OTP
ROOT=$HOME/Documents/IOCs/example_ioc_mounts/db
python3 scripts/migrate_vacuum_readbacks.py --root "$ROOT" --scope bi
sudo systemctl stop injector_bridge.service
sudo systemctl stop example_ioc.service
python3 scripts/migrate_vacuum_readbacks.py --root "$ROOT" --scope bi \
  --apply --confirm-offline-training-ioc
sudo systemctl start example_ioc.service
# Verificar IP, EPICS_CA_ADDR_LIST y el argumento --ioc del puente.
sudo systemctl start injector_bridge.service
python3 scripts/audit_vacuum_readbacks.py --scope bi
\`\`\`

**Resultado observado en VM:** \`UNHEALTHY=0 of 39\`. Esta cifra valida estado/alarma, no calibración física ni coherencia de cada par \`OpenStat/CloseStat\`.

**Pendiente para \`ai\`:** piloto \`LEBT:VAC01:VacSGVC\` y posteriormente otros diez \`ai\`. Ejecutar primero \`--scope pilot-ai\` en dry-run; cambiar únicamente con servicios detenidos y validar presión \`1e-6\` mbar, \`UDF=0\`, \`STAT/SEVR=NO_ALARM\`. \`PREC=0\` puede hacer que un widget muestre cero; usar \`caget -e 12\` para comprobar precisión. Solo después aplicar \`--scope ai\` y verificar \`UNHEALTHY=0 of 11\`.

## 5. Puente Python, propietarios y arranque

**Jerarquía:** Phoebus ⇄ Channel Access ⇄ Soft IOC ⇄ puente EPICS ⇄ motor Python. La red física y el equipo son sintetizados por Python, no por el IOC. El puente integral \`vacuum_full_bridge.py\` limita los readbacks a 50 PV con propietarios explícitos de \`vacuum_network\`, válvulas y MFC. El IOC conserva la propiedad de los cuatro \`calc\` de OPI, evitando dos escritores.

**Entrada de comandos:** los pulsos se detectan por flanco y no deben reproducirse al reconectar. Los MFC mantienen setpoints de nivel. No convertir un valor \`1500\` en booleano; rechazarlo sin accionar equipos. Registrar fallos de entradas de forma aislada para que el motor no se cierre por una única PV inválida.

**Arranque observado de TP en el modelo reducido:**

\`\`\`text
TPOnCmd (flanco) + PP running + PV abierta + P_foreline <= 3 mbar
  -> TPOnStat=1
  -> rampa de velocidad aprox. 600 s (parámetro de entrenamiento)
  -> TPSpeedStat=1 al alcanzar velocidad nominal sin fallo
\`\`\`

\`TPSpeedStat\` no es condición de **arranque** de TP. Interviene en la fórmula de \`VAC02:SVOpenPrecond\`, pero no en la de VAC01. El modelo actual no garantiza detener TP si PP se apaga posteriormente. La OPI no implementa automáticamente la autorización como bloqueo de válvula.

**Reinicio observado:** a las 11:11:36 JST el puente terminó con \`ValueError: Boolean PV must have a native 0/1 value, got 1500\` tras una escritura de prueba manual. systemd ejecutó un reinicio a las 11:11:41. El nuevo motor publicó \`TPOnStat=0\`; no existe aún restauración persistente de bombas y válvulas. No confundir esto con fallo físico de TP.

\`\`\`bash
sudo systemctl status injector_bridge.service --no-pager
sudo journalctl -u injector_bridge.service -n 100 --no-pager -o short-iso
sudo podman ps
sudo podman network inspect internal
\`\`\`

**Quadlet del puente:** mantener \`Network=internal.network\`, \`EPICS_CA_AUTO_ADDR_LIST=NO\`, \`EPICS_CA_ADDR_LIST=10.0.3.16\`, \`--ioc 10.0.3.16\`. Para publicar solo en VM aislada, la versión integral requiere confirmaciones explícitas \`BRIDGE_ALLOW_WRITES=YES\`, \`BRIDGE_ISOLATED_ACK=YES\`, \`BRIDGE_SCOPE_ACK=FULL_VACUUM\`. No publicar por defecto fuera del laboratorio de entrenamiento. El modo \`--quality-mode process-stale-udf\` queda **descartado para esta instalación**.

## 6. Diagnóstico rápido por síntoma

| Síntoma | Comprobación | Resolución confirmada o pendiente |
|---|---|---|
| \`caget\` correcto, Phoebus Off | \`cainfo\`, PV Table \`ca://...\`, settings CA Java | Configurar \`org.phoebus.pv.ca/addr_list\` y deshabilitar autodescubrimiento |
| PV cambia de host CA al reiniciar | \`podman inspect\`, Quadlet | IP fija \`IP=10.0.3.16\` y validar tras reinicio |
| \`Unit example_ioc.service not found\` | \`podman-system-generator --dryrun\` | Corregir \`IP:10.0.3.16\` a \`IP=10.0.3.16\` |
| \`PVOpenPrecond\` constante / entradas inválidas | \`.CALC\`, \`.INPA...\` | Restaurar enlaces originales de \`calc\` en DB |
| \`UDF=0\` pero \`STAT=UDF, SEVR=INVALID\` | \`.DTYP\`, \`.SCAN\`, \`.INP\`, \`.PROC\` | Readback simulador \`Soft Channel / Passive / INP 0\`; \`.PROC\` por sí solo **falló** |
| Puente reinicia, estados de TP se pierden | \`journalctl\`, \`NRestarts\` | Aislar conversiones inválidas y diseñar snapshot/restore |
| \`TPOnStat=1\` y \`TPSpeedStat=0\` | \`tp_acceleration_s\`, tiempo desde arranque | Normal durante la rampa configurada, alrededor de 600 s |
| \`SVOpenPrecond=1\` pero maniobra insegura | Diferenciar \`calc\` OPI de \`permit_pv\` de válvula | Bloqueo real del modelo aún pendiente |
| Ambos \`OpenStat\`/\`CloseStat\` muestran «Close» | \`caget -n\` de los dos campos | Validar valores complementarios y mapeo de etiquetas |

## 7. Pruebas de aceptación progresivas

1. **Seguridad de red:** verificar que no existe ruta a CA/PVA de producción; inspeccionar \`cainfo\` y rutas.
2. **Esquema:** comparar catálogo OPI, DB original, DB de simulación, tipos, rangos, alarmas, escalas y periodos; detectar PV duplicadas.
3. **Calidad EPICS:** \`UNHEALTHY=0 of 39\` logrado; pendiente \`UNHEALTHY=0 of 11\`. Verificar enumeraciones y complementos numéricos.
4. **Semántica de comandos:** comprobar pulsos \`0 -> 1 -> 0\`, setpoints analógicos y rechazo de valores no permitidos, sin cerrar el motor.
5. **PP -> PV -> TP:** leer permisos, estados, presión \`F\` y tiempos; registrar \`TPOnStat\` y \`TPSpeedStat\` durante 600 s continuos.
6. **SV:** contrastar fórmulas originales VAC01/VAC02, enlaces y estado de alarma. Ejecutar pruebas negativas con permisos no concedidos antes de considerar válido un bloqueo en Python.
7. **Restart/rollback:** verificar IP estática y comportamiento explícito ante reinicio del puente e IOC.
8. **CI:** \`python3 -m pytest -q\` más pruebas de los scripts de migración y del puente; los tests locales no sustituyen pruebas CA reales.

Para inspección sin comandos de actuation:

\`\`\`bash
python3 scripts/audit_vacuum_readbacks.py --scope bi
python3 scripts/audit_vacuum_readbacks.py --scope pilot-ai
python3 scripts/monitor_vacuum_cycle.py --ioc 10.0.3.16 --station VAC01 --minutes 13
\`\`\`

## 8. Reproducir y sincronizar el estado de la VM con Git

**La copia en \`example_ioc_mounts/db\` y los Quadlet bajo \`/etc/containers/systemd\` no están dentro de \`~/Documents/Injector_LIPAc_OTP\`.** Ejecutar \`git push\` desde el repositorio, por sí solo, **no los versiona**. Hacer una comparación explícita antes de subir:

\`\`\`bash
cd ~/Documents/Injector_LIPAc_OTP
git status --short
git branch --show-current
git remote -v
diff -u db/plcInjectorApp/db/plcInjector_StatusForOpi.db \
  ~/Documents/IOCs/example_ioc_mounts/db/plcInjectorApp/db/plcInjector_StatusForOpi.db || true
diff -u db/plcInjectorApp/db/plcInjector_Input.db \
  ~/Documents/IOCs/example_ioc_mounts/db/plcInjectorApp/db/plcInjector_Input.db || true
\`\`\`

Para otras DB, comparar sus rutas relativas y trasladar **únicamente las modificaciones aprobadas del simulador**. No copiar respaldos \`.bak*\`, volcados, contraseñas, claves, históricos, archivos de proceso \`.pyc\` ni \`settings.ini\` corporativos. Versionar plantillas Quadlet depuradas, nunca secretos o contenido propietario no autorizado.

Secuencia segura de integración: guardar cambios locales; recuperar la rama actualizada desde GitHub; comparar con lo instalado; ejecutar pruebas; subir solo archivos revisados. Usar una rama para código no validado por CI y abrir una PR. No forzar \`git push --force\` sobre \`main\`.

## 9. Recuperación

- **DB:** restaurar copia \`.bak_\` o \`.bak_readbacks_\` del archivo alterado, con IOC detenido.
- **Quadlet:** conservar copia \`.container.bak\`, restaurarla y ejecutar \`systemctl daemon-reload\`.
- **Puente:** mantener la imagen anterior para rollback; nunca arrancar dos publicadores a la vez.
- **Alarmas:** nunca escribir a mano \`STAT\`, \`SEVR\` o a los \`calc\` para disimular un error.
- **Estado físico simulado:** actualmente se reinicializa al reiniciar Python. No interpretar un nuevo \`Off\` tras restart como una orden externa.

## 10. Mejoras pendientes, con prioridad

- Integrar en Git todas las fuentes locales exactas del puente, herramientas y tests, cotejándolas con este documento.
- Validar los 11 analógicos y la precisión de visualización de presiones de alto vacío.
- Añadir manejo tolerante a entradas mal tipadas sin reiniciar todo el motor, con alarma y registro diagnóstico.
- Diseñar checkpoint de estado del motor más política de restauración segura.
- Implementar autorización de actuadores en Python con fail-closed y validación separada de las fórmulas OPI.
- Validar pares \`OpenStat/CloseStat\`, fallos, comandos repetidos y tasas de publicación.
- Fijar despliegue reproducible: imagen y dependencias, versión de Python, plantillas Quadlet, comprobación de aislamiento y tests automáticos.

**Fuente de verdad:** código del repositorio, archivos de IOC realmente montados, \`caget/cainfo\`, \`journalctl\` y pruebas de regresión. Una guía no sustituye la evidencia de esos ensayos.
