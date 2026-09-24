import { ref, computed } from 'vue';
import { loginApi } from '../services/api.js'; // Ajusta según la ubicación de tu api.js

// ESTADO GLOBAL COMPARTIDO
const token = ref(localStorage.getItem('gio_token') || null);
const usuario = ref(JSON.parse(localStorage.getItem('gio_user') || 'null'));
const cargando = ref(false);
const errorLogin = ref(null);

export function useAuth() {
  // Propiedad reactiva que escucha App.vue para alternar la vista
  const estaAutenticado = computed(() => !!token.value);

  const iniciarSesion = async (expediente, password) => {
    cargando.value = true;
    errorLogin.value = null;

    try {
      const response = await loginApi({
        username: expediente,
        expediente: expediente,
        password: password
      });

      // Extraer Token de la respuesta según formato JWT o Rest Framework
      const tokenRecibido = response.data.access || response.data.token || response.data.key;
      const datosUsuario = response.data.user || response.data.usuario || { 
        expediente, 
        nombre: expediente, 
        rol: 'ADMIN' 
      };

      if (!tokenRecibido) {
        throw new Error('El servidor no devolvió un token de sesión.');
      }

      localStorage.setItem('gio_token', tokenRecibido);
      localStorage.setItem('gio_user', JSON.stringify(datosUsuario));

      token.value = tokenRecibido;
      usuario.value = datosUsuario;

    } catch (err) {
      console.error('Error en iniciarSesion:', err);
      if (err.response?.data) {
        errorLogin.value = err.response.data.detail || err.response.data.error || 'Credenciales inválidas.';
      } else {
        errorLogin.value = 'No se pudo conectar con el servidor.';
      }
    } finally {
      cargando.value = false;
    }
  };

  const cerrarSesion = () => {
    localStorage.removeItem('gio_token');
    localStorage.removeItem('gio_user');
    token.value = null;
    usuario.value = null;
  };

  return {
    token,
    usuario,
    estaAutenticado,
    cargando,
    errorLogin,
    iniciarSesion,
    cerrarSesion
  };
}