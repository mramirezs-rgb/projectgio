import re
from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

UsuarioGIO = get_user_model()


class ModeloUsuarioTests(APITestCase):
    def test_create_user_usa_expediente_como_llave(self):
        usuario = UsuarioGIO.objects.create_user(expediente='oqu-8821', password='Gio.2026.Seg')
        self.assertEqual(usuario.expediente, 'OQU-8821')
        self.assertEqual(usuario.username, 'oqu-8821')
        self.assertEqual(usuario.rol, UsuarioGIO.Rol.TECNICO)
        self.assertTrue(usuario.check_password('Gio.2026.Seg'))

    def test_create_superuser_queda_como_admin(self):
        admin = UsuarioGIO.objects.create_superuser(expediente='GER-0001', password='Gio.2026.Seg')
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.es_admin)
        self.assertTrue(admin.tiene_vision_global)

    def test_expediente_vacio_es_invalido(self):
        with self.assertRaises(ValueError):
            UsuarioGIO.objects.create_user(expediente='', password='Gio.2026.Seg')


class LoginTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = UsuarioGIO.objects.create_user(
            expediente='SUB-0001', password='Gio.2026.Seg', rol=UsuarioGIO.Rol.PI_SUB,
            first_name='Beto', last_name='Subgerencia', area_operativa='PUEBLA')

    def test_login_devuelve_tokens_y_perfil_con_rol(self):
        respuesta = self.client.post(reverse('token_obtain_pair'),
                                     {'expediente': 'SUB-0001', 'password': 'Gio.2026.Seg'},
                                     format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertIn('access', respuesta.data)
        self.assertIn('refresh', respuesta.data)
        self.assertEqual(respuesta.data['user']['rol'], UsuarioGIO.Rol.PI_SUB)
        self.assertEqual(respuesta.data['user']['nombre'], 'Beto Subgerencia')
        self.assertTrue(respuesta.data['user']['permisos']['vision_global'])
        self.assertFalse(respuesta.data['user']['permisos']['gestionar_usuarios'])

    def test_login_es_insensible_a_mayusculas_en_el_expediente(self):
        respuesta = self.client.post(reverse('token_obtain_pair'),
                                     {'expediente': 'sub-0001', 'password': 'Gio.2026.Seg'},
                                     format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)

    def test_credenciales_invalidas(self):
        respuesta = self.client.post(reverse('token_obtain_pair'),
                                     {'expediente': 'SUB-0001', 'password': 'incorrecta'},
                                     format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_perfil_requiere_token(self):
        self.assertEqual(self.client.get(reverse('mi-perfil')).status_code,
                         status.HTTP_401_UNAUTHORIZED)
        self.client.force_authenticate(user=self.usuario)
        self.assertEqual(self.client.get(reverse('mi-perfil')).data['expediente'], 'SUB-0001')


class GestionUsuariosTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = UsuarioGIO.objects.create_user(
            expediente='GER-0001', password='Gio.2026.Seg', rol=UsuarioGIO.Rol.ADMIN)
        cls.sub = UsuarioGIO.objects.create_user(
            expediente='SUB-0001', password='Gio.2026.Seg', rol=UsuarioGIO.Rol.PI_SUB)

    def test_solo_gerencia_administra_usuarios(self):
        url = reverse('usuario-list')
        self.client.force_authenticate(user=self.sub)
        self.assertEqual(self.client.get(url).status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(self.client.get(url).status_code, status.HTTP_200_OK)

    def test_gerencia_crea_tecnico_con_password_hasheada(self):
        self.client.force_authenticate(user=self.admin)
        respuesta = self.client.post(reverse('usuario-list'), {
            'expediente': 'tec-4410', 'first_name': 'Luis', 'last_name': 'Serrano',
            'rol': UsuarioGIO.Rol.TECNICO, 'area_operativa': 'PUEBLA',
            'password': 'Campo.2026.Seg',
        }, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED)
        self.assertNotIn('password', respuesta.data)
        creado = UsuarioGIO.objects.get(expediente='TEC-4410')
        self.assertNotEqual(creado.password, 'Campo.2026.Seg')
        self.assertTrue(creado.check_password('Campo.2026.Seg'))

    def test_password_debil_se_rechaza(self):
        self.client.force_authenticate(user=self.admin)
        respuesta = self.client.post(reverse('usuario-list'), {
            'expediente': 'TEC-0002', 'rol': UsuarioGIO.Rol.TECNICO, 'password': '123456',
        }, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', respuesta.data)

    def test_baja_de_usuario_lo_desactiva_sin_borrarlo(self):
        self.client.force_authenticate(user=self.admin)
        respuesta = self.client.delete(reverse('usuario-detail', args=[self.sub.pk]))
        self.assertEqual(respuesta.status_code, status.HTTP_204_NO_CONTENT)
        self.sub.refresh_from_db()
        self.assertFalse(self.sub.is_active)

    def test_cambio_de_password_propio(self):
        self.client.force_authenticate(user=self.sub)
        url = reverse('cambiar-password')
        self.assertEqual(
            self.client.post(url, {'password_actual': 'mala', 'password_nueva': 'Otra.2026.Seg'},
                             format='json').status_code,
            status.HTTP_400_BAD_REQUEST)
        respuesta = self.client.post(
            url, {'password_actual': 'Gio.2026.Seg', 'password_nueva': 'Otra.2026.Seg'},
            format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.sub.refresh_from_db()
        self.assertTrue(self.sub.check_password('Otra.2026.Seg'))


class CuentaPropiaTests(APITestCase):
    """Cada usuario cambia su contraseña y registra su correo de recuperación."""

    @classmethod
    def setUpTestData(cls):
        cls.tecnico = UsuarioGIO.objects.create_user(
            expediente='TEC-4410', password='Gio.2026.Seg', rol=UsuarioGIO.Rol.TECNICO,
            first_name='Luis', last_name='Serrano')

    def setUp(self):
        self.client.force_authenticate(user=self.tecnico)

    def test_password_nueva_debil_o_igual_se_rechaza(self):
        url = reverse('cambiar-password')
        for nueva in ('', '12345678', 'Gio.2026.Seg'):
            respuesta = self.client.post(url, {'password_actual': 'Gio.2026.Seg',
                                               'password_nueva': nueva}, format='json')
            self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST, nueva)
            self.assertIn('password_nueva', respuesta.data)
        self.tecnico.refresh_from_db()
        self.assertTrue(self.tecnico.check_password('Gio.2026.Seg'))

    def test_registra_su_correo_confirmando_la_contrasena(self):
        url = reverse('correo-recuperacion')
        respuesta = self.client.post(url, {'password_actual': 'mala',
                                           'email': 'luis@empresa.mx'}, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        respuesta = self.client.post(url, {'password_actual': 'Gio.2026.Seg',
                                           'email': 'no-es-correo'}, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', respuesta.data)
        respuesta = self.client.post(url, {'password_actual': 'Gio.2026.Seg',
                                           'email': ' Luis@Empresa.MX '}, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(respuesta.data['email'], 'Luis@empresa.mx')
        self.tecnico.refresh_from_db()
        self.assertEqual(self.tecnico.email, 'Luis@empresa.mx')


@override_settings(URL_PUBLICA='https://gio.empresa.mx',
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class RecuperacionPasswordTests(APITestCase):
    """¿Olvidó su contraseña?: un enlace por correo para crear una nueva."""

    @classmethod
    def setUpTestData(cls):
        cls.tecnico = UsuarioGIO.objects.create_user(
            expediente='TEC-4410', password='Gio.2026.Seg', rol=UsuarioGIO.Rol.TECNICO,
            first_name='Luis', last_name='Serrano', email='luis@empresa.mx')
        cls.sin_correo = UsuarioGIO.objects.create_user(
            expediente='OQU-8821', password='Gio.2026.Seg', rol=UsuarioGIO.Rol.PI_EVALUADOR)

    def setUp(self):
        cache.clear()

    def pedir(self, expediente):
        return self.client.post(reverse('recuperar-password'), {'expediente': expediente},
                                format='json')

    def enlace(self):
        self.assertEqual(len(mail.outbox), 1)
        coincidencia = re.search(r'https://gio\.empresa\.mx/restablecer/([^/\s]+)/([^/\s]+)',
                                 mail.outbox[0].body)
        self.assertIsNotNone(coincidencia, mail.outbox[0].body)
        return coincidencia.groups()

    def restablecer(self, uid, token, nueva='Nueva.2026.Seg'):
        return self.client.post(reverse('restablecer-password'),
                                {'uid': uid, 'token': token, 'password_nueva': nueva},
                                format='json')

    def test_envia_el_enlace_al_correo_registrado(self):
        respuesta = self.pedir('tec-4410')
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(mail.outbox[0].to, ['luis@empresa.mx'])
        self.assertIn('TEC-4410', mail.outbox[0].body)
        uid, token = self.enlace()
        self.assertEqual(self.restablecer(uid, token).status_code, status.HTTP_200_OK)
        self.tecnico.refresh_from_db()
        self.assertTrue(self.tecnico.check_password('Nueva.2026.Seg'))

    def test_la_respuesta_no_revela_si_el_expediente_existe(self):
        respuestas = [self.pedir(expediente) for expediente in ('TEC-4410', 'OQU-8821', 'NO-EXISTE')]
        self.assertEqual({r.status_code for r in respuestas}, {status.HTTP_200_OK})
        self.assertEqual(len({r.data['detail'] for r in respuestas}), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_usuario_dado_de_baja_no_recibe_enlace(self):
        UsuarioGIO.objects.filter(pk=self.tecnico.pk).update(is_active=False)
        self.pedir('TEC-4410')
        self.assertEqual(mail.outbox, [])

    def test_el_enlace_sirve_una_sola_vez(self):
        self.pedir('TEC-4410')
        uid, token = self.enlace()
        self.assertEqual(self.restablecer(uid, token).status_code, status.HTTP_200_OK)
        segunda = self.restablecer(uid, token, 'Otra.2026.Seg')
        self.assertEqual(segunda.status_code, status.HTTP_400_BAD_REQUEST)
        self.tecnico.refresh_from_db()
        self.assertTrue(self.tecnico.check_password('Nueva.2026.Seg'))

    def test_enlace_alterado_o_password_debil_se_rechazan(self):
        self.pedir('TEC-4410')
        uid, token = self.enlace()
        self.assertEqual(self.restablecer(uid, 'token-falso').status_code,
                         status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.restablecer('no-es-uid', token).status_code,
                         status.HTTP_400_BAD_REQUEST)
        debil = self.restablecer(uid, token, '12345678')
        self.assertEqual(debil.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password_nueva', debil.data)

    @override_settings(PASSWORD_RESET_TIMEOUT=60)
    def test_el_enlace_vence(self):
        self.pedir('TEC-4410')
        uid, token = self.enlace()
        with patch('django.contrib.auth.tokens.PasswordResetTokenGenerator._now',
                   return_value=datetime.now() + timedelta(minutes=5)):
            self.assertEqual(self.restablecer(uid, token).status_code,
                             status.HTTP_400_BAD_REQUEST)

    def test_si_el_correo_falla_lo_dice(self):
        with patch('usuarios.recuperacion.send_mail', side_effect=OSError('Sin conexión SMTP')):
            respuesta = self.pedir('TEC-4410')
        self.assertEqual(respuesta.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_no_requiere_sesion_aunque_llegue_un_token_vencido(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer token-vencido')
        self.assertEqual(self.pedir('TEC-4410').status_code, status.HTTP_200_OK)
