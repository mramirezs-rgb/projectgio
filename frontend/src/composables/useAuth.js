import { computed, ref } from 'vue'
import {
  getPerfil,
  guardarSesion,
  limpiarSesion,
  loginApi,
  mensajeDeError,
  tokenActual,
  usuarioGuardado,
} from '../services/api.js'

const token = ref(tokenActual())
const usuario = ref(usuarioGuardado())
const cargando = ref(false)
const errorLogin = ref(null)

const PERMISOS_VACIOS = {
  vision_global: false,
  asignar: false,
  crear_folio: false,
  gestionar_usuarios: false,
  liquidar: false,
  cargar_evidencia: false,
  exportar: false,
}

export const ROLES = {
  TECNICO: 'TECNICO',
  PI_EVALUADOR: 'PI_EVALUADOR',
  PI_SUB: 'PI_SUB',
  ADMIN: 'ADMIN',
}

export const rutaInicialPara = (rol) => (rol === ROLES.TECNICO ? '/campo' : '/tablero')

export function useAuth() {
  const estaAutenticado = computed(() => !!token.value)
  const rol = computed(() => usuario.value?.rol || null)
  const permisos = computed(() => ({ ...PERMISOS_VACIOS, ...(usuario.value?.permisos || {}) }))

  const esTecnico = computed(() => rol.value === ROLES.TECNICO)
  const esEvaluador = computed(() => rol.value === ROLES.PI_EVALUADOR)
  const esSubgerencia = computed(() => rol.value === ROLES.PI_SUB)
  const esGerencia = computed(() => rol.value === ROLES.ADMIN || !!usuario.value?.is_superuser)

  const iniciarSesion = async (expediente, password) => {
    cargando.value = true
    errorLogin.value = null
    try {
      const { data } = await loginApi({
        expediente: String(expediente || '').trim(),
        password,
      })
      if (!data.access) throw new Error('El servidor no devolvió un token de sesión.')
      guardarSesion({ access: data.access, refresh: data.refresh, usuario: data.user })
      token.value = data.access
      usuario.value = data.user
      return data.user
    } catch (error) {
      errorLogin.value =
        error?.response?.status === 401
          ? 'Expediente o contraseña incorrectos.'
          : mensajeDeError(error, 'No se pudo iniciar sesión.')
      throw error
    } finally {
      cargando.value = false
    }
  }

  const refrescarPerfil = async () => {
    if (!token.value) return null
    try {
      const { data } = await getPerfil()
      usuario.value = data
      guardarSesion({ usuario: data })
      return data
    } catch {
      return null
    }
  }

  const cerrarSesion = () => {
    limpiarSesion()
    token.value = null
    usuario.value = null
    errorLogin.value = null
  }

  return {
    token,
    usuario,
    rol,
    permisos,
    cargando,
    errorLogin,
    estaAutenticado,
    esTecnico,
    esEvaluador,
    esSubgerencia,
    esGerencia,
    iniciarSesion,
    refrescarPerfil,
    cerrarSesion,
  }
}
