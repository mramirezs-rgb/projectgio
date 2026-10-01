from rest_framework import viewsets, filters, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django_filters import rest_framework as django_filters
from django.contrib.auth import get_user_model
from .models import Incidente
from .serializers import IncidenteSerializer

User = get_user_model()


class IncidenteFilter(django_filters.FilterSet):
    tecnico_expediente = django_filters.CharFilter(field_name='tecnico__username')
    folio = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = Incidente
        fields = ['tecnico', 'evaluador', 'central', 'estatus_io', 'estatus_qp', 'area_operativa']


class IncidenteViewSet(viewsets.ModelViewSet):
    serializer_class = IncidenteSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [django_filters.DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = IncidenteFilter
    search_fields = ['folio', 'incidente', 'empresa', 'referencia', 'cope', 'ips']
    ordering_fields = ['fecha_ingreso', 'dilacion_dias', 'id']

    def get_queryset(self):
        user = self.request.user
        
        # Si la petición no viene autenticada, no se retornan datos
        if not user or not user.is_authenticated:
            return Incidente.objects.none()

        queryset = Incidente.objects.all().select_related('tecnico', 'evaluador')

        # 1. TÉCNICO: Solo ve sus folios asignados
        if user.rol == 'TECNICO':
            return queryset.filter(tecnico=user)

        # 2. PLANTA INTERNA - EVALUADOR (Rango Bajo): Solo ve los folios asignados a él para evaluación/liquidación
        elif user.rol == 'PI_EVALUADOR':
            return queryset.filter(evaluador=user)

        # 3. PLANTA INTERNA - SUBGERENCIA y GERENCIA/ADMIN: Ven todo el catálogo de folios
        elif user.rol in ['PI_SUB', 'ADMIN'] or user.is_superuser:
            return queryset

        return queryset.none()

    def perform_create(self, serializer):
        serializer.save(actualizado_por_gio=True)

    def perform_update(self, serializer):
        serializer.save(actualizado_por_gio=True)


class TecnicoListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Obtiene todos los usuarios registrados con rol TECNICO para los menús desplegables de asignación
        tecnicos = User.objects.filter(rol='TECNICO')
        data = [
            {
                'id': t.id,
                'nombre': f"{t.first_name} {t.last_name}".strip() or t.username or t.expediente
            }
            for t in tecnicos
        ]
        return Response(data)


class CentralListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        raw_centrales = Incidente.objects.exclude(
            central__isnull=True
        ).values_list('central', flat=True)
        
        unicas = sorted(list({c.strip() for c in raw_centrales if c and str(c).strip()}))
        data = [{'id': c, 'nombre': c} for c in unicas]
        return Response(data)

class EvaluadorListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        evaluadores = User.objects.filter(rol='PI_EVALUADOR')
        data = [
            {
                'id': e.id,
                'nombre': f"{e.first_name} {e.last_name}".strip() or getattr(e, 'username', '') or getattr(e, 'expediente', '') or f"Evaluador {e.id}"
            }
            for e in evaluadores
        ]
        return Response(data)