<script setup>
import { ref } from 'vue'
import { TRANSICIONES, etiquetaEstatus } from '../composables/useIncidentes.js'
import { formatearHoras } from '../utils/formato.js'

const props = defineProps({
  columnas: { type: Array, required: true },
  puedeMover: { type: Boolean, default: false },
})

const emit = defineEmits(['editar', 'mover'])

const arrastrado = ref(null)
const columnaActiva = ref(null)

const destinosValidos = (estatus) => TRANSICIONES[estatus] || []

const iniciarArrastre = (evento, item) => {
  if (!props.puedeMover) return
  arrastrado.value = item
  evento.dataTransfer.effectAllowed = 'move'
  evento.dataTransfer.setData('text/plain', String(item.id))
}

const terminarArrastre = () => {
  arrastrado.value = null
  columnaActiva.value = null
}

const puedeSoltarEn = (idColumna) => {
  if (!props.puedeMover || !arrastrado.value) return false
  if (arrastrado.value.estatus === idColumna) return false
  return destinosValidos(arrastrado.value.estatus).includes(idColumna)
}

const sobreColumna = (evento, idColumna) => {
  if (!puedeSoltarEn(idColumna)) return
  evento.preventDefault()
  evento.dataTransfer.dropEffect = 'move'
  columnaActiva.value = idColumna
}

const soltar = (evento, idColumna) => {
  if (!puedeSoltarEn(idColumna)) return
  evento.preventDefault()
  emit('mover', { incidente: arrastrado.value, estatus: idColumna })
  terminarArrastre()
}
</script>

<template>
  <div class="tablero">
    <section
      v-for="columna in columnas"
      :key="columna.id"
      class="tablero__columna"
      :class="{
        'tablero__columna--destino': puedeSoltarEn(columna.id),
        'tablero__columna--activa': columnaActiva === columna.id,
      }"
      @dragover="sobreColumna($event, columna.id)"
      @dragleave="columnaActiva = null"
      @drop="soltar($event, columna.id)"
    >
      <header class="tablero__cabecera" :style="{ borderTopColor: columna.color }">
        <span class="tablero__titulo">{{ columna.titulo }}</span>
        <span class="tablero__conteo">{{ columna.items.length }}</span>
      </header>

      <div class="tablero__cuerpo">
        <article
          v-for="item in columna.items"
          :key="item.id"
          class="ficha"
          :class="`ficha--${item.semaforo || 'normal'}`"
          :draggable="puedeMover"
          tabindex="0"
          role="button"
          :aria-label="`Folio ${item.folio}, ${etiquetaEstatus(item.estatus)}`"
          @click="emit('editar', item)"
          @keydown.enter.prevent="emit('editar', item)"
          @keydown.space.prevent="emit('editar', item)"
          @dragstart="iniciarArrastre($event, item)"
          @dragend="terminarArrastre"
        >
          <div class="ficha__alto">
            <span class="ficha__folio">{{ item.folio }}</span>
            <span class="gio-semaforo" :class="`gio-semaforo--${item.semaforo || 'normal'}`">
              {{ item.dilacion_dias ?? 0 }}d
            </span>
          </div>

          <h4 class="ficha__empresa">{{ item.empresa || 'Sin empresa registrada' }}</h4>

          <dl class="ficha__datos">
            <div>
              <dt>Central</dt>
              <dd>{{ item.central || item.area_operativa || '—' }}</dd>
            </div>
            <div>
              <dt>Técnico</dt>
              <dd>{{ item.tecnico_nombre || 'Sin asignar' }}</dd>
            </div>
          </dl>

          <footer class="ficha__pie">
            <span class="ficha__servicio">{{ item.tipo_servicio || 'Servicio' }}</span>
            <span class="ficha__marcas">
              <span v-if="item.total_evidencias" class="ficha__evidencias" title="Evidencias cargadas">
                {{ item.total_evidencias }} ev.
              </span>
              <span
                class="gio-enlace"
                :class="`gio-enlace--${(item.estado_enlace || 'desconocido').toLowerCase()}`"
              >
                {{ item.estado_enlace || 'N/D' }}
              </span>
            </span>
          </footer>

          <p v-if="item.estatus === 'LIQUIDADO'" class="ficha__mttr">
            MTTR {{ formatearHoras(item.mttr_horas) }}
            <span v-if="item.exportado_sisa === false" class="ficha__pendiente">por exportar</span>
          </p>
        </article>

        <p v-if="columna.items.length === 0" class="gio-vacio">Sin folios</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.tablero {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(255px, 1fr));
  gap: 0.85rem;
  align-items: start;
}

.tablero__columna {
  background-color: var(--panel);
  border: 1px solid var(--borde);
  border-radius: var(--radio);
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 300px);
  min-height: 160px;
  transition:
    border-color 0.15s ease,
    background-color 0.15s ease;
}

.tablero__columna--destino {
  border-color: rgb(56 189 248 / 0.45);
}

.tablero__columna--activa {
  background-color: rgb(56 189 248 / 0.07);
  border-color: var(--acento-claro);
}

.tablero__cabecera {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.7rem 0.9rem;
  background-color: #0a1222;
  border-top: 3px solid var(--acento);
  border-bottom: 1px solid var(--borde);
  border-radius: var(--radio) var(--radio) 0 0;
}

.tablero__titulo {
  font-size: 0.8125rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.tablero__conteo {
  background-color: var(--panel-alto);
  color: #cbd5e1;
  font-size: 0.72rem;
  font-weight: 700;
  padding: 0.1rem 0.5rem;
  border-radius: 999px;
}

.tablero__cuerpo {
  padding: 0.7rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.ficha {
  background-color: #0a1222;
  border: 1px solid var(--borde);
  border-left: 3px solid var(--borde);
  border-radius: 8px;
  padding: 0.7rem;
  cursor: pointer;
  transition:
    transform 0.12s ease,
    border-color 0.12s ease;
}

.ficha:hover,
.ficha:focus-visible {
  transform: translateY(-2px);
  border-color: var(--acento-claro);
}

.ficha--alerta {
  border-left-color: var(--alerta);
}
.ficha--critico {
  border-left-color: var(--peligro);
}
.ficha--cerrado {
  border-left-color: var(--ok);
}

.ficha__alto {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.35rem;
}

.ficha__folio {
  font-family: ui-monospace, 'SFMono-Regular', Menlo, monospace;
  font-weight: 700;
  font-size: 0.8125rem;
  color: var(--acento-claro);
}

.ficha__empresa {
  font-size: 0.875rem;
  margin-bottom: 0.5rem;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.ficha__datos {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  margin: 0 0 0.55rem;
  font-size: 0.72rem;
}

.ficha__datos div {
  display: flex;
  gap: 0.35rem;
}

.ficha__datos dt {
  color: #64748b;
  min-width: 52px;
}

.ficha__datos dd {
  margin: 0;
  color: var(--apagado);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ficha__pie {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  border-top: 1px solid var(--borde);
  padding-top: 0.45rem;
  font-size: 0.6875rem;
}

.ficha__servicio {
  color: #64748b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ficha__marcas {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-shrink: 0;
}

.ficha__evidencias {
  color: #a5b4fc;
  font-weight: 600;
}

.ficha__mttr {
  margin: 0.45rem 0 0;
  font-size: 0.6875rem;
  color: #6ee7b7;
  display: flex;
  gap: 0.4rem;
  align-items: center;
}

.ficha__pendiente {
  color: #fcd34d;
  border: 1px solid rgb(245 158 11 / 0.4);
  border-radius: 999px;
  padding: 0 0.35rem;
}
</style>
