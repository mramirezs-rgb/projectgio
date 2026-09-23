from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import IncidenteViewSet, TecnicoListView, CentralListView

router = DefaultRouter()
router.register(r'incidentes', IncidenteViewSet, basename='incidente')

urlpatterns = [
    path('', include(router.urls)),
    path('tecnicos/', TecnicoListView.as_view(), name='tecnicos-list'),
    path('centrales/', CentralListView.as_view(), name='centrales-list'),
]