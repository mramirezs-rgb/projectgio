import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

export const CLAVE_TOKEN = 'gio_token'
export const CLAVE_REFRESH = 'gio_refresh'
export const CLAVE_USUARIO = 'gio_user'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
})

let alCaducarSesion = null
export const registrarCaducidadSesion = (manejador) => {
  alCaducarSesion = manejador
}

const leer = (clave) => {
  try {
    return localStorage.getItem(clave)
  } catch {
    return null
  }
}

const escribir = (clave, valor) => {
  try {
    if (valor === null || valor === undefined) localStorage.removeItem(clave)
    else localStorage.setItem(clave, valor)
  } catch {
    /* almacenamiento no disponible */
  }
}

export const guardarSesion = ({ access, refresh, usuario }) => {
  if (access) escribir(CLAVE_TOKEN, access)
  if (refresh) escribir(CLAVE_REFRESH, refresh)
  if (usuario) escribir(CLAVE_USUARIO, JSON.stringify(usuario))
}

export const limpiarSesion = () => {
  escribir(CLAVE_TOKEN, null)
  escribir(CLAVE_REFRESH, null)
  escribir(CLAVE_USUARIO, null)
}

export const tokenActual = () => leer(CLAVE_TOKEN)

export const usuarioGuardado = () => {
  try {
    return JSON.parse(leer(CLAVE_USUARIO) || 'null')
  } catch {
    return null
  }
}

api.interceptors.request.use((config) => {
  const token = leer(CLAVE_TOKEN)
  if (token) config.headers.Authorization = `Bearer ${token}`
  if (config.data instanceof FormData) delete config.headers['Content-Type']
  return config
})

let refrescoEnCurso = null

const refrescarToken = () => {
  const refresh = leer(CLAVE_REFRESH)
  if (!refresh) return Promise.reject(new Error('sin-refresh'))
  if (!refrescoEnCurso) {
    refrescoEnCurso = axios
      .post(`${API_BASE_URL}/auth/refresh/`, { refresh })
      .then(({ data }) => {
        escribir(CLAVE_TOKEN, data.access)
        if (data.refresh) escribir(CLAVE_REFRESH, data.refresh)
        return data.access
      })
      .finally(() => {
        refrescoEnCurso = null
      })
  }
  return refrescoEnCurso
}

api.interceptors.response.use(
  (respuesta) => respuesta,
  async (error) => {
    const peticion = error.config || {}
    const esRutaAuth = String(peticion.url || '').includes('/auth/')

    if (error.response?.status === 401 && !peticion._reintentada && !esRutaAuth) {
      peticion._reintentada = true
      try {
        const nuevoToken = await refrescarToken()
        peticion.headers = { ...peticion.headers, Authorization: `Bearer ${nuevoToken}` }
        return api(peticion)
      } catch {
        limpiarSesion()
        if (alCaducarSesion) alCaducarSesion()
        return Promise.reject(error)
      }
    }

    if (error.response?.status === 401 && !esRutaAuth) {
      limpiarSesion()
      if (alCaducarSesion) alCaducarSesion()
    }
    return Promise.reject(error)
  },
)

export const mensajeDeError = (error, respaldo = 'Ocurrió un error inesperado.') => {
  if (error?.code === 'ECONNABORTED') return 'La petición excedió el tiempo de espera.'
  const datos = error?.response?.data
  if (!datos) return error?.message === 'Network Error' ? 'No hay conexión con el servidor GIO.' : respaldo
  if (typeof datos === 'string') return datos
  if (datos.detail) return datos.detail
  const partes = []
  for (const [campo, valor] of Object.entries(datos)) {
    const texto = Array.isArray(valor) ? valor.join(' ') : String(valor)
    partes.push(campo === 'detail' || campo === 'non_field_errors' ? texto : `${campo}: ${texto}`)
  }
  return partes.join('\n') || respaldo
}

export const loginApi = (credenciales) => api.post('/auth/login/', credenciales)
export const getPerfil = () => api.get('/auth/me/')
export const cambiarPassword = (datos) => api.post('/auth/password/', datos)

export const getIncidentes = (params) => api.get('/incidentes/', { params })
export const getIncidente = (id) => api.get(`/incidentes/${id}/`)
export const createIncidente = (datos) => api.post('/incidentes/', datos)
export const updateIncidente = (id, datos) => api.patch(`/incidentes/${id}/`, datos)
export const deleteIncidente = (id) => api.delete(`/incidentes/${id}/`)
export const liquidarIncidente = (id, datos) => api.post(`/incidentes/${id}/liquidar/`, datos)
export const getBitacora = (id) => api.get(`/incidentes/${id}/bitacora/`)
export const getMetricas = (params) => api.get('/incidentes/metricas/', { params })
export const asignarMasivo = (datos) => api.post('/incidentes/asignar-masivo/', datos)

export const getEvidencias = (id) => api.get(`/incidentes/${id}/evidencias/`)
export const subirEvidencia = (id, formData, onProgreso) =>
  api.post(`/incidentes/${id}/evidencias/`, formData, {
    timeout: 90000,
    onUploadProgress: (evento) => {
      if (onProgreso && evento.total) onProgreso(Math.round((evento.loaded * 100) / evento.total))
    },
  })
export const eliminarEvidencia = (idEvidencia) => api.delete(`/evidencias/${idEvidencia}/`)

export const getTecnicos = () => api.get('/tecnicos/')
export const getEvaluadores = () => api.get('/evaluadores/')
export const getCentrales = () => api.get('/centrales/')
export const getAreas = () => api.get('/areas/')
export const getCatalogos = () => api.get('/catalogos/')

export const getUsuarios = (params) => api.get('/usuarios/', { params })
export const createUsuario = (datos) => api.post('/usuarios/', datos)
export const updateUsuario = (id, datos) => api.patch(`/usuarios/${id}/`, datos)
export const desactivarUsuario = (id) => api.delete(`/usuarios/${id}/`)

export default api
