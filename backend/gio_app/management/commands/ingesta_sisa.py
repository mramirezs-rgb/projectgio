import json
import logging
import os
import shutil
import time
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q, Value
from django.db.models.functions import Concat
from django.utils import timezone

from gio_app.models import BitacoraIncidente, Incidente

from ._sisa import (
    a_fecha,
    entero,
    es_cuenta_generica,
    folio_valido,
    leer_tabla,
    limpiar_central,
    limpiar_folio,
    normalizar_telefono,
    primer_valor,
)

UsuarioGIO = get_user_model()
log = logging.getLogger('gio.ingesta')

EXTENSIONES = ('*.csv', '*.xlsx', '*.xls')

ESTADOS_ENLACE = {
    'UP': Incidente.EstadoEnlace.UP,
    'DOWN': Incidente.EstadoEnlace.DOWN,
    'OK': Incidente.EstadoEnlace.UP,
    'FALLA': Incidente.EstadoEnlace.DOWN,
}

CAMPOS_SISA = (
    'incidente', 'referencia', 'empresa', 'tipo_servicio', 'area_operativa', 'central',
    'cope', 'ctro_trabajo', 'oqu', 'dir_pta_a', 'punta_a', 'ips', 'dslam', 'red_secundaria',
    'desc_f1', 'desc_cod4', 'desc_carls', 'desc_cod5', 'cve_liq', 'desc_liq', 'leyenda_sisa',
    'observaciones_sisa', 'obs_usuario', 'descripcion', 'telefono_tecnico',
    'estado_enlace', 'fecha_ingreso',
)

# Una vez liquidado en GIO, la liquidación del técnico manda: el reporte SISA puede seguir trayendo
# el folio con datos anteriores hasta que procese el archivo de retorno.
CAMPOS_DE_LIQUIDACION = ('estado_enlace', 'cve_liq', 'desc_liq', 'desc_cod4', 'desc_carls',
                         'desc_cod5')


# Qué versión de cada reporte de la carpeta compartida ya se copió (fecha de modificación y tamaño).
ESTADO_DEL_ORIGEN = '.origen_sisa.json'


def es_archivo_temporal(ruta):
    """Excel deja un `~$nombre.xlsx` mientras alguien tiene abierto el libro; no es un reporte."""
    return ruta.name.startswith(('~$', '.'))


class Command(BaseCommand):
    help = ('Ingesta los reportes de averías exportados por SISA desde la carpeta aislada '
            'private_data/sisa_imports/ y los inserta como folios PENDIENTE.')

    def add_arguments(self, parser):
        parser.add_argument('--archivo', help='Procesa únicamente la ruta indicada.')
        parser.add_argument('--carpeta', help='Carpeta de ingesta alterna.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Analiza los archivos sin escribir en la base de datos.')
        parser.add_argument('--sin-mover', action='store_true',
                            help='No mueve los archivos procesados a la subcarpeta procesados/.')
        parser.add_argument('--no-actualizar', action='store_true',
                            help='Solo inserta folios nuevos; no refresca los datos SISA existentes.')
        parser.add_argument('--espera', type=int, default=None, metavar='SEGUNDOS',
                            help='Omite los archivos modificados hace menos de estos segundos, que '
                                 'pueden estar copiándose (por omisión GIO_SISA_ESPERA_SEGUNDOS).')
        parser.add_argument('--origen', metavar='RUTA',
                            help='Reporte o carpeta en la red de donde se copian los reportes nuevos '
                                 '(por omisión GIO_SISA_ORIGEN).')

    def handle(self, *args, **opciones):
        self.dry_run = opciones['dry_run']
        self.actualizar = not opciones['no_actualizar']

        if opciones['archivo']:
            rutas = [Path(opciones['archivo'])]
            if not rutas[0].exists():
                raise CommandError(f'No existe el archivo {rutas[0]}')
            carpeta = rutas[0].parent
        else:
            carpeta = Path(opciones['carpeta']) if opciones['carpeta'] else settings.SISA_IMPORTS_DIR
            espera = max(settings.SISA_ESPERA_SEGUNDOS if opciones['espera'] is None
                         else opciones['espera'], 0)
            origen = opciones['origen'] or settings.SISA_ORIGEN
            try:
                carpeta.mkdir(parents=True, exist_ok=True)
                if origen:
                    self._traer_del_origen(Path(origen), carpeta, espera)
                rutas = self._listos_para_leer(carpeta, espera)
            except OSError as error:
                raise CommandError(
                    f'No se puede abrir la carpeta {carpeta}: {error}. Si es una carpeta de red, '
                    'revise que la computadora que la comparte esté encendida y que la cuenta que '
                    'ejecuta esta tarea tenga permiso.') from error

        if not rutas:
            self.stdout.write(self.style.WARNING(f'Sin archivos pendientes en {carpeta}'))
            return

        self._cache_tecnicos = None
        self._cache_evaluadores = None
        totales = {'archivos': 0, 'nuevos': 0, 'actualizados': 0, 'omitidos': 0, 'errores': 0}

        for ruta in rutas:
            self.stdout.write(f'Procesando {ruta.name} ...')
            try:
                resultado = self._procesar_archivo(ruta)
            except Exception as error:
                totales['errores'] += 1
                log.exception('Fallo en la ingesta de %s', ruta.name)
                self.stderr.write(self.style.ERROR(f'  {ruta.name}: {error}'))
                continue

            totales['archivos'] += 1
            for clave in ('nuevos', 'actualizados', 'omitidos'):
                totales[clave] += resultado[clave]
            self.stdout.write(
                f"  nuevos={resultado['nuevos']} actualizados={resultado['actualizados']} "
                f"omitidos={resultado['omitidos']}"
            )

            if not self.dry_run and not opciones['sin_mover'] and not opciones['archivo']:
                try:
                    self._archivar(ruta)
                except OSError as error:
                    # Lo leído ya quedó guardado; si se vuelve a leer, solo refresca los folios.
                    log.warning('No se pudo archivar %s: %s', ruta.name, error)
                    self.stdout.write(self.style.WARNING(
                        f'  no se pudo archivar {ruta.name} ({error}); se volverá a leer en la '
                        'siguiente corrida sin duplicar folios.'))

        resumen = (f"Ingesta finalizada: {totales['archivos']} archivo(s), "
                   f"{totales['nuevos']} folio(s) nuevo(s), "
                   f"{totales['actualizados']} actualizado(s), "
                   f"{totales['omitidos']} omitido(s), {totales['errores']} con error.")
        estilo = self.style.WARNING if self.dry_run else self.style.SUCCESS
        self.stdout.write(estilo(('[DRY-RUN] ' if self.dry_run else '') + resumen))

    def _traer_del_origen(self, origen, carpeta, espera):
        """Copia a la carpeta de ingesta los reportes de la carpeta compartida que cambiaron desde
        la última vez. El original se queda donde está: esa computadora lo sigue usando."""
        try:
            if origen.is_dir():
                candidatos = sorted(r for patron in EXTENSIONES for r in origen.glob(patron)
                                    if r.is_file() and not es_archivo_temporal(r))
            else:
                candidatos = [origen]
            versiones = {ruta: [ruta.stat().st_mtime, ruta.stat().st_size] for ruta in candidatos}
        except OSError as error:
            # Si la otra computadora está apagada se procesa lo que ya haya en la carpeta local.
            log.warning('No se pudo leer el origen %s: %s', origen, error)
            self.stdout.write(self.style.WARNING(
                f'No se pudo leer la carpeta compartida {origen} ({error}). Revise que la otra '
                'computadora esté encendida; se reintentará en la siguiente corrida.'))
            return

        ruta_estado = carpeta / ESTADO_DEL_ORIGEN
        try:
            copiados = json.loads(ruta_estado.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            copiados = {}
        limite = time.time() - espera

        for ruta, version in versiones.items():
            if copiados.get(str(ruta)) == version:
                continue
            if version[0] > limite:
                self.stdout.write(f'{ruta.name} se está actualizando en la carpeta compartida; '
                                  'se copiará en la siguiente corrida.')
                continue
            destino = carpeta / ruta.name
            temporal = destino.with_name(destino.name + '.copiando')
            try:
                # copy2 conserva la fecha de modificación, así que la copia se lee en esta corrida.
                shutil.copy2(ruta, temporal)
                os.replace(temporal, destino)
            except OSError as error:
                temporal.unlink(missing_ok=True)
                self.stdout.write(self.style.WARNING(f'No se pudo copiar {ruta}: {error}'))
                continue
            self.stdout.write(f'Copiado de la carpeta compartida: {ruta}')
            # En una prueba (--dry-run) no se da por leído: la siguiente corrida lo vuelve a copiar.
            if not self.dry_run:
                copiados[str(ruta)] = version

        if not self.dry_run:
            ruta_estado.write_text(json.dumps(copiados, indent=1), encoding='utf-8')

    def _listos_para_leer(self, carpeta, espera):
        """Reportes de la carpeta, sin temporales de Excel ni archivos que aún se están copiando."""
        limite = time.time() - espera
        rutas = []
        for ruta in sorted(r for patron in EXTENSIONES for r in carpeta.glob(patron)):
            if es_archivo_temporal(ruta):
                continue
            try:
                modificado = ruta.stat().st_mtime if ruta.is_file() else None
            except OSError:
                # La otra computadora lo movió o lo borró mientras se revisaba la carpeta.
                continue
            if modificado is None:
                continue
            if modificado > limite:
                self.stdout.write(f'{ruta.name} se sigue copiando o se acaba de modificar; '
                                  'se leerá en la siguiente corrida.')
                continue
            rutas.append(ruta)
        return rutas

    def _archivar(self, ruta):
        destino_dir = settings.SISA_IMPORTS_PROCESADOS_DIR
        destino_dir.mkdir(parents=True, exist_ok=True)
        marca = timezone.localtime().strftime('%Y%m%d_%H%M%S')
        destino = destino_dir / f'{ruta.stem}_{marca}{ruta.suffix}'
        # Un reporte de la carpeta compartida llega siempre con el mismo nombre: no se pisa el anterior.
        consecutivo = 1
        while destino.exists():
            consecutivo += 1
            destino = destino_dir / f'{ruta.stem}_{marca}_{consecutivo}{ruta.suffix}'
        shutil.move(str(ruta), str(destino))
        self.stdout.write(f'  archivado en {destino}')

    def _tecnicos(self):
        if self._cache_tecnicos is None:
            self._cache_tecnicos = {}
            self._cache_telefonos = {}
            consulta = UsuarioGIO.objects.filter(
                rol=UsuarioGIO.Rol.TECNICO, is_active=True
            ).annotate(
                completo=Concat('first_name', Value(' '), 'last_name'),
            )
            for usuario in consulta:
                for clave in {usuario.expediente.upper(),
                              usuario.username.upper(),
                              ' '.join(usuario.completo.split()).upper()}:
                    if clave:
                        self._cache_tecnicos.setdefault(clave, usuario)
                telefono = normalizar_telefono(usuario.telefono)
                if telefono:
                    self._cache_telefonos.setdefault(telefono, usuario)
        return self._cache_tecnicos

    def _resolver_tecnico(self, nombre, telefono):
        """Vincula al técnico por nombre (o expediente) y, si no coincide, por su teléfono."""
        clave = ' '.join(nombre.split()).upper() if nombre else ''
        if clave:
            usuario = self._tecnicos().get(clave)
            if usuario:
                return usuario, ''
            usuario = UsuarioGIO.objects.filter(
                Q(expediente__iexact=clave) | Q(username__iexact=clave),
                rol=UsuarioGIO.Rol.TECNICO,
            ).first()
            if usuario:
                return usuario, ''
        if telefono:
            self._tecnicos()
            usuario = self._cache_telefonos.get(telefono)
            if usuario:
                return usuario, ''
        return None, clave

    def _evaluadores(self):
        if self._cache_evaluadores is None:
            self._cache_evaluadores = {}
            consulta = UsuarioGIO.objects.filter(
                rol=UsuarioGIO.Rol.PI_EVALUADOR, is_active=True
            ).annotate(
                completo=Concat('first_name', Value(' '), 'last_name'),
            )
            for usuario in consulta:
                for clave in {usuario.expediente.upper(),
                              usuario.username.upper(),
                              ' '.join(usuario.completo.split()).upper()}:
                    if clave:
                        self._cache_evaluadores.setdefault(clave, usuario)
        return self._cache_evaluadores

    def _resolver_evaluador(self, nombre):
        """La columna OQU trae al técnico de planta interna responsable del folio."""
        clave = ' '.join(nombre.split()).upper() if nombre else ''
        # Las cuentas de operadora no son personas: el folio queda para el reparto por turnos.
        if not clave or es_cuenta_generica(clave):
            return None, ''
        usuario = self._evaluadores().get(clave)
        return (usuario, '') if usuario else (None, clave)

    def _vincular_telefono(self, tecnico, telefono):
        """Guarda en el usuario el teléfono que trae el reporte si aún no tiene uno."""
        if not telefono or tecnico.telefono:
            return False
        tecnico.telefono = telefono
        tecnico.save(update_fields=['telefono'])
        self._cache_telefonos.setdefault(telefono, tecnico)
        return True

    def _procesar_archivo(self, ruta):
        marco = leer_tabla(ruta)
        nuevos = actualizados = omitidos = 0
        sin_enlazar = set()
        oqu_sin_enlazar = set()
        telefonos_vinculados = set()

        with transaction.atomic():
            for _, cruda in marco.iterrows():
                fila = {str(k): v for k, v in cruda.items()}
                folio = limpiar_folio(primer_valor(fila, ['FOLIO', 'FOLIO SISA', 'NO FOLIO']))
                if not folio_valido(folio):
                    omitidos += 1
                    continue

                datos = self._mapear(fila)
                tecnico_nombre = primer_valor(
                    fila, ['TECNICO ASIGNADO', 'TECNICO', 'RESPONSABLE', 'PROVEEDOR'])
                telefono = normalizar_telefono(datos.get('telefono_tecnico'))
                tecnico, no_enlazado = self._resolver_tecnico(tecnico_nombre, telefono)
                if no_enlazado:
                    sin_enlazar.add(no_enlazado)
                if tecnico:
                    if self._vincular_telefono(tecnico, telefono):
                        telefonos_vinculados.add(tecnico.expediente)
                    if not datos.get('telefono_tecnico') and tecnico.telefono:
                        datos['telefono_tecnico'] = tecnico.telefono
                evaluador, oqu_no_enlazado = self._resolver_evaluador(datos.get('oqu'))
                if oqu_no_enlazado:
                    oqu_sin_enlazar.add(oqu_no_enlazado)

                existente = Incidente.objects.filter(folio=folio).first()

                if existente:
                    if not self.actualizar:
                        omitidos += 1
                        continue
                    cambios = []
                    liquidado = existente.estatus == Incidente.Estatus.LIQUIDADO
                    for campo in CAMPOS_SISA:
                        if liquidado and campo in CAMPOS_DE_LIQUIDACION:
                            continue
                        valor = datos.get(campo)
                        if valor in (None, ''):
                            continue
                        if getattr(existente, campo) != valor:
                            setattr(existente, campo, valor)
                            cambios.append(campo)
                    # Solo se completa el técnico de planta interna si el folio no tiene uno.
                    if evaluador and existente.evaluador_id is None:
                        existente.evaluador = evaluador
                        cambios.append('evaluador')
                    if not cambios:
                        omitidos += 1
                        continue
                    if not self.dry_run:
                        existente.origen_sisa = ruta.name
                        existente.save()
                        BitacoraIncidente.registrar(
                            existente, None, BitacoraIncidente.Accion.INGESTA,
                            detalle=f'{ruta.name}: {", ".join(sorted(cambios))}',
                        )
                    actualizados += 1
                    continue

                estatus = (Incidente.Estatus.ASIGNADO if tecnico
                           else Incidente.Estatus.PENDIENTE)
                ahora = timezone.now()
                apertura = datos.get('fecha_ingreso') or ahora
                if apertura > ahora:
                    apertura = ahora
                if self.dry_run:
                    nuevos += 1
                    continue

                incidente = Incidente(
                    folio=folio,
                    estatus=estatus,
                    fecha_apertura=apertura,
                    tecnico=tecnico,
                    evaluador=evaluador,
                    origen_sisa=ruta.name,
                    **{campo: datos.get(campo) or '' for campo in CAMPOS_SISA
                       if campo != 'fecha_ingreso'},
                )
                incidente.fecha_ingreso = datos.get('fecha_ingreso')
                incidente.estado_enlace = (datos.get('estado_enlace')
                                           or Incidente.EstadoEnlace.DESCONOCIDO)
                incidente.save()
                BitacoraIncidente.registrar(
                    incidente, None, BitacoraIncidente.Accion.INGESTA,
                    detalle=f'Alta automática desde {ruta.name}',
                )
                nuevos += 1

            if self.dry_run:
                transaction.set_rollback(True)

        if sin_enlazar:
            muestra = ', '.join(sorted(sin_enlazar)[:8])
            self.stdout.write(self.style.WARNING(
                f'  {len(sin_enlazar)} técnico(s) del archivo sin usuario GIO: {muestra}'
            ))
        if oqu_sin_enlazar:
            muestra = ', '.join(sorted(oqu_sin_enlazar)[:8])
            self.stdout.write(self.style.WARNING(
                f'  {len(oqu_sin_enlazar)} técnico(s) de planta interna (OQU) sin usuario GIO: '
                f'{muestra}'
            ))
        if telefonos_vinculados:
            self.stdout.write(
                f'  teléfono vinculado a {len(telefonos_vinculados)} técnico(s): '
                f'{", ".join(sorted(telefonos_vinculados))}'
            )
        return {'nuevos': nuevos, 'actualizados': actualizados, 'omitidos': omitidos}

    def _mapear(self, fila):
        enlace_crudo = primer_valor(fila, ['ESTATUS I/O', 'ESTATUS IO', 'ESTADO ENLACE']).upper()
        return {
            'incidente': primer_valor(fila, ['INCIDENTE'], 50),
            'referencia': primer_valor(fila, ['REFERENCIA'], 50),
            'empresa': primer_valor(fila, ['EMPRESA', 'CLIENTE'], 150),
            'tipo_servicio': primer_valor(fila, ['TIPO SERVICIO'], 50),
            'area_operativa': primer_valor(fila, ['AREA', 'AREA OPERATIVA', 'DIVISIONAL',
                                                  'REGION'], 100).upper(),
            'central': limpiar_central(primer_valor(fila, ['CENTRAL']))[:100],
            'cope': limpiar_central(primer_valor(fila, ['COPE']))[:100],
            'ctro_trabajo': primer_valor(fila, ['CTRO TRABAJO'], 100),
            'oqu': primer_valor(fila, ['OQU'], 100),
            'dir_pta_a': primer_valor(fila, ['DIR PTA A', 'DIRECCION']),
            'punta_a': primer_valor(fila, ['PUNTA A'], 100),
            'ips': primer_valor(fila, ['IPS', 'IP'], 50),
            'dslam': primer_valor(fila, ['DSLAM'], 100),
            'red_secundaria': primer_valor(fila, ['RED SECUNDARIA'], 100),
            'desc_f1': primer_valor(fila, ['DESC F1'], 255),
            'desc_cod4': primer_valor(fila, ['DESC COD4'], 255),
            'desc_carls': primer_valor(fila, ['DESC CARLS'], 255),
            'desc_cod5': primer_valor(fila, ['DESC COD5'], 255),
            'cve_liq': primer_valor(fila, ['CVE LIQ'], 50),
            'desc_liq': primer_valor(fila, ['DESC LIQ']),
            'leyenda_sisa': primer_valor(fila, ['LEYENDA SISA'], 100),
            'observaciones_sisa': primer_valor(fila, ['OBSERVACIONES SISA']),
            'obs_usuario': primer_valor(fila, ['OBS USUARIO', 'OBSERVACIONES USUARIO']),
            'descripcion': primer_valor(fila, ['SINTOMA', 'DESC F1', 'OBS USUARIO']),
            'telefono_tecnico': primer_valor(fila, ['TELEFONO TECNICO'], 20),
            # Vacío si el reporte no lo indica: así no borra el estado que ya registró GIO.
            'estado_enlace': ESTADOS_ENLACE.get(enlace_crudo, ''),
            'fecha_ingreso': a_fecha(primer_valor(fila, ['FECHA INGRESO', 'FECHA APERTURA',
                                                         'FECHA'])),
            'dilacion_sisa': entero(primer_valor(fila, ['DILACION DIAS', 'DILACION'])),
        }
