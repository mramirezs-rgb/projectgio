<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { etiquetaEstatus } from '../composables/useIncidentes.js'
import { getDetalleIndicador, mensajeDeError } from '../services/api.js'
import { formatearHoras } from '../utils/formato.js'

const props = defineProps({
  // mttr, liquidacion, dilacion, criticos o sin_tecnico.
  indicador: { type: String, required: true },
  // Los mismos filtros con los que se calculó el indicador.
  filtros: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['close'])

const router = useRouter()
const cargando = ref(true)
const problema = ref('')
const detalle = ref(null)

const conUnidad = (valor, unidad) => {
  if (valor === null || valor === undefined || valor === '') return '—'
  if (unidad === 'h') return formatearHoras(valor)
  if (unidad === 'd') return `${valor} ${Number(valor) === 1 ? 'día' : 'días'}`
  if (unidad === '%') return `${valor}%`
  return valor
}

const abrirFolio = (id) => {
  emit('close')
  router.push({ name: 'tablero', query: { folio: String(id) } })
}

const alPulsarTecla = (evento) => {
  if (evento.key === 'Escape') emit('close')
}

onMounted(async () => {
  document.addEventListener('keydown', alPulsarTecla)
  try {
    const { data } = await getDetalleIndicador({ ...props.filtros, indicador: props.indicador })
    detalle.value = data
  } catch (error) {
    problema.value = mensajeDeError(error, 'No se pudo consultar el detalle del indicador.')
  } finally {
    cargando.value = false
  }
})

onUnmounted(() => document.removeEventListener('keydown', alPulsarTecla))
</script>

<template>
  <div class="velo" role="dialog" aria-modal="true" aria-labelledby="detalle-titulo" @click.self="emit('close')">
    <section class="caja gio-panel">
      <header class="caja__cabecera">
        <h2 id="detalle-titulo">{{ detalle?.titulo || 'Detalle del indicador' }}</h2>
        <button type="button" class="caja__cerrar" aria-label="Cerrar" @click="emit('close')">
          &times;
        </button>
      </header>

      <div class="caja__cuerpo">
        <p v-if="cargando" class="gio-cargando">Consultando el detalle…</p>
        <p v-else-if="problema" class="detalle__error" role="alert">{{ problema }}</p>

        <template v-else-if="detalle">
          <dl class="resumen">
            <div v-for="dato in detalle.resumen" :key="dato.etiqueta" class="resumen__dato">
              <dt>{{ dato.etiqueta }}</dt>
              <dd>{{ conUnidad(dato.valor, dato.unidad) }}</dd>
            </div>
          </dl>

          <section v-for="desglose in detalle.desgloses" :key="desglose.titulo" class="bloque">
            <h3>{{ desglose.titulo }}</h3>
            <div class="tabla-contenedor">
              <table class="listado">
                <thead>
                  <tr>
                    <th v-for="columna in desglose.columnas" :key="columna.titulo">
                      {{ columna.titulo }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-if="!desglose.filas.length">
                    <td :colspan="desglose.columnas.length" class="gio-vacio">Sin datos.</td>
                  </tr>
                  <tr v-for="(fila, indice) in desglose.filas" :key="indice">
                    <td v-for="(celda, posicion) in fila" :key="posicion">
                      {{ conUnidad(celda, desglose.columnas[posicion].unidad) }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section v-if="detalle.folios" class="bloque">
            <h3>{{ detalle.folios.titulo }}</h3>
            <p v-if="detalle.folios.total > detalle.folios.filas.length" class="bloque__nota">
              Se muestran {{ detalle.folios.filas.length }} de {{ detalle.folios.total }} folios.
            </p>
            <div class="tabla-contenedor">
              <table class="listado">
                <thead>
                  <tr>
                    <th>Folio</th>
                    <th>Empresa</th>
                    <th>Área</th>
                    <th>Estatus</th>
                    <th>Técnico</th>
                    <th>{{ detalle.folios.columna }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-if="!detalle.folios.filas.length">
                    <td colspan="6" class="gio-vacio">No hay folios en este indicador.</td>
                  </tr>
                  <tr v-for="folio in detalle.folios.filas" :key="folio.id">
                    <td>
                      <button
                        type="button"
                        class="listado__folio"
                        :title="`Abrir el folio ${folio.folio}`"
                        @click="abrirFolio(folio.id)"
                      >
                        {{ folio.folio }}
                      </button>
                    </td>
                    <td>{{ folio.empresa || '—' }}</td>
                    <td>{{ folio.area_operativa || '—' }}</td>
                    <td>{{ etiquetaEstatus(folio.estatus) }}</td>
                    <td>{{ folio.tecnico_nombre }}</td>
                    <td class="listado__valor">
                      {{ conUnidad(folio.valor, detalle.folios.unidad) }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </template>
      </div>

      <footer class="caja__pie">
        <button type="button" class="gio-boton gio-boton--secundario" @click="emit('close')">
          Cerrar
        </button>
      </footer>
    </section>
  </div>
</template>

<style scoped>
.velo {
  position: fixed;
  inset: 0;
  background-color: var(--velo);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  z-index: 100;
}

.caja {
  width: 100%;
  max-width: 860px;
  max-height: 92vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.caja__cabecera {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.9rem 1.2rem;
  background-color: var(--superficie);
  border-bottom: 1px solid var(--borde);
}

.caja__cabecera h2 {
  font-size: 1rem;
}

.caja__cerrar {
  background: none;
  border: none;
  color: var(--apagado);
  font-size: 1.6rem;
  line-height: 1;
}

.caja__cuerpo {
  padding: 1.2rem;
  display: flex;
  flex-direction: column;
  gap: 1.2rem;
  overflow-y: auto;
}

.caja__pie {
  display: flex;
  justify-content: flex-end;
  padding: 0.8rem 1.2rem;
  border-top: 1px solid var(--borde);
}

.detalle__error {
  margin: 0;
  padding: 0.7rem 0.85rem;
  background: rgb(239 68 68 / 0.12);
  border: 1px solid rgb(239 68 68 / 0.4);
  color: var(--rojo-texto);
  font-size: 0.8125rem;
}

.resumen {
  margin: 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.6rem;
}

.resumen__dato {
  padding: 0.65rem 0.8rem;
  border: 1px solid var(--borde);
  border-top: 3px solid var(--acento);
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.resumen dt {
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--apagado);
}

.resumen dd {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 700;
  line-height: 1.15;
  font-variant-numeric: tabular-nums;
}

.bloque {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.bloque h3 {
  font-size: 0.9rem;
}

.bloque__nota {
  margin: 0;
  font-size: 0.75rem;
  color: var(--tenue);
}

.tabla-contenedor {
  overflow-x: auto;
}

.listado {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

.listado th {
  text-align: left;
  padding: 0.45rem 0.6rem;
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--apagado);
  border-bottom: 1px solid var(--borde);
  white-space: nowrap;
}

.listado td {
  padding: 0.45rem 0.6rem;
  border-bottom: 1px solid var(--linea);
  font-variant-numeric: tabular-nums;
}

.listado__folio {
  padding: 0;
  background: none;
  border: none;
  font-family: ui-monospace, 'SFMono-Regular', Menlo, monospace;
  font-weight: 700;
  color: var(--acento-claro);
  text-decoration: underline;
  cursor: pointer;
}

.listado__valor {
  font-weight: 700;
  white-space: nowrap;
}
</style>
