import secrets
import string

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

UsuarioGIO = get_user_model()

PLANTILLA = [
    ('GER-0001', 'Gerencia', 'CASE Puebla', UsuarioGIO.Rol.ADMIN, 'PUEBLA', True),
    ('SUB-0001', 'Subgerencia', 'Planta Interna', UsuarioGIO.Rol.PI_SUB, 'PUEBLA', False),
    ('OQU-8821', 'Evaluador', 'Planta Interna', UsuarioGIO.Rol.PI_EVALUADOR, 'PUEBLA', False),
    ('TEC-4410', 'Tecnico', 'Planta Externa', UsuarioGIO.Rol.TECNICO, 'PUEBLA', False),
]


def password_aleatoria(longitud=14):
    alfabeto = string.ascii_letters + string.digits + '!@#$%&*'
    return ''.join(secrets.choice(alfabeto) for _ in range(longitud))


class Command(BaseCommand):
    help = ('Crea las carpetas aisladas de intercambio SISA y, opcionalmente, un juego inicial '
            'de usuarios por rol con contraseñas aleatorias.')

    def add_arguments(self, parser):
        parser.add_argument('--con-usuarios', action='store_true',
                            help='Crea los usuarios base por rol si aún no existen.')
        parser.add_argument('--password', help='Contraseña a usar para todos los usuarios base.')

    def handle(self, *args, **opciones):
        for carpeta in (settings.PRIVATE_DATA_DIR, settings.SISA_IMPORTS_DIR,
                        settings.SISA_IMPORTS_PROCESADOS_DIR, settings.SISA_EXPORTS_DIR,
                        settings.MEDIA_ROOT):
            carpeta.mkdir(parents=True, exist_ok=True)
            self.stdout.write(f'Carpeta lista: {carpeta}')

        if not opciones['con_usuarios']:
            return

        creados = []
        with transaction.atomic():
            for expediente, nombre, apellido, rol, area, staff in PLANTILLA:
                if UsuarioGIO.objects.filter(expediente=expediente).exists():
                    self.stdout.write(f'Ya existe {expediente}, se omite.')
                    continue
                password = opciones['password'] or password_aleatoria()
                UsuarioGIO.objects.create_user(
                    expediente=expediente,
                    password=password,
                    first_name=nombre,
                    last_name=apellido,
                    rol=rol,
                    area_operativa=area,
                    is_staff=staff,
                    is_superuser=staff,
                )
                creados.append((expediente, rol, password))

        if not creados:
            return

        self.stdout.write(self.style.SUCCESS('\nUsuarios creados (guarde estas credenciales):'))
        for expediente, rol, password in creados:
            self.stdout.write(f'  {expediente:<12} {rol:<14} {password}')
        self.stdout.write(self.style.WARNING(
            '\nCambie estas contraseñas desde /api/auth/password/ antes de operar en producción.'))
