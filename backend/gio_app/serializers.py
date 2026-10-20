from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import BitacoraIncidente, EvidenciaIncidente, Incidente, MensajeFolio, TurnoEvaluador

UsuarioGIO = get_user_model()

FORMATOS_IMAGEN = ('JPEG', 'JPG', 'PNG', 'WEBP')

MAX_CARACTERES_MENSAJE = 2000


def validar_imagen(archivo):
    """Peso y formato de una foto de evidencia o del chat; el cliente ya la comprimió."""
    if archivo.size > settings.EVIDENCIA_MAX_BYTES:
        limite_kb = settings.EVIDENCIA_MAX_BYTES // 1024
        raise serializers.ValidationError(
            f'La imagen pesa {archivo.size // 1024} KB y el límite es {limite_kb} KB. '
            'Debe comprimirse antes de enviarse.'
        )
    formato = str(getattr(archivo.image, 'format', '') or '').upper()
    if formato not in FORMATOS_IMAGEN:
        raise serializers.ValidationError('Formato no admitido. Use JPEG, PNG o WebP.')
    return archivo


def url_de_imagen(campo, peticion):
    if not campo:
        return None
    return peticion.build_absolute_uri(campo.url) if peticion else campo.url


class EvidenciaIncidenteSerializer(serializers.ModelSerializer):
    imagen_url = serializers.SerializerMethodField()
    subido_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model = EvidenciaIncidente
        fields = ['id', 'incidente', 'imagen', 'imagen_url', 'descripcion', 'coordenadas_gps',
                  'tamano_bytes', 'fecha_captura', 'subido_por', 'subido_por_nombre', 'creado_en']
        read_only_fields = ['tamano_bytes', 'subido_por', 'creado_en', 'incidente']
        extra_kwargs = {'imagen': {'write_only': True}}

    def get_imagen_url(self, obj):
        return url_de_imagen(obj.imagen, self.context.get('request'))

    def get_subido_por_nombre(self, obj):
        return obj.subido_por.nombre_completo if obj.subido_por else 'Sin registro'

    def validate_imagen(self, archivo):
        return validar_imagen(archivo)


class BitacoraIncidenteSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.SerializerMethodField()
    accion_display = serializers.CharField(source='get_accion_display', read_only=True)

    class Meta:
        model = BitacoraIncidente
        fields = ['id', 'accion', 'accion_display', 'campo', 'valor_anterior', 'valor_nuevo',
                  'detalle', 'usuario', 'usuario_nombre', 'registrado_en']

    def get_usuario_nombre(self, obj):
        return obj.usuario.nombre_completo if obj.usuario else 'Sistema'


class MensajeFolioSerializer(serializers.ModelSerializer):
    texto = serializers.CharField(
        max_length=MAX_CARACTERES_MENSAJE, required=False, allow_blank=True,
        error_messages={
            'max_length': f'El mensaje admite hasta {MAX_CARACTERES_MENSAJE} caracteres.',
        },
    )
    imagen_url = serializers.SerializerMethodField()
    autor_nombre = serializers.SerializerMethodField()
    autor_rol = serializers.SerializerMethodField()

    class Meta:
        model = MensajeFolio
        fields = ['id', 'texto', 'imagen', 'imagen_url', 'autor', 'autor_nombre', 'autor_rol',
                  'creado_en']
        read_only_fields = ['autor', 'creado_en']
        extra_kwargs = {'imagen': {'write_only': True, 'required': False}}

    def get_imagen_url(self, obj):
        return url_de_imagen(obj.imagen, self.context.get('request'))

    def get_autor_nombre(self, obj):
        return obj.autor.nombre_completo if obj.autor else 'Usuario eliminado'

    def get_autor_rol(self, obj):
        return obj.autor.rol if obj.autor else ''

    def validate_imagen(self, archivo):
        return validar_imagen(archivo)

    def validate(self, datos):
        if not datos.get('texto') and not datos.get('imagen'):
            raise serializers.ValidationError({'texto': 'Escriba un mensaje o adjunte una foto.'})
        return datos


class PermisosFolioMixin:
    """Estado de liquidación calculado para el usuario que consulta el folio."""

    def _usuario(self):
        peticion = self.context.get('request')
        return peticion.user if peticion else None

    def get_bloqueado(self, obj):
        return obj.bloqueado_para(self._usuario())

    def get_puede_cancelar_liquidacion(self, obj):
        return obj.puede_cancelar_liquidacion(self._usuario())


class IncidenteSerializer(PermisosFolioMixin, serializers.ModelSerializer):
    tecnico_nombre = serializers.SerializerMethodField()
    evaluador_nombre = serializers.SerializerMethodField()
    estatus_display = serializers.CharField(source='get_estatus_display', read_only=True)
    mttr_horas = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    horas_abierto = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    semaforo = serializers.CharField(read_only=True)
    transiciones_validas = serializers.ListField(child=serializers.CharField(), read_only=True)
    evidencias = EvidenciaIncidenteSerializer(many=True, read_only=True)
    total_evidencias = serializers.IntegerField(source='evidencias.count', read_only=True)
    bloqueado = serializers.SerializerMethodField()
    puede_cancelar_liquidacion = serializers.SerializerMethodField()

    class Meta:
        model = Incidente
        fields = [
            'id', 'folio', 'incidente', 'referencia', 'empresa', 'tipo_servicio',
            'estatus', 'estatus_display', 'transiciones_validas', 'codigo_fallo', 'estado_enlace',
            'fecha_apertura', 'fecha_cierre', 'fecha_ingreso', 'dilacion_dias', 'semaforo',
            'mttr_horas', 'horas_abierto', 'bloqueado', 'puede_cancelar_liquidacion',
            'area_operativa', 'central', 'cope', 'ctro_trabajo', 'oqu',
            'tecnico', 'tecnico_nombre', 'evaluador', 'evaluador_nombre', 'telefono_tecnico',
            'descripcion', 'diagnostico_final', 'obs_usuario', 'observaciones_sisa',
            'dir_pta_a', 'punta_a', 'ips', 'dslam', 'red_secundaria',
            'desc_f1', 'desc_cod4', 'desc_carls', 'desc_cod5', 'cve_liq', 'desc_liq',
            'leyenda_sisa', 'exportado_sisa', 'estado_sincronizacion', 'origen_sisa',
            'evidencias', 'total_evidencias', 'creado_en', 'actualizado_en',
        ]
        read_only_fields = [
            'fecha_cierre', 'dilacion_dias', 'exportado_sisa', 'estado_sincronizacion',
            'origen_sisa', 'creado_en', 'actualizado_en',
        ]

    def get_tecnico_nombre(self, obj):
        return obj.tecnico.nombre_completo if obj.tecnico else 'Sin asignar'

    def get_evaluador_nombre(self, obj):
        return obj.evaluador.nombre_completo if obj.evaluador else 'Sin asignar'

    def validate_folio(self, valor):
        valor = (valor or '').strip()
        if not valor:
            raise serializers.ValidationError('El folio es obligatorio.')
        return valor

    def validate_tecnico(self, usuario):
        if usuario and not usuario.es_tecnico:
            raise serializers.ValidationError(
                'El usuario seleccionado no es técnico de planta externa.')
        return usuario

    def validate_evaluador(self, usuario):
        if usuario and not (usuario.es_evaluador or usuario.tiene_vision_global):
            raise serializers.ValidationError(
                'El usuario seleccionado no es técnico de planta interna.')
        return usuario

    def validate(self, datos):
        instancia = self.instance
        nuevo_estatus = datos.get('estatus', instancia.estatus if instancia else Incidente.Estatus.PENDIENTE)

        if instancia and not instancia.puede_transicionar_a(nuevo_estatus):
            permitidas = ', '.join(instancia.transiciones_validas()) or 'ninguna'
            raise serializers.ValidationError({
                'estatus': f'Transición no permitida desde {instancia.estatus}. Permitidas: {permitidas}.'
            })

        tecnico = datos.get('tecnico', instancia.tecnico if instancia else None)
        if nuevo_estatus in (Incidente.Estatus.ASIGNADO, Incidente.Estatus.EN_PROCESO) and not tecnico:
            raise serializers.ValidationError({
                'tecnico': 'Debe asignarse un técnico antes de pasar el folio a ASIGNADO o EN_PROCESO.'
            })

        if nuevo_estatus == Incidente.Estatus.LIQUIDADO:
            diagnostico = datos.get('diagnostico_final',
                                    instancia.diagnostico_final if instancia else '')
            if not (diagnostico or '').strip():
                raise serializers.ValidationError({
                    'diagnostico_final': 'El diagnóstico final es obligatorio para liquidar el folio.'
                })
        return datos


class IncidenteListaSerializer(PermisosFolioMixin, serializers.ModelSerializer):
    tecnico_nombre = serializers.SerializerMethodField()
    evaluador_nombre = serializers.SerializerMethodField()
    estatus_display = serializers.CharField(source='get_estatus_display', read_only=True)
    mttr_horas = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    horas_abierto = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    semaforo = serializers.CharField(read_only=True)
    total_evidencias = serializers.IntegerField(source='evidencias.count', read_only=True)
    bloqueado = serializers.SerializerMethodField()
    puede_cancelar_liquidacion = serializers.SerializerMethodField()

    class Meta:
        model = Incidente
        fields = [
            'id', 'folio', 'referencia', 'empresa', 'tipo_servicio', 'estatus', 'estatus_display',
            'codigo_fallo', 'estado_enlace', 'fecha_apertura', 'fecha_cierre', 'dilacion_dias',
            'semaforo', 'mttr_horas', 'horas_abierto', 'bloqueado', 'puede_cancelar_liquidacion',
            'area_operativa', 'central', 'tecnico', 'tecnico_nombre', 'evaluador',
            'evaluador_nombre', 'dir_pta_a', 'ips', 'telefono_tecnico', 'descripcion', 'desc_f1',
            'diagnostico_final', 'cve_liq', 'desc_liq', 'total_evidencias', 'exportado_sisa',
        ]

    def get_tecnico_nombre(self, obj):
        return obj.tecnico.nombre_completo if obj.tecnico else 'Sin asignar'

    def get_evaluador_nombre(self, obj):
        return obj.evaluador.nombre_completo if obj.evaluador else 'Sin asignar'


CAMPOS_EDITABLES_TECNICO = (
    'estatus', 'diagnostico_final', 'codigo_fallo', 'estado_enlace',
    'desc_cod4', 'desc_carls', 'desc_cod5', 'cve_liq', 'desc_liq',
)

CAMPOS_EDITABLES_EVALUADOR = CAMPOS_EDITABLES_TECNICO + (
    'descripcion', 'observaciones_sisa', 'obs_usuario', 'desc_f1',
    'ips', 'dslam', 'red_secundaria', 'leyenda_sisa', 'tecnico', 'fecha_apertura',
)


def _solo_lectura_excepto(editables):
    declarados = {
        'tecnico_nombre', 'evaluador_nombre', 'estatus_display', 'mttr_horas', 'horas_abierto',
        'semaforo', 'transiciones_validas', 'evidencias', 'total_evidencias',
        'bloqueado', 'puede_cancelar_liquidacion',
    }
    return [
        campo for campo in IncidenteSerializer.Meta.fields
        if campo not in editables and campo not in declarados
    ]


class IncidenteTecnicoSerializer(IncidenteSerializer):
    class Meta(IncidenteSerializer.Meta):
        read_only_fields = _solo_lectura_excepto(CAMPOS_EDITABLES_TECNICO)


class IncidenteEvaluadorSerializer(IncidenteSerializer):
    class Meta(IncidenteSerializer.Meta):
        read_only_fields = _solo_lectura_excepto(CAMPOS_EDITABLES_EVALUADOR)


class AsignacionMasivaSerializer(serializers.Serializer):
    folios = serializers.ListField(child=serializers.CharField(), allow_empty=False, max_length=500)
    tecnico = serializers.PrimaryKeyRelatedField(
        queryset=UsuarioGIO.objects.filter(rol=UsuarioGIO.Rol.TECNICO, is_active=True),
        required=False, allow_null=True,
    )
    evaluador = serializers.PrimaryKeyRelatedField(
        queryset=UsuarioGIO.objects.filter(rol=UsuarioGIO.Rol.PI_EVALUADOR, is_active=True),
        required=False, allow_null=True,
    )

    def validate(self, datos):
        if 'tecnico' not in datos and 'evaluador' not in datos:
            raise serializers.ValidationError('Indique al menos un técnico o un evaluador.')
        return datos


class CatalogoSerializer(serializers.Serializer):
    id = serializers.CharField()
    nombre = serializers.CharField()


class TurnoEvaluadorSerializer(serializers.ModelSerializer):
    evaluador_nombre = serializers.CharField(source='evaluador.nombre_completo', read_only=True)
    evaluador_expediente = serializers.CharField(source='evaluador.expediente', read_only=True)
    area_operativa = serializers.CharField(source='evaluador.area_operativa', read_only=True)
    hora_inicio = serializers.TimeField(format='%H:%M')
    hora_fin = serializers.TimeField(format='%H:%M')
    cruza_medianoche = serializers.BooleanField(read_only=True)

    class Meta:
        model = TurnoEvaluador
        fields = ['id', 'fecha', 'hora_inicio', 'hora_fin', 'cruza_medianoche', 'evaluador',
                  'evaluador_nombre', 'evaluador_expediente', 'area_operativa']


MAX_DIAS_PROGRAMACION = 62


class HorarioDiaSerializer(serializers.Serializer):
    """Un día de la semana en la programación: horario o descanso."""
    hora_inicio = serializers.TimeField(required=False)
    hora_fin = serializers.TimeField(required=False)
    descanso = serializers.BooleanField(required=False, default=False)

    def validate(self, datos):
        if datos.get('descanso'):
            return {'descanso': True}
        inicio, fin = datos.get('hora_inicio'), datos.get('hora_fin')
        if inicio is None or fin is None:
            raise serializers.ValidationError('Indique hora de inicio y de fin, o marque descanso.')
        if inicio == fin:
            raise serializers.ValidationError('La hora de inicio y la de fin no pueden ser iguales.')
        return {'hora_inicio': inicio, 'hora_fin': fin}


class ProgramarTurnosSerializer(serializers.Serializer):
    evaluadores = serializers.PrimaryKeyRelatedField(
        queryset=UsuarioGIO.objects.filter(rol=UsuarioGIO.Rol.PI_EVALUADOR, is_active=True),
        many=True, allow_empty=False,
    )
    desde = serializers.DateField()
    hasta = serializers.DateField()
    # De lunes a domingo; null deja ese día sin cambios.
    horarios = serializers.ListField(
        child=HorarioDiaSerializer(allow_null=True), min_length=7, max_length=7,
    )

    def validate(self, datos):
        if datos['hasta'] < datos['desde']:
            raise serializers.ValidationError({'hasta': 'La fecha final es anterior a la inicial.'})
        if (datos['hasta'] - datos['desde']).days >= MAX_DIAS_PROGRAMACION:
            raise serializers.ValidationError(
                {'hasta': f'Programe como máximo {MAX_DIAS_PROGRAMACION} días a la vez.'})
        if all(horario is None for horario in datos['horarios']):
            raise serializers.ValidationError({'horarios': 'No hay ningún día por modificar.'})
        return datos


class RepartoTurnosSerializer(serializers.Serializer):
    fecha = serializers.DateField()
    limite = serializers.IntegerField(min_value=0, required=False, default=0)
