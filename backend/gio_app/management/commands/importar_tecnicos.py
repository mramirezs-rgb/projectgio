import secrets
import string
import unicodedata
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ._sisa import leer_tabla, primer_valor

UsuarioGIO = get_user_model()

EXTENSIONES = ('*.csv', '*.xlsx', '*.xls')


def sin_acentos(texto):
    return unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode('utf-8')


def partir_nombre(nombre_completo):
    partes = nombre_completo.split()
    if len(partes) >= 4:
        return ' '.join(partes[:2]), ' '.join(partes[2:])
    if len(partes) == 3:
        return partes[0], ' '.join(partes[1:])
    if len(partes) == 2:
        return partes[0], partes[1]
    return nombre_completo, ''


def expediente_desde_nombre(nombre_completo, usados):
    base = sin_acentos(nombre_completo).upper().split()
    iniciales = ''.join(parte[0] for parte in base[:3]) or 'TEC'
    candidato = f'TEC-{iniciales}'[:20]
    sufijo = 1
    while candidato in usados or UsuarioGIO.objects.filter(expediente=candidato).exists():
        sufijo += 1
        candidato = f'TEC-{iniciales}{sufijo}'[:20]
    usados.add(candidato)
    return candidato


def password_aleatoria(longitud=14):
    alfabeto = string.ascii_letters + string.digits + '!@#$%&*'
    return ''.join(secrets.choice(alfabeto) for _ in range(longitud))


class Command(BaseCommand):
    help = ('Da de alta usuarios con rol TECNICO a partir de la columna TECNICO ASIGNADO de los '
            'reportes SISA. Sin --confirmar solo muestra la propuesta de altas.')

    def add_arguments(self, parser):
        parser.add_argument('--archivo', help='Reporte SISA a leer.')
        parser.add_argument('--carpeta', help='Carpeta de reportes alterna.')
        parser.add_argument('--confirmar', action='store_true',
                            help='Ejecuta las altas; sin este indicador solo se listan.')
        parser.add_argument('--area', default='', help='Área operativa a asignar a las altas.')
        parser.add_argument('--password', help='Contraseña inicial común (por defecto aleatoria).')

    def handle(self, *args, **opciones):
        if opciones['archivo']:
            rutas = [Path(opciones['archivo'])]
            if not rutas[0].exists():
                raise CommandError(f'No existe el archivo {rutas[0]}')
        else:
            carpeta = Path(opciones['carpeta']) if opciones['carpeta'] else settings.SISA_IMPORTS_DIR
            rutas = sorted(r for patron in EXTENSIONES for r in carpeta.glob(patron) if r.is_file())
        if not rutas:
            raise CommandError('No se encontraron reportes SISA para analizar.')

        existentes = set()
        for usuario in UsuarioGIO.objects.all():
            existentes.add(usuario.expediente.upper())
            existentes.add(usuario.username.upper())
            existentes.add(' '.join(usuario.get_full_name().split()).upper())

        nombres = set()
        for ruta in rutas:
            marco = leer_tabla(ruta)
            for _, cruda in marco.iterrows():
                fila = {str(k): v for k, v in cruda.items()}
                nombre = primer_valor(fila, ['TECNICO ASIGNADO', 'TECNICO', 'RESPONSABLE'])
                nombre = ' '.join(nombre.split()).upper()
                if nombre and nombre not in existentes and len(nombre.split()) >= 2:
                    nombres.add(nombre)

        if not nombres:
            self.stdout.write(self.style.SUCCESS('Todos los técnicos del reporte ya existen en GIO.'))
            return

        usados = set()
        propuestas = []
        for nombre in sorted(nombres):
            primero, apellidos = partir_nombre(nombre)
            propuestas.append((expediente_desde_nombre(nombre, usados), primero, apellidos))

        self.stdout.write(f'{len(propuestas)} técnico(s) sin usuario GIO:')
        for expediente, primero, apellidos in propuestas:
            self.stdout.write(f'  {expediente:<20} {primero} {apellidos}')

        if not opciones['confirmar']:
            self.stdout.write(self.style.WARNING(
                '\nRevise la lista y vuelva a ejecutar con --confirmar para dar de alta.'))
            return

        credenciales = []
        with transaction.atomic():
            for expediente, primero, apellidos in propuestas:
                password = opciones['password'] or password_aleatoria()
                UsuarioGIO.objects.create_user(
                    expediente=expediente,
                    password=password,
                    first_name=primero[:150],
                    last_name=apellidos[:150],
                    rol=UsuarioGIO.Rol.TECNICO,
                    area_operativa=(opciones['area'] or '').upper(),
                )
                credenciales.append((expediente, f'{primero} {apellidos}'.strip(), password))

        self.stdout.write(self.style.SUCCESS(f'\n{len(credenciales)} usuario(s) creado(s):'))
        for expediente, nombre, password in credenciales:
            self.stdout.write(f'  {expediente:<20} {nombre:<40} {password}')
