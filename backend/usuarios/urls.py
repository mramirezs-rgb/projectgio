from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CambiarPasswordView,
    CorreoRecuperacionView,
    LoginView,
    MiPerfilView,
    RecuperarPasswordView,
    RefreshView,
    RestablecerPasswordView,
    UsuarioViewSet,
)

router = DefaultRouter()
router.register(r'usuarios', UsuarioViewSet, basename='usuario')

urlpatterns = [
    path('auth/login/', LoginView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', RefreshView.as_view(), name='token_refresh'),
    path('auth/me/', MiPerfilView.as_view(), name='mi-perfil'),
    path('auth/password/', CambiarPasswordView.as_view(), name='cambiar-password'),
    path('auth/correo/', CorreoRecuperacionView.as_view(), name='correo-recuperacion'),
    path('auth/recuperar/', RecuperarPasswordView.as_view(), name='recuperar-password'),
    path('auth/restablecer/', RestablecerPasswordView.as_view(), name='restablecer-password'),
    path('', include(router.urls)),
]
