<script setup>
import { ref } from 'vue'
import { LIMITE_BYTES, useCompresionImagen } from '../composables/useCompresionImagen.js'
import { eliminarEvidencia, mensajeDeError, subirEvidencia } from '../services/api.js'
import { confirmarAccion, mostrarError, notificar } from '../utils/alerts.js'
import { formatearBytes, formatearFecha } from '../utils/formato.js'

const props = defineProps({
  incidenteId: { type: [Number, String], required: true },
  evidencias: { type: Array, default: () => [] },
  maximo: { type: Number, default: 12 },
  soloLectura: { type: Boolean, default: false },
})

const emit = defineEmits(['cambio'])

const { comprimiendo, procesar } = useCompresionImagen()
const entrada = ref(null)
const subiendo = ref(false)
const progreso = ref(0)
const ultimo = ref(null)
const problema = ref('')

const abrirSelector = () => entrada.value?.click()

const seleccionar = async (evento) => {
  const archivos = Array.from(evento.target.files || [])
  evento.target.value = ''
  if (!archivos.length) return

  problema.value = ''
  const disponibles = props.maximo - props.evidencias.length
  if (disponibles <= 0) {
    problema.value = `Este folio ya tiene el máximo de ${props.maximo} evidencias.`
    return
  }

  for (const archivo of archivos.slice(0, disponibles)) {
    try {
      const resultado = await procesar(archivo, { limite: LIMITE_BYTES })
      ultimo.value = resultado

      const formulario = new FormData()
      formulario.append('imagen', resultado.archivo)
      formulario.append('descripcion', archivo.name.slice(0, 120))
      const posicion = await ubicacion()
      if (posicion) formulario.append('coordenadas_gps', posicion)

      subiendo.value = true
      progreso.value = 0
      await subirEvidencia(props.incidenteId, formulario, (valor) => {
        progreso.value = valor
      })
      notificar(`Evidencia enviada (${formatearBytes(resultado.bytesFinales)})`)
      emit('cambio')
    } catch (error) {
      problema.value = error?.response
        ? mensajeDeError(error, 'No se pudo enviar la evidencia.')
        : error.message
      mostrarError('Evidencia no enviada', problema.value)
    } finally {
      subiendo.value = false
      progreso.value = 0
    }
  }
}

const ubicacion = () =>
  new Promise((resolve) => {
    if (!navigator.geolocation) return resolve(null)
    const temporizador = setTimeout(() => resolve(null), 4000)
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        clearTimeout(temporizador)
        resolve(`${coords.latitude.toFixed(5)},${coords.longitude.toFixed(5)}`)
      },
      () => {
        clearTimeout(temporizador)
        resolve(null)
      },
      { timeout: 4000, maximumAge: 60000 },
    )
  })

const quitar = async (evidencia) => {
  if (!(await confirmarAccion('Eliminar evidencia', '¿Desea eliminar esta fotografía?', 'Eliminar')))
    return
  try {
    await eliminarEvidencia(evidencia.id)
    notificar('Evidencia eliminada')
    emit('cambio')
  } catch (error) {
    mostrarError('No se pudo eliminar', mensajeDeError(error))
  }
}
</script>

<template>
  <section class="evidencias">
    <header class="evidencias__cabecera">
      <div>
        <span class="gio-etiqueta">Evidencia fotográfica</span>
        <p class="evidencias__contador">
          {{ evidencias.length }} de {{ maximo }} · se comprime a máx.
          {{ formatearBytes(LIMITE_BYTES) }} antes de enviarse
        </p>
      </div>
      <button
        v-if="!soloLectura"
        type="button"
        class="gio-boton gio-boton--primario"
        :disabled="comprimiendo || subiendo || evidencias.length >= maximo"
        @click="abrirSelector"
      >
        {{ comprimiendo ? 'Comprimiendo…' : subiendo ? `Enviando ${progreso}%` : 'Tomar foto' }}
      </button>
      <input
        ref="entrada"
        type="file"
        accept="image/*"
        capture="environment"
        multiple
        class="evidencias__oculto"
        @change="seleccionar"
      />
    </header>

    <div v-if="subiendo" class="evidencias__barra" role="progressbar" :aria-valuenow="progreso">
      <span :style="{ width: `${progreso}%` }"></span>
    </div>

    <p v-if="problema" class="evidencias__problema" role="alert">{{ problema }}</p>

    <p v-else-if="ultimo" class="evidencias__resumen">
      {{ ultimo.dimensionOriginal }} → {{ ultimo.dimensionFinal }} ·
      {{ formatearBytes(ultimo.bytesOriginales) }} → {{ formatearBytes(ultimo.bytesFinales) }}
      ({{ ultimo.ahorro }}% menos datos)
    </p>

    <ul v-if="evidencias.length" class="evidencias__galeria">
      <li v-for="evidencia in evidencias" :key="evidencia.id" class="evidencias__item">
        <a :href="evidencia.imagen_url" target="_blank" rel="noopener">
          <img :src="evidencia.imagen_url" :alt="evidencia.descripcion || 'Evidencia del folio'" />
        </a>
        <div class="evidencias__meta">
          <span>{{ formatearFecha(evidencia.fecha_captura) }}</span>
          <span>{{ formatearBytes(evidencia.tamano_bytes) }}</span>
          <span v-if="evidencia.coordenadas_gps">{{ evidencia.coordenadas_gps }}</span>
        </div>
        <button
          v-if="!soloLectura"
          type="button"
          class="gio-boton gio-boton--peligro evidencias__quitar"
          @click="quitar(evidencia)"
        >
          Quitar
        </button>
      </li>
    </ul>

    <p v-else class="gio-vacio">Aún no hay evidencias cargadas para este folio.</p>
  </section>
</template>

<style scoped>
.evidencias {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.evidencias__cabecera {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.evidencias__contador {
  margin: 0;
  font-size: 0.75rem;
  color: var(--apagado);
}

.evidencias__oculto {
  display: none;
}

.evidencias__barra {
  height: 6px;
  background-color: var(--panel-alto);
  border-radius: 999px;
  overflow: hidden;
}

.evidencias__barra span {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, var(--acento), var(--acento-claro));
  transition: width 0.2s ease;
}

.evidencias__problema,
.evidencias__resumen {
  margin: 0;
  font-size: 0.78rem;
  padding: 0.5rem 0.65rem;
  border-radius: 8px;
}

.evidencias__problema {
  background: rgb(239 68 68 / 0.12);
  border: 1px solid rgb(239 68 68 / 0.4);
  color: #fca5a5;
  white-space: pre-line;
}

.evidencias__resumen {
  background: rgb(16 185 129 / 0.1);
  border: 1px solid rgb(16 185 129 / 0.3);
  color: #6ee7b7;
}

.evidencias__galeria {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0.75rem;
}

.evidencias__item {
  background-color: #0a1222;
  border: 1px solid var(--borde);
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.evidencias__item img {
  width: 100%;
  aspect-ratio: 4 / 3;
  object-fit: cover;
  display: block;
}

.evidencias__meta {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  padding: 0.45rem 0.55rem;
  font-size: 0.68rem;
  color: var(--apagado);
}

.evidencias__quitar {
  margin: 0 0.55rem 0.55rem;
  padding: 0.3rem;
  font-size: 0.7rem;
}
</style>
