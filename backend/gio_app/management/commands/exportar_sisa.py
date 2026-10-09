import logging
from pathlib import Path

import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from gio_app.models import BitacoraIncidente, Incidente

log = logging.getLogger('gio.exportacion')

COLUMNAS = [
    'FOLIO', 'DIAGNOSTICO FINAL', 'TECNICO', 'EVALUADOR', 'MTTR HORAS', 'ESTATUS',
    'CVE LIQ', 'DESC LIQ', 'CODIGO FALLO', 'FECHA APERTURA', 'FECHA CIERRE',
    'AREA OPERATIVA', 'CENTRAL',
]


class Command(BaseCommand):
    help = ('Genera el archivo CSV de retorno para SISA/LSA con los folios LIQUIDADO que '
            'aún no han sido exportados, calculando el MTTR en horas.')

    def add_arguments(self, parser):
        parser.add_argument('--carpeta', help='Carpeta de salida alterna.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Calcula el retorno sin escribir el archivo ni marcar folios.')
        parser.add_argument('--limite', type=int, default=0,
                            help='Exporta como máximo N folios en esta corrida.')
        parser.add_argument('--reexportar', action='store_true',
                            help='Incluye folios ya exportados previamente.')

    def handle(self, *args, **opciones):
        consulta = Incidente.objects.filter(
            estatus=Incidente.Estatus.LIQUIDADO, fecha_cierre__isnull=False
        ).select_related('tecnico', 'evaluador').order_by('fecha_cierre')

        if not opciones['reexportar']:
            consulta = consulta.filter(exportado_sisa=False)
        if opciones['limite'] > 0:
            consulta = consulta[:opciones['limite']]

        incidentes = list(consulta)
        if not incidentes:
            self.stdout.write(self.style.WARNING('No hay folios liquidados pendientes de exportar.'))
            return

        filas = [{
            'FOLIO': inc.folio,
            'DIAGNOSTICO FINAL': inc.diagnostico_final,
            'TECNICO': inc.tecnico.nombre_completo if inc.tecnico else '',
            'EVALUADOR': inc.evaluador.nombre_completo if inc.evaluador else '',
            'MTTR HORAS': f'{inc.mttr_horas:.2f}' if inc.mttr_horas is not None else '',
            'ESTATUS': inc.estatus,
            'CVE LIQ': inc.cve_liq,
            'DESC LIQ': inc.desc_liq,
            'CODIGO FALLO': inc.codigo_fallo,
            'FECHA APERTURA': timezone.localtime(inc.fecha_apertura).strftime('%Y-%m-%d %H:%M:%S'),
            'FECHA CIERRE': timezone.localtime(inc.fecha_cierre).strftime('%Y-%m-%d %H:%M:%S'),
            'AREA OPERATIVA': inc.area_operativa,
            'CENTRAL': inc.central,
        } for inc in incidentes]

        marco = pd.DataFrame(filas, columns=COLUMNAS)
        mttr = pd.to_numeric(marco['MTTR HORAS'], errors='coerce').dropna()

        promedio = f' MTTR promedio {mttr.mean():.2f} h.' if len(mttr) else ''

        if opciones['dry_run']:
            self.stdout.write(self.style.WARNING(
                f'[DRY-RUN] {len(marco)} folio(s) listos para exportar.{promedio}'))
            self.stdout.write(marco.head(10).to_string(index=False))
            return

        carpeta = Path(opciones['carpeta']) if opciones['carpeta'] else settings.SISA_EXPORTS_DIR
        carpeta.mkdir(parents=True, exist_ok=True)
        destino = carpeta / f'RETORNO_SISA_{timezone.localtime():%Y%m%d_%H%M}.csv'

        marco.to_csv(destino, index=False, encoding='utf-8-sig')

        with transaction.atomic():
            ahora = timezone.now()
            Incidente.objects.filter(pk__in=[inc.pk for inc in incidentes]).update(
                exportado_sisa=True,
                estado_sincronizacion=Incidente.Sincronizacion.EXPORTADO,
                ultimo_intento_sinc=ahora,
                error_sincronizacion='',
            )
            BitacoraIncidente.objects.bulk_create([
                BitacoraIncidente(
                    incidente=inc, usuario=None,
                    accion=BitacoraIncidente.Accion.EXPORTACION,
                    campo='exportado_sisa', valor_anterior='False', valor_nuevo='True',
                    detalle=f'{destino.name} — MTTR {inc.mttr_horas} h',
                ) for inc in incidentes
            ])

        log.info('Retorno SISA generado en %s con %s folios', destino, len(incidentes))
        self.stdout.write(self.style.SUCCESS(
            f'Retorno generado: {destino} ({len(incidentes)} folio(s)).{promedio}'))
