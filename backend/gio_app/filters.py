from django_filters import rest_framework as filtros

from .models import Incidente


class IncidenteFilter(filtros.FilterSet):
    folio = filtros.CharFilter(lookup_expr='icontains')
    empresa = filtros.CharFilter(lookup_expr='icontains')
    central = filtros.CharFilter(lookup_expr='iexact')
    area_operativa = filtros.CharFilter(lookup_expr='iexact')
    tecnico_expediente = filtros.CharFilter(field_name='tecnico__expediente', lookup_expr='iexact')
    evaluador_expediente = filtros.CharFilter(field_name='evaluador__expediente', lookup_expr='iexact')
    sin_tecnico = filtros.BooleanFilter(field_name='tecnico', lookup_expr='isnull')
    sin_evaluador = filtros.BooleanFilter(field_name='evaluador', lookup_expr='isnull')
    dilacion_min = filtros.NumberFilter(field_name='dilacion_dias', lookup_expr='gte')
    dilacion_max = filtros.NumberFilter(field_name='dilacion_dias', lookup_expr='lte')
    abierto_desde = filtros.DateTimeFilter(field_name='fecha_apertura', lookup_expr='gte')
    abierto_hasta = filtros.DateTimeFilter(field_name='fecha_apertura', lookup_expr='lte')
    estatus = filtros.MultipleChoiceFilter(choices=Incidente.Estatus.choices)

    class Meta:
        model = Incidente
        fields = [
            'estatus', 'codigo_fallo', 'estado_enlace', 'tecnico', 'evaluador',
            'central', 'area_operativa', 'cope', 'tipo_servicio', 'exportado_sisa',
        ]
