from datetime import timedelta

from django.contrib.auth import get_user_model
from django.conf import settings
from django.db.models import Count, Exists, Max, Min, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import Incidente, LecturaChat, MensajeFolio
from .reparto import ids_de_turno

UsuarioGIO = get_user_model()

MAX_RECIENTES = 20
LARGO_VISTA_PREVIA = 120

# Los avisos de folios ajenos (apoyo a quien descansa y mensajes de Gerencia para Subgerencia)
# solo cuentan mensajes recientes, para no anunciar de golpe conversaciones antiguas.
DIAS_DE_AVISOS_AJENOS = 3

# Los mensajes de Gerencia son prioritarios: avisan a todos los que pueden ver el folio.
DE_GERENCIA = Q(autor__rol=UsuarioGIO.Rol.ADMIN) | Q(autor__is_superuser=True)


def folios_en_apoyo(usuario, ahora=None):
    """Folios de otros que un técnico de planta interna de turno atiende en el chat.

    Son los folios abiertos de su zona que no tienen técnico de planta interna o cuyo técnico
    no tiene turno hoy (está de descanso). Quien no está de turno no cubre a nadie, así que si
    no se han programado turnos nadie recibe avisos de folios ajenos.
    """
    de_turno = ids_de_turno(ahora)
    if usuario.pk not in de_turno:
        return Incidente.objects.none()
    folios = (Incidente.objects.exclude(estatus=Incidente.Estatus.LIQUIDADO)
              .exclude(evaluador=usuario)
              .filter(Q(evaluador__isnull=True) | ~Q(evaluador__in=list(de_turno))))
    if usuario.area_operativa:
        folios = folios.filter(area_operativa=usuario.area_operativa)
    return folios


def sin_atender(ahora):
    """Condición de los mensajes que nadie más que su autor ha leído pasado el plazo.

    Un mensaje así se perdió para quien debía recibirlo (no tiene GIO abierto, descansa o el
    folio no tiene a nadie asignado), así que se avisa a supervisión y a planta interna de turno.
    """
    minutos = settings.CHAT_SIN_ATENDER_MINUTOS
    if minutos <= 0:
        return None
    leido_por_otro = (LecturaChat.objects
                      .filter(incidente=OuterRef('incidente'), ultimo_leido__gte=OuterRef('pk'))
                      .exclude(usuario=OuterRef('autor')))
    return (Q(creado_en__lte=ahora - timedelta(minutes=minutos))
            & Q(creado_en__gte=ahora - timedelta(days=DIAS_DE_AVISOS_AJENOS))
            & ~Exists(leido_por_otro))


def lecturas_del_chat(incidente):
    """Hasta dónde leyó cada quien el chat del folio, incluidos sus dos técnicos asignados."""
    lecturas = {lectura.usuario_id: lectura for lectura in
                incidente.lecturas_chat.select_related('usuario')}
    filas = []
    asignados = [usuario for usuario in (incidente.tecnico, incidente.evaluador) if usuario]
    for usuario in asignados + [lectura.usuario for pk, lectura in lecturas.items()
                                if pk not in {asignado.pk for asignado in asignados}]:
        lectura = lecturas.get(usuario.pk)
        filas.append({
            'usuario': usuario.pk,
            'nombre': usuario.nombre_completo,
            'rol': usuario.rol,
            'asignado': usuario in asignados,
            'ultimo_leido': lectura.ultimo_leido if lectura else 0,
        })
    return {'lecturas': filas, 'minutos_para_escalar': settings.CHAT_SIN_ATENDER_MINUTOS}


def mensajes_pendientes(usuario, folios, ahora=None):
    """Mensajes que el usuario no ha leído en los chats que le corresponden.

    `folios` son los que el usuario tiene a su cargo. Recibe avisos de:
    - todos sus folios, si es técnico de planta externa o interna;
    - los folios que cubre mientras su técnico de planta interna descansa (`folios_en_apoyo`);
    - los chats en los que ya escribió, sea cual sea su rol;
    - los mensajes recientes de Gerencia de cualquier folio, si es Subgerencia;
    - los mensajes que nadie ha leído pasado el plazo (`sin_atender`), si es Subgerencia,
      Gerencia o técnico de planta interna de turno, este último solo los de su zona.
    Van primero los folios con mensajes de Gerencia y después los que nadie ha atendido.
    """
    ahora = ahora or timezone.now()
    recientes = Q(creado_en__gte=ahora - timedelta(days=DIAS_DE_AVISOS_AJENOS))
    donde_escribio = MensajeFolio.objects.filter(autor=usuario).values('incidente')
    if usuario.tiene_vision_global:
        seguidos = Q(incidente__in=donde_escribio)
        if not usuario.es_admin:
            seguidos |= DE_GERENCIA & recientes
    else:
        seguidos = Q(incidente__in=folios.values('pk')) | Q(incidente__in=donde_escribio)
        if usuario.es_evaluador:
            en_apoyo = folios_en_apoyo(usuario, ahora).values('pk')
            seguidos |= Q(incidente__in=en_apoyo) & recientes

    # Lo que nadie ha leído se escala; si el plazo es 0, la condición nunca se cumple.
    olvidados = sin_atender(ahora) or Q(pk__in=[])
    if usuario.tiene_vision_global:
        seguidos |= olvidados
    elif usuario.es_evaluador and usuario.pk in ids_de_turno(ahora):
        de_su_zona = (Q(incidente__area_operativa=usuario.area_operativa)
                      if usuario.area_operativa else Q())
        seguidos |= olvidados & de_su_zona

    leido_hasta = (LecturaChat.objects
                   .filter(incidente=OuterRef('incidente'), usuario=usuario)
                   .values('ultimo_leido')[:1])
    por_folio = list(
        MensajeFolio.objects
        .filter(seguidos)
        .exclude(autor=usuario)
        .filter(pk__gt=Coalesce(Subquery(leido_hasta), Value(0)))
        .values('incidente')
        .annotate(sin_leer=Count('id'), ultimo=Max('id'),
                  de_gerencia=Count('id', filter=DE_GERENCIA),
                  ultimo_de_gerencia=Max('id', filter=DE_GERENCIA),
                  sin_atender=Count('id', filter=olvidados),
                  sin_atender_desde=Min('creado_en', filter=olvidados))
        .order_by('-ultimo')
    )
    # Orden estable: primero los folios con mensajes de Gerencia, luego los que nadie ha
    # atendido; cada grupo, del más reciente al más antiguo.
    por_folio.sort(key=lambda fila: (not fila['de_gerencia'], not fila['sin_atender']))

    primeros = por_folio[:MAX_RECIENTES]
    datos_folio = Incidente.objects.in_bulk([fila['incidente'] for fila in primeros])
    # De un folio prioritario se muestra el último mensaje de Gerencia, no el último a secas.
    a_mostrar = {fila['incidente']: fila['ultimo_de_gerencia'] or fila['ultimo']
                 for fila in primeros}
    ultimos = MensajeFolio.objects.select_related('autor').in_bulk(a_mostrar.values())

    return {
        'total': sum(fila['sin_leer'] for fila in por_folio),
        'de_gerencia': sum(fila['de_gerencia'] for fila in por_folio),
        'sin_atender': sum(fila['sin_atender'] for fila in por_folio),
        'por_folio': {str(fila['incidente']): fila['sin_leer'] for fila in por_folio},
        'gerencia_por_folio': {str(fila['incidente']): fila['de_gerencia']
                               for fila in por_folio if fila['de_gerencia']},
        'recientes': [
            {
                'id': fila['incidente'],
                'folio': datos_folio[fila['incidente']].folio,
                'empresa': datos_folio[fila['incidente']].empresa,
                'sin_leer': fila['sin_leer'],
                'de_gerencia': fila['de_gerencia'],
                'sin_atender': fila['sin_atender'],
                'sin_atender_desde': fila['sin_atender_desde'],
                'ultimo': _vista_previa(ultimos[a_mostrar[fila['incidente']]]),
            }
            for fila in primeros
        ],
    }


def _vista_previa(mensaje):
    texto = ' '.join(mensaje.texto.split())
    if mensaje.imagen:
        texto = f'Foto: {texto}' if texto else 'Envió una foto'
    if len(texto) > LARGO_VISTA_PREVIA:
        texto = texto[:LARGO_VISTA_PREVIA - 1] + '…'
    return {
        'texto': texto,
        'autor_nombre': mensaje.autor.nombre_completo if mensaje.autor else 'Usuario eliminado',
        'autor_rol': mensaje.autor.rol if mensaje.autor else '',
        'creado_en': mensaje.creado_en,
    }
