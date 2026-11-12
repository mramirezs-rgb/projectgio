"""Área operativa de los técnicos, deducida de los folios que atienden."""
import unicodedata
from collections import Counter

from django.contrib.auth import get_user_model

from .models import Incidente

UsuarioGIO = get_user_model()


def _clave(texto):
    sin_acentos = unicodedata.normalize('NFD', texto or '').encode('ascii', 'ignore').decode()
    return ' '.join(sin_acentos.upper().split())


AREAS_POR_CLAVE = {_clave(valor): valor for valor, _ in UsuarioGIO.areas_operativas()}


def area_reconocida(texto):
    """El área de usuario que corresponde al texto del reporte (CÓRDOBA -> CORDOBA), o ''."""
    return AREAS_POR_CLAVE.get(_clave(texto), '')


def proponer_areas(recalcular=False):
    """Pares (técnico, área) donde el área es la más frecuente entre los folios del técnico.

    Planta externa cuenta los folios en que es técnico; planta interna, en los que es
    evaluador. Solo se consideran técnicos activos y, salvo con `recalcular`, los que aún no
    tienen área. Quien no tiene folios en un área reconocida no aparece.
    """
    tecnicos = UsuarioGIO.objects.filter(rol__in=UsuarioGIO.ROLES_CON_AREA, is_active=True)
    if not recalcular:
        tecnicos = tecnicos.filter(area_operativa='')
    tecnicos = {usuario.pk: usuario for usuario in tecnicos}

    conteos = {}
    for campo in ('tecnico_id', 'evaluador_id'):
        filas = (Incidente.objects.filter(**{f'{campo}__in': tecnicos})
                 .exclude(area_operativa='').values_list(campo, 'area_operativa'))
        for pk, area in filas:
            area = area_reconocida(area)
            if area:
                conteos.setdefault(pk, Counter())[area] += 1

    propuestas = []
    for pk, conteo in conteos.items():
        # Con empate gana el área alfabéticamente primera, para que el resultado sea estable.
        area = min(conteo, key=lambda nombre: (-conteo[nombre], nombre))
        if area != tecnicos[pk].area_operativa:
            propuestas.append((tecnicos[pk], area))
    return sorted(propuestas, key=lambda par: par[0].expediente)


def asignar_areas(propuestas):
    for usuario, area in propuestas:
        usuario.area_operativa = area
        usuario.save(update_fields=['area_operativa'])
    return len(propuestas)
