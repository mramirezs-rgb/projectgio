<script setup>
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { ROLES, useAuth } from '../composables/useAuth.js'
import { useChat } from '../composables/useChat.js'
import { enviarMensaje, getMensajes, mensajeDeError } from '../services/api.js'

const props = defineProps({
  incidenteId: { type: Number, required: true },
})

// Mientras el chat está a la vista se buscan mensajes nuevos con esta frecuencia.
const INTERVALO_MS = 5000
const MAX_CARACTERES = 2000

const LADO_POR_ROL = {
  [ROLES.TECNICO]: 'Planta externa',
  [ROLES.PI_EVALUADOR]: 'Planta interna',
  [ROLES.PI_SUB]: 'Subgerencia',
  [ROLES.ADMIN]: 'Gerencia',
}

const { usuario } = useAuth()
const { marcarLeido } = useChat()

const mensajes = ref([])
const cargando = ref(false)
const problema = ref('')
const texto = ref('')
const enviando = ref(false)
const lista = ref(null)
let temporizador = null

// En teléfono, Enter hace salto de línea como en el teclado del sistema; se envía con el botón.
const esTactil =
  typeof window !== 'undefined' && !!window.matchMedia?.('(pointer: coarse)').matches

const esPropio = (mensaje) => mensaje.autor === usuario.value?.id

const horaDe = (valor) => {
  const fecha = new Date(valor)
  if (Number.isNaN(fecha.getTime())) return ''
  const hora = fecha.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })
  if (fecha.toDateString() === new Date().toDateString()) return hora
  return `${fecha.toLocaleDateString('es-MX', { day: '2-digit', month: 'short' })} ${hora}`
}

const cercaDelFinal = () => {
  const caja = lista.value
  return !caja || caja.scrollHeight - caja.scrollTop - caja.clientHeight < 80
}

const bajarAlFinal = async () => {
  await nextTick()
  if (lista.value) lista.value.scrollTop = lista.value.scrollHeight
}

const agregar = (nuevos) => {
  const conocidos = new Set(mensajes.value.map((m) => m.id))
  const frescos = nuevos.filter((m) => !conocidos.has(m.id))
  if (frescos.length) mensajes.value = [...mensajes.value, ...frescos]
  return frescos.length
}

const cargar = async () => {
  cargando.value = true
  problema.value = ''
  try {
    const { data } = await getMensajes(props.incidenteId)
    mensajes.value = data || []
    marcarLeido(props.incidenteId)
    bajarAlFinal()
  } catch (error) {
    problema.value = mensajeDeError(error, 'No se pudieron cargar los mensajes.')
  } finally {
    cargando.value = false
  }
}

const buscarNuevos = async () => {
  if (document.hidden || cargando.value) return
  const ultimo = mensajes.value.at(-1)?.id
  try {
    const { data } = await getMensajes(props.incidenteId, ultimo ? { despues: ultimo } : {})
    const seguir = cercaDelFinal()
    if (agregar(data || [])) {
      marcarLeido(props.incidenteId)
      if (seguir) bajarAlFinal()
    }
  } catch {
    /* se reintenta en la siguiente vuelta */
  }
}

const enviar = async () => {
  const contenido = texto.value.trim()
  if (!contenido || enviando.value) return
  enviando.value = true
  problema.value = ''
  try {
    const { data } = await enviarMensaje(props.incidenteId, contenido)
    agregar([data])
    texto.value = ''
    bajarAlFinal()
  } catch (error) {
    problema.value = mensajeDeError(error, 'No se pudo enviar el mensaje.')
  } finally {
    enviando.value = false
  }
}

const alPulsarEnter = (evento) => {
  if (esTactil || evento.shiftKey || evento.isComposing) return
  evento.preventDefault()
  enviar()
}

const iniciar = () => {
  clearInterval(temporizador)
  mensajes.value = []
  cargar()
  temporizador = setInterval(buscarNuevos, INTERVALO_MS)
}

onMounted(iniciar)
onUnmounted(() => clearInterval(temporizador))
watch(() => props.incidenteId, iniciar)
</script>

<template>
  <section class="chat">
    <header class="chat__cabecera">
      <span class="gio-etiqueta">Chat del folio</span>
      <small>Planta externa, planta interna y supervisión</small>
    </header>

    <div ref="lista" class="chat__lista" role="log" aria-live="polite" aria-label="Mensajes">
      <p v-if="cargando && !mensajes.length" class="gio-cargando">Cargando mensajes…</p>
      <p v-else-if="!mensajes.length" class="gio-vacio">
        Aún no hay mensajes. Lo que se escriba aquí queda en el folio para todos los involucrados.
      </p>
      <article
        v-for="mensaje in mensajes"
        :key="mensaje.id"
        class="chat__mensaje"
        :class="{ 'chat__mensaje--propio': esPropio(mensaje) }"
      >
        <header class="chat__autor">
          <strong>{{ esPropio(mensaje) ? 'Usted' : mensaje.autor_nombre }}</strong>
          <span v-if="LADO_POR_ROL[mensaje.autor_rol]">{{ LADO_POR_ROL[mensaje.autor_rol] }}</span>
        </header>
        <p class="chat__texto">{{ mensaje.texto }}</p>
        <time class="chat__hora" :datetime="mensaje.creado_en">{{ horaDe(mensaje.creado_en) }}</time>
      </article>
    </div>

    <p v-if="problema" class="chat__problema" role="alert">{{ problema }}</p>

    <form class="chat__forma" @submit.prevent="enviar">
      <textarea
        v-model="texto"
        rows="2"
        :maxlength="MAX_CARACTERES"
        placeholder="Escriba un mensaje…"
        aria-label="Mensaje"
        @keydown.enter="alPulsarEnter"
      ></textarea>
      <button
        type="submit"
        class="gio-boton gio-boton--primario"
        :disabled="enviando || !texto.trim()"
      >
        {{ enviando ? 'Enviando…' : 'Enviar' }}
      </button>
    </form>
  </section>
</template>

<style scoped>
.chat {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.chat__cabecera {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 4px 12px;
}
.chat__cabecera small {
  font-size: 0.75rem;
  color: var(--tenue);
}

.chat__lista {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 160px;
  max-height: min(55vh, 420px);
  overflow-y: auto;
  padding: 12px;
  background-color: var(--superficie);
  border: 1px solid var(--borde);
}

.chat__mensaje {
  align-self: flex-start;
  max-width: min(85%, 520px);
  padding: 8px 12px;
  background-color: var(--panel-alto);
  color: var(--texto);
}
.chat__mensaje--propio {
  align-self: flex-end;
  background-color: var(--acento);
  color: var(--sobre-acento);
}

.chat__autor {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 2px 8px;
  font-size: 0.75rem;
}
.chat__autor span {
  font-size: 0.6875rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  opacity: 0.75;
}

.chat__texto {
  margin: 4px 0 2px;
  font-size: 0.875rem;
  line-height: 1.4;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.chat__hora {
  display: block;
  font-size: 0.6875rem;
  text-align: right;
  opacity: 0.75;
}

.chat__problema {
  margin: 0;
  font-size: 0.8125rem;
  color: var(--rojo-texto);
}

.chat__forma {
  display: flex;
  gap: 8px;
  align-items: stretch;
}
.chat__forma textarea {
  flex: 1;
  min-width: 0;
  resize: vertical;
}
.chat__forma .gio-boton {
  flex-shrink: 0;
}
</style>
