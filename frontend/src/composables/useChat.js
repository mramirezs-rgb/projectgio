import { ref } from 'vue'
import { getMensajesPendientes } from '../services/api.js'

// Cada cuánto se revisan mensajes sin leer de todos los folios. El chat abierto consulta aparte.
const INTERVALO_AVISOS_MS = 30000

const total = ref(0)
const porFolio = ref({})
const recientes = ref([])
let temporizador = null

const consultar = async () => {
  if (document.hidden) return
  try {
    const { data } = await getMensajesPendientes()
    total.value = data.total || 0
    porFolio.value = data.por_folio || {}
    recientes.value = data.recientes || []
  } catch {
    /* se reintenta en la siguiente vuelta */
  }
}

// Al volver a la pestaña o desbloquear el teléfono se revisa de inmediato.
const alCambiarVisibilidad = () => {
  if (!document.hidden) consultar()
}

export const iniciarAvisosDeChat = () => {
  if (temporizador) return
  consultar()
  temporizador = setInterval(consultar, INTERVALO_AVISOS_MS)
  document.addEventListener('visibilitychange', alCambiarVisibilidad)
}

export const detenerAvisosDeChat = () => {
  clearInterval(temporizador)
  temporizador = null
  document.removeEventListener('visibilitychange', alCambiarVisibilidad)
  total.value = 0
  porFolio.value = {}
  recientes.value = []
}

export function useChat() {
  const sinLeerDe = (id) => porFolio.value[id] || 0

  // El servidor marca como leído lo que devuelve al chat abierto; aquí solo se refleja.
  const marcarLeido = (id) => {
    const pendientes = porFolio.value[id]
    if (!pendientes) return
    const { [id]: _, ...resto } = porFolio.value
    porFolio.value = resto
    total.value = Math.max(0, total.value - pendientes)
    recientes.value = recientes.value.filter((item) => String(item.id) !== String(id))
  }

  return { total, recientes, sinLeerDe, marcarLeido, actualizarAvisos: consultar }
}
