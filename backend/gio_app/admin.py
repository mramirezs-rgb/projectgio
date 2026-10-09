from django.contrib import admin
from django.utils.html import format_html

from .models import BitacoraIncidente, EvidenciaIncidente, Incidente


class EvidenciaInline(admin.TabularInline):
    model = EvidenciaIncidente
    extra = 0
    readonly_fields = ('tamano_bytes', 'subido_por', 'creado_en', 'vista_previa')
    fields = ('imagen', 'vista_previa', 'descripcion', 'coordenadas_gps',
              'tamano_bytes', 'fecha_captura', 'subido_por')

    @admin.display(description='Vista previa')
    def vista_previa(self, obj):
        if obj.pk and obj.imagen:
            return format_html('<img src="{}" style="max-height:90px" />', obj.imagen.url)
        return '—'


class BitacoraInline(admin.TabularInline):
    model = BitacoraIncidente
    extra = 0
    can_delete = False
    readonly_fields = ('accion', 'campo', 'valor_anterior', 'valor_nuevo',
                       'detalle', 'usuario', 'registrado_en')
    fields = readonly_fields
    ordering = ('-registrado_en',)

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Incidente)
class IncidenteAdmin(admin.ModelAdmin):
    list_display = ('folio', 'empresa', 'estatus', 'area_operativa', 'central',
                    'tecnico', 'evaluador', 'dilacion_dias', 'mttr_horas', 'exportado_sisa')
    list_filter = ('estatus', 'exportado_sisa', 'area_operativa', 'estado_enlace', 'codigo_fallo')
    search_fields = ('folio', 'empresa', 'referencia', 'ips', 'central')
    autocomplete_fields = ('tecnico', 'evaluador')
    date_hierarchy = 'fecha_apertura'
    readonly_fields = ('fecha_cierre', 'dilacion_dias', 'mttr_horas',
                       'creado_en', 'actualizado_en', 'exportado_sisa')
    inlines = (EvidenciaInline, BitacoraInline)

    @admin.display(description='MTTR (h)')
    def mttr_horas(self, obj):
        return obj.mttr_horas if obj.mttr_horas is not None else '—'


@admin.register(EvidenciaIncidente)
class EvidenciaIncidenteAdmin(admin.ModelAdmin):
    list_display = ('id', 'incidente', 'tamano_bytes', 'fecha_captura', 'subido_por')
    list_filter = ('fecha_captura',)
    search_fields = ('incidente__folio', 'descripcion')
    autocomplete_fields = ('incidente', 'subido_por')


@admin.register(BitacoraIncidente)
class BitacoraIncidenteAdmin(admin.ModelAdmin):
    list_display = ('registrado_en', 'incidente', 'accion', 'campo',
                    'valor_anterior', 'valor_nuevo', 'usuario')
    list_filter = ('accion', 'registrado_en')
    search_fields = ('incidente__folio', 'detalle')
    readonly_fields = tuple(f.name for f in BitacoraIncidente._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
