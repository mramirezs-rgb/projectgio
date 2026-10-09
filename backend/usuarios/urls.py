from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CambiarPasswordView, LoginView, MiPerfilView, RefreshView, UsuarioViewSet

router = DefaultRouter()
router.register(r'usuarios', UsuarioViewSet, basename='usuario')

urlpatterns = [
    path('auth/login/', LoginView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', RefreshView.as_view(), name='token_refresh'),
    path('auth/me/', MiPerfilView.as_view(), name='mi-perfil'),
    path('auth/password/', CambiarPasswordView.as_view(), name='cambiar-password'),
    path('', include(router.urls)),
]
