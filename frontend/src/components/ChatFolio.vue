<script setup>
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { ROLES, useAuth } from '../composables/useAuth.js'
import { useChat } from '../composables/useChat.js'
import { LIMITE_BYTES, useCompresionImagen } from '../composables/useCompresionImagen.js'
import { enviarMensaje, getMensajes, mensajeDeError } from '../services/api.js'
import { formatearBytes } from '../utils/formato.js'

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
const { marcarLeido, mostrarChat, ocultarChat } = useChat()
const { comprimiendo, procesar } = useCompresionImagen()

const mensajes = ref([])
const cargando = ref(false)
const problema = ref('')
const texto = ref('')
const enviando = ref(false)
const progreso = ref(0)
const lista = ref(null)
const entradaFoto = ref(null)
// Foto ya comprimida que se enviará con el siguiente mensaje, y su URL local para la vista previa.
const foto = ref(null)
const vistaPrevia = ref('')
let temporizador = null
// Si el usuario está al final de la conversación, las fotos que terminan de cargar la mantienen ahí.
let siguiendo = true

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
  siguiendo = true
  await nextTick()
  if (lista.value) lista.value.scrollTop = lista.value.scrollHeight
}

const alDesplazar = () => {
  siguiendo = cercaDelFinal()
}

const alCargarImagen = () => {
  if (siguiendo) bajarAlFinal()
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

const quitarFoto = () => {
  if (vistaPrevia.value) URL.revokeObjectURL(vistaPrevia.value)
  vistaPrevia.value = ''
  foto.value = null
}

// Se comprime en el teléfono igual que las evidencias; sin `capture` para elegir cámara o galería.
const seleccionarFoto = async (evento) => {
  const archivo = evento.target.files?.[0]
  evento.target.value = ''
  if (!archivo) return
  problema.value = ''
  try {
    const resultado = await procesar(archivo, { limite: LIMITE_BYTES })
    quitarFoto()
    foto.value = resultado
    vistaPrevia.value = URL.createObjectURL(resultado.archivo)
  } catch (error) {
    problema.value = error.message
  }
}

const enviar = async () => {
  const contenido = texto.value.trim()
  if ((!contenido && !foto.value) || enviando.value || comprimiendo.value) return
  let datos = { texto: contenido }
  if (foto.value) {
    datos = new FormData()
    datos.append('texto', contenido)
    datos.append('imagen', foto.value.archivo)
  }
  enviando.value = true
  progreso.value = 0
  problema.value = ''
  try {
    const { data } = await enviarMensaje(props.incidenteId, datos, (valor) => {
      progreso.value = valor
    })
    agregar([data])
    texto.value = ''
    quitarFoto()
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
  mostrarChat(props.incidenteId)
  mensajes.value = []
  cargar()
  temporizador = setInterval(buscarNuevos, INTERVALO_MS)
}

onMounted(iniciar)
onUnmounted(() => {
  clearInterval(temporizador)
  ocultarChat(props.incidenteId)
  quitarFoto()
})
watch(
  () => props.incidenteId,
  (_, anterior) => {
    ocultarChat(anterior)
    quitarFoto()
    iniciar()
  },
)
</script>

<template>
  <section class="chat">
    <header class="chat__cabecera">
      <span class="gio-etiqueta">Chat del folio</span>
      <small>Planta externa, planta interna y supervisión</small>
    </header>

    <div
      ref="lista"
      class="chat__lista"
      role="log"
      aria-live="polite"
      aria-label="Mensajes"
      @scroll.passive="alDesplazar"
    >
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
        <a
          v-if="mensaje.imagen_url"
          :href="mensaje.imagen_url"
          target="_blank"
          rel="noopener"
          class="chat__foto"
        >
          <img
            :src="mensaje.imagen_url"
            alt="Foto enviada en el chat"
            loading="lazy"
            @load="alCargarImagen"
          />
        </a>
        <p v-if="mensaje.texto" class="chat__texto">{{ mensaje.texto }}</p>
        <time class="chat__hora" :datetime="mensaje.creado_en">{{ horaDe(mensaje.creado_en) }}</time>
      </article>
    </div>

    <p v-if="problema" class="chat__problema" role="alert">{{ problema }}</p>
    <p v-if="comprimiendo" class="chat__estado">Preparando la foto…</p>
    <div v-else-if="foto" class="chat__adjunto">
      <img :src="vistaPrevia" alt="Foto por enviar" />
      <span>Foto lista · {{ formatearBytes(foto.bytesFinales) }}</span>
      <button
        type="button"
        class="gio-boton gio-boton--secundario"
        :disabled="enviando"
        @click="quitarFoto"
      >
        Quitar
      </button>
    </div>

    <form class="chat__forma" @submit.prevent="enviar">
      <button
        type="button"
        class="gio-boton gio-boton--secundario chat__adjuntar"
        :disabled="enviando || comprimiendo"
        aria-label="Adjuntar foto"
        title="Adjuntar foto"
        @click="entradaFoto?.click()"
      >
        <svg
          viewBox="0 0 24 24"
          width="20"
          height="20"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path
            d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"
          />
          <circle cx="12" cy="13" r="4" />
        </svg>
      </button>
      <input
        ref="entradaFoto"
        type="file"
        accept="image/*"
        class="chat__oculto"
        @change="seleccionarFoto"
      />
      <textarea
        v-model="texto"
        rows="2"
        :maxlength="MAX_CARACTERES"
        :placeholder="foto ? 'Agregue un comentario (opcional)…' : 'Escriba un mensaje…'"
        aria-label="Mensaje"
        @keydown.enter="alPulsarEnter"
      ></textarea>
      <button
        type="submit"
        class="gio-boton gio-boton--primario"
        :disabled="enviando || comprimiendo || (!texto.trim() && !foto)"
      >
        {{ enviando ? (foto ? `Enviando ${progreso}%` : 'Enviando…') : 'Enviar' }}
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

.chat__foto {
  display: block;
  margin-top: 6px;
}
.chat__foto img {
  display: block;
  max-width: min(100%, 280px);
  max-height: 280px;
  object-fit: contain;
  background-color: var(--panel);
}

.chat__estado {
  margin: 0;
  font-size: 0.8125rem;
  color: var(--apagado);
}

.chat__adjunto {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px;
  border: 1px solid var(--borde);
  background-color: var(--superficie);
  font-size: 0.8125rem;
  color: var(--apagado);
}
.chat__adjunto img {
  width: 56px;
  height: 56px;
  object-fit: cover;
  flex-shrink: 0;
}
.chat__adjunto span {
  flex: 1;
  min-width: 0;
}

.chat__adjuntar {
  padding: 0 12px;
}

.chat__oculto {
  display: none;
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
