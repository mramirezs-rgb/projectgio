import uuid
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def ruta_evidencia(instance, filename):
    extension = (filename.rsplit('.', 1)[-1] or 'jpg').lower()[:5]
    folio = (instance.incidente.folio or 'sin-folio').replace('/', '-')
    fecha = timezone.now()
    return f'evidencias/{fecha:%Y/%m}/{folio}/{uuid.uuid4().hex}.{extension}'


class Incidente(models.Model):
    class Estatus(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        ASIGNADO = 'ASIGNADO', 'Asignado'
        EN_PROCESO = 'EN_PROCESO', 'En proceso'
        LIQUIDADO = 'LIQUIDADO', 'Liquidado'

    class CodigoFallo(models.TextChoices):
        F1 = 'F1', 'F1 — Familia de falla'
        COD4 = 'COD4', 'COD4 — Causa raíz'
        CARLS = 'CARLS', 'CARLS — Diagnóstico'
        COD5 = 'COD5', 'COD5 — Acción correctiva'

    class EstadoEnlace(models.TextChoices):
        UP = 'UP', 'UP (en línea)'
        DOWN = 'DOWN', 'DOWN (caído)'
        DESCONOCIDO = 'DESCONOCIDO', 'Desconocido'

    class Sincronizacion(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente de exportar'
        EXPORTADO = 'EXPORTADO', 'Exportado a SISA'
        ERROR = 'ERROR', 'Error de sincronización'

    TRANSICIONES = {
        Estatus.PENDIENTE: {Estatus.ASIGNADO, Estatus.EN_PROCESO},
        Estatus.ASIGNADO: {Estatus.PENDIENTE, Estatus.EN_PROCESO},
        Estatus.EN_PROCESO: {Estatus.ASIGNADO, Estatus.LIQUIDADO},
        Estatus.LIQUIDADO: {Estatus.EN_PROCESO},
    }

    folio = models.CharField(max_length=50, unique=True, db_index=True)
    incidente = models.CharField(max_length=50, blank=True, default='')
    referencia = models.CharField(max_length=50, blank=True, default='')
    empresa = models.CharField(max_length=150, blank=True, default='')
    tipo_servicio = models.CharField(max_length=50, blank=True, default='')

    estatus = models.CharField(max_length=15, choices=Estatus.choices,
                               default=Estatus.PENDIENTE, db_index=True)
    codigo_fallo = models.CharField(max_length=10, choices=CodigoFallo.choices, blank=True, default='')
    estado_enlace = models.CharField(max_length=15, choices=EstadoEnlace.choices,
                                     default=EstadoEnlace.DESCONOCIDO)

    fecha_apertura = models.DateTimeField(default=timezone.now, db_index=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    fecha_ingreso = models.DateTimeField(null=True, blank=True)
    dilacion_dias = models.IntegerField(default=0, db_index=True)

    area_operativa = models.CharField(max_length=100, blank=True, default='', db_index=True)
    central = models.CharField(max_length=100, blank=True, default='', db_index=True)
    cope = models.CharField(max_length=100, blank=True, default='')
    ctro_trabajo = models.CharField(max_length=100, blank=True, default='')
    oqu = models.CharField(max_length=100, blank=True, default='')

    tecnico = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='incidentes_asignados',
    )
    evaluador = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='incidentes_evaluados',
    )
    telefono_tecnico = models.CharField(max_length=20, blank=True, default='')

    descripcion = models.TextField(blank=True, default='')
    diagnostico_final = models.TextField(blank=True, default='')
    obs_usuario = models.TextField(blank=True, default='')
    observaciones_sisa = models.TextField(blank=True, default='')

    dir_pta_a = models.TextField(blank=True, default='')
    punta_a = models.CharField(max_length=100, blank=True, default='')
    ips = models.CharField(max_length=50, blank=True, default='')
    dslam = models.CharField(max_length=100, blank=True, default='')
    red_secundaria = models.CharField(max_length=100, blank=True, default='')

    desc_f1 = models.CharField(max_length=255, blank=True, default='')
    desc_cod4 = models.CharField(max_length=255, blank=True, default='')
    desc_carls = models.CharField(max_length=255, blank=True, default='')
    desc_cod5 = models.CharField(max_length=255, blank=True, default='')
    cve_liq = models.CharField(max_length=50, blank=True, default='')
    desc_liq = models.TextField(blank=True, default='')
    leyenda_sisa = models.CharField(max_length=100, blank=True, default='')

    exportado_sisa = models.BooleanField(default=False, db_index=True)
    estado_sincronizacion = models.CharField(max_length=30, choices=Sincronizacion.choices,
                                             default=Sincronizacion.PENDIENTE)
    ultimo_intento_sinc = models.DateTimeField(null=True, blank=True)
    error_sincronizacion = models.TextField(blank=True, default='')
    origen_sisa = models.CharField(max_length=120, blank=True, default='')

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'incidentes_red'
        ordering = ['-fecha_apertura', '-id']
        verbose_name = 'incidente'
        verbose_name_plural = 'incidentes'
        indexes = [
            models.Index(fields=['estatus', 'exportado_sisa']),
            models.Index(fields=['tecnico', 'estatus']),
            models.Index(fields=['evaluador', 'estatus']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(estatus='LIQUIDADO', fecha_cierre__isnull=False)
                | ~models.Q(estatus='LIQUIDADO'),
                name='liquidado_requiere_fecha_cierre',
            ),
        ]

    def __str__(self):
        return f'{self.folio} — {self.empresa or "sin empresa"}'

    def clean(self):
        if self.fecha_cierre and self.fecha_cierre < self.fecha_apertura:
            raise ValidationError({'fecha_cierre': 'El cierre no puede ser anterior a la apertura.'})

    def save(self, *args, **kwargs):
        self.folio = (self.folio or '').strip()
        self.area_operativa = (self.area_operativa or '').strip().upper()
        self.central = (self.central or '').strip().upper()

        if self.estatus == self.Estatus.LIQUIDADO:
            if not self.fecha_cierre:
                self.fecha_cierre = timezone.now()
        else:
            self.fecha_cierre = None
            self.exportado_sisa = False
            self.estado_sincronizacion = self.Sincronizacion.PENDIENTE

        self.dilacion_dias = self.calcular_dilacion()
        return super().save(*args, **kwargs)

    def calcular_dilacion(self):
        referencia = self.fecha_cierre or timezone.now()
        if not self.fecha_apertura:
            return 0
        return max(0, (referencia - self.fecha_apertura).days)

    @property
    def mttr_horas(self):
        if not self.fecha_cierre or not self.fecha_apertura:
            return None
        return self._horas_entre(self.fecha_apertura, self.fecha_cierre)

    @property
    def horas_abierto(self):
        if not self.fecha_apertura:
            return Decimal('0.00')
        return self._horas_entre(self.fecha_apertura, self.fecha_cierre or timezone.now())

    @staticmethod
    def _horas_entre(inicio, fin):
        segundos = max(0.0, (fin - inicio).total_seconds())
        horas = Decimal(segundos) / Decimal(3600)
        return horas.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @property
    def semaforo(self):
        if self.estatus == self.Estatus.LIQUIDADO:
            return 'cerrado'
        dias = self.calcular_dilacion()
        if dias >= settings.DILACION_UMBRAL_CRITICO_DIAS:
            return 'critico'
        if dias >= settings.DILACION_UMBRAL_DIAS:
            return 'alerta'
        return 'normal'

    def transiciones_validas(self):
        return sorted(self.TRANSICIONES.get(self.estatus, set()))

    def puede_transicionar_a(self, nuevo_estatus):
        if nuevo_estatus == self.estatus:
            return True
        return nuevo_estatus in self.TRANSICIONES.get(self.estatus, set())


class EvidenciaIncidente(models.Model):
    incidente = models.ForeignKey(Incidente, on_delete=models.CASCADE, related_name='evidencias')
    imagen = models.ImageField(upload_to=ruta_evidencia)
    descripcion = models.CharField(max_length=255, blank=True, default='')
    coordenadas_gps = models.CharField(max_length=60, blank=True, default='')
    tamano_bytes = models.PositiveIntegerField(default=0)
    fecha_captura = models.DateTimeField(default=timezone.now)
    subido_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name='evidencias_subidas')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'incidentes_evidencias'
        ordering = ['-fecha_captura', '-id']
        verbose_name = 'evidencia'
        verbose_name_plural = 'evidencias'

    def __str__(self):
        return f'Evidencia {self.pk} — folio {self.incidente.folio}'

    def save(self, *args, **kwargs):
        if self.imagen and not self.tamano_bytes:
            self.tamano_bytes = getattr(self.imagen, 'size', 0) or 0
        return super().save(*args, **kwargs)


class BitacoraIncidente(models.Model):
    class Accion(models.TextChoices):
        CREACION = 'CREACION', 'Creación'
        ACTUALIZACION = 'ACTUALIZACION', 'Actualización'
        CAMBIO_ESTATUS = 'CAMBIO_ESTATUS', 'Cambio de estatus'
        ASIGNACION = 'ASIGNACION', 'Asignación'
        LIQUIDACION = 'LIQUIDACION', 'Liquidación'
        EVIDENCIA = 'EVIDENCIA', 'Carga de evidencia'
        INGESTA = 'INGESTA', 'Ingesta SISA'
        EXPORTACION = 'EXPORTACION', 'Exportación SISA'

    incidente = models.ForeignKey(Incidente, on_delete=models.CASCADE, related_name='bitacora')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                null=True, blank=True, related_name='acciones_bitacora')
    accion = models.CharField(max_length=20, choices=Accion.choices)
    campo = models.CharField(max_length=60, blank=True, default='')
    valor_anterior = models.TextField(blank=True, default='')
    valor_nuevo = models.TextField(blank=True, default='')
    detalle = models.CharField(max_length=255, blank=True, default='')
    registrado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'incidentes_bitacora'
        ordering = ['-registrado_en', '-id']
        verbose_name = 'registro de bitácora'
        verbose_name_plural = 'bitácora de incidentes'

    def __str__(self):
        return f'{self.registrado_en:%Y-%m-%d %H:%M} — {self.incidente_id} — {self.accion}'

    @classmethod
    def registrar(cls, incidente, usuario, accion, campo='', anterior='', nuevo='', detalle=''):
        return cls.objects.create(
            incidente=incidente,
            usuario=usuario if (usuario and usuario.is_authenticated) else None,
            accion=accion,
            campo=campo or '',
            valor_anterior='' if anterior is None else str(anterior),
            valor_nuevo='' if nuevo is None else str(nuevo),
            detalle=detalle or '',
        )
