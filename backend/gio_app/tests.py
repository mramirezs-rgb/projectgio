import io
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from .models import BitacoraIncidente, Incidente

UsuarioGIO = get_user_model()


def imagen_en_memoria(nombre='evidencia.jpg', tamano=(64, 64), calidad=70):
    buffer = io.BytesIO()
    Image.new('RGB', tamano, (18, 52, 86)).save(buffer, format='JPEG', quality=calidad)
    buffer.seek(0)
    return SimpleUploadedFile(nombre, buffer.read(), content_type='image/jpeg')


class BaseGIOTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = UsuarioGIO.objects.create_user(
            expediente='GER-0001', password='Gio.Admin.2026', rol=UsuarioGIO.Rol.ADMIN,
            first_name='Ana', last_name='Gerencia')
        cls.sub = UsuarioGIO.objects.create_user(
            expediente='SUB-0001', password='Gio.Sub.2026', rol=UsuarioGIO.Rol.PI_SUB,
            first_name='Beto', last_name='Subgerencia')
        cls.evaluador = UsuarioGIO.objects.create_user(
            expediente='OQU-8821', password='Gio.Eval.2026', rol=UsuarioGIO.Rol.PI_EVALUADOR,
            first_name='Carla', last_name='Evaluadora')
        cls.otro_evaluador = UsuarioGIO.objects.create_user(
            expediente='OQU-9000', password='Gio.Eval2.2026', rol=UsuarioGIO.Rol.PI_EVALUADOR,
            first_name='Dora', last_name='Evaluadora')
        cls.tecnico = UsuarioGIO.objects.create_user(
            expediente='TEC-4410', password='Gio.Tec.2026', rol=UsuarioGIO.Rol.TECNICO,
            first_name='Luis', last_name='Serrano')
        cls.otro_tecnico = UsuarioGIO.objects.create_user(
            expediente='TEC-9999', password='Gio.Tec2.2026', rol=UsuarioGIO.Rol.TECNICO,
            first_name='Mario', last_name='Campos')

    def setUp(self):
        self.propio = Incidente.objects.create(
            folio='12578004', empresa='SERVICIOS MULTIPLES', area_operativa='PUEBLA',
            central='LOS PINOS', tecnico=self.tecnico, evaluador=self.evaluador,
            estatus=Incidente.Estatus.ASIGNADO,
            fecha_apertura=timezone.now() - timedelta(days=7))
        self.ajeno = Incidente.objects.create(
            folio='12586093', empresa='UNINET', area_operativa='VERACRUZ',
            tecnico=self.otro_tecnico, evaluador=self.otro_evaluador,
            estatus=Incidente.Estatus.PENDIENTE)

    def autenticar(self, usuario):
        self.client.force_authenticate(user=usuario)


class ModeloIncidenteTests(BaseGIOTestCase):
    def test_mttr_es_nulo_mientras_no_se_liquida(self):
        self.assertIsNone(self.propio.mttr_horas)

    def test_mttr_en_horas_y_fracciones(self):
        self.propio.fecha_apertura = timezone.now() - timedelta(hours=5, minutes=30)
        self.propio.estatus = Incidente.Estatus.EN_PROCESO
        self.propio.diagnostico_final = 'Empalme reparado'
        self.propio.save()
        self.propio.estatus = Incidente.Estatus.LIQUIDADO
        self.propio.save()
        self.assertAlmostEqual(float(self.propio.mttr_horas), 5.5, places=1)

    def test_liquidar_asigna_fecha_cierre_y_dilacion(self):
        self.propio.estatus = Incidente.Estatus.EN_PROCESO
        self.propio.save()
        self.propio.estatus = Incidente.Estatus.LIQUIDADO
        self.propio.diagnostico_final = 'Servicio restablecido'
        self.propio.save()
        self.assertIsNotNone(self.propio.fecha_cierre)
        self.assertEqual(self.propio.dilacion_dias, 7)

    def test_reabrir_limpia_cierre_y_marca_pendiente_de_exportar(self):
        self.propio.estatus = Incidente.Estatus.EN_PROCESO
        self.propio.save()
        self.propio.estatus = Incidente.Estatus.LIQUIDADO
        self.propio.diagnostico_final = 'Cerrado'
        self.propio.save()
        self.propio.exportado_sisa = True
        self.propio.save()
        self.propio.estatus = Incidente.Estatus.EN_PROCESO
        self.propio.save()
        self.assertIsNone(self.propio.fecha_cierre)
        self.assertFalse(self.propio.exportado_sisa)

    def test_transiciones_de_la_maquina_de_estados(self):
        self.assertTrue(self.ajeno.puede_transicionar_a(Incidente.Estatus.ASIGNADO))
        self.assertFalse(self.ajeno.puede_transicionar_a(Incidente.Estatus.LIQUIDADO))

    def test_semaforo_por_dilacion(self):
        self.assertEqual(self.propio.semaforo, 'alerta')
        self.propio.fecha_apertura = timezone.now() - timedelta(days=30)
        self.propio.save()
        self.assertEqual(self.propio.semaforo, 'critico')


class VisibilidadPorRolTests(BaseGIOTestCase):
    def url(self):
        return reverse('incidente-list')

    def test_anonimo_recibe_401(self):
        self.assertEqual(self.client.get(self.url()).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_tecnico_solo_ve_sus_folios(self):
        self.autenticar(self.tecnico)
        respuesta = self.client.get(self.url())
        folios = [item['folio'] for item in respuesta.data['results']]
        self.assertEqual(folios, ['12578004'])

    def test_evaluador_solo_ve_los_folios_que_evalua(self):
        self.autenticar(self.evaluador)
        folios = [i['folio'] for i in self.client.get(self.url()).data['results']]
        self.assertEqual(folios, ['12578004'])

    def test_subgerencia_y_gerencia_ven_todo(self):
        for usuario in (self.sub, self.admin):
            self.autenticar(usuario)
            self.assertEqual(self.client.get(self.url()).data['count'], 2)

    def test_tecnico_no_puede_leer_folio_ajeno(self):
        self.autenticar(self.tecnico)
        url = reverse('incidente-detail', args=[self.ajeno.pk])
        self.assertEqual(self.client.get(url).status_code, status.HTTP_404_NOT_FOUND)


class PermisosEscrituraTests(BaseGIOTestCase):
    def test_tecnico_no_puede_crear_folios(self):
        self.autenticar(self.tecnico)
        respuesta = self.client.post(reverse('incidente-list'), {'folio': 'NUEVO-1'})
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

    def test_subgerencia_puede_crear_folios(self):
        self.autenticar(self.sub)
        respuesta = self.client.post(reverse('incidente-list'), {
            'folio': 'NUEVO-1', 'empresa': 'ACME', 'area_operativa': 'puebla',
            'central': 'los pinos',
        })
        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED)
        self.assertEqual(respuesta.data['estatus'], Incidente.Estatus.PENDIENTE)
        self.assertEqual(respuesta.data['area_operativa'], 'PUEBLA')

    def test_tecnico_no_puede_reasignar_el_folio(self):
        self.autenticar(self.tecnico)
        url = reverse('incidente-detail', args=[self.propio.pk])
        respuesta = self.client.patch(url, {'tecnico': self.otro_tecnico.pk}, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.propio.refresh_from_db()
        self.assertEqual(self.propio.tecnico_id, self.tecnico.pk)

    def test_transicion_invalida_se_rechaza(self):
        self.autenticar(self.sub)
        url = reverse('incidente-detail', args=[self.propio.pk])
        respuesta = self.client.patch(url, {'estatus': Incidente.Estatus.LIQUIDADO}, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('estatus', respuesta.data)

    def test_asignar_sin_tecnico_se_rechaza(self):
        self.autenticar(self.sub)
        url = reverse('incidente-detail', args=[self.ajeno.pk])
        respuesta = self.client.patch(url, {'estatus': Incidente.Estatus.ASIGNADO,
                                            'tecnico': None}, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cambio_de_estatus_queda_en_bitacora(self):
        self.autenticar(self.sub)
        url = reverse('incidente-detail', args=[self.propio.pk])
        self.client.patch(url, {'estatus': Incidente.Estatus.EN_PROCESO}, format='json')
        registro = BitacoraIncidente.objects.filter(
            incidente=self.propio, campo='estatus').first()
        self.assertIsNotNone(registro)
        self.assertEqual(registro.valor_nuevo, Incidente.Estatus.EN_PROCESO)
        self.assertEqual(registro.usuario, self.sub)

    def test_asignacion_masiva_solo_para_subgerencia(self):
        self.autenticar(self.evaluador)
        url = reverse('incidente-asignar-masivo')
        self.assertEqual(
            self.client.post(url, {'folios': ['12578004'], 'tecnico': self.tecnico.pk},
                             format='json').status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.autenticar(self.sub)
        respuesta = self.client.post(
            url, {'folios': ['12586093', 'NO-EXISTE'], 'tecnico': self.tecnico.pk}, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(respuesta.data['actualizados'], 1)
        self.assertEqual(respuesta.data['no_encontrados'], ['NO-EXISTE'])
        self.ajeno.refresh_from_db()
        self.assertEqual(self.ajeno.estatus, Incidente.Estatus.ASIGNADO)


class EvidenciaYLiquidacionTests(BaseGIOTestCase):
    def setUp(self):
        super().setUp()
        self.propio.estatus = Incidente.Estatus.EN_PROCESO
        self.propio.save()
        self.url_evidencias = reverse('incidente-evidencias', args=[self.propio.pk])
        self.url_liquidar = reverse('incidente-liquidar', args=[self.propio.pk])

    def test_no_se_liquida_sin_evidencia(self):
        self.autenticar(self.tecnico)
        respuesta = self.client.post(self.url_liquidar,
                                     {'diagnostico_final': 'Empalme reparado'}, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('evidencias', respuesta.data)

    def test_no_se_liquida_sin_diagnostico(self):
        self.autenticar(self.tecnico)
        respuesta = self.client.post(self.url_liquidar, {}, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('diagnostico_final', respuesta.data)

    @override_settings(EVIDENCIA_MAX_BYTES=512 * 1024)
    def test_flujo_completo_de_liquidacion(self):
        self.autenticar(self.tecnico)
        carga = self.client.post(self.url_evidencias,
                                 {'imagen': imagen_en_memoria(), 'coordenadas_gps': '19.04,-98.20'},
                                 format='multipart')
        self.assertEqual(carga.status_code, status.HTTP_201_CREATED)
        self.assertGreater(carga.data['tamano_bytes'], 0)

        respuesta = self.client.post(self.url_liquidar, {
            'diagnostico_final': 'Reemplazo de puerto DSLAM y prueba de continuidad.',
            'cve_liq': '331',
        }, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(respuesta.data['estatus'], Incidente.Estatus.LIQUIDADO)
        self.assertIsNotNone(respuesta.data['fecha_cierre'])
        self.assertIsNotNone(respuesta.data['mttr_horas'])
        self.assertFalse(respuesta.data['exportado_sisa'])

    @override_settings(EVIDENCIA_MAX_BYTES=1024)
    def test_evidencia_excedida_se_rechaza(self):
        self.autenticar(self.tecnico)
        grande = imagen_en_memoria(tamano=(900, 900), calidad=98)
        respuesta = self.client.post(self.url_evidencias, {'imagen': grande}, format='multipart')
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('imagen', respuesta.data)

    def test_tecnico_ajeno_no_puede_cargar_evidencia(self):
        self.autenticar(self.otro_tecnico)
        respuesta = self.client.post(self.url_evidencias, {'imagen': imagen_en_memoria()},
                                     format='multipart')
        self.assertEqual(respuesta.status_code, status.HTTP_404_NOT_FOUND)


class MetricasTests(BaseGIOTestCase):
    def test_metricas_cubren_todo_el_universo_visible(self):
        self.autenticar(self.admin)
        respuesta = self.client.get(reverse('incidente-metricas'))
        self.assertEqual(respuesta.data['total'], 2)
        self.assertEqual(respuesta.data['pendientes'], 1)
        self.assertEqual(respuesta.data['asignados'], 1)
        self.assertEqual(respuesta.data['en_dilacion'], 1)
        self.assertIsNone(respuesta.data['mttr_horas_promedio'])

    def test_metricas_respetan_el_filtro_por_rol(self):
        self.autenticar(self.tecnico)
        self.assertEqual(self.client.get(reverse('incidente-metricas')).data['total'], 1)


class CatalogosTests(BaseGIOTestCase):
    def test_catalogo_de_tecnicos(self):
        self.autenticar(self.sub)
        datos = self.client.get(reverse('tecnicos-list')).data
        self.assertEqual({t['expediente'] for t in datos}, {'TEC-4410', 'TEC-9999'})

    def test_catalogo_de_evaluadores_no_devuelve_404(self):
        self.autenticar(self.sub)
        respuesta = self.client.get(reverse('evaluadores-list'))
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(len(respuesta.data), 2)

    def test_centrales_son_unicas_y_segun_rol(self):
        self.autenticar(self.tecnico)
        self.assertEqual([c['nombre'] for c in self.client.get(reverse('centrales-list')).data],
                         ['LOS PINOS'])

    def test_catalogos_expone_transiciones_y_limites(self):
        self.autenticar(self.tecnico)
        datos = self.client.get(reverse('catalogos')).data
        self.assertIn('PENDIENTE', datos['transiciones'])
        self.assertIn('evidencia_max_bytes', datos['limites'])
