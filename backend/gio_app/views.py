import logging
from datetime import date

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters as drf_filters

from usuarios.permissions import (
    PuedeAsignar, PuedeCrearIncidente, PuedeEditarIncidente, PuedeExportar,
)

from .chat import mensajes_pendientes
from .desempeno import desempeno_de_campo
from .exportacion import MAX_FILAS, generar_csv, generar_xlsx, nombre_de_archivo
from .filters import IncidenteFilter
from .models import (
    BitacoraIncidente, EvidenciaIncidente, Incidente, LecturaChat, TurnoEvaluador,
)
from .reparto import programar_turnos, repartir_folios_del_dia
from .serializers import (
    AsignacionMasivaSerializer,
    BitacoraIncidenteSerializer,
    EvidenciaIncidenteSerializer,
    IncidenteEvaluadorSerializer,
    IncidenteListaSerializer,
    IncidenteSerializer,
    IncidenteTecnicoSerializer,
    MAX_DIAS_PROGRAMACION,
    MensajeFolioSerializer,
    ProgramarTurnosSerializer,
    RepartoTurnosSerializer,
    TurnoEvaluadorSerializer,
)

UsuarioGIO = get_user_model()
log = logging.getLogger('gio.exportacion')

FORMATOS_EXPORTACION = {
    'xlsx': (generar_xlsx,
             'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
    'csv': (generar_csv, 'text/csv; charset=utf-8'),
}

CAMPOS_AUDITADOS = (
    'estatus', 'tecnico', 'evaluador', 'diagnostico_final', 'codigo_fallo',
    'estado_enlace', 'cve_liq', 'desc_liq', 'central', 'area_operativa',
)

MENSAJE_BLOQUEADO = 'El folio está liquidado y no admite cambios. Solo Gerencia puede modificarlo.'

# Mensajes que trae la primera carga de un chat; después se piden solo los nuevos.
MAX_MENSAJES_POR_CONSULTA = 200


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


def area_de_consulta(request):
    return (request.query_params.get('area') or '').strip().upper()


def filtrar_por_zona(queryset, area):
    """Usuarios de la zona indicada o sin zona asignada."""
    if not area:
        return queryset
    return queryset.filter(Q(area_operativa=area) | Q(area_operativa=''))


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

    def update(self, request, *args, **kwargs):
        if self.get_object().bloqueado_para(request.user):
            raise PermissionDenied(MENSAJE_BLOQUEADO)
        return super().update(request, *args, **kwargs)

    def perform_create(self, serializer):
        incidente = serializer.save()
        BitacoraIncidente.registrar(
            incidente, self.request.user, BitacoraIncidente.Accion.CREACION,
            detalle=f'Folio creado manualmente por {self.request.user.expediente}',
        )

    def perform_update(self, serializer):
        anterior = {campo: getattr(serializer.instance, campo) for campo in CAMPOS_AUDITADOS}
        incidente = serializer.save()
        detalle = ('Liquidado por Gerencia al registrar la descripción de liquidación'
                   if getattr(serializer, 'liquidacion_por_descripcion', False) else '')
        self._auditar_cambios(incidente, anterior, detalle_estatus=detalle)

    def perform_destroy(self, instance):
        BitacoraIncidente.registrar(
            instance, self.request.user, BitacoraIncidente.Accion.ACTUALIZACION,
            detalle='Folio eliminado',
        )
        instance.delete()

    def _auditar_cambios(self, incidente, anterior, detalle_estatus=''):
        for campo, valor_anterior in anterior.items():
            valor_nuevo = getattr(incidente, campo)
            if valor_anterior == valor_nuevo:
                continue
            detalle = ''
            if campo == 'estatus':
                accion = (BitacoraIncidente.Accion.LIQUIDACION
                          if valor_nuevo == Incidente.Estatus.LIQUIDADO
                          else BitacoraIncidente.Accion.CAMBIO_ESTATUS)
                detalle = detalle_estatus
            elif campo in ('tecnico', 'evaluador'):
                accion = BitacoraIncidente.Accion.ASIGNACION
            else:
                accion = BitacoraIncidente.Accion.ACTUALIZACION
            BitacoraIncidente.registrar(
                incidente, self.request.user, accion, campo=campo,
                anterior=valor_anterior, nuevo=valor_nuevo, detalle=detalle,
            )

    @action(detail=True, methods=['post'], url_path='liquidar')
    def liquidar(self, request, pk=None):
        incidente = self.get_object()
        if incidente.bloqueado_para(request.user):
            raise PermissionDenied(MENSAJE_BLOQUEADO)
        gerencia = Incidente.liquida_como_gerencia(request.user)
        diagnostico = (request.data.get('diagnostico_final') or '').strip()
        descripcion = (request.data.get('desc_liq') or incidente.desc_liq or '').strip()
        if gerencia and not (diagnostico or incidente.diagnostico_final.strip() or descripcion):
            raise ValidationError({'diagnostico_final': (
                'Indique el diagnóstico final o la descripción de liquidación.')})
        if not gerencia and not diagnostico:
            raise ValidationError({'diagnostico_final': 'El diagnóstico final es obligatorio.'})
        if not incidente.puede_transicionar_a(Incidente.Estatus.LIQUIDADO, request.user):
            raise ValidationError({
                'estatus': f'El folio en estatus {incidente.estatus} no puede liquidarse directamente.'
            })

        estatus_anterior = incidente.estatus
        incidente.estatus = Incidente.Estatus.LIQUIDADO
        incidente.diagnostico_final = diagnostico or incidente.diagnostico_final
        incidente.cve_liq = (request.data.get('cve_liq') or incidente.cve_liq or '').strip()
        incidente.desc_liq = descripcion
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

    @action(detail=True, methods=['post'], url_path='cancelar-liquidacion')
    def cancelar_liquidacion(self, request, pk=None):
        incidente = self.get_object()
        if not incidente.puede_cancelar_liquidacion(request.user):
            raise PermissionDenied(
                'Solo Gerencia puede cancelar una liquidación. El técnico asignado puede hacerlo '
                'únicamente el mismo día y dentro de la hora posterior al cierre.'
            )
        cierre = timezone.localtime(incidente.fecha_cierre).strftime('%Y-%m-%d %H:%M')
        incidente.estatus = Incidente.Estatus.PENDIENTE
        incidente.save()

        BitacoraIncidente.registrar(
            incidente, request.user, BitacoraIncidente.Accion.CANCELACION_LIQUIDACION,
            campo='estatus', anterior=Incidente.Estatus.LIQUIDADO, nuevo=incidente.estatus,
            detalle=f'Liquidación del {cierre} cancelada',
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
        if incidente.bloqueado_para(request.user):
            raise PermissionDenied(MENSAJE_BLOQUEADO)
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

    @action(detail=True, methods=['get', 'post'], url_path='mensajes', throttle_scope='chat')
    def mensajes(self, request, pk=None):
        """Chat del folio. GET devuelve los últimos mensajes, o con `despues` solo los posteriores
        a ese id, y los marca como leídos para quien consulta. POST acepta JSON con `texto` o
        multipart con `texto` e `imagen`. Admite mensajes aunque el folio esté liquidado: la
        conversación no modifica el folio."""
        incidente = self.get_object()
        if request.method == 'POST':
            contexto = {'request': request}
            serializer = MensajeFolioSerializer(data=request.data, context=contexto)
            serializer.is_valid(raise_exception=True)
            mensaje = serializer.save(incidente=incidente, autor=request.user)
            LecturaChat.marcar(incidente, request.user, mensaje.pk)
            return Response(MensajeFolioSerializer(mensaje, context=contexto).data,
                            status=status.HTTP_201_CREATED)

        consulta = incidente.mensajes.select_related('autor')
        despues = request.query_params.get('despues')
        if despues:
            try:
                consulta = consulta.filter(pk__gt=int(despues))
            except ValueError:
                raise ValidationError({'despues': 'Indique el id del último mensaje recibido.'})
            mensajes = list(consulta[:MAX_MENSAJES_POR_CONSULTA])
        else:
            mensajes = list(consulta.order_by('-id')[:MAX_MENSAJES_POR_CONSULTA])[::-1]
        if mensajes:
            LecturaChat.marcar(incidente, request.user, mensajes[-1].pk)
        return Response(MensajeFolioSerializer(mensajes, many=True,
                                               context={'request': request}).data)

    @action(detail=False, methods=['get'], url_path='mensajes-pendientes')
    def pendientes_de_chat(self, request):
        return Response(mensajes_pendientes(request.user, self.get_queryset()))

    @action(detail=False, methods=['post'], url_path='asignar-masivo',
            permission_classes=[PuedeAsignar])
    def asignar_masivo(self, request):
        serializer = AsignacionMasivaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data
        folios = [f.strip() for f in datos['folios'] if f.strip()]

        encontrados_todos = list(self.get_queryset().filter(folio__in=folios))
        encontrados = {inc.folio for inc in encontrados_todos}
        incidentes = [inc for inc in encontrados_todos if not inc.bloqueado_para(request.user)]
        bloqueados = sorted(inc.folio for inc in encontrados_todos if inc not in incidentes)
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
            'bloqueados': bloqueados,
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

    @action(detail=False, methods=['get'], url_path='exportar', permission_classes=[PuedeExportar])
    def exportar(self, request):
        """Todos los folios que coinciden con los filtros del tablero, sin paginar.

        Se usa `formato` (xlsx o csv) y no `format`, que DRF reserva para elegir el renderer.
        """
        formato = (request.query_params.get('formato') or 'xlsx').lower()
        if formato not in FORMATOS_EXPORTACION:
            raise ValidationError({'formato': 'Use xlsx o csv.'})

        queryset = (self.filter_queryset(self.get_queryset())
                    .prefetch_related(None)
                    .annotate(num_evidencias=Count('evidencias', distinct=True)))
        total = queryset.count()
        if total > MAX_FILAS:
            raise ValidationError({'detail': (
                f'La consulta tiene {total} folios y el máximo por reporte es {MAX_FILAS}. '
                'Acote los filtros (área, estatus o fechas) y vuelva a intentar.')})

        generar, tipo = FORMATOS_EXPORTACION[formato]
        contenido = generar(queryset.iterator(chunk_size=2000))
        log.info('Reporte %s de %s folios descargado por %s', formato, total,
                 request.user.expediente)

        respuesta = HttpResponse(contenido, content_type=tipo)
        respuesta['Content-Disposition'] = f'attachment; filename="{nombre_de_archivo(formato)}"'
        respuesta['X-Total-Folios'] = str(total)
        return respuesta

    @action(detail=False, methods=['get'], url_path='desempeno', permission_classes=[PuedeAsignar])
    def desempeno(self, request):
        return Response(desempeno_de_campo(area=area_de_consulta(request)))


class TecnicoListView(APIView):
    def get(self, request):
        tecnicos = UsuarioGIO.objects.filter(rol=UsuarioGIO.Rol.TECNICO, is_active=True)
        if not request.user.tiene_vision_global and request.user.area_operativa:
            tecnicos = filtrar_por_zona(tecnicos, request.user.area_operativa)
        tecnicos = filtrar_por_zona(tecnicos, area_de_consulta(request))
        return Response([
            {'id': t.id, 'expediente': t.expediente, 'nombre': t.nombre_completo,
             'area_operativa': t.area_operativa, 'telefono': t.telefono}
            for t in tecnicos.order_by('first_name', 'last_name', 'expediente')
        ])


class EvaluadorListView(APIView):
    def get(self, request):
        evaluadores = UsuarioGIO.objects.filter(rol=UsuarioGIO.Rol.PI_EVALUADOR, is_active=True)
        evaluadores = filtrar_por_zona(evaluadores, area_de_consulta(request))
        return Response([
            {'id': e.id, 'expediente': e.expediente, 'nombre': e.nombre_completo,
             'area_operativa': e.area_operativa}
            for e in evaluadores.order_by('first_name', 'last_name', 'expediente')
        ])


class CentralListView(APIView):
    def get(self, request):
        consulta = queryset_por_rol(request.user).exclude(central='')
        area = area_de_consulta(request)
        if area:
            consulta = consulta.filter(area_operativa=area)
        pares = (consulta.values_list('central', 'area_operativa')
                 .distinct()
                 .order_by('central', 'area_operativa'))
        centrales = {}
        for central, area_central in pares:
            centrales.setdefault(central, area_central)
        return Response([
            {'id': central, 'nombre': central, 'area': area_central}
            for central, area_central in centrales.items()
        ])


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


def _fecha_de_consulta(texto, campo='fecha'):
    if not texto:
        return timezone.localdate()
    try:
        return date.fromisoformat(texto)
    except ValueError:
        raise ValidationError({campo: 'Use el formato AAAA-MM-DD.'})


class TurnosView(APIView):
    """Horarios de planta interna. GET por fecha o rango; POST programa varios técnicos y días."""
    permission_classes = [PuedeAsignar]

    def get(self, request):
        parametros = request.query_params
        if parametros.get('desde') or parametros.get('hasta'):
            desde = _fecha_de_consulta(parametros.get('desde'), 'desde')
            hasta = _fecha_de_consulta(parametros.get('hasta') or parametros.get('desde'), 'hasta')
        else:
            desde = hasta = _fecha_de_consulta(parametros.get('fecha'))
        if (hasta - desde).days >= MAX_DIAS_PROGRAMACION:
            raise ValidationError({'hasta': f'Consulte como máximo {MAX_DIAS_PROGRAMACION} días.'})
        turnos = (TurnoEvaluador.objects.filter(fecha__range=(desde, hasta))
                  .select_related('evaluador')
                  .order_by('fecha', 'hora_inicio', 'evaluador__expediente'))
        return Response(TurnoEvaluadorSerializer(turnos, many=True).data)

    def post(self, request):
        serializer = ProgramarTurnosSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data
        resultado = programar_turnos(datos['evaluadores'], datos['desde'], datos['hasta'],
                                     datos['horarios'])
        return Response(resultado)


class RepartoTurnosView(APIView):
    """Reparte equitativamente entre los evaluadores de turno los folios abiertos sin asignar."""
    permission_classes = [PuedeAsignar]

    def post(self, request):
        serializer = RepartoTurnosSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data
        resultado = repartir_folios_del_dia(datos['fecha'], request.user, datos['limite'])
        return Response({
            'fecha': resultado['fecha'],
            'evaluadores_de_turno': resultado['evaluadores_de_turno'],
            'asignados': resultado['asignados'],
            'sin_zona': resultado['sin_zona'],
            'por_evaluador': resultado['por_evaluador'],
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
        if instance.incidente.bloqueado_para(usuario):
            raise PermissionDenied(MENSAJE_BLOQUEADO)
        if not (usuario.tiene_vision_global or instance.subido_por_id == usuario.id):
            raise PermissionDenied('Solo puede eliminar las evidencias que usted cargó.')
        BitacoraIncidente.registrar(
            instance.incidente, usuario, BitacoraIncidente.Accion.EVIDENCIA,
            detalle=f'Evidencia #{instance.pk} eliminada',
        )
        instance.imagen.delete(save=False)
        instance.delete()
