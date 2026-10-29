import shutil
from itertools import chain
from pathlib import Path

from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from gio_app.models import (
    BitacoraIncidente, EvidenciaIncidente, Incidente, LecturaChat, MensajeFolio,
)

PALABRA_DE_CONFIRMACION = 'BORRAR'


class Command(BaseCommand):
    help = ('Borra todos los folios con sus evidencias, chat y bitácora, por ejemplo los de prueba, '
            'para empezar de cero. Antes guarda un respaldo en backend/respaldos/ que se recupera '
            'con loaddata. No toca usuarios ni turnos.')

    def add_arguments(self, parser):
        parser.add_argument('--noinput', '--no-input', action='store_false', dest='interactive',
                            help=f'No pide escribir {PALABRA_DE_CONFIRMACION} para confirmar.')
        parser.add_argument('--carpeta', help='Carpeta del respaldo (por omisión backend/respaldos).')

    def handle(self, *args, **opciones):
        # Solo los folios que existen ahora: uno que llegue por la ingesta mientras tanto se conserva.
        ultimo = Incidente.objects.aggregate(ultimo=Max('pk'))['ultimo']
        if ultimo is None:
            self.stdout.write('No hay folios que borrar.')
            return
        folios = Incidente.objects.filter(pk__lte=ultimo)
        relacionados = {
            'evidencias': EvidenciaIncidente.objects.filter(incidente__in=folios),
            'mensajes del chat': MensajeFolio.objects.filter(incidente__in=folios),
            'registros de bitácora': BitacoraIncidente.objects.filter(incidente__in=folios),
        }

        self.stdout.write(f'Se borrarán {folios.count()} folio(s) con:')
        for nombre, consulta in relacionados.items():
            self.stdout.write(f'  {consulta.count()} {nombre}')
        self.stdout.write('Los usuarios y los turnos no se tocan.')
        self._avisar_pendientes_de_sisa(folios)

        if opciones['interactive']:
            respuesta = input(f'\nEscriba {PALABRA_DE_CONFIRMACION} para continuar: ')
            if respuesta.strip() != PALABRA_DE_CONFIRMACION:
                self.stdout.write(self.style.WARNING('Cancelado: no se borró nada.'))
                return

        base = Path(opciones['carpeta']) if opciones['carpeta'] else settings.BASE_DIR / 'respaldos'
        respaldo = base / f'folios_{timezone.localtime():%Y%m%d_%H%M%S}'
        respaldo.mkdir(parents=True)
        fotos = [nombre for nombre in chain(
            relacionados['evidencias'].values_list('imagen', flat=True),
            relacionados['mensajes del chat'].values_list('imagen', flat=True),
        ) if nombre]

        # El respaldo se escribe completo antes de borrar: si falla, no se borra nada.
        objetos = chain(
            folios.order_by('pk'),
            relacionados['evidencias'].order_by('pk'),
            relacionados['mensajes del chat'].order_by('pk'),
            LecturaChat.objects.filter(incidente__in=folios).order_by('pk'),
            relacionados['registros de bitácora'].order_by('pk'),
        )
        with (respaldo / 'folios.json').open('w', encoding='utf-8') as archivo:
            serializers.serialize('json', objetos, stream=archivo)

        with transaction.atomic():
            borrados = folios.count()
            folios.delete()

        no_movidas = self._mover_fotos(fotos, respaldo / 'media')

        self.stdout.write(self.style.SUCCESS(f'\n{borrados} folio(s) borrado(s).'))
        self.stdout.write(f'Respaldo en {respaldo}')
        if no_movidas:
            self.stdout.write(self.style.WARNING(
                f'{no_movidas} foto(s) no se pudieron mover al respaldo y siguen en '
                f'{settings.MEDIA_ROOT}.'))
        self.stdout.write(
            f'Para recuperarlo: python manage.py loaddata "{respaldo / "folios.json"}" y regrese '
            f'el contenido de "{respaldo / "media"}" a "{settings.MEDIA_ROOT}".')

    def _avisar_pendientes_de_sisa(self, folios):
        sin_enviar = folios.filter(estatus=Incidente.Estatus.LIQUIDADO, exportado_sisa=False).count()
        if sin_enviar:
            self.stdout.write(self.style.WARNING(
                f'{sin_enviar} folio(s) liquidado(s) aún no se enviaban a SISA y ya no se enviarán.'))
        retornos = (list(settings.SISA_EXPORTS_DIR.glob('RETORNO_SISA_*.csv'))
                    if settings.SISA_EXPORTS_DIR.is_dir() else [])
        if retornos:
            self.stdout.write(self.style.WARNING(
                f'Hay {len(retornos)} archivo(s) RETORNO_SISA en {settings.SISA_EXPORTS_DIR}. Si son '
                'de las pruebas, muévalos antes de que la computadora de SISA los cargue.'))

    @staticmethod
    def _mover_fotos(nombres, destino):
        """Las fotos van al respaldo en lugar de borrarse; devuelve cuántas no se pudieron mover."""
        no_movidas = 0
        for nombre in nombres:
            origen = Path(settings.MEDIA_ROOT) / nombre
            if not origen.is_file():
                continue
            final = destino / nombre
            try:
                final.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(origen), str(final))
            except OSError:
                no_movidas += 1
        return no_movidas
