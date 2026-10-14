from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AreaListView,
    CatalogosView,
    CentralListView,
    EvaluadorListView,
    EvidenciaViewSet,
    IncidenteViewSet,
    RepartoTurnosView,
    TecnicoListView,
    TurnosView,
)

router = DefaultRouter()
router.register(r'incidentes', IncidenteViewSet, basename='incidente')
router.register(r'evidencias', EvidenciaViewSet, basename='evidencia')

urlpatterns = [
    path('tecnicos/', TecnicoListView.as_view(), name='tecnicos-list'),
    path('evaluadores/', EvaluadorListView.as_view(), name='evaluadores-list'),
    path('centrales/', CentralListView.as_view(), name='centrales-list'),
    path('areas/', AreaListView.as_view(), name='areas-list'),
    path('catalogos/', CatalogosView.as_view(), name='catalogos'),
    path('turnos/', TurnosView.as_view(), name='turnos'),
    path('turnos/repartir/', RepartoTurnosView.as_view(), name='turnos-repartir'),
    path('', include(router.urls)),
]
