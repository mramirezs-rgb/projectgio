# Intercambio de archivos SISA por la red

Guía para que el reporte de SISA llegue desde otra computadora al servidor GIO y para que el archivo
de retorno regrese a la misma carpeta, sin pasarlo a mano.

## Cómo funciona

Windows puede **compartir una carpeta** con las demás computadoras de la red local. La carpeta
compartida tiene una ruta de red con la forma `\\NOMBRE-DEL-EQUIPO\NombreDelRecurso`; quien tenga
un usuario con permiso la abre desde el Explorador como si fuera una carpeta propia. Es lo que ya
hacen hoy cuando "les pasan el archivo por la red".

La "carpeta secreta" de GIO es `private_data/`. No se sube a GitHub (está en `.gitignore`) y solo
la usa el servidor. Tiene tres subcarpetas:

| Carpeta | Quién escribe | Para qué |
| --- | --- | --- |
| `private_data\sisa_imports\` | La computadora de SISA | Deja aquí el reporte (`.xlsx`, `.xls` o `.csv`). |
| `private_data\sisa_imports\procesados\` | GIO | Guarda cada reporte ya leído, con fecha y hora. |
| `private_data\sisa_exports\` | GIO | Deja aquí `RETORNO_SISA_AAAAMMDD_HHMMSS.csv` con los folios liquidados. |

```
Computadora de SISA                         Servidor GIO
reporte.xlsx  ──── lo copia ────▶  private_data\sisa_imports\     ingesta_sisa (cada 15 min)
                                     └─ procesados\reporte_<fecha>.xlsx
RETORNO_SISA_*.csv ◀── lo toma ──  private_data\sisa_exports\     exportar_sisa (cada 15 min)
```

Cada 15 minutos el servidor ejecuta `backend\scripts\sincronizar_sisa.bat`, que lee los reportes
nuevos, da de alta o actualiza los folios, mueve el reporte a `procesados\` y genera el retorno con
los folios liquidados que aún no se habían enviado.

## Opción recomendada: el servidor GIO comparte `private_data`

Así los datos viven en el servidor, la tarea programada lee su propio disco (sin contraseñas de red)
y, si la otra computadora está apagada, GIO sigue funcionando y los archivos esperan en la carpeta.

En los pasos se usa `C:\GIO\projectgio` como ruta del proyecto y `SERVIDOR-GIO` como nombre del
servidor: cámbielos por los suyos. El nombre se ve con `hostname` y la IP con `ipconfig` (dirección
IPv4). Conviene reservar esa IP en el módem o router para que la ruta no cambie.

### 1. Crear las carpetas

En el servidor, dentro de `backend` y con el entorno virtual activo:

```bat
python manage.py inicializar_gio
```

### 2. Crear una cuenta solo para el intercambio

En el servidor, en PowerShell **como administrador**:

```powershell
New-LocalUser -Name "gio_sisa" -Password (Read-Host -AsSecureString "Contraseña") `
  -PasswordNeverExpires -UserMayNotChangePassword -Description "Intercambio de archivos SISA"
```

Use una contraseña larga. Esta cuenta solo sirve para abrir la carpeta; no puede entrar a GIO.

### 3. Compartir únicamente `private_data`

```powershell
$carpeta = "C:\GIO\projectgio\private_data"
New-SmbShare -Name 'GIO_SISA$' -Path $carpeta -ChangeAccess "$env:COMPUTERNAME\gio_sisa"
icacls $carpeta /grant "gio_sisa:(OI)(CI)M"
```

- El `$` al final del nombre oculta la carpeta al explorar la red. No es una contraseña: lo que la
  protege son los permisos.
- No comparta la carpeta del proyecto completa: ahí está `backend\.env` con la contraseña de la base
  de datos y la clave secreta.
- No dé permiso a "Todos" (*Everyone*).

### 4. Red privada y uso compartido activado

En el servidor:

1. **Configuración → Red e Internet → Ethernet (o Wi‑Fi)** → *Tipo de perfil de red*: **Privada**.
2. **Configuración → Red e Internet → Configuración de red avanzada → Configuración de uso
   compartido avanzado → Redes privadas** → activar **Uso compartido de archivos e impresoras**.
   En Windows 10 está en **Panel de control → Centro de redes y recursos compartidos → Cambiar
   configuración de uso compartido avanzado**.

### 5. En la computadora de SISA

1. En la barra de direcciones del Explorador escriba `\\SERVIDOR-GIO\GIO_SISA$` (o con la IP:
   `\\192.168.1.50\GIO_SISA$`).
2. Cuando pida credenciales: usuario `SERVIDOR-GIO\gio_sisa` y su contraseña. Marque **Recordar mis
   credenciales**.
3. Guarde o copie el reporte en `sisa_imports`. El nombre da igual y puede ser siempre el mismo: GIO
   lo mueve a `procesados` en cuanto lo lee.
4. Recoja el retorno en `sisa_exports`. Después de cargarlo en SISA, puede moverlo a una subcarpeta
   (por ejemplo `sisa_exports\cargados`) para saber cuáles ya se procesaron; GIO no lee esa carpeta.

Si en esa computadora un programa o script deja el reporte de forma automática, guarde antes las
credenciales para la cuenta que lo ejecuta:

```bat
cmdkey /add:SERVIDOR-GIO /user:SERVIDOR-GIO\gio_sisa /pass
copy /Y "C:\Reportes\reporte.xlsx" "\\SERVIDOR-GIO\GIO_SISA$\sisa_imports\"
```

### 6. Programar la sincronización en el servidor

Primero pruébela a mano: haga doble clic en `backend\scripts\sincronizar_sisa.bat` y revise
`backend\logs\sisa.log`.

Después créela en el Programador de tareas, en una consola **como administrador** (pedirá la
contraseña del usuario de Windows con el que instaló GIO):

```bat
schtasks /Create /TN "GIO\Sincronizar SISA" /SC MINUTE /MO 15 /RU "SERVIDOR-GIO\su_usuario" /RP * ^
  /TR "C:\GIO\projectgio\backend\scripts\sincronizar_sisa.bat"
```

En el Programador de tareas, revise en la tarea:

- **General**: *Ejecutar tanto si el usuario inició sesión como si no*.
- **Configuración**: *Si la tarea ya se está ejecutando: No iniciar una nueva instancia*.

## Otra opción: la computadora de SISA comparte su carpeta

### El reporte está en una carpeta compartida de la otra computadora

Si la otra computadora deja el reporte en su propia carpeta compartida y lo va actualizando, GIO lo
copia de ahí. En `backend\.env` ponga la ruta del archivo (o de la carpeta, si deja varios):

```ini
GIO_SISA_ORIGEN=\\PC-SISA\reportes\Reporte_Completo.xls
```

En cada corrida, `ingesta_sisa`:

1. Revisa si el reporte cambió desde la última vez (fecha de modificación y tamaño).
2. Si cambió, lo **copia** a `private_data\sisa_imports` y procesa esa copia; el original no se
   mueve ni se modifica, porque esa computadora lo sigue usando.
3. Si no cambió, no hace nada. Si la otra computadora lo está escribiendo en ese momento, espera a
   la siguiente corrida.

Con una carpeta en lugar de un archivo, toma sus `.xlsx`, `.xls` y `.csv` y omite los `~$…` de Excel.
Cada versión leída queda en `procesados`; las antiguas se pueden borrar cuando quiera.

- GIO solo necesita permiso de **lectura** en esa carpeta.
- Si la otra computadora está apagada, `sisa.log` dirá *No se pudo leer la carpeta compartida…* y
  GIO sigue con lo demás; lo reintenta en la siguiente corrida.

### Toda la entrada o el retorno en la otra computadora

GIO también puede usar directamente carpetas de la otra computadora. En `backend\.env`:

```ini
GIO_SISA_IMPORTS_DIR=\\PC-SISA\GIO_Reportes
GIO_SISA_EXPORTS_DIR=\\PC-SISA\GIO_Retorno
```

Aquí GIO mueve lo leído a `procesados` y escribe el retorno en esas carpetas, así que necesita
permiso de **modificar** en ambas. Se puede usar solo `GIO_SISA_EXPORTS_DIR` junto con
`GIO_SISA_ORIGEN` para que el retorno quede del lado de la computadora de SISA.

### En los dos casos

- Use siempre la ruta `\\...`, nunca una letra de unidad como `Z:`: las tareas programadas no ven
  las unidades de red asignadas.
- La cuenta de Windows que ejecuta la tarea debe tener guardada la credencial de la otra
  computadora. Inicie sesión con esa cuenta y guárdela una vez:
  `cmdkey /add:PC-SISA /user:PC-SISA\usuario /pass`.

## Lo que GIO cuida por su cuenta

- **Archivos a medio copiar**: solo lee un reporte que lleva al menos 60 s sin cambios
  (`GIO_SISA_ESPERA_SEGUNDOS`); si no, lo deja para la siguiente corrida.
- **Excel abierto**: ignora los archivos `~$reporte.xlsx` que Excel crea mientras alguien tiene el
  libro abierto.
- **Archivo bloqueado**: si no puede moverlo a `procesados` porque está abierto en otra
  computadora, lo vuelve a leer después sin duplicar folios.
- **Retorno completo o nada**: el CSV se escribe con otro nombre y se renombra ya terminado, así la
  otra computadora nunca toma uno a medias. Nunca reemplaza un retorno anterior y, si no puede
  escribirlo, los folios siguen pendientes para la siguiente corrida.
- **La liquidación manda**: si el reporte de SISA sigue trayendo un folio que ya se liquidó en GIO,
  no se reemplazan su clave, su descripción de liquidación ni el estado del enlace.
- **`.xls` que en realidad son páginas web**: muchos sistemas exportan así; GIO también los lee.

## Si algo no funciona

| Qué pasa | Causa probable | Qué hacer |
| --- | --- | --- |
| "No se encuentra la ruta de acceso de la red" | Servidor apagado, nombre mal escrito o uso compartido desactivado | Pruebe con la IP (`\\192.168.1.50\GIO_SISA$`) y revise el paso 4. |
| "Acceso denegado" | Faltan permisos | Repita el paso 3 y entre con `SERVIDOR-GIO\gio_sisa`. |
| El reporte se queda en `sisa_imports` y el log dice *se sigue copiando* | Se modificó hace menos de 60 s | Normal: se lee en la siguiente corrida. |
| El log dice *con error* y el reporte no se mueve | No es un reporte legible o no tiene columna FOLIO | Ábralo y revise; corrija y vuelva a dejarlo. |
| No aparece ningún `RETORNO_SISA` | No hay folios liquidados pendientes | Normal. Gerencia lo ve en el tablero, botón **Exportaciones SISA**. |
