# Sistema GIO — Gestión de Incidencias y Enlace Operativo

Plataforma web desacoplada (*headless*) para el enlace operativo entre la Planta Interna (OQU) y la
Planta Externa del CASE Puebla: ingesta automatizada de averías SISA, tablero Kanban con semáforos
de dilación, módulo móvil de campo con compresión de evidencia en el cliente, cálculo de MTTR y
robot de retorno hacia los sistemas legados.

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
  sisa_exports/          Archivos RETORNO_SISA_*.csv generados
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
| `PI_EVALUADOR` | Solo donde es `evaluador` | Diagnóstico, datos de red y validación del trabajo de campo |
| `TECNICO` | Solo donde es `tecnico` | Liquidación y carga de evidencias de su propio folio |

El filtrado se aplica en el servidor (`get_queryset`), por lo que un técnico recibe `404` al pedir
un folio ajeno, y los campos editables se restringen por serializador según el rol.

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

Subgerencia y Gerencia descargan desde el tablero el botón **Exportar**, en Excel (`.xlsx`) o CSV
(`GET /api/incidentes/exportar/?formato=xlsx|csv`). El reporte incluye **todos** los folios que
coinciden con los filtros, la búsqueda y el orden activos, no solo la página visible, hasta
50 000 folios por descarga. El Excel trae encabezado fijo, autofiltro, fechas como fecha y MTTR como
número. Los textos que una hoja de cálculo ejecutaría como fórmula (empiezan con `=`, `+`, `-` o
`@`) se guardan como texto en Excel y con un apóstrofo inicial en CSV.

## Intercambio con SISA

Los reportes clasificados no se cargan por la interfaz web: se depositan en carpetas del servidor y
se procesan en segundo plano. La carpeta `private_data/` puede compartirse en la red para que la
computadora de SISA deje ahí el reporte y recoja el retorno; los pasos están en
[`docs/carpeta-compartida-sisa.md`](docs/carpeta-compartida-sisa.md).

```bash
# Ingesta: private_data/sisa_imports/*.csv|xlsx|xls -> folios PENDIENTE
python manage.py ingesta_sisa --dry-run
python manage.py ingesta_sisa

# Alta revisada de técnicos que aparecen en el reporte pero no existen en GIO
python manage.py importar_tecnicos
python manage.py importar_tecnicos --confirmar

# Retorno: folios LIQUIDADO sin exportar -> private_data/sisa_exports/RETORNO_SISA_*.csv
python manage.py exportar_sisa --dry-run
python manage.py exportar_sisa
```

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
otros nombres. `--area` se aplica a todas las altas; sin él, el usuario queda sin zona y en el
reparto puede recibir folios de cualquier área. El área operativa es la
columna `ÁREA` (p. ej. JALAPA); XALAPA es una COPE/central dentro de ella. En un folio que ya está
liquidado en GIO, la ingesta no reemplaza la clave ni la descripción de liquidación, los códigos
COD4/CARLS/COD5 ni el estado del enlace; y si el reporte no trae la columna `ESTATUS I/O`, no borra
el estado del enlace que ya se había registrado.

Como la carpeta puede ser de red, la ingesta solo lee reportes que llevan
`GIO_SISA_ESPERA_SEGUNDOS` (60 por omisión) sin modificarse, ignora los `~$…` que Excel crea
mientras un libro está abierto, lee también los `.xls` que en realidad son tablas HTML y, si no
puede mover un archivo a `procesados/`, lo vuelve a leer en la siguiente corrida sin duplicar
folios. La exportación marca `exportado_sisa = True` en la misma transacción en que escribe el
retorno: lo escribe con otro nombre y lo renombra completo, nunca reemplaza un retorno anterior y,
si falla, los folios siguen pendientes. Las rutas relativas de `GIO_PRIVATE_DATA_DIR` se toman desde
`backend/`; `GIO_SISA_IMPORTS_DIR` y `GIO_SISA_EXPORTS_DIR` permiten apuntar la entrada y el retorno
a otra carpeta, incluso de otra computadora (`\\PC-SISA\GIO_Reportes`).

Programación sugerida en el servidor: `backend\scripts\sincronizar_sisa.bat` cada 15 minutos en el
Programador de tareas de Windows (ejecuta la ingesta y el retorno y deja el resultado en
`backend\logs\sisa.log`). Con cron:

```
*/15 * * * *  python manage.py ingesta_sisa && python manage.py exportar_sisa
```

## Evidencia fotográfica

El cliente intercepta la cámara, reescala con la API Canvas y reduce la calidad de forma iterativa
hasta que el *payload* queda por debajo de **500 KB** antes de emitir el `POST`. El servidor valida
de nuevo el peso (`GIO_EVIDENCIA_MAX_BYTES`, 1 MB por omisión) y el formato con Pillow, y limita el
número de evidencias por folio. Cuando el navegador lo permite se adjuntan las coordenadas GPS de
la captura.

## Chat del folio

Cada folio tiene su propio chat para que planta externa y planta interna se coordinen sin salir de
GIO; la conversación queda guardada en el folio junto con sus datos, evidencias y bitácora. Puede
escribir quien puede ver el folio: el técnico de planta externa asignado, el técnico de planta
interna (`evaluador`) y Subgerencia o Gerencia. Si el folio se reasigna, el nuevo técnico ve el
historial completo. Se admite conversar aunque el folio esté liquidado, porque el chat no modifica
el folio. Los mensajes no se editan ni se borran y Gerencia los consulta en el admin.

Además de texto se pueden enviar fotos, de la cámara o de la galería, con un comentario opcional.
Se comprimen en el teléfono igual que las evidencias y el servidor valida el mismo peso y formato.
Las fotos del chat se guardan en `media/chat/` y no cuentan como evidencia del folio, así que
planta interna también puede enviarlas (por ejemplo, una captura de gestión).

En la barra superior, el ícono de mensajes muestra cuántos hay sin leer y lleva al chat de cada
folio; las tarjetas del tablero y de la vista de campo también lo indican. El técnico y el
evaluador reciben avisos de todos sus folios; Subgerencia y Gerencia, solo de los chats en que ya
escribieron. Un mensaje cuenta como leído cuando se abre el chat de ese folio.

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
| `GET` | `/api/catalogos/` | Estatus, códigos de fallo, roles, áreas y límites |

Las métricas se calculan sobre el universo completo que el rol puede ver y respetan los filtros
activos, de modo que los indicadores no dependen de la página en pantalla.

## Pruebas

```bash
cd backend
python manage.py test
```

## Configuración

Todas las credenciales y rutas se leen del entorno (`backend/.env`); véase `backend/.env.example`.
Con `GIO_DEBUG=0` la aplicación exige `GIO_SECRET_KEY` y activa HSTS, redirección HTTPS y cookies
seguras.
