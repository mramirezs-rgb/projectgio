import secrets
import string
import unicodedata
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ._sisa import es_cuenta_generica, leer_tabla, normalizar_telefono, primer_valor

UsuarioGIO = get_user_model()

EXTENSIONES = ('*.csv', '*.xlsx', '*.xls')


def sin_acentos(texto):
    return unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode('utf-8')


def partir_nombre(nombre_completo):
    """Las dos últimas palabras son los apellidos; las demás, el nombre."""
    partes = nombre_completo.split()
    if len(partes) >= 4:
        return ' '.join(partes[:-2]), ' '.join(partes[-2:])
    if len(partes) == 3:
        return partes[0], ' '.join(partes[1:])
    if len(partes) == 2:
        return partes[0], partes[1]
    return nombre_completo, ''


def expediente_desde_nombre(nombre_completo, usados, prefijo='TEC'):
    base = sin_acentos(nombre_completo).upper().split()
    iniciales = ''.join(parte[0] for parte in base[:3]) or prefijo
    candidato = f'{prefijo}-{iniciales}'[:20]
    sufijo = 1
    while candidato in usados or UsuarioGIO.objects.filter(expediente=candidato).exists():
        sufijo += 1
        candidato = f'{prefijo}-{iniciales}{sufijo}'[:20]
    usados.add(candidato)
    return candidato


def password_aleatoria(longitud=14):
    alfabeto = string.ascii_letters + string.digits + '!@#$%&*'
    return ''.join(secrets.choice(alfabeto) for _ in range(longitud))


class Command(BaseCommand):
    help = ('Da de alta a los técnicos de los reportes SISA: planta externa desde TECNICO ASIGNADO '
            '(con su TELEFONO TECNICO) y planta interna desde OQU. Sin --confirmar solo muestra '
            'la propuesta.')

    def add_arguments(self, parser):
        parser.add_argument('--archivo', help='Reporte SISA a leer.')
        parser.add_argument('--carpeta', help='Carpeta de reportes alterna.')
        parser.add_argument('--confirmar', action='store_true',
                            help='Ejecuta las altas; sin este indicador solo se listan.')
        parser.add_argument('--area', default='', help='Área operativa a asignar a las altas.')
        parser.add_argument('--password', help='Contraseña inicial común (por defecto aleatoria).')
        parser.add_argument('--excluir', action='append', default=[], metavar='TEXTO',
                            help='Omite los nombres que contienen este texto; se puede repetir.')

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

        existentes = {}
        for usuario in UsuarioGIO.objects.all():
            for clave in (usuario.expediente.upper(), usuario.username.upper(),
                          ' '.join(usuario.get_full_name().split()).upper()):
                if clave:
                    existentes.setdefault(clave, usuario)

        excluir = [' '.join(texto.split()).upper() for texto in opciones['excluir'] if texto.strip()]

        # Nombre -> (rol, teléfono) para las altas; técnicos existentes a los que les falta teléfono.
        nuevos = {}
        por_completar = {}
        omitidos = set()
        for ruta in rutas:
            marco = leer_tabla(ruta)
            for _, cruda in marco.iterrows():
                fila = {str(k): v for k, v in cruda.items()}
                externo = primer_valor(fila, ['TECNICO ASIGNADO', 'TECNICO', 'RESPONSABLE'])
                telefono = normalizar_telefono(primer_valor(fila, ['TELEFONO TECNICO', 'TELEFONO']))
                candidatos = (
                    (externo, UsuarioGIO.Rol.TECNICO, telefono),
                    (primer_valor(fila, ['OQU']), UsuarioGIO.Rol.PI_EVALUADOR, ''),
                )
                for nombre, rol, telefono_fila in candidatos:
                    nombre = ' '.join(nombre.split()).upper()
                    if not nombre:
                        continue
                    if es_cuenta_generica(nombre) or any(texto in nombre for texto in excluir):
                        omitidos.add(nombre)
                        continue
                    usuario = existentes.get(nombre)
                    if usuario:
                        if telefono_fila and not usuario.telefono and usuario.es_tecnico:
                            por_completar.setdefault(usuario.pk, (usuario, telefono_fila))
                        continue
                    if len(nombre.split()) >= 2:
                        rol_previo, telefono_previo = nuevos.get(nombre, (rol, ''))
                        nuevos[nombre] = (rol_previo, telefono_previo or telefono_fila)

        if omitidos:
            self.stdout.write(
                f'{len(omitidos)} nombre(s) omitido(s) por ser cuentas de operadora o por '
                f'--excluir: {", ".join(sorted(omitidos))}')

        if not nuevos and not por_completar:
            self.stdout.write(self.style.SUCCESS(
                'Todos los técnicos del reporte ya existen en GIO y tienen teléfono.'))
            return

        usados = set()
        propuestas = []
        for nombre in sorted(nuevos):
            rol, telefono = nuevos[nombre]
            prefijo = 'OQU' if rol == UsuarioGIO.Rol.PI_EVALUADOR else 'TEC'
            primero, apellidos = partir_nombre(nombre)
            propuestas.append((expediente_desde_nombre(nombre, usados, prefijo), primero,
                               apellidos, rol, telefono))

        if propuestas:
            self.stdout.write(f'{len(propuestas)} técnico(s) sin usuario GIO:')
            for expediente, primero, apellidos, rol, telefono in propuestas:
                self.stdout.write(
                    f'  {expediente:<20} {primero} {apellidos}  [{UsuarioGIO.Rol(rol).label}]'
                    f'  tel. {telefono or "sin teléfono"}')
        if por_completar:
            self.stdout.write(f'{len(por_completar)} técnico(s) existente(s) sin teléfono:')
            for usuario, telefono in por_completar.values():
                self.stdout.write(f'  {usuario.expediente:<20} {usuario.nombre_completo}  tel. {telefono}')

        if not opciones['confirmar']:
            self.stdout.write(self.style.WARNING(
                '\nRevise la lista y vuelva a ejecutar con --confirmar para aplicar los cambios.'))
            return

        credenciales = []
        with transaction.atomic():
            for expediente, primero, apellidos, rol, telefono in propuestas:
                password = opciones['password'] or password_aleatoria()
                UsuarioGIO.objects.create_user(
                    expediente=expediente,
                    password=password,
                    first_name=primero[:150],
                    last_name=apellidos[:150],
                    rol=rol,
                    area_operativa=(opciones['area'] or '').upper(),
                    telefono=telefono,
                )
                credenciales.append((expediente, f'{primero} {apellidos}'.strip(), password))
            for usuario, telefono in por_completar.values():
                usuario.telefono = telefono
                usuario.save(update_fields=['telefono'])

        if credenciales:
            self.stdout.write(self.style.SUCCESS(f'\n{len(credenciales)} usuario(s) creado(s):'))
            for expediente, nombre, password in credenciales:
                self.stdout.write(f'  {expediente:<20} {nombre:<40} {password}')
        if por_completar:
            self.stdout.write(self.style.SUCCESS(
                f'\nTeléfono vinculado a {len(por_completar)} técnico(s) existente(s).'))
