from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

UsuarioGIO = get_user_model()


class UsuarioSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(source='nombre_completo', read_only=True)
    rol_display = serializers.CharField(source='get_rol_display', read_only=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=False,
                                     style={'input_type': 'password'})
    folios_asignados = serializers.IntegerField(read_only=True)

    class Meta:
        model = UsuarioGIO
        fields = [
            'id', 'expediente', 'username', 'first_name', 'last_name', 'email',
            'nombre', 'rol', 'rol_display', 'area_operativa', 'telefono',
            'is_active', 'last_login', 'date_joined', 'password', 'folios_asignados',
        ]
        read_only_fields = ['id', 'last_login', 'date_joined']
        extra_kwargs = {'username': {'required': False}}

    def validate_expediente(self, value):
        return value.strip().upper()

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, datos):
        """Un técnico activo necesita un área; una baja siempre queda en el área de bajas."""
        actual = self.instance

        def valor(campo, omision):
            return datos.get(campo, getattr(actual, campo) if actual else omision)

        if not valor('is_active', True):
            datos['area_operativa'] = UsuarioGIO.Area.BAJA
            return datos
        con_area = valor('rol', UsuarioGIO.Rol.TECNICO) in UsuarioGIO.ROLES_CON_AREA
        area = valor('area_operativa', '')
        if area == UsuarioGIO.Area.BAJA:
            reactivacion = bool(actual and not actual.is_active
                                and 'area_operativa' not in datos)
            if reactivacion and not con_area:
                # Subgerencia y Gerencia no trabajan por zona: al volver quedan sin área.
                area = datos['area_operativa'] = ''
            else:
                raise serializers.ValidationError({'area_operativa': (
                    'Elija el área en la que trabajará el usuario al reactivarlo.'
                    if reactivacion else 'El área Baja es solo para usuarios dados de baja.')})
        if con_area and not area:
            raise serializers.ValidationError({
                'area_operativa': 'Los técnicos de planta externa e interna deben tener un área.'})
        return datos

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        if not password:
            raise serializers.ValidationError({'password': 'La contraseña es obligatoria al crear un usuario.'})
        return UsuarioGIO.objects.create_user(
            expediente=validated_data.pop('expediente'),
            password=password,
            **validated_data,
        )

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for campo, valor in validated_data.items():
            setattr(instance, campo, valor)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class PerfilSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(source='nombre_completo', read_only=True)
    rol_display = serializers.CharField(source='get_rol_display', read_only=True)
    permisos = serializers.SerializerMethodField()

    class Meta:
        model = UsuarioGIO
        fields = [
            'id', 'expediente', 'username', 'nombre', 'first_name', 'last_name',
            'email', 'rol', 'rol_display', 'area_operativa', 'telefono',
            'is_superuser', 'permisos',
        ]

    def get_permisos(self, obj):
        return {
            'vision_global': obj.tiene_vision_global,
            'asignar': obj.puede_asignar,
            'crear_folio': obj.puede_asignar,
            'gestionar_usuarios': obj.puede_gestionar_usuarios,
            'liquidar': obj.es_tecnico or obj.es_evaluador or obj.tiene_vision_global,
            'cargar_evidencia': obj.es_tecnico or obj.tiene_vision_global,
            'exportar': obj.tiene_vision_global,
        }


class GIOTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['rol'] = user.rol
        token['expediente'] = user.expediente
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = PerfilSerializer(self.user).data
        return data
