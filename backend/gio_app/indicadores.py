"""Detalle de cada indicador de Métricas: resumen, desgloses y los folios que lo explican."""
from statistics import median

from django.conf import settings
from django.db.models import Avg, Count, Max, Q

from .models import Incidente

MAX_FOLIOS_DETALLE = 50

LIQUIDADO = Incidente.Estatus.LIQUIDADO
ABIERTO = ~Q(estatus=LIQUIDADO)
CAMPOS_FOLIO = ('id', 'folio', 'empresa', 'area_operativa', 'estatus',
                'tecnico__first_name', 'tecnico__last_name', 'tecnico__expediente')


def _dato(etiqueta, valor, unidad=''):
    return {'etiqueta': etiqueta, 'valor': valor, 'unidad': unidad}


def _columna(titulo, unidad=''):
    return {'titulo': titulo, 'unidad': unidad}


def _redondear(valor):
    return None if valor is None else round(valor, 2)


def _area(valor):
    return valor or 'SIN ÁREA'


def _fila_folio(folio, valor):
    nombre = f"{folio['tecnico__first_name'] or ''} {folio['tecnico__last_name'] or ''}".strip()
    return {
        'id': folio['id'],
        'folio': folio['folio'],
        'empresa': folio['empresa'],
        'area_operativa': folio['area_operativa'],
        'estatus': folio['estatus'],
        'tecnico_nombre': nombre or folio['tecnico__expediente'] or 'Sin asignar',
        'valor': valor,
    }


def _folios_por_dilacion(queryset, titulo):
    """Los folios con más días de dilación de la consulta, que ya viene acotada a los abiertos."""
    filas = queryset.order_by('-dilacion_dias', 'fecha_apertura').values(
        *CAMPOS_FOLIO, 'dilacion_dias')[:MAX_FOLIOS_DETALLE]
    return {
        'titulo': titulo,
        'columna': 'Dilación',
        'unidad': 'd',
        'total': queryset.count(),
        'filas': [_fila_folio(fila, fila['dilacion_dias']) for fila in filas],
    }


def _mttr(queryset):
    liquidados = list(queryset.filter(estatus=LIQUIDADO, fecha_cierre__isnull=False)
                      .values(*CAMPOS_FOLIO, 'fecha_apertura', 'fecha_cierre'))
    for folio in liquidados:
        segundos = (folio['fecha_cierre'] - folio['fecha_apertura']).total_seconds()
        folio['horas'] = round(max(segundos, 0) / 3600, 2)
    horas = [folio['horas'] for folio in liquidados]

    por_area = {}
    for folio in liquidados:
        por_area.setdefault(_area(folio['area_operativa']), []).append(folio['horas'])
    areas = sorted(por_area.items(), key=lambda par: -sum(par[1]) / len(par[1]))
    lentos = sorted(liquidados, key=lambda folio: -folio['horas'])[:MAX_FOLIOS_DETALLE]

    return {
        'titulo': 'MTTR (tiempo medio de reparación)',
        'resumen': [
            _dato('Folios liquidados', len(horas)),
            _dato('Promedio', _redondear(sum(horas) / len(horas)) if horas else None, 'h'),
            _dato('Mediana', _redondear(median(horas)) if horas else None, 'h'),
            _dato('Más rápido', min(horas) if horas else None, 'h'),
            _dato('Más lento', max(horas) if horas else None, 'h'),
        ],
        'desgloses': [{
            'titulo': 'MTTR por área',
            'columnas': [_columna('Área'), _columna('Liquidados'), _columna('Promedio', 'h'),
                         _columna('Más lento', 'h')],
            'filas': [[area, len(valores), _redondear(sum(valores) / len(valores)), max(valores)]
                      for area, valores in areas],
        }],
        'folios': {
            'titulo': 'Liquidaciones que más tardaron',
            'columna': 'MTTR',
            'unidad': 'h',
            'total': len(liquidados),
            'filas': [_fila_folio(folio, folio['horas']) for folio in lentos],
        },
    }


def _porcentaje(parte, total):
    return round(parte * 100 / total) if total else 0


def _liquidacion(queryset):
    conteo = queryset.aggregate(
        total=Count('id'),
        liquidados=Count('id', filter=Q(estatus=LIQUIDADO)),
        pendientes=Count('id', filter=Q(estatus=Incidente.Estatus.PENDIENTE)),
        asignados=Count('id', filter=Q(estatus=Incidente.Estatus.ASIGNADO)),
        en_proceso=Count('id', filter=Q(estatus=Incidente.Estatus.EN_PROCESO)),
    )
    areas = (queryset.values('area_operativa')
             .annotate(total=Count('id'), liquidados=Count('id', filter=Q(estatus=LIQUIDADO)))
             .order_by('-total'))
    return {
        'titulo': 'Tasa de liquidación',
        'resumen': [
            _dato('Tasa de liquidación', _porcentaje(conteo['liquidados'], conteo['total']), '%'),
            _dato('Liquidados', conteo['liquidados']),
            _dato('Abiertos', conteo['total'] - conteo['liquidados']),
            _dato('Pendientes', conteo['pendientes']),
            _dato('Asignados', conteo['asignados']),
            _dato('En proceso', conteo['en_proceso']),
        ],
        'desgloses': [{
            'titulo': 'Liquidación por área',
            'columnas': [_columna('Área'), _columna('Folios'), _columna('Liquidados'),
                         _columna('Abiertos'), _columna('Tasa', '%')],
            'filas': [[_area(fila['area_operativa']), fila['total'], fila['liquidados'],
                       fila['total'] - fila['liquidados'],
                       _porcentaje(fila['liquidados'], fila['total'])] for fila in areas],
        }],
        'folios': _folios_por_dilacion(queryset.filter(ABIERTO),
                                       'Folios abiertos con más días'),
    }


def _dilacion(queryset):
    umbral = settings.DILACION_UMBRAL_DIAS
    critico = settings.DILACION_UMBRAL_CRITICO_DIAS
    abiertos = queryset.filter(ABIERTO)
    conteo = abiertos.aggregate(
        total=Count('id'), promedio=Avg('dilacion_dias'), mayor=Max('dilacion_dias'),
        normales=Count('id', filter=Q(dilacion_dias__lt=umbral)),
        en_alerta=Count('id', filter=Q(dilacion_dias__gte=umbral, dilacion_dias__lt=critico)),
        criticos=Count('id', filter=Q(dilacion_dias__gte=critico)),
    )
    areas = (abiertos.values('area_operativa')
             .annotate(total=Count('id'), promedio=Avg('dilacion_dias'),
                       mayor=Max('dilacion_dias'),
                       en_dilacion=Count('id', filter=Q(dilacion_dias__gte=umbral)))
             .order_by('-mayor', '-total'))
    return {
        'titulo': 'Dilación de los folios abiertos',
        'resumen': [
            _dato('Dilación mayor', conteo['mayor'], 'd'),
            _dato('Dilación promedio', _redondear(conteo['promedio']), 'd'),
            _dato('Folios abiertos', conteo['total']),
            _dato(f'En dilación (≥ {umbral} d)', conteo['en_alerta'] + conteo['criticos']),
            _dato(f'Críticos (≥ {critico} d)', conteo['criticos']),
        ],
        'desgloses': [
            {
                'titulo': 'Folios abiertos por días de dilación',
                'columnas': [_columna('Rango'), _columna('Folios')],
                'filas': [
                    [f'Menos de {umbral} días', conteo['normales']],
                    [f'De {umbral} a {critico - 1} días', conteo['en_alerta']],
                    [f'{critico} días o más', conteo['criticos']],
                ],
            },
            {
                'titulo': 'Dilación por área',
                'columnas': [_columna('Área'), _columna('Abiertos'), _columna('En dilación'),
                             _columna('Promedio', 'd'), _columna('Mayor', 'd')],
                'filas': [[_area(fila['area_operativa']), fila['total'], fila['en_dilacion'],
                           _redondear(fila['promedio']), fila['mayor']] for fila in areas],
            },
        ],
        'folios': _folios_por_dilacion(abiertos, 'Folios con más días de dilación'),
    }


def _criticos(queryset):
    critico = settings.DILACION_UMBRAL_CRITICO_DIAS
    criticos = queryset.filter(ABIERTO, dilacion_dias__gte=critico)
    conteo = criticos.aggregate(
        total=Count('id'), mayor=Max('dilacion_dias'),
        sin_tecnico=Count('id', filter=Q(tecnico__isnull=True)),
        en_proceso=Count('id', filter=Q(estatus=Incidente.Estatus.EN_PROCESO)),
    )
    areas = (criticos.values('area_operativa')
             .annotate(total=Count('id'), mayor=Max('dilacion_dias'),
                       sin_tecnico=Count('id', filter=Q(tecnico__isnull=True)))
             .order_by('-total'))
    tecnicos = (criticos.filter(tecnico__isnull=False)
                .values('tecnico__first_name', 'tecnico__last_name', 'tecnico__expediente')
                .annotate(total=Count('id'), mayor=Max('dilacion_dias'))
                .order_by('-total')[:20])
    return {
        'titulo': f'Folios críticos (≥ {critico} días sin liquidar)',
        'resumen': [
            _dato('Folios críticos', conteo['total']),
            _dato('Dilación mayor', conteo['mayor'], 'd'),
            _dato('Sin técnico asignado', conteo['sin_tecnico']),
            _dato('En proceso', conteo['en_proceso']),
        ],
        'desgloses': [
            {
                'titulo': 'Críticos por área',
                'columnas': [_columna('Área'), _columna('Críticos'), _columna('Sin técnico'),
                             _columna('Mayor', 'd')],
                'filas': [[_area(fila['area_operativa']), fila['total'], fila['sin_tecnico'],
                           fila['mayor']] for fila in areas],
            },
            {
                'titulo': 'Críticos por técnico de planta externa',
                'columnas': [_columna('Técnico'), _columna('Críticos'), _columna('Mayor', 'd')],
                'filas': [[
                    f"{fila['tecnico__first_name']} {fila['tecnico__last_name']}".strip()
                    or fila['tecnico__expediente'],
                    fila['total'], fila['mayor'],
                ] for fila in tecnicos],
            },
        ],
        'folios': _folios_por_dilacion(criticos, 'Folios críticos'),
    }


def _sin_tecnico(queryset):
    sin_tecnico = queryset.filter(tecnico__isnull=True)
    abiertos = sin_tecnico.filter(ABIERTO)
    conteo = sin_tecnico.aggregate(
        total=Count('id'),
        abiertos=Count('id', filter=ABIERTO),
        liquidados=Count('id', filter=Q(estatus=LIQUIDADO)),
        sin_evaluador=Count('id', filter=ABIERTO & Q(evaluador__isnull=True)),
    )
    mayor = abiertos.aggregate(v=Max('dilacion_dias'))['v']
    areas = (abiertos.values('area_operativa')
             .annotate(total=Count('id'), mayor=Max('dilacion_dias'))
             .order_by('-total'))
    return {
        'titulo': 'Folios sin técnico asignado',
        'resumen': [
            _dato('Sin técnico', conteo['total']),
            _dato('Abiertos por despachar', conteo['abiertos']),
            _dato('Liquidados sin técnico', conteo['liquidados']),
            _dato('Tampoco tienen técnico de planta interna', conteo['sin_evaluador']),
            _dato('Dilación mayor', mayor, 'd'),
        ],
        'desgloses': [{
            'titulo': 'Abiertos sin técnico por área',
            'columnas': [_columna('Área'), _columna('Folios'), _columna('Mayor', 'd')],
            'filas': [[_area(fila['area_operativa']), fila['total'], fila['mayor']]
                      for fila in areas],
        }],
        'folios': _folios_por_dilacion(abiertos, 'Folios abiertos sin técnico'),
    }


INDICADORES = {
    'mttr': _mttr,
    'liquidacion': _liquidacion,
    'dilacion': _dilacion,
    'criticos': _criticos,
    'sin_tecnico': _sin_tecnico,
}


def detalle_de_indicador(indicador, queryset):
    """`queryset` trae los folios que el usuario puede ver, ya con los filtros de la consulta."""
    detalle = INDICADORES[indicador](queryset.order_by())
    detalle['indicador'] = indicador
    return detalle
