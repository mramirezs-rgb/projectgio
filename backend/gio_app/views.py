from rest_framework import viewsets, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from django_filters import rest_framework as django_filters
from .models import Incidente
from .serializers import IncidenteSerializer

class IncidenteFilter(django_filters.FilterSet):
    tecnico = django_filters.CharFilter(field_name='tecnico_asignado', lookup_expr='icontains')
    central = django_filters.CharFilter(field_name='central', lookup_expr='icontains')
    estatus = django_filters.CharFilter(field_name='estatus_io', lookup_expr='icontains')

    class Meta:
        model = Incidente
        fields = ['tecnico', 'central', 'estatus', 'tecnico_asignado', 'estatus_io']

class IncidenteViewSet(viewsets.ModelViewSet):
    queryset = Incidente.objects.all()
    serializer_class = IncidenteSerializer
    filter_backends = [django_filters.DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = IncidenteFilter
    search_fields = ['folio', 'incidente', 'empresa', 'referencia', 'cope', 'ips']
    ordering_fields = ['fecha_ingreso', 'dilacion_dias', 'id']

    def perform_create(self, serializer):
        serializer.save(actualizado_por_gio=True)

    def perform_update(self, serializer):
        serializer.save(actualizado_por_gio=True)

class TecnicoListView(APIView):
    def get(self, request):
        # Filtra nulos y cadenas vacías directamente en PostgreSQL y Python
        raw_tecnicos = Incidente.objects.exclude(
            tecnico_asignado__isnull=True
        ).values_list('tecnico_asignado', flat=True)
        
        unicos = sorted(list({t.strip() for t in raw_tecnicos if t and str(t).strip()}))
        data = [{'id': t, 'nombre': t} for t in unicos]
        return Response(data)

class CentralListView(APIView):
    def get(self, request):
        raw_centrales = Incidente.objects.exclude(
            central__isnull=True
        ).values_list('central', flat=True)
        
        unicas = sorted(list({c.strip() for c in raw_centrales if c and str(c).strip()}))
        data = [{'id': c, 'nombre': c} for c in unicas]
        return Response(data)