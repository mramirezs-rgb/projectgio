from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters as drf_filters

from usuarios.permissions import PuedeAsignar, PuedeCrearIncidente, PuedeEditarIncidente

from .filters import IncidenteFilter
from .models import BitacoraIncidente, EvidenciaIncidente, Incidente
from .serializers import (
    AsignacionMasivaSerializer,
    BitacoraIncidenteSerializer,
    EvidenciaIncidenteSerializer,
    IncidenteEvaluadorSerializer,
    IncidenteListaSerializer,
    IncidenteSerializer,
    IncidenteTecnicoSerializer,
)

UsuarioGIO = get_user_model()

CAMPOS_AUDITADOS = (
    'estatus', 'tecnico', 'evaluador', 'diagnostico_final', 'codigo_fallo',
    'estado_enlace', 'cve_liq', 'desc_liq', 'central', 'area_operativa',
)


def queryset_por_rol(usuario):
    base = Incidente.objects.select_related('tecnico', 'evaluador').prefetch_related('evidencias')
    if not usuario or not usuario.is_authenticated:
        return base.none()
    if usuario.tiene_vision_global:
        return base
    if usuario.es_evaluador:
        return base.filter(evaluador=usuario)
    if usuario.es_tecnico:
        return base.filter(tecnico=usuario)
    return base.none()


class IncidenteViewSet(viewsets.ModelViewSet):
    throttle_scope = None
    permission_classes = [PuedeCrearIncidente, PuedeEditarIncidente]
    filter_backends = [DjangoFilterBackend, drf_filters.SearchFilter, drf_filters.OrderingFilter]
    filterset_class = IncidenteFilter
    search_fields = ['folio', 'incidente', 'empresa', 'referencia', 'cope', 'central', 'ips', 'dir_pta_a']
    ordering_fields = ['fecha_apertura', 'fecha_cierre', 'dilacion_dias', 'folio', 'estatus', 'id']
    ordering = ['-fecha_apertura']

    def get_queryset(self):
        return queryset_por_rol(self.request.user)

    def get_serializer_class(self):
        if self.action == 'list':
            return IncidenteListaSerializer
        usuario = self.request.user
        if self.request.method in ('PUT', 'PATCH'):
            if usuario.es_tecnico:
                return IncidenteTecnicoSerializer
            if usuario.es_evaluador:
                return IncidenteEvaluadorSerializer
        return IncidenteSerializer

    def perform_create(self, serializer):
        incidente = serializer.save()
        BitacoraIncidente.registrar(
            incidente, self.request.user, BitacoraIncidente.Accion.CREACION,
            detalle=f'Folio creado manualmente por {self.request.user.expediente}',
        )

    def perform_update(self, serializer):
        anterior = {campo: getattr(serializer.instance, campo) for campo in CAMPOS_AUDITADOS}
        incidente = serializer.save()
        self._auditar_cambios(incidente, anterior)

    def perform_destroy(self, instance):
        BitacoraIncidente.registrar(
            instance, self.request.user, BitacoraIncidente.Accion.ACTUALIZACION,
            detalle='Folio eliminado',
        )
        instance.delete()

    def _auditar_cambios(self, incidente, anterior):
        for campo, valor_anterior in anterior.items():
            valor_nuevo = getattr(incidente, campo)
            if valor_anterior == valor_nuevo:
                continue
            if campo == 'estatus':
                accion = (BitacoraIncidente.Accion.LIQUIDACION
                          if valor_nuevo == Incidente.Estatus.LIQUIDADO
                          else BitacoraIncidente.Accion.CAMBIO_ESTATUS)
            elif campo in ('tecnico', 'evaluador'):
                accion = BitacoraIncidente.Accion.ASIGNACION
            else:
                accion = BitacoraIncidente.Accion.ACTUALIZACION
            BitacoraIncidente.registrar(
                incidente, self.request.user, accion, campo=campo,
                anterior=valor_anterior, nuevo=valor_nuevo,
            )

    @action(detail=True, methods=['post'], url_path='liquidar')
    def liquidar(self, request, pk=None):
        incidente = self.get_object()
        diagnostico = (request.data.get('diagnostico_final') or '').strip()
        if not diagnostico:
            raise ValidationError({'diagnostico_final': 'El diagnóstico final es obligatorio.'})
        if not incidente.puede_transicionar_a(Incidente.Estatus.LIQUIDADO):
            raise ValidationError({
                'estatus': f'El folio en estatus {incidente.estatus} no puede liquidarse directamente.'
            })
        if not incidente.evidencias.exists():
            raise ValidationError({
                'evidencias': 'Debe cargarse al menos una evidencia fotográfica antes de liquidar.'
            })

        estatus_anterior = incidente.estatus
        incidente.estatus = Incidente.Estatus.LIQUIDADO
        incidente.diagnostico_final = diagnostico
        incidente.cve_liq = (request.data.get('cve_liq') or incidente.cve_liq or '').strip()
        incidente.desc_liq = (request.data.get('desc_liq') or incidente.desc_liq or '').strip()
        incidente.codigo_fallo = (request.data.get('codigo_fallo') or incidente.codigo_fallo or '')
        incidente.estado_enlace = request.data.get('estado_enlace') or Incidente.EstadoEnlace.UP
        incidente.exportado_sisa = False
        incidente.estado_sincronizacion = Incidente.Sincronizacion.PENDIENTE
        incidente.save()

        BitacoraIncidente.registrar(
            incidente, request.user, BitacoraIncidente.Accion.LIQUIDACION, campo='estatus',
            anterior=estatus_anterior, nuevo=incidente.estatus,
            detalle=f'MTTR {incidente.mttr_horas} h',
        )
        return Response(IncidenteSerializer(incidente, context={'request': request}).data)

    @action(detail=True, methods=['get', 'post'], url_path='evidencias',
            parser_classes=[MultiPartParser, FormParser], throttle_scope='evidencia')
    def evidencias(self, request, pk=None):
        incidente = self.get_object()
        if request.method == 'GET':
            serializer = EvidenciaIncidenteSerializer(
                incidente.evidencias.all(), many=True, context={'request': request})
            return Response(serializer.data)

        self.check_object_permissions(request, incidente)
        if incidente.evidencias.count() >= settings.EVIDENCIA_MAX_POR_FOLIO:
            raise ValidationError({
                'evidencias': f'El folio alcanzó el máximo de {settings.EVIDENCIA_MAX_POR_FOLIO} evidencias.'
            })
        serializer = EvidenciaIncidenteSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        evidencia = serializer.save(incidente=incidente, subido_por=request.user)
        BitacoraIncidente.registrar(
            incidente, request.user, BitacoraIncidente.Accion.EVIDENCIA,
            detalle=f'Evidencia #{evidencia.pk} ({evidencia.tamano_bytes // 1024} KB)',
        )
        return Response(
            EvidenciaIncidenteSerializer(evidencia, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['get'], url_path='bitacora')
    def bitacora(self, request, pk=None):
        incidente = self.get_object()
        serializer = BitacoraIncidenteSerializer(incidente.bitacora.all()[:200], many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='asignar-masivo',
            permission_classes=[PuedeAsignar])
    def asignar_masivo(self, request):
        serializer = AsignacionMasivaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data
        folios = [f.strip() for f in datos['folios'] if f.strip()]

        incidentes = list(self.get_queryset().filter(folio__in=folios))
        encontrados = {inc.folio for inc in incidentes}
        actualizados = 0

        with transaction.atomic():
            for incidente in incidentes:
                cambios = []
                if 'tecnico' in datos:
                    anterior = incidente.tecnico
                    incidente.tecnico = datos['tecnico']
                    cambios.append(('tecnico', anterior, incidente.tecnico))
                if 'evaluador' in datos:
                    anterior = incidente.evaluador
                    incidente.evaluador = datos['evaluador']
                    cambios.append(('evaluador', anterior, incidente.evaluador))
                if incidente.tecnico and incidente.estatus == Incidente.Estatus.PENDIENTE:
                    cambios.append(('estatus', incidente.estatus, Incidente.Estatus.ASIGNADO))
                    incidente.estatus = Incidente.Estatus.ASIGNADO
                incidente.save()
                for campo, anterior, nuevo in cambios:
                    BitacoraIncidente.registrar(
                        incidente, request.user, BitacoraIncidente.Accion.ASIGNACION,
                        campo=campo, anterior=anterior, nuevo=nuevo,
                        detalle='Reasignación masiva',
                    )
                actualizados += 1

        return Response({
            'actualizados': actualizados,
            'no_encontrados': sorted(set(folios) - encontrados),
        })

    @action(detail=False, methods=['get'], url_path='metricas')
    def metricas(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        umbral = settings.DILACION_UMBRAL_DIAS
        critico = settings.DILACION_UMBRAL_CRITICO_DIAS

        agregados = queryset.aggregate(
            total=Count('id'),
            pendientes=Count('id', filter=Q(estatus=Incidente.Estatus.PENDIENTE)),
            asignados=Count('id', filter=Q(estatus=Incidente.Estatus.ASIGNADO)),
            en_proceso=Count('id', filter=Q(estatus=Incidente.Estatus.EN_PROCESO)),
            liquidados=Count('id', filter=Q(estatus=Incidente.Estatus.LIQUIDADO)),
            sin_tecnico=Count('id', filter=Q(tecnico__isnull=True)),
            en_dilacion=Count('id', filter=Q(dilacion_dias__gte=umbral)
                              & ~Q(estatus=Incidente.Estatus.LIQUIDADO)),
            criticos=Count('id', filter=Q(dilacion_dias__gte=critico)
                           & ~Q(estatus=Incidente.Estatus.LIQUIDADO)),
            pendientes_exportar=Count('id', filter=Q(estatus=Incidente.Estatus.LIQUIDADO,
                                                     exportado_sisa=False)),
        )

        periodos = (queryset.filter(estatus=Incidente.Estatus.LIQUIDADO,
                                    fecha_cierre__isnull=False)
                    .values_list('fecha_apertura', 'fecha_cierre'))
        mttr = [round((cierre - apertura).total_seconds() / 3600, 2)
                for apertura, cierre in periodos if apertura and cierre]
        agregados['mttr_horas_promedio'] = round(sum(mttr) / len(mttr), 2) if mttr else None
        agregados['mttr_horas_maximo'] = round(max(mttr), 2) if mttr else None
        agregados['mttr_horas_minimo'] = round(min(mttr), 2) if mttr else None
        agregados['dilacion_promedio_dias'] = queryset.exclude(
            estatus=Incidente.Estatus.LIQUIDADO).aggregate(v=Avg('dilacion_dias'))['v']
        if agregados['dilacion_promedio_dias'] is not None:
            agregados['dilacion_promedio_dias'] = round(agregados['dilacion_promedio_dias'], 2)

        agregados['por_area'] = list(
            queryset.exclude(area_operativa='')
            .values('area_operativa')
            .annotate(total=Count('id'),
                      abiertos=Count('id', filter=~Q(estatus=Incidente.Estatus.LIQUIDADO)))
            .order_by('-total')[:20]
        )
        agregados['por_tecnico'] = list(
            queryset.filter(tecnico__isnull=False)
            .values('tecnico__expediente', 'tecnico__first_name', 'tecnico__last_name')
            .annotate(total=Count('id'),
                      abiertos=Count('id', filter=~Q(estatus=Incidente.Estatus.LIQUIDADO)))
            .order_by('-abiertos')[:20]
        )
        agregados['umbral_dilacion_dias'] = umbral
        agregados['umbral_critico_dias'] = critico
        agregados['generado_en'] = timezone.now()
        return Response(agregados)


class TecnicoListView(APIView):
    def get(self, request):
        tecnicos = UsuarioGIO.objects.filter(rol=UsuarioGIO.Rol.TECNICO, is_active=True)
        if not request.user.tiene_vision_global and request.user.area_operativa:
            tecnicos = tecnicos.filter(
                Q(area_operativa=request.user.area_operativa) | Q(area_operativa=''))
        return Response([
            {'id': t.id, 'expediente': t.expediente, 'nombre': t.nombre_completo,
             'area_operativa': t.area_operativa, 'telefono': t.telefono}
            for t in tecnicos.order_by('first_name', 'last_name', 'expediente')
        ])


class EvaluadorListView(APIView):
    def get(self, request):
        evaluadores = UsuarioGIO.objects.filter(rol=UsuarioGIO.Rol.PI_EVALUADOR, is_active=True)
        return Response([
            {'id': e.id, 'expediente': e.expediente, 'nombre': e.nombre_completo,
             'area_operativa': e.area_operativa}
            for e in evaluadores.order_by('first_name', 'last_name', 'expediente')
        ])


class CentralListView(APIView):
    def get(self, request):
        valores = (queryset_por_rol(request.user)
                   .exclude(central='')
                   .values_list('central', flat=True)
                   .distinct()
                   .order_by('central'))
        return Response([{'id': c, 'nombre': c} for c in valores])


class AreaListView(APIView):
    def get(self, request):
        valores = (queryset_por_rol(request.user)
                   .exclude(area_operativa='')
                   .values_list('area_operativa', flat=True)
                   .distinct()
                   .order_by('area_operativa'))
        return Response([{'id': a, 'nombre': a} for a in valores])


class CatalogosView(APIView):
    def get(self, request):
        return Response({
            'estatus': [{'id': v, 'nombre': n} for v, n in Incidente.Estatus.choices],
            'codigos_fallo': [{'id': v, 'nombre': n} for v, n in Incidente.CodigoFallo.choices],
            'estado_enlace': [{'id': v, 'nombre': n} for v, n in Incidente.EstadoEnlace.choices],
            'roles': [{'id': v, 'nombre': n} for v, n in UsuarioGIO.Rol.choices],
            'areas': [{'id': v, 'nombre': n} for v, n in UsuarioGIO.Area.choices],
            'transiciones': {k: sorted(v) for k, v in Incidente.TRANSICIONES.items()},
            'limites': {
                'evidencia_max_bytes': settings.EVIDENCIA_MAX_BYTES,
                'evidencia_max_por_folio': settings.EVIDENCIA_MAX_POR_FOLIO,
                'dilacion_umbral_dias': settings.DILACION_UMBRAL_DIAS,
                'dilacion_umbral_critico_dias': settings.DILACION_UMBRAL_CRITICO_DIAS,
            },
        })


class EvidenciaViewSet(viewsets.ModelViewSet):
    serializer_class = EvidenciaIncidenteSerializer
    http_method_names = ['get', 'delete', 'head', 'options']

    def get_queryset(self):
        return EvidenciaIncidente.objects.filter(
            incidente__in=queryset_por_rol(self.request.user)
        ).select_related('incidente', 'subido_por')

    def perform_destroy(self, instance):
        usuario = self.request.user
        if not (usuario.tiene_vision_global or instance.subido_por_id == usuario.id):
            raise PermissionDenied('Solo puede eliminar las evidencias que usted cargó.')
        BitacoraIncidente.registrar(
            instance.incidente, usuario, BitacoraIncidente.Accion.EVIDENCIA,
            detalle=f'Evidencia #{instance.pk} eliminada',
        )
        instance.imagen.delete(save=False)
        instance.delete()
