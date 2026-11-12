import { computed, ref, watch } from 'vue'
import router from '../router/index.js'
import { getMensajesPendientes } from '../services/api.js'
import { avisarMensaje, avisarMensajeDeGerencia, hayDialogoAbierto } from '../utils/alerts.js'
import { ROLES, useAuth } from './useAuth.js'

// Cada cuánto se revisan mensajes sin leer de todos los folios. El chat abierto consulta aparte.
const INTERVALO_AVISOS_MS = 15000
const TITULO_PAGINA = document.title

// Consultas seguidas sin respuesta a partir de las cuales se avisa que no están llegando mensajes.
const FALLOS_PARA_AVISAR = 3

const total = ref(0)
const deGerencia = ref(0)
// Mensajes que nadie leyó a tiempo y se escalaron a quien consulta.
const sinAtender = ref(0)
const sinConexion = ref(false)
let fallos = 0
// 'default' (aún no se pregunta), 'granted', 'denied' o 'unsupported'. Las notificaciones del
// sistema solo existen en una dirección segura (https o localhost).
const permisoDelSistema = ref(
  typeof Notification !== 'undefined' && window.isSecureContext
    ? Notification.permission
    : 'unsupported',
)
const porFolio = ref({})
// Mensajes de Gerencia sin leer por folio: son prioritarios y se avisan aparte.
const gerenciaPorFolio = ref({})
const recientes = ref([])
// Folio cuyo chat está en pantalla: sus mensajes se ven ahí y no necesitan aviso.
const chatEnPantalla = ref(null)
// Cuántos mensajes sin leer de cada folio ya se avisaron, para avisar solo los que lleguen después.
let anunciados = {}
let anunciadosDeGerencia = {}
// Lo ya avisado con sonido y notificación del sistema mientras la pestaña no estaba a la vista.
let avisadosFuera = {}
let temporizador = null
let audio = null

// El contador en el título se ve aunque GIO esté en otra pestaña.
watch(total, (cantidad) => {
  document.title = cantidad ? `(${cantidad}) ${TITULO_PAGINA}` : TITULO_PAGINA
})

const rutaDelChat = (id) => {
  const { rol } = useAuth()
  return {
    name: rol.value === ROLES.TECNICO ? 'campo' : 'tablero',
    query: { folio: String(id), chat: '1' },
  }
}

const irAlChat = (id) => router.push(rutaDelChat(id))

// Dos tonos cortos; tres si el mensaje es de Gerencia. El navegador solo deja sonar después de
// que el usuario tocó la página alguna vez.
const sonar = (prioritario = false) => {
  try {
    const Contexto = window.AudioContext || window.webkitAudioContext
    if (!Contexto) return
    audio = audio || new Contexto()
    if (audio.state === 'suspended') audio.resume()
    const tonos = prioritario ? [880, 660, 880] : [660, 880]
    tonos.forEach((frecuencia, indice) => {
      const inicio = audio.currentTime + indice * 0.18
      const oscilador = audio.createOscillator()
      const volumen = audio.createGain()
      oscilador.frequency.value = frecuencia
      volumen.gain.setValueAtTime(0.0001, inicio)
      volumen.gain.exponentialRampToValueAtTime(0.25, inicio + 0.02)
      volumen.gain.exponentialRampToValueAtTime(0.0001, inicio + 0.16)
      oscilador.connect(volumen).connect(audio.destination)
      oscilador.start(inicio)
      oscilador.stop(inicio + 0.17)
    })
  } catch {
    /* el navegador no permite sonar */
  }
}

// Notificación del sistema operativo: se ve aunque GIO esté en otra pestaña o minimizado.
const notificarAlSistema = async (titulo, cuerpo, id) => {
  if (permisoDelSistema.value !== 'granted') return
  const opciones = {
    body: cuerpo,
    tag: `gio-chat-${id}`,
    renotify: true,
    icon: '/pwa-192x192.png',
    data: { url: router.resolve(rutaDelChat(id)).href },
  }
  try {
    // En teléfonos solo el service worker puede mostrarlas.
    const registro = await navigator.serviceWorker?.getRegistration()
    if (registro) {
      await registro.showNotification(titulo, opciones)
      return
    }
    const aviso = new Notification(titulo, opciones)
    aviso.onclick = () => {
      window.focus()
      irAlChat(id)
      aviso.close()
    }
  } catch {
    /* el navegador no permite notificar */
  }
}

// Con la pestaña oculta el aviso emergente espera a que vuelva a verse; mientras tanto se avisa
// con sonido y, si el usuario lo activó, con una notificación del sistema.
const avisarFueraDePantalla = () => {
  const nuevos = Object.entries(porFolio.value).filter(
    ([id, cantidad]) => cantidad > (avisadosFuera[id] || 0),
  )
  avisadosFuera = { ...porFolio.value }
  if (!nuevos.length) return
  const ids = new Set(nuevos.map(([id]) => id))
  const ultimo = recientes.value.find((item) => ids.has(String(item.id)))
  const prioritario = nuevos.some(([id]) => gerenciaPorFolio.value[id])
  sonar(prioritario)
  const destino = ultimo?.id ?? nuevos[0][0]
  const inicio = prioritario ? 'Mensaje de Gerencia' : 'Mensaje nuevo'
  notificarAlSistema(
    ultimo ? `${inicio} · Folio ${ultimo.folio}` : inicio,
    ultimo ? `${ultimo.ultimo.autor_nombre}: ${ultimo.ultimo.texto}` : '',
    destino,
  )
}

const vibrar = (patron) => {
  // El navegador solo deja vibrar después de que el usuario tocó la página alguna vez.
  if (!(navigator.userActivation?.hasBeenActive ?? true)) return
  try {
    navigator.vibrate?.(patron)
  } catch {
    /* el navegador no permite vibrar */
  }
}

// Los mensajes de Gerencia se avisan antes que los demás, con un aviso propio que dura más. Si
// hay otro diálogo abierto, esperan a la siguiente consulta.
const anunciarDeGerencia = () => {
  const nuevos = Object.entries(gerenciaPorFolio.value)
    .filter(([id, cantidad]) => cantidad > (anunciadosDeGerencia[id] || 0))
    .filter(([id]) => id !== String(chatEnPantalla.value))
  if (!nuevos.length || hayDialogoAbierto()) return false

  const cantidad = nuevos.reduce(
    (suma, [id, n]) => suma + n - (anunciadosDeGerencia[id] || 0),
    0,
  )
  anunciadosDeGerencia = { ...gerenciaPorFolio.value }
  // Ya quedan avisados también como mensajes comunes.
  anunciados = { ...porFolio.value }
  const ids = new Set(nuevos.map(([id]) => id))
  const ultimo = recientes.value.find((item) => ids.has(String(item.id)))
  const destino = ultimo?.id ?? nuevos[0][0]
  const titulo =
    cantidad === 1 ? 'Mensaje de Gerencia' : `${cantidad} mensajes de Gerencia`
  avisarMensajeDeGerencia(
    ultimo && nuevos.length === 1 ? `${titulo} · Folio ${ultimo.folio}` : titulo,
    ultimo ? `${ultimo.ultimo.autor_nombre}: ${ultimo.ultimo.texto}` : '',
    () => irAlChat(destino),
  )
  vibrar([300, 100, 300, 100, 300])
  sonar(true)
  return true
}

const anunciarNuevos = () => {
  if (anunciarDeGerencia()) return
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
  vibrar([150, 80, 150])
  sonar()
}

// Sigue consultando con la pestaña oculta para mantener el contador del título al día; el aviso
// emergente espera a que la pantalla vuelva a estar a la vista.
const consultar = async () => {
  try {
    const { data } = await getMensajesPendientes()
    total.value = data.total || 0
    deGerencia.value = data.de_gerencia || 0
    sinAtender.value = data.sin_atender || 0
    fallos = 0
    sinConexion.value = false
    porFolio.value = data.por_folio || {}
    gerenciaPorFolio.value = data.gerencia_por_folio || {}
    recientes.value = data.recientes || []
  } catch {
    // Se reintenta en la siguiente vuelta; si falla varias veces seguidas se le dice al usuario,
    // porque mientras tanto no se entera de los mensajes nuevos.
    fallos += 1
    if (fallos >= FALLOS_PARA_AVISAR) sinConexion.value = true
    return
  }
  // Si un folio se leyó en otro equipo, su siguiente mensaje debe volver a avisarse.
  for (const id of Object.keys(anunciados)) {
    anunciados[id] = Math.min(anunciados[id], porFolio.value[id] || 0)
  }
  for (const id of Object.keys(anunciadosDeGerencia)) {
    anunciadosDeGerencia[id] = Math.min(anunciadosDeGerencia[id], gerenciaPorFolio.value[id] || 0)
  }
  if (document.hidden) {
    avisarFueraDePantalla()
  } else {
    avisadosFuera = { ...porFolio.value }
    anunciarNuevos()
  }
}

// El navegador pide el permiso al usuario; solo puede hacerse como respuesta a un clic.
export const activarNotificacionesDelSistema = async () => {
  if (permisoDelSistema.value === 'unsupported') return
  try {
    permisoDelSistema.value = await Notification.requestPermission()
  } catch {
    permisoDelSistema.value = 'denied'
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
  deGerencia.value = 0
  sinAtender.value = 0
  sinConexion.value = false
  fallos = 0
  avisadosFuera = {}
  porFolio.value = {}
  gerenciaPorFolio.value = {}
  recientes.value = []
  anunciados = {}
  anunciadosDeGerencia = {}
}

const foliosConMensajes = computed(() => Object.keys(porFolio.value).length)

export function useChat() {
  const sinLeerDe = (id) => porFolio.value[id] || 0

  // El servidor marca como leído lo que devuelve al chat abierto; aquí solo se refleja.
  const marcarLeido = (id) => {
    delete anunciados[id]
    delete anunciadosDeGerencia[id]
    delete avisadosFuera[id]
    const pendientes = porFolio.value[id]
    if (!pendientes) return
    const { [id]: _, ...resto } = porFolio.value
    porFolio.value = resto
    const { [id]: prioritarios = 0, ...restoGerencia } = gerenciaPorFolio.value
    gerenciaPorFolio.value = restoGerencia
    deGerencia.value = Math.max(0, deGerencia.value - prioritarios)
    total.value = Math.max(0, total.value - pendientes)
    const leido = recientes.value.find((item) => String(item.id) === String(id))
    sinAtender.value = Math.max(0, sinAtender.value - (leido?.sin_atender || 0))
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
    deGerencia,
    sinAtender,
    sinConexion,
    foliosConMensajes,
    permisoDelSistema,
    recientes,
    sinLeerDe,
    marcarLeido,
    mostrarChat,
    ocultarChat,
    irAlChat,
    actualizarAvisos: consultar,
  }
}
