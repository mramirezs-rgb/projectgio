from rest_framework import serializers
from .models import Incidente

class IncidenteSerializer(serializers.ModelSerializer):
    area = serializers.CharField(source='area_operativa', read_only=True)
    dilacion = serializers.IntegerField(source='dilacion_dias', read_only=True)
    tecnico = serializers.CharField(source='tecnico_asignado', read_only=True)
    tecnico_nombre = serializers.CharField(source='tecnico_asignado', read_only=True)
    central_nombre = serializers.CharField(source='central', read_only=True)

    class Meta:
        model = Incidente
        fields = '__all__'