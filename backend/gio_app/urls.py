from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect  # Importar redirect
from rest_framework.routers import DefaultRouter
from gio_app.views import IncidenteViewSet, TecnicoViewSet, CentralViewSet

router = DefaultRouter()
router.register(r'incidentes', IncidenteViewSet, basename='incidente')
router.register(r'tecnicos', TecnicoViewSet, basename='tecnico')
router.register(r'centrales', CentralViewSet, basename='central')

urlpatterns = [
    path('', lambda request: redirect('api/', permanent=False)),  # Redirige / hacia /api/
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
]