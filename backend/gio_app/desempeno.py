from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from .models import Incidente

UsuarioGIO = get_user_model()


def _fila_vacia(usuario):
    return {
        'id': usuario.pk,
        'expediente': usuario.expediente,
        'nombre': usuario.nombre_completo,
        'rol': usuario.rol,
        'rol_display': usuario.get_rol_display(),
        'area_operativa': usuario.area_operativa,
        'abiertos': 0,
        'en_proceso': 0,
        'liquidados': 0,
        'liquidados_hoy': 0,
        'criticos': 0,
        'mttr_horas_promedio': None,
        'dilacion_promedio_dias': None,
        '_mttr': [],
        '_dilaciones': [],
    }


def desempeno_de_campo(area=''):
    """Carga y resultados por técnico de planta externa e interna.

    Cada técnico cuenta los folios en los que participa: como técnico asignado para
    planta externa y como evaluador para planta interna. Se incluyen también los técnicos
    sin folios para que sea visible quién no tiene carga.
    """
    ahora = timezone.now()
    hoy = timezone.localdate(ahora)
    critico = settings.DILACION_UMBRAL_CRITICO_DIAS

    usuarios = UsuarioGIO.objects.filter(
        rol__in=[UsuarioGIO.Rol.TECNICO, UsuarioGIO.Rol.PI_EVALUADOR], is_active=True)
    if area:
        usuarios = usuarios.filter(Q(area_operativa=area) | Q(area_operativa=''))
    usuarios = list(usuarios.order_by('first_name', 'last_name', 'expediente'))

    filas = {usuario.pk: _fila_vacia(usuario) for usuario in usuarios}
    if filas:
        folios = Incidente.objects.filter(
            Q(tecnico_id__in=filas) | Q(evaluador_id__in=filas)
        ).values('tecnico_id', 'evaluador_id', 'estatus', 'dilacion_dias',
                 'fecha_apertura', 'fecha_cierre')

        for folio in folios:
            participantes = {folio['tecnico_id'], folio['evaluador_id']} & filas.keys()
            liquidado = folio['estatus'] == Incidente.Estatus.LIQUIDADO
            for pk in participantes:
                fila = filas[pk]
                if liquidado:
                    fila['liquidados'] += 1
                    cierre = folio['fecha_cierre']
                    if cierre and timezone.localtime(cierre).date() == hoy:
                        fila['liquidados_hoy'] += 1
                    if folio['fecha_apertura'] and cierre:
                        horas = (cierre - folio['fecha_apertura']).total_seconds() / 3600
                        fila['_mttr'].append(max(horas, 0))
                    continue
                fila['abiertos'] += 1
                if folio['estatus'] == Incidente.Estatus.EN_PROCESO:
                    fila['en_proceso'] += 1
                if folio['dilacion_dias'] >= critico:
                    fila['criticos'] += 1
                fila['_dilaciones'].append(folio['dilacion_dias'])

    for fila in filas.values():
        mttr = fila.pop('_mttr')
        dilaciones = fila.pop('_dilaciones')
        if mttr:
            fila['mttr_horas_promedio'] = round(sum(mttr) / len(mttr), 2)
        if dilaciones:
            fila['dilacion_promedio_dias'] = round(sum(dilaciones) / len(dilaciones), 2)

    return {
        'generado_en': ahora,
        'tecnicos_planta_externa': [f for f in filas.values()
                                    if f['rol'] == UsuarioGIO.Rol.TECNICO],
        'tecnicos_planta_interna': [f for f in filas.values()
                                    if f['rol'] == UsuarioGIO.Rol.PI_EVALUADOR],
    }
