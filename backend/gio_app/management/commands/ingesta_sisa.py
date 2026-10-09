import logging
import shutil
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
    folio_valido,
    leer_tabla,
    limpiar_central,
    limpiar_folio,
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
            carpeta.mkdir(parents=True, exist_ok=True)
            rutas = sorted(
                ruta for patron in EXTENSIONES for ruta in carpeta.glob(patron) if ruta.is_file()
            )

        if not rutas:
            self.stdout.write(self.style.WARNING(f'Sin archivos pendientes en {carpeta}'))
            return

        self._cache_tecnicos = None
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
                self._archivar(ruta)

        resumen = (f"Ingesta finalizada: {totales['archivos']} archivo(s), "
                   f"{totales['nuevos']} folio(s) nuevo(s), "
                   f"{totales['actualizados']} actualizado(s), "
                   f"{totales['omitidos']} omitido(s), {totales['errores']} con error.")
        estilo = self.style.WARNING if self.dry_run else self.style.SUCCESS
        self.stdout.write(estilo(('[DRY-RUN] ' if self.dry_run else '') + resumen))

    def _archivar(self, ruta):
        destino_dir = settings.SISA_IMPORTS_PROCESADOS_DIR
        destino_dir.mkdir(parents=True, exist_ok=True)
        marca = timezone.now().strftime('%Y%m%d_%H%M%S')
        destino = destino_dir / f'{ruta.stem}_{marca}{ruta.suffix}'
        shutil.move(str(ruta), str(destino))
        self.stdout.write(f'  archivado en {destino.relative_to(settings.PRIVATE_DATA_DIR)}')

    def _tecnicos(self):
        if self._cache_tecnicos is None:
            self._cache_tecnicos = {}
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
        return self._cache_tecnicos

    def _resolver_tecnico(self, nombre):
        if not nombre:
            return None, ''
        clave = ' '.join(nombre.split()).upper()
        usuario = self._tecnicos().get(clave)
        if usuario:
            return usuario, ''
        usuario = UsuarioGIO.objects.filter(
            Q(expediente__iexact=clave) | Q(username__iexact=clave),
            rol=UsuarioGIO.Rol.TECNICO,
        ).first()
        if usuario:
            return usuario, ''
        return None, clave

    def _procesar_archivo(self, ruta):
        marco = leer_tabla(ruta)
        nuevos = actualizados = omitidos = 0
        sin_enlazar = set()

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
                tecnico, no_enlazado = self._resolver_tecnico(tecnico_nombre)
                if no_enlazado:
                    sin_enlazar.add(no_enlazado)

                existente = Incidente.objects.filter(folio=folio).first()

                if existente:
                    if not self.actualizar:
                        omitidos += 1
                        continue
                    cambios = []
                    for campo in CAMPOS_SISA:
                        valor = datos.get(campo)
                        if valor in (None, ''):
                            continue
                        if getattr(existente, campo) != valor:
                            setattr(existente, campo, valor)
                            cambios.append(campo)
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
                    origen_sisa=ruta.name,
                    **{campo: datos.get(campo) or '' for campo in CAMPOS_SISA
                       if campo != 'fecha_ingreso'},
                )
                incidente.fecha_ingreso = datos.get('fecha_ingreso')
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
            'estado_enlace': ESTADOS_ENLACE.get(enlace_crudo, Incidente.EstadoEnlace.DESCONOCIDO),
            'fecha_ingreso': a_fecha(primer_valor(fila, ['FECHA INGRESO', 'FECHA APERTURA',
                                                         'FECHA'])),
            'dilacion_sisa': entero(primer_valor(fila, ['DILACION DIAS', 'DILACION'])),
        }
