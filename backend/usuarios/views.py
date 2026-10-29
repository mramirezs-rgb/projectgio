import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as ErrorDeDjango
from django.db.models import Count, Q
from rest_framework import filters, serializers, status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from gio_app.models import Incidente

from .permissions import EsAdmin
from .recuperacion import enviar_correo_de_recuperacion, usuario_del_enlace
from .serializers import GIOTokenObtainPairSerializer, PerfilSerializer, UsuarioSerializer

UsuarioGIO = get_user_model()
log = logging.getLogger('gio.cuentas')

# La misma respuesta exista o no el expediente, para no revelar quién tiene cuenta.
MENSAJE_RECUPERACION = (
    'Si el expediente existe y tiene un correo registrado, le enviamos un enlace para crear una '
    'nueva contraseña. Revise también la carpeta de correo no deseado.'
)


def errores_de_password(nueva, usuario):
    """Mensajes de las reglas de contraseña (largo, comunes, solo números, parecida al nombre)."""
    if not nueva:
        return ['Escriba la nueva contraseña.']
    try:
        validate_password(nueva, user=usuario)
    except ErrorDeDjango as error:
        return list(error.messages)
    return []


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
        errores = errores_de_password(nueva, request.user)
        if not errores and nueva == actual:
            errores = ['La nueva contraseña debe ser distinta de la actual.']
        if errores:
            return Response({'password_nueva': errores}, status=status.HTTP_400_BAD_REQUEST)
        request.user.set_password(nueva)
        request.user.save(update_fields=['password'])
        return Response({'detail': 'Contraseña actualizada.'})


class CorreoRecuperacionView(APIView):
    """El propio usuario registra el correo al que le llegará el enlace si olvida su contraseña."""

    def post(self, request):
        if not request.user.check_password(request.data.get('password_actual') or ''):
            return Response({'password_actual': ['La contraseña actual no es correcta.']},
                            status=status.HTTP_400_BAD_REQUEST)
        campo = serializers.EmailField(allow_blank=True, error_messages={
            'invalid': 'Escriba un correo válido, por ejemplo nombre@empresa.com.mx.'})
        try:
            correo = campo.run_validation(request.data.get('email') or '')
        except serializers.ValidationError as error:
            return Response({'email': error.detail}, status=status.HTTP_400_BAD_REQUEST)
        request.user.email = UsuarioGIO.objects.normalize_email(correo)
        request.user.save(update_fields=['email'])
        return Response(PerfilSerializer(request.user).data)


class RecuperarPasswordView(APIView):
    """¿Olvidó su contraseña?: envía un enlace al correo registrado del expediente."""
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = 'recuperacion'

    def post(self, request):
        expediente = str(request.data.get('expediente') or '').strip()
        if not expediente:
            return Response({'expediente': ['Escriba su expediente.']},
                            status=status.HTTP_400_BAD_REQUEST)
        usuario = (UsuarioGIO.objects.filter(expediente__iexact=expediente, is_active=True)
                   .exclude(email='').first())
        if usuario:
            try:
                enviar_correo_de_recuperacion(usuario, request)
            except OSError:
                log.exception('No se pudo enviar el correo de recuperación a %s', usuario.expediente)
                return Response(
                    {'detail': 'No se pudo enviar el correo. Intente más tarde o pida el cambio de '
                               'contraseña a la Gerencia.'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE)
            log.info('Enlace de recuperación enviado a %s', usuario.expediente)
        return Response({'detail': MENSAJE_RECUPERACION})


class RestablecerPasswordView(APIView):
    """Crea la nueva contraseña con el enlace del correo; el enlace deja de servir al usarse."""
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = 'login'

    def post(self, request):
        usuario = usuario_del_enlace(str(request.data.get('uid') or ''),
                                     str(request.data.get('token') or ''))
        if not usuario:
            return Response(
                {'detail': 'El enlace no es válido o ya venció. Pida uno nuevo desde '
                           '"¿Olvidó su contraseña?".'},
                status=status.HTTP_400_BAD_REQUEST)
        nueva = request.data.get('password_nueva') or ''
        errores = errores_de_password(nueva, usuario)
        if errores:
            return Response({'password_nueva': errores}, status=status.HTTP_400_BAD_REQUEST)
        usuario.set_password(nueva)
        usuario.save(update_fields=['password'])
        log.info('Contraseña restablecida por correo para %s', usuario.expediente)
        return Response({'detail': 'Contraseña actualizada. Ya puede iniciar sesión.'})


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
