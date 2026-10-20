from django.db.models import Count, Max, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce

from .models import Incidente, LecturaChat, MensajeFolio

MAX_RECIENTES = 20
LARGO_VISTA_PREVIA = 120


def mensajes_pendientes(usuario, folios):
    """Mensajes que el usuario no ha leído en los chats de los folios que le corresponden.

    `folios` son los que el usuario puede ver. El técnico y el evaluador reciben avisos de todos
    sus folios; Subgerencia y Gerencia, que ven todo, solo de los chats en que ya escribieron.
    """
    if usuario.tiene_vision_global:
        folios = folios.filter(pk__in=MensajeFolio.objects.filter(autor=usuario)
                               .values('incidente'))

    leido_hasta = (LecturaChat.objects
                   .filter(incidente=OuterRef('incidente'), usuario=usuario)
                   .values('ultimo_leido')[:1])
    por_folio = list(
        MensajeFolio.objects
        .filter(incidente__in=folios.values('pk'))
        .exclude(autor=usuario)
        .filter(pk__gt=Coalesce(Subquery(leido_hasta), Value(0)))
        .values('incidente')
        .annotate(sin_leer=Count('id'), ultimo=Max('id'))
        .order_by('-ultimo')
    )

    recientes = por_folio[:MAX_RECIENTES]
    datos_folio = Incidente.objects.in_bulk([fila['incidente'] for fila in recientes])
    ultimos = (MensajeFolio.objects.select_related('autor')
               .in_bulk([fila['ultimo'] for fila in recientes]))

    return {
        'total': sum(fila['sin_leer'] for fila in por_folio),
        'por_folio': {str(fila['incidente']): fila['sin_leer'] for fila in por_folio},
        'recientes': [
            {
                'id': fila['incidente'],
                'folio': datos_folio[fila['incidente']].folio,
                'empresa': datos_folio[fila['incidente']].empresa,
                'sin_leer': fila['sin_leer'],
                'ultimo': _vista_previa(ultimos[fila['ultimo']]),
            }
            for fila in recientes
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
        'creado_en': mensaje.creado_en,
    }
