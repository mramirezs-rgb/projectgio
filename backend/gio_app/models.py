from django.db import models
from django.conf import settings

class Incidente(models.Model):
    id = models.BigAutoField(primary_key=True)
    incidente = models.CharField(max_length=50, blank=True, null=True)
    folio = models.CharField(unique=True, max_length=50)
    referencia = models.CharField(max_length=50, blank=True, null=True)
    obs_usuario = models.TextField(blank=True, null=True)
    empresa = models.CharField(max_length=150, blank=True, null=True)
    area_operativa = models.CharField(max_length=100, blank=True, null=True)
    dilacion_dias = models.IntegerField(blank=True, null=True)
    central = models.CharField(max_length=100, help_text="Nombre de la central (Ej. Puebla Centro)")
    
    tipo_servicio = models.CharField(max_length=50, blank=True, null=True)
    dir_pta_a = models.TextField(blank=True, null=True)
    punta_a = models.CharField(max_length=100, blank=True, null=True)
    ctro_trabajo = models.CharField(max_length=100, blank=True, null=True)
    desc_f1 = models.CharField(max_length=255, blank=True, null=True)
    observaciones_sisa = models.TextField(blank=True, null=True)
    desc_cod4 = models.CharField(max_length=255, blank=True, null=True)
    desc_carls = models.CharField(max_length=255, blank=True, null=True)
    desc_cod5 = models.CharField(max_length=255, blank=True, null=True)
    tecnico = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incidentes_asignados'
    )
    telefono_tecnico = models.CharField(max_length=20, blank=True, null=True)
    ips = models.CharField(max_length=50, blank=True, null=True)
    fecha_ingreso = models.DateTimeField(blank=True, null=True)
    estatus_io = models.CharField(max_length=10, blank=True, null=True)
    cope = models.CharField(max_length=100, blank=True, null=True)
    red_secundaria = models.CharField(max_length=100, blank=True, null=True)
    dslam = models.CharField(max_length=100, blank=True, null=True)
    estatus_qp = models.CharField(max_length=20, blank=True, null=True)
    cve_liq = models.CharField(max_length=50, blank=True, null=True)
    desc_liq = models.TextField(blank=True, null=True)
    leyenda_sisa = models.CharField(max_length=100, blank=True, null=True)
    oqu = models.CharField(max_length=100, blank=True, null=True)
    actualizado_por_gio = models.BooleanField(blank=True, null=True, default=True)
    estado_sincronizacion = models.CharField(max_length=30, blank=True, null=True)
    ultimo_intento_sinc = models.DateTimeField(blank=True, null=True)
    error_sincronizacion = models.TextField(blank=True, null=True)
    creado_en = models.DateTimeField(blank=True, null=True)
    actualizado_en = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False  # Si quieres que Django administre la creación/migración de esta tabla en PostgreSQL, cambia esto a True
        db_table = 'incidentes_red'
        ordering = ['-id']

    def __str__(self):
        return f"{self.folio} - {self.empresa}"