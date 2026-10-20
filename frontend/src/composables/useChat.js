import { ref, watch } from 'vue'
import router from '../router/index.js'
import { getMensajesPendientes } from '../services/api.js'
import { avisarMensaje, hayDialogoAbierto } from '../utils/alerts.js'
import { ROLES, useAuth } from './useAuth.js'

// Cada cuánto se revisan mensajes sin leer de todos los folios. El chat abierto consulta aparte.
const INTERVALO_AVISOS_MS = 15000
const TITULO_PAGINA = document.title

const total = ref(0)
const porFolio = ref({})
const recientes = ref([])
// Folio cuyo chat está en pantalla: sus mensajes se ven ahí y no necesitan aviso.
const chatEnPantalla = ref(null)
// Cuántos mensajes sin leer de cada folio ya se avisaron, para avisar solo los que lleguen después.
let anunciados = {}
let temporizador = null

// El contador en el título se ve aunque GIO esté en otra pestaña.
watch(total, (cantidad) => {
  document.title = cantidad ? `(${cantidad}) ${TITULO_PAGINA}` : TITULO_PAGINA
})

const irAlChat = (id) => {
  const { rol } = useAuth()
  router.push({
    name: rol.value === ROLES.TECNICO ? 'campo' : 'tablero',
    query: { folio: String(id), chat: '1' },
  })
}

const anunciarNuevos = () => {
  const nuevos = Object.entries(porFolio.value)
    .filter(([id, cantidad]) => cantidad > (anunciados[id] || 0))
    .filter(([id]) => id !== String(chatEnPantalla.value))
  if (!nuevos.length || hayDialogoAbierto()) return

  const cantidad = nuevos.reduce((suma, [id, n]) => suma + n - (anunciados[id] || 0), 0)
  anunciados = { ...porFolio.value }
  const ids = new Set(nuevos.map(([id]) => id))
  const ultimo = recientes.value.find((item) => ids.has(String(item.id)))
  const destino = ultimo?.id ?? nuevos[0][0]
  const vistaPrevia = ultimo ? `${ultimo.ultimo.autor_nombre}: ${ultimo.ultimo.texto}` : ''

  if (nuevos.length === 1) {
    const titulo = cantidad === 1 ? 'Mensaje nuevo' : `${cantidad} mensajes nuevos`
    avisarMensaje(
      ultimo ? `${titulo} · Folio ${ultimo.folio}` : titulo,
      vistaPrevia,
      () => irAlChat(destino),
    )
  } else {
    avisarMensaje(
      `${cantidad} mensajes nuevos en ${nuevos.length} folios`,
      ultimo ? `Folio ${ultimo.folio} · ${vistaPrevia}` : '',
      () => irAlChat(destino),
    )
  }
  // El navegador solo deja vibrar después de que el usuario tocó la página alguna vez.
  if (navigator.userActivation?.hasBeenActive ?? true) {
    try {
      navigator.vibrate?.([150, 80, 150])
    } catch {
      /* el navegador no permite vibrar */
    }
  }
}

// Sigue consultando con la pestaña oculta para mantener el contador del título al día; el aviso
// emergente espera a que la pantalla vuelva a estar a la vista.
const consultar = async () => {
  try {
    const { data } = await getMensajesPendientes()
    total.value = data.total || 0
    porFolio.value = data.por_folio || {}
    recientes.value = data.recientes || []
  } catch {
    return /* se reintenta en la siguiente vuelta */
  }
  // Si un folio se leyó en otro equipo, su siguiente mensaje debe volver a avisarse.
  for (const id of Object.keys(anunciados)) {
    anunciados[id] = Math.min(anunciados[id], porFolio.value[id] || 0)
  }
  if (!document.hidden) anunciarNuevos()
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
  anunciados = {}
}

export function useChat() {
  const sinLeerDe = (id) => porFolio.value[id] || 0

  // El servidor marca como leído lo que devuelve al chat abierto; aquí solo se refleja.
  const marcarLeido = (id) => {
    delete anunciados[id]
    const pendientes = porFolio.value[id]
    if (!pendientes) return
    const { [id]: _, ...resto } = porFolio.value
    porFolio.value = resto
    total.value = Math.max(0, total.value - pendientes)
    recientes.value = recientes.value.filter((item) => String(item.id) !== String(id))
  }

  const mostrarChat = (id) => {
    chatEnPantalla.value = id
  }

  const ocultarChat = (id) => {
    if (chatEnPantalla.value === id) chatEnPantalla.value = null
  }

  return {
    total,
    recientes,
    sinLeerDe,
    marcarLeido,
    mostrarChat,
    ocultarChat,
    irAlChat,
    actualizarAvisos: consultar,
  }
}
