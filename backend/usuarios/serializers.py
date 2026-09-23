# usuarios/serializers.py
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = {
            'id': self.user.id,
            'expediente': self.user.expediente,
            'username': self.user.username,
            'nombre': self.user.get_full_name() or self.user.username,
            'email': self.user.email,
            'rol': getattr(self.user, 'rol', 'PI'),
            'area_operativa': getattr(self.user, 'area_operativa', ''),
        }
        return data