# Sistema GIO — Gestión de Incidencias y Enlace Operativo

Plataforma web desacoplada (*headless*) para el enlace operativo entre la Planta Interna (OQU) y la
Planta Externa del CASE Puebla: ingesta automatizada de averías SISA, tablero Kanban con semáforos
de dilación, módulo móvil de campo con compresión de evidencia en el cliente y cálculo de MTTR.

- **Backend:** Python / Django 6 + Django REST Framework, autenticación JWT, PostgreSQL 15.
- **Frontend:** Vue 3 (Composition API) + Vite + Tailwind CSS + SweetAlert2, instalable como PWA.
- **Intercambio SISA:** comandos de administración de Django sobre carpetas aisladas del servidor.

## Estructura

```
backend/                 API REST, modelos, RBAC y comandos ETL
  gio_app/               Incidentes, evidencias, bitácora, métricas
  usuarios/              Modelo UsuarioGIO (acceso por expediente) y gestión de usuarios
  scripts/               sincronizar_sisa.bat para el Programador de tareas de Windows
frontend/                Cliente Vue 3 (escritorio PI + móvil PE)
private_data/            Carpetas aisladas de intercambio SISA (no se versionan)
  sisa_imports/          Reportes de averías a ingerir
  sisa_imports/procesados/
```

## Puesta en marcha

### Backend

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py inicializar_gio --con-usuarios
python manage.py runserver
```

`inicializar_gio` crea las carpetas de intercambio y, con `--con-usuarios`, un usuario por rol con
contraseña aleatoria que se imprime una sola vez en la terminal.

Para una base de datos ya existente con la tabla `incidentes_red` creada fuera de Django:

```bash
python manage.py migrate --fake-initial
```

Durante el desarrollo puede trabajarse sobre SQLite con `GIO_DB_ENGINE=sqlite` en el `.env`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

El servidor de desarrollo levanta en `http://localhost:5173` y redirige `/api` y `/media` hacia
`http://localhost:8000`, por lo que no se requiere configuración adicional de CORS en local.

## Control de acceso por roles

El acceso se realiza con el **expediente** corporativo, no con correo electrónico.

| Rol | Visibilidad de folios | Operaciones |
| --- | --- | --- |
| `ADMIN` | Todos | CRUD completo de folios y **único rol con CRUD de usuarios** |
| `PI_SUB` | Todos | Alta de folios, reasignación individual y masiva; sin consola de usuarios |
| `PI_EVALUADOR` | En el tablero, solo donde es `evaluador`; puede abrir cualquier otro folio para revisarlo y usar su chat | Diagnóstico, datos de red y validación del trabajo de campo de sus folios |
| `TECNICO` | Solo donde es `tecnico` | Liquidación y carga de evidencias de su propio folio |

El filtrado se aplica en el servidor (`get_queryset`), por lo que un técnico recibe `404` al pedir
un folio ajeno, y los campos editables se restringen por serializador según el rol.

### Áreas y bajas

Los técnicos de planta externa y de planta interna trabajan por zona, así que **deben tener un
área operativa**: GIO no deja guardarlos sin ella y la consola de **Usuarios** avisa de los que aún
no la tienen. Las áreas son Puebla, Pachuca, Veracruz, Poza Rica, Jalapa, Tlaxcala, Córdoba,
Coatzacoalcos y Quintana Roo. Subgerencia y Gerencia pueden quedar sin área.

Para no asignarlas una por una, GIO deduce el área de cada técnico de los folios que atiende: la
más frecuente entre los folios en que es técnico (planta externa) o evaluador (planta interna).

```bash
# Muestra la propuesta sin guardar nada
python manage.py asignar_areas
# Guarda el área de los técnicos que no la tienen
python manage.py asignar_areas --confirmar
# Revisa también a los que ya tienen área y la cambia si la mayoría de sus folios es de otra
python manage.py asignar_areas --recalcular --confirmar
```

Además, **cada ingesta del reporte de SISA** asigna el área a los técnicos que aún no la tienen, con
los folios ya actualizados, y lo anota en `sisa.log`. La ingesta nunca cambia un área ya asignada:
eso solo lo hace `--recalcular` o la edición en **Usuarios**. Quien no tiene folios en un área
reconocida queda sin área y el comando lo lista para asignarla a mano.

Al **dar de baja** a un usuario, además de quitarle el acceso, GIO lo pasa al área **Baja**: deja de
aparecer en su zona, en las listas de técnicos, en el reparto y en el desempeño, y en **Usuarios**
queda al final de la lista. Sus folios históricos se conservan. Para reactivar a un técnico hay que
elegir el área en la que trabajará.

## Contraseña y correo de recuperación

Gerencia da de alta a cada usuario con una contraseña inicial. Después, cada quien entra a **Mi
cuenta** (el ícono de persona en la barra superior) para cambiar su contraseña y registrar su
**correo de recuperación**; ambos cambios piden la contraseña actual. Mientras no haya correo, el
ícono muestra un punto de aviso.

Si alguien olvida su contraseña, en el inicio de sesión usa **¿Olvidó su contraseña?** y escribe su
expediente. GIO envía a su correo de recuperación un enlace que sirve una sola vez y vence en
`GIO_RECUPERACION_MINUTOS` (60 por omisión); también deja de servir si la persona vuelve a entrar con
su contraseña anterior. La respuesta en pantalla es la misma exista o no el expediente, para no
revelar quién tiene cuenta, y las solicitudes se limitan con `GIO_THROTTLE_RECUPERACION`. Quien no
registró correo pide el cambio a Gerencia, que puede asignarle una contraseña nueva en **Usuarios**.

El envío usa el servidor de correo (SMTP) definido en `GIO_EMAIL_HOST`, `GIO_EMAIL_PORT`,
`GIO_EMAIL_USUARIO`, `GIO_EMAIL_PASSWORD` y `GIO_EMAIL_REMITENTE`; sin `GIO_EMAIL_HOST` el correo
solo se imprime en la consola del servidor. El enlace se arma con `GIO_URL_PUBLICA`, la dirección
con la que los técnicos abren GIO (por ejemplo `https://gio.empresa.com.mx`).

## Ciclo de vida del folio

```
PENDIENTE ⇄ ASIGNADO ⇄ EN_PROCESO → LIQUIDADO
                            ↑____________|   (cancelar liquidación → PENDIENTE)
```

Transiciones fuera de este grafo se rechazan con `400`. Pasar a `ASIGNADO` o `EN_PROCESO` exige
técnico asignado; liquidar exige diagnóstico final; la evidencia fotográfica es opcional. Al
liquidar se sella `fecha_cierre` y se calcula el MTTR en horas y fracciones; al reabrir se limpia el
cierre y el folio vuelve a quedar pendiente de exportación.

Gerencia (`ADMIN`) puede liquidar un folio desde cualquier estatus, sin pasar por `EN_PROCESO` ni
tener técnico asignado, y le basta el diagnóstico final o la descripción de liquidación. Además, si
al editar un folio escribe o cambia la descripción de liquidación y no elige otro estatus, el folio
se liquida al guardar; la bitácora lo registra así. Una descripción que ya traía el folio (por
ejemplo, de la ingesta SISA) no lo liquida por sí sola.

Un folio liquidado queda bloqueado: solo Gerencia puede modificarlo. El técnico de planta externa
asignado puede cancelar su propia liquidación únicamente el mismo día y dentro de la hora posterior
al cierre (`POST /api/incidentes/{id}/cancelar-liquidacion/`); la cancelación devuelve el folio a
`PENDIENTE`. Gerencia puede cancelar en cualquier momento. Los técnicos de planta interna solo
pueden iniciar otro folio.

Cada cambio de estatus, asignación, liquidación y carga de evidencia queda en
`BitacoraIncidente`, que es de solo lectura en el admin y en la API.

## Reporte de folios

Subgerencia y Gerencia descargan desde el tablero con el botón **Exportar**, en Excel (`.xlsx`) o CSV
(`GET /api/incidentes/exportar/?formato=xlsx|csv`). El reporte incluye **todos** los folios que
coinciden con los filtros, la búsqueda y el orden activos, no solo la página visible, hasta
50 000 folios por descarga. El Excel trae encabezado fijo, autofiltro, fechas como fecha y MTTR como
número. Los textos que una hoja de cálculo ejecutaría como fórmula (empiezan con `=`, `+`, `-` o
`@`) se guardan como texto en Excel y con un apóstrofo inicial en CSV.

## Intercambio con SISA

Los reportes clasificados no se cargan por la interfaz web: se depositan en carpetas del servidor y
se procesan en segundo plano. La carpeta `private_data/` puede compartirse en la red para que la
computadora de SISA deje ahí el reporte; los pasos están en
[`docs/carpeta-compartida-sisa.md`](docs/carpeta-compartida-sisa.md).

```bash
# Ingesta: private_data/sisa_imports/*.csv|xlsx|xls -> folios PENDIENTE
python manage.py ingesta_sisa --dry-run
python manage.py ingesta_sisa

# Alta revisada de técnicos que aparecen en el reporte pero no existen en GIO
python manage.py importar_tecnicos
python manage.py importar_tecnicos --confirmar
```

El retorno hacia SISA (`exportar_sisa` y los archivos `RETORNO_SISA_*.csv`) está **retirado por
ahora** y se retomará más adelante. Los campos del folio que llevaban ese control
(`exportado_sisa`, `estado_sincronizacion`) se conservan en la base de datos para entonces, pero ya
no se muestran ni se usan.

La ingesta nunca borra registros ni crea usuarios por su cuenta: inserta folios nuevos, refresca
solo los campos de origen SISA de los ya existentes (sin tocar estatus ni asignaciones), reporta los
técnicos que no pudo enlazar y archiva el archivo leído en `procesados/`.
El técnico se enlaza por
`TÉCNICO ASIGNADO` y, si el nombre no coincide, por `TELÉFONO TECNICO`; cuando el técnico aún no
tiene teléfono en GIO se le guarda el del reporte (nunca se sobrescribe uno existente).
La columna `OQU` es el técnico de planta interna:
se asigna a los folios nuevos y a los existentes que aún no tienen uno (nunca reemplaza al
asignado). `importar_tecnicos` da de alta a los técnicos de planta externa con su teléfono y a los
de `OQU` con rol de planta interna (expediente `OQU-…`). Omite las cuentas de operadora que SISA
pone en `OQU` (por ejemplo, `CASPUE OPERADORA INTERNET`), porque no son personas; esos folios
quedan sin técnico de planta interna para el reparto por turnos. Con `--excluir TEXTO` se omiten
otros nombres. Cada alta toma como área la más frecuente de sus folios en el reporte; `--area` fija
la misma para todas. Si el reporte no trae un área reconocida, el comando lo avisa y hay que
asignarla después en **Usuarios**. El área operativa es la
columna `ÁREA` (p. ej. JALAPA); XALAPA es una COPE/central dentro de ella. En un folio que ya está
liquidado en GIO, la ingesta no reemplaza la clave ni la descripción de liquidación, los códigos
COD4/CARLS/COD5 ni el estado del enlace; y si el reporte no trae la columna `ESTATUS I/O`, no borra
el estado del enlace que ya se había registrado.

Como la carpeta puede ser de red, la ingesta solo lee reportes que llevan
`GIO_SISA_ESPERA_SEGUNDOS` (60 por omisión) sin modificarse, ignora los `~$…` que Excel crea
mientras un libro está abierto, lee también los `.xls` que en realidad son tablas HTML y, si no
puede mover un archivo a `procesados/`, lo vuelve a leer en la siguiente corrida sin duplicar
folios. Las rutas relativas de `GIO_PRIVATE_DATA_DIR` se toman desde
`backend/`; `GIO_SISA_IMPORTS_DIR` permite apuntar la entrada
a otra carpeta, incluso de otra computadora (`\\PC-SISA\GIO_Reportes`). Si la otra computadora
deja el reporte en su propia carpeta compartida, `GIO_SISA_ORIGEN` apunta a ese archivo o carpeta:
la ingesta copia a `sisa_imports` solo lo que cambió desde la última vez y no toca el original.

Programación sugerida en el servidor: `backend\scripts\sincronizar_sisa.bat` cada 15 minutos en el
Programador de tareas de Windows (ejecuta la ingesta y deja el resultado en
`backend\logs\sisa.log`). Con cron:

```
*/15 * * * *  python manage.py ingesta_sisa
```

### Empezar de cero

Para quitar los folios de prueba antes de operar con datos reales:

```bash
python manage.py borrar_folios
```

El comando muestra cuántos folios, evidencias, mensajes y registros de bitácora se borrarán, avisa si
quedaron archivos `RETORNO_SISA` en `sisa_exports/`, y
pide escribir `BORRAR` para continuar. Antes de borrar guarda un respaldo en
`backend/respaldos/folios_<fecha>/` (`folios.json` y las fotos), que no se sube al repositorio y se
recupera con `python manage.py loaddata`. No toca usuarios ni turnos. Un folio que llegue por la
ingesta mientras se ejecuta se conserva.

## Evidencia fotográfica

El cliente intercepta la cámara, reescala con la API Canvas y reduce la calidad de forma iterativa
hasta que el *payload* queda por debajo de **500 KB** antes de emitir el `POST`. El servidor valida
de nuevo el peso (`GIO_EVIDENCIA_MAX_BYTES`, 1 MB por omisión) y el formato con Pillow, y limita el
número de evidencias por folio. Cuando el navegador lo permite se adjuntan las coordenadas GPS de
la captura.

## Chat del folio

Cada folio tiene su propio chat para que planta externa y planta interna se coordinen sin salir de
GIO; la conversación queda guardada en el folio junto con sus datos, evidencias y bitácora. Puede
escribir quien puede ver el folio: el técnico de planta externa asignado, cualquier técnico de
planta interna (`evaluador`) y Subgerencia o Gerencia. Si el folio se reasigna, el nuevo técnico ve el
historial completo. Se admite conversar aunque el folio esté liquidado, porque el chat no modifica
el folio. Los mensajes no se editan ni se borran y Gerencia los consulta en el admin.

Además de texto se pueden enviar fotos, de la cámara o de la galería, con un comentario opcional.
Se comprimen en el teléfono igual que las evidencias y el servidor valida el mismo peso y formato.
Las fotos del chat se guardan en `media/chat/` y no cuentan como evidencia del folio, así que
planta interna también puede enviarlas (por ejemplo, una captura de gestión).

En la barra superior, el ícono de mensajes muestra cuántos hay sin leer y lleva al chat de cada
folio; las tarjetas del tablero y de la vista de campo también lo indican. El técnico y el
evaluador reciben avisos de todos sus folios y de los chats en que ya escribieron; Subgerencia y
Gerencia, solo de los chats en que ya escribieron. Un mensaje cuenta como leído cuando se abre el
chat de ese folio.

**Los mensajes de Gerencia son prioritarios.** Avisan a todos los que atienden el folio y también
a Subgerencia, aunque no haya escrito en ese chat. En la bandeja van primero y marcados en rojo, su
alerta es distinta y dura más, y dentro del chat se distinguen del resto.

**Apoyo cuando el técnico de planta interna descansa.** Cualquier técnico de planta interna puede
abrir el chat de un folio que no es suyo, leerlo y responder; el folio se le muestra de solo
lectura y, si hace falta modificarlo, Subgerencia se lo reasigna. Quien **está de turno** recibe
además los avisos de los folios abiertos de su zona cuyo técnico de planta interna no tiene turno
ese día (o que no tienen ninguno), así un mensaje no se queda sin leer hasta que regrese. Esto
depende de la programación de **Turnos**: sin turnos programados nadie recibe avisos de folios
ajenos. Estos avisos y los de Gerencia para Subgerencia solo cuentan mensajes de los últimos tres
días, para no anunciar conversaciones antiguas.

Cuando llega un mensaje aparece una alerta en la esquina con el folio, quién escribe y el texto; al
tocarla se abre ese chat. En teléfonos Android además vibra, y el título de la pestaña muestra los
mensajes sin leer, por ejemplo `(2) GIO`, aunque se esté en otra pestaña. La alerta nunca reemplaza
un diálogo abierto: espera a que se cierre. Los avisos se revisan cada 15 s y el chat abierto cada
5 s. Solo funcionan con GIO abierto: no hay notificaciones del sistema con la aplicación cerrada.

## API

| Método | Ruta | Descripción |
| --- | --- | --- |
| `POST` | `/api/auth/login/` | Tokens JWT + perfil y permisos del usuario |
| `POST` | `/api/auth/refresh/` | Renovación del token de acceso |
| `GET` | `/api/auth/me/` | Perfil del usuario autenticado |
| `POST` | `/api/auth/password/` | Cambio de contraseña propia |
| `POST` | `/api/auth/correo/` | Registro del correo de recuperación propio (pide la contraseña actual) |
| `POST` | `/api/auth/recuperar/` | Envía el enlace de recuperación al correo del expediente (sin sesión) |
| `POST` | `/api/auth/restablecer/` | Nueva contraseña con el enlace del correo (sin sesión) |
| `GET/POST` | `/api/usuarios/` | Gestión de usuarios (solo `ADMIN`) |
| `GET/POST` | `/api/incidentes/` | Listado filtrado y paginado / alta de folio |
| `GET/PATCH` | `/api/incidentes/{id}/` | Detalle y actualización según rol |
| `POST` | `/api/incidentes/{id}/liquidar/` | Liquidación con diagnóstico (evidencia opcional) |
| `GET/POST` | `/api/incidentes/{id}/evidencias/` | Consulta y carga de fotografías |
| `GET` | `/api/incidentes/{id}/bitacora/` | Auditoría del folio |
| `GET/POST` | `/api/incidentes/{id}/mensajes/` | Chat del folio (texto y foto opcional); `?despues=<id>` trae solo los nuevos |
| `GET` | `/api/incidentes/mensajes-pendientes/` | Mensajes sin leer por folio para quien consulta |
| `POST` | `/api/incidentes/asignar-masivo/` | Reasignación por lote (`PI_SUB`, `ADMIN`) |
| `GET` | `/api/incidentes/metricas/` | MTTR, dilación y carga por área y técnico |
| `GET` | `/api/incidentes/metricas/detalle/?indicador=` | Detalle de un indicador (`mttr`, `liquidacion`, `dilacion`, `criticos`, `sin_tecnico`): resumen, desgloses por área y folios |
| `GET` | `/api/catalogos/` | Estatus, códigos de fallo, roles, áreas y límites |

Las métricas se calculan sobre el universo completo que el rol puede ver y respetan los filtros
activos, de modo que los indicadores no dependen de la página en pantalla.

En **Métricas**, cada indicador (MTTR, tasa de liquidación, dilación, folios críticos y sin técnico)
se abre al presionarlo y muestra su detalle con los mismos filtros: un resumen con varios datos, el
desglose por área y los folios que lo explican (hasta 50), que llevan al folio en el tablero.

En el tablero, el indicador **Dilación mayor** muestra los días del folio abierto con más dilación,
no la cantidad de folios; esa cantidad y los críticos aparecen debajo, y al presionarlo se abre el
mismo detalle de dilación.

El **Desempeño de campo** se consulta por ocho áreas: Puebla, Coatzacoalcos, Poza Rica, Tlaxcala,
Pachuca, Quintana Roo, Córdoba y Veracruz.

## Pruebas

```bash
cd backend
python manage.py test
```

## Configuración

Todas las credenciales y rutas se leen del entorno (`backend/.env`); véase `backend/.env.example`.
Con `GIO_DEBUG=0` la aplicación exige `GIO_SECRET_KEY` y activa HSTS, redirección HTTPS y cookies
seguras.
