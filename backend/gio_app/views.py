from rest_framework import viewsets, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny  # Usar AllowAny si quieres omitir el token en pruebas
from django_filters import rest_framework as django_filters
from .models import Incidente
from .serializers import IncidenteSerializer


class IncidenteFilter(django_filters.FilterSet):
    tecnico_expediente = django_filters.CharFilter(field_name='tecnico__username')

    class Meta:
        model = Incidente
        fields = ['tecnico', 'central', 'estatus_io', 'estatus_qp', 'area_operativa']


class IncidenteViewSet(viewsets.ModelViewSet):
    queryset = Incidente.objects.all()
    serializer_class = IncidenteSerializer
    permission_classes = [AllowAny]  # Cambiar a [IsAuthenticated] cuando requieras JWT obligatorio
    filter_backends = [django_filters.DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = IncidenteFilter
    search_fields = ['folio', 'incidente', 'empresa', 'referencia', 'cope', 'ips']
    ordering_fields = ['fecha_ingreso', 'dilacion_dias', 'id']

    def perform_create(self, serializer):
        serializer.save(actualizado_por_gio=True)

    def perform_update(self, serializer):
        serializer.save(actualizado_por_gio=True)


class TecnicoListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        incidentes = Incidente.objects.filter(tecnico__isnull=False).select_related('tecnico')
        tecnicos_dict = {}
        for inc in incidentes:
            if inc.tecnico and inc.tecnico.id not in tecnicos_dict:
                nombre_tecnico = getattr(inc.tecnico, 'get_full_name', lambda: '')() or str(inc.tecnico)
                tecnicos_dict[inc.tecnico.id] = {
                    'id': inc.tecnico.id,
                    'nombre': nombre_tecnico
                }
        
        data = sorted(list(tecnicos_dict.values()), key=lambda x: x['nombre'])
        return Response(data)


class CentralListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        raw_centrales = Incidente.objects.exclude(
            central__isnull=True
        ).values_list('central', flat=True)
        
        unicas = sorted(list({c.strip() for c in raw_centrales if c and str(c).strip()}))
        data = [{'id': c, 'nombre': c} for c in unicas]
        return Response(data)