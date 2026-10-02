import { ref, computed } from 'vue';
import { loginApi } from '../services/api.js';

// ESTADO GLOBAL COMPARTIDO
const token = ref(localStorage.getItem('gio_token') || null);
const usuario = ref(JSON.parse(localStorage.getItem('gio_user') || 'null'));
const cargando = ref(false);
const errorLogin = ref(null);
export function useAuth() {
  const estaAutenticado = computed(() => !!token.value);
  const esTecnico = computed(() => usuario.value?.rol === 'TECNICO');
  const esEvaluador = computed(() => usuario.value?.rol === 'PI_EVALUADOR');
  const esSubgerencia = computed(() => usuario.value?.rol === 'PI_SUB');
  const esGerencia = computed(() => usuario.value?.rol === 'ADMIN' || usuario.value?.is_superuser);
  const puedeCrearFolio = computed(() => esSubgerencia.value || esGerencia.value);
  const puedeAsignar = computed(() => esSubgerencia.value || esGerencia.value);
  const puedeGestionarUsuarios = computed(() => esGerencia.value);
  const iniciarSesion = async (expediente, password) => {
    cargando.value = true;
    errorLogin.value = null;
    try {
      const response = await loginApi({
        username: expediente,
        expediente: expediente,
        password: password
      });
      const tokenRecibido = response.data.access || response.data.token || response.data.key;
      // Fallback seguro: Si el backend no envía rol, asignamos el de menor nivel.
      const datosUsuario = response.data.user || response.data.usuario || { 
        id: null,
        expediente, 
        nombre: expediente, 
        rol: 'PI_EVALUADOR' 
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
    errorLogin,esTecnico,
    esEvaluador,
    esSubgerencia,
    esGerencia,
    puedeCrearFolio,
    puedeAsignar,
    puedeGestionarUsuarios,
    iniciarSesion,
    cerrarSesion
  };
}