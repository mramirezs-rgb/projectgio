from rest_framework import serializers
from .models import Incidente

class IncidenteSerializer(serializers.ModelSerializer):
    area = serializers.ReadOnlyField(source='area_operativa')
    dilacion = serializers.ReadOnlyField(source='dilacion_dias')
    estado_enlace = serializers.ReadOnlyField(source='estatus_qp')
    central_nombre = serializers.ReadOnlyField(source='central')
    
    tecnico_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Incidente
        fields = '__all__'

    def get_tecnico_nombre(self, obj):
        if not obj.tecnico:
            return "Sin Asignar"
        
        nombre = f"{getattr(obj.tecnico, 'first_name', '')} {getattr(obj.tecnico, 'last_name', '')}".strip()
        
        if nombre:
            return nombre
        elif getattr(obj.tecnico, 'username', None):
            return obj.tecnico.username
        else:
            return "Sin Asignar"