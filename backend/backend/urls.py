from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from gio_app.views import IncidenteViewSet, TecnicoListView, CentralListView

router = DefaultRouter()
router.register(r'incidentes', IncidenteViewSet, basename='incidente')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/tecnicos/', TecnicoListView.as_view(), name='tecnicos-list'),
    path('api/centrales/', CentralListView.as_view(), name='centrales-list'),
    path('api/', include(router.urls)),
]