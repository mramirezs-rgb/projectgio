from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from gio_app.models import Incidente

from ._sisa import a_fecha, entero, folio_valido, leer_tabla, limpiar_folio, primer_valor
from .ingesta_sisa import EXTENSIONES, es_archivo_temporal


def _fecha(valor):
    return timezone.localtime(valor).strftime('%d/%m/%Y %H:%M') if valor else '—'


class Command(BaseCommand):
    help = ('Compara la dilación de cada folio de un reporte de SISA con la de GIO y lista los '
            'folios abiertos en GIO que el reporte ya no trae. No modifica nada.')

    def add_arguments(self, parser):
        parser.add_argument('--archivo', help='Reporte a comparar. Por omisión, el más reciente de '
                                              'sisa_imports o de sisa_imports/procesados.')
        parser.add_argument('--fecha', help='Fecha en que SISA generó el reporte (AAAA-MM-DD). Por '
                                            'omisión se deduce de FECHA INGRESO y DILACIÓN DÍAS.')
        parser.add_argument('--muestra', type=int, default=15,
                            help='Cuántos folios listar en cada grupo (15 por omisión).')

    def handle(self, *args, **opciones):
        ruta = Path(opciones['archivo']) if opciones['archivo'] else self._ultimo_reporte()
        if not ruta.is_file():
            raise CommandError(f'No existe el archivo {ruta}')
        reporte = self._leer(ruta)
        if not reporte:
            raise CommandError(f'{ruta.name} no trae folios.')
        fecha = self._fecha_del_reporte(opciones['fecha'], ruta, reporte.values())
        muestra = max(opciones['muestra'], 0)

        Incidente.refrescar_dilaciones()
        en_gio = {inc.folio: inc for inc in Incidente.objects.filter(folio__in=list(reporte))}
        coinciden, distintas, liquidados, sin_dato = 0, [], 0, 0
        for folio, (ingreso, dilacion_sisa) in reporte.items():
            inc = en_gio.get(folio)
            if not inc:
                continue
            fin = fecha
            if inc.fecha_cierre:
                fin = min(fin, timezone.localdate(inc.fecha_cierre))
            dilacion_gio = max(0, (fin - timezone.localdate(inc.fecha_apertura)).days)
            if inc.fecha_cierre and fin < fecha:
                # GIO congela la dilación al liquidar; SISA la sigue contando hasta que cierra.
                liquidados += 1
            elif dilacion_sisa is None:
                sin_dato += 1
            elif dilacion_sisa == dilacion_gio:
                coinciden += 1
            else:
                distintas.append((folio, dilacion_sisa, dilacion_gio, inc.fecha_apertura, ingreso))

        self.stdout.write(f'Reporte: {ruta.name} (generado el {fecha:%d/%m/%Y})')
        self.stdout.write(f'Folios en el reporte: {len(reporte)}')
        self.stdout.write(f'  misma dilación en GIO y en SISA: {coinciden}')
        self.stdout.write(f'  dilación distinta: {len(distintas)}')
        self.stdout.write(f'  liquidados en GIO antes de esa fecha (no se comparan): {liquidados}')
        self.stdout.write(f'  sin DILACIÓN DÍAS en el reporte: {sin_dato}')
        self.stdout.write(f'  no están en GIO: {len(reporte) - len(en_gio)}')
        if distintas:
            self.stdout.write(self.style.WARNING('\nDilación distinta (SISA → GIO):'))
            for folio, sisa, gio, apertura, ingreso in distintas[:muestra]:
                self.stdout.write(f'  {folio}: SISA {sisa} d, GIO {gio} d — apertura en GIO '
                                  f'{_fecha(apertura)}, ingreso en SISA {_fecha(ingreso)}')

        self._abiertos_fuera_del_reporte(reporte, muestra)

    def _abiertos_fuera_del_reporte(self, reporte, muestra):
        """Los indicadores del tablero cuentan todos los folios abiertos de GIO, también los que SISA
        ya no reporta."""
        umbral = settings.DILACION_UMBRAL_DIAS
        critico = settings.DILACION_UMBRAL_CRITICO_DIAS
        abiertos = Incidente.objects.exclude(estatus=Incidente.Estatus.LIQUIDADO)
        fuera = abiertos.exclude(folio__in=list(reporte))

        def resumen(consulta):
            return (f'{consulta.count()} abiertos, {consulta.filter(dilacion_dias__gte=umbral).count()}'
                    f' con {umbral} días o más, '
                    f'{consulta.filter(dilacion_dias__gte=critico).count()} con {critico} o más')

        self.stdout.write(f'\nTablero de GIO hoy: {resumen(abiertos)}.')
        self.stdout.write(f'  de ellos, no vienen en el reporte: {resumen(fuera)}.')
        if fuera.exists():
            self.stdout.write('  Cuentan en el tablero aunque SISA ya no los reporte; si ya se '
                              'atendieron, hay que liquidarlos en GIO. Los de mayor dilación:')
            for inc in fuera.order_by('-dilacion_dias', 'folio')[:muestra]:
                self.stdout.write(f'  {inc.folio}: {inc.dilacion_dias} d, '
                                  f'{inc.get_estatus_display()}, abierto el {_fecha(inc.fecha_apertura)}'
                                  f', {inc.empresa or "sin empresa"}')

    @staticmethod
    def _ultimo_reporte():
        carpetas = (settings.SISA_IMPORTS_DIR, settings.SISA_IMPORTS_PROCESADOS_DIR)
        reportes = [r for carpeta in carpetas if carpeta.is_dir() for patron in EXTENSIONES
                    for r in carpeta.glob(patron) if not es_archivo_temporal(r)]
        if not reportes:
            raise CommandError('No hay reportes en sisa_imports ni en sisa_imports/procesados. '
                               'Indique uno con --archivo.')
        return max(reportes, key=lambda ruta: ruta.stat().st_mtime)

    @staticmethod
    def _leer(ruta):
        """Folio -> (fecha de ingreso, dilación según SISA o None si el reporte no la trae)."""
        reporte = {}
        for _, cruda in leer_tabla(ruta).iterrows():
            fila = {str(k): v for k, v in cruda.items()}
            folio = limpiar_folio(primer_valor(fila, ['FOLIO', 'FOLIO SISA', 'NO FOLIO']))
            if not folio_valido(folio):
                continue
            dilacion = primer_valor(fila, ['DILACION DIAS', 'DILACION'])
            ingreso = a_fecha(primer_valor(fila, ['FECHA INGRESO', 'FECHA APERTURA', 'FECHA']))
            reporte[folio] = (ingreso, entero(dilacion, None) if dilacion else None)
        return reporte

    @staticmethod
    def _fecha_del_reporte(texto, ruta, filas):
        """SISA calcula DILACIÓN DÍAS el día que genera el reporte: ingreso + dilación da esa fecha
        en casi todas las filas. Sin esos datos se usa la fecha de modificación del archivo."""
        if texto:
            try:
                return date.fromisoformat(texto)
            except ValueError as error:
                raise CommandError('Use --fecha AAAA-MM-DD.') from error
        fechas = Counter(timezone.localdate(ingreso) + timedelta(days=dilacion)
                         for ingreso, dilacion in filas if ingreso and dilacion is not None)
        if fechas:
            return fechas.most_common(1)[0][0]
        modificado = datetime.fromtimestamp(ruta.stat().st_mtime, tz=timezone.get_current_timezone())
        return modificado.date()
