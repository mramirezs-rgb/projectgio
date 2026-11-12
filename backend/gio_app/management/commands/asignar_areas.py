from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from gio_app.areas import asignar_areas, proponer_areas

UsuarioGIO = get_user_model()


class Command(BaseCommand):
    help = ('Asigna a cada técnico sin área operativa la más frecuente entre sus folios. '
            'Sin --confirmar solo muestra la propuesta.')

    def add_arguments(self, parser):
        parser.add_argument('--confirmar', action='store_true',
                            help='Guarda las áreas; sin este indicador solo se listan.')
        parser.add_argument('--recalcular', action='store_true',
                            help='Revisa también a los técnicos que ya tienen área y propone '
                                 'cambiarla si la mayoría de sus folios es de otra.')

    def handle(self, *args, **opciones):
        propuestas = proponer_areas(recalcular=opciones['recalcular'])
        if propuestas:
            self.stdout.write(f'{len(propuestas)} técnico(s) por asignar:')
            for usuario, area in propuestas:
                self.stdout.write(
                    f'  {usuario.expediente:<20} {usuario.nombre_completo:<40} '
                    f'{usuario.area_operativa or "sin área"} -> {area}')

        pendientes = UsuarioGIO.objects.filter(
            rol__in=UsuarioGIO.ROLES_CON_AREA, is_active=True, area_operativa='',
        ).exclude(pk__in=[usuario.pk for usuario, _ in propuestas]).order_by('expediente')
        if pendientes:
            self.stdout.write(self.style.WARNING(
                f'{len(pendientes)} técnico(s) sin área y sin folios en un área reconocida; '
                'asígnela en Usuarios:'))
            for usuario in pendientes:
                self.stdout.write(f'  {usuario.expediente:<20} {usuario.nombre_completo}')

        if not propuestas:
            if not pendientes:
                self.stdout.write(self.style.SUCCESS('Todos los técnicos tienen área.'))
            return
        if not opciones['confirmar']:
            self.stdout.write(self.style.WARNING(
                '\nRevise la lista y vuelva a ejecutar con --confirmar para guardar.'))
            return
        asignar_areas(propuestas)
        self.stdout.write(self.style.SUCCESS(f'\nÁrea asignada a {len(propuestas)} técnico(s).'))
