from rest_framework import serializers
from .models import Incidente

class IncidenteSerializer(serializers.ModelSerializer):
    # Alias de LECTURA para el frontend (no interfieren con la escritura)
    area = serializers.ReadOnlyField(source='area_operativa')
    dilacion = serializers.ReadOnlyField(source='dilacion_dias')
    estado_enlace = serializers.ReadOnlyField(source='estatus_qp')
    central_nombre = serializers.ReadOnlyField(source='central')
    
    # Campo calculado para mostrar el nombre completo del técnico en tablas y kanban
    tecnico_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Incidente
        fields = '__all__'

    def get_tecnico_nombre(self, obj):
        if obj.tecnico:
            nombre = f"{getattr(obj.tecnico, 'first_name', '')} {getattr(obj.tecnico, 'last_name', '')}".strip()
            return nombre if nombre else getattr(obj.tecnico, 'username', str(obj.tecnico))
        return "Sin Asignar"