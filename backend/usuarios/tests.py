from django.contrib.auth import get_user_model
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
