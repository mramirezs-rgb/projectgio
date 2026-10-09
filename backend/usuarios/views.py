from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from rest_framework import filters, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from gio_app.models import Incidente

from .permissions import EsAdmin
from .serializers import GIOTokenObtainPairSerializer, PerfilSerializer, UsuarioSerializer

UsuarioGIO = get_user_model()


class LoginView(TokenObtainPairView):
    serializer_class = GIOTokenObtainPairSerializer
    throttle_scope = 'login'


class RefreshView(TokenRefreshView):
    throttle_scope = 'login'


class MiPerfilView(APIView):
    def get(self, request):
        return Response(PerfilSerializer(request.user).data)


class CambiarPasswordView(APIView):
    def post(self, request):
        actual = request.data.get('password_actual') or ''
        nueva = request.data.get('password_nueva') or ''
        if not request.user.check_password(actual):
            return Response({'password_actual': ['La contraseña actual no es correcta.']},
                            status=status.HTTP_400_BAD_REQUEST)
        serializer = UsuarioSerializer(request.user, data={'password': nueva}, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'detail': 'Contraseña actualizada.'})


class UsuarioViewSet(viewsets.ModelViewSet):
    serializer_class = UsuarioSerializer
    permission_classes = [EsAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['expediente', 'username', 'first_name', 'last_name', 'email']
    ordering_fields = ['expediente', 'rol', 'date_joined', 'last_login']
    ordering = ['expediente']

    def get_queryset(self):
        return UsuarioGIO.objects.annotate(
            folios_asignados=Count(
                'incidentes_asignados',
                filter=~Q(incidentes_asignados__estatus=Incidente.Estatus.LIQUIDADO),
                distinct=True,
            )
        )

    def perform_destroy(self, instance):
        if instance.pk == self.request.user.pk:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'detail': 'No puede eliminar su propia cuenta.'})
        instance.is_active = False
        instance.save(update_fields=['is_active'])
