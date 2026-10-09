<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { COLUMNAS_KANBAN } from '../composables/useIncidentes.js'
import { getAreas, getMetricas, mensajeDeError } from '../services/api.js'
import { mostrarAdvertencia, notificar } from '../utils/alerts.js'
import { descargarCSV, formatearFecha, formatearHoras, marcaDeTiempo } from '../utils/formato.js'

const cargando = ref(false)
const problema = ref('')
const datos = ref(null)
const areas = ref([])

const filtros = reactive({ area_operativa: '', abierto_desde: '', abierto_hasta: '' })

const cargar = async () => {
  cargando.value = true
  problema.value = ''
  try {
    const params = {}
    for (const [clave, valor] of Object.entries(filtros)) if (valor) params[clave] = valor
    const { data } = await getMetricas(params)
    datos.value = data
  } catch (error) {
    problema.value = mensajeDeError(error, 'No se pudieron calcular las métricas.')
    datos.value = null
  } finally {
    cargando.value = false
  }
}

onMounted(async () => {
  try {
    const { data } = await getAreas()
    areas.value = data || []
  } catch {
    areas.value = []
  }
  await cargar()
})

const tasaLiquidacion = computed(() => {
  if (!datos.value?.total) return 0
  return Math.round((datos.value.liquidados / datos.value.total) * 100)
})

const porEstatus = computed(() => {
  if (!datos.value) return []
  const mapa = {
    PENDIENTE: datos.value.pendientes,
    ASIGNADO: datos.value.asignados,
    EN_PROCESO: datos.value.en_proceso,
    LIQUIDADO: datos.value.liquidados,
  }
  const total = datos.value.total || 1
  return COLUMNAS_KANBAN.map((columna) => ({
    ...columna,
    valor: mapa[columna.id] || 0,
    porcentaje: Math.round(((mapa[columna.id] || 0) / total) * 100),
  }))
})

const nombreTecnico = (fila) =>
  `${fila.tecnico__first_name || ''} ${fila.tecnico__last_name || ''}`.trim() ||
  fila.tecnico__expediente

const exportarArea = () => {
  if (!datos.value?.por_area?.length) {
    mostrarAdvertencia('Sin datos', 'No hay resultados por área para exportar.')
    return
  }
  descargarCSV(
    `GIO_Metricas_Area_${marcaDeTiempo()}.csv`,
    ['Area operativa', 'Folios totales', 'Folios abiertos'],
    datos.value.por_area.map((fila) => [fila.area_operativa, fila.total, fila.abiertos]),
  )
  notificar('Métricas por área descargadas')
}

const exportarTecnico = () => {
  if (!datos.value?.por_tecnico?.length) {
    mostrarAdvertencia('Sin datos', 'No hay carga por técnico para exportar.')
    return
  }
  descargarCSV(
    `GIO_Carga_Tecnicos_${marcaDeTiempo()}.csv`,
    ['Expediente', 'Tecnico', 'Folios totales', 'Folios abiertos'],
    datos.value.por_tecnico.map((fila) => [
      fila.tecnico__expediente,
      nombreTecnico(fila),
      fila.total,
      fila.abiertos,
    ]),
  )
  notificar('Carga por técnico descargada')
}
</script>

<template>
  <div class="metricas">
    <header class="metricas__cabecera">
      <div>
        <h1>Métricas operativas</h1>
        <p v-if="datos">Calculado el {{ formatearFecha(datos.generado_en) }}</p>
      </div>
      <div class="metricas__filtros">
        <div>
          <label class="gio-etiqueta" for="m-area">Área</label>
          <select id="m-area" v-model="filtros.area_operativa" @change="cargar">
            <option value="">Todas</option>
            <option v-for="area in areas" :key="area.id" :value="area.nombre">
              {{ area.nombre }}
            </option>
          </select>
        </div>
        <div>
          <label class="gio-etiqueta" for="m-desde">Apertura desde</label>
          <input id="m-desde" v-model="filtros.abierto_desde" type="date" @change="cargar" />
        </div>
        <div>
          <label class="gio-etiqueta" for="m-hasta">Apertura hasta</label>
          <input id="m-hasta" v-model="filtros.abierto_hasta" type="date" @change="cargar" />
        </div>
        <button type="button" class="gio-boton gio-boton--secundario" @click="cargar">
          Recalcular
        </button>
      </div>
    </header>

    <p v-if="problema" class="metricas__error" role="alert">{{ problema }}</p>
    <p v-else-if="cargando" class="gio-cargando">Calculando indicadores…</p>

    <template v-else-if="datos">
      <section class="tarjetas">
        <article class="tarjeta gio-panel">
          <span class="tarjeta__titulo">MTTR promedio</span>
          <strong>{{ formatearHoras(datos.mttr_horas_promedio) }}</strong>
          <small>
            mín. {{ formatearHoras(datos.mttr_horas_minimo) }} · máx.
            {{ formatearHoras(datos.mttr_horas_maximo) }}
          </small>
        </article>
        <article class="tarjeta gio-panel">
          <span class="tarjeta__titulo">Tasa de liquidación</span>
          <strong>{{ tasaLiquidacion }}%</strong>
          <small>{{ datos.liquidados }} de {{ datos.total }} folios</small>
        </article>
        <article class="tarjeta gio-panel">
          <span class="tarjeta__titulo">Dilación promedio (abiertos)</span>
          <strong>{{ datos.dilacion_promedio_dias ?? '—' }} d</strong>
          <small>{{ datos.en_dilacion }} sobre el umbral de {{ datos.umbral_dilacion_dias }} d</small>
        </article>
        <article class="tarjeta tarjeta--alerta gio-panel">
          <span class="tarjeta__titulo">Folios críticos</span>
          <strong class="tarjeta__rojo">{{ datos.criticos }}</strong>
          <small>≥ {{ datos.umbral_critico_dias }} días sin liquidar</small>
        </article>
        <article class="tarjeta gio-panel">
          <span class="tarjeta__titulo">Sin técnico asignado</span>
          <strong>{{ datos.sin_tecnico }}</strong>
          <small>requieren despacho</small>
        </article>
        <article class="tarjeta gio-panel">
          <span class="tarjeta__titulo">Pendientes de exportar a SISA</span>
          <strong>{{ datos.pendientes_exportar }}</strong>
          <small>se envían con el robot de retorno</small>
        </article>
      </section>

      <section class="bloque gio-panel">
        <h2>Distribución por estatus</h2>
        <ul class="barras">
          <li v-for="fila in porEstatus" :key="fila.id">
            <div class="barras__alto">
              <span>{{ fila.titulo }}</span>
              <span>{{ fila.valor }} ({{ fila.porcentaje }}%)</span>
            </div>
            <div class="barras__pista">
              <span :style="{ width: `${fila.porcentaje}%`, backgroundColor: fila.color }"></span>
            </div>
          </li>
        </ul>
      </section>

      <section class="bloque gio-panel">
        <header class="bloque__cabecera">
          <h2>Folios por área operativa</h2>
          <button type="button" class="gio-boton gio-boton--secundario" @click="exportarArea">
            Exportar CSV
          </button>
        </header>
        <table class="listado">
          <thead>
            <tr>
              <th>Área</th>
              <th>Totales</th>
              <th>Abiertos</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!datos.por_area.length">
              <td colspan="3" class="gio-vacio">Sin información por área.</td>
            </tr>
            <tr v-for="fila in datos.por_area" :key="fila.area_operativa">
              <td>{{ fila.area_operativa }}</td>
              <td>{{ fila.total }}</td>
              <td>{{ fila.abiertos }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="bloque gio-panel">
        <header class="bloque__cabecera">
          <h2>Carga por técnico</h2>
          <button type="button" class="gio-boton gio-boton--secundario" @click="exportarTecnico">
            Exportar CSV
          </button>
        </header>
        <table class="listado">
          <thead>
            <tr>
              <th>Técnico</th>
              <th>Expediente</th>
              <th>Totales</th>
              <th>Abiertos</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!datos.por_tecnico.length">
              <td colspan="4" class="gio-vacio">Sin folios asignados.</td>
            </tr>
            <tr v-for="fila in datos.por_tecnico" :key="fila.tecnico__expediente">
              <td>{{ nombreTecnico(fila) }}</td>
              <td class="listado__mono">{{ fila.tecnico__expediente }}</td>
              <td>{{ fila.total }}</td>
              <td>{{ fila.abiertos }}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </template>
  </div>
</template>

<style scoped>
.metricas {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.metricas__cabecera {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.metricas__cabecera h1 {
  font-size: 1.3rem;
}

.metricas__cabecera p {
  margin: 0.2rem 0 0;
  font-size: 0.78rem;
  color: var(--apagado);
}

.metricas__filtros {
  display: flex;
  align-items: flex-end;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.metricas__filtros > div {
  min-width: 150px;
}

.metricas__error {
  margin: 0;
  padding: 0.7rem 0.85rem;
  border-radius: 8px;
  background: rgb(239 68 68 / 0.12);
  border: 1px solid rgb(239 68 68 / 0.4);
  color: #fca5a5;
  font-size: 0.8125rem;
}

.tarjetas {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 0.75rem;
}

.tarjeta {
  padding: 0.85rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  border-top: 3px solid var(--acento);
}

.tarjeta--alerta {
  border-top-color: var(--peligro);
}

.tarjeta__titulo {
  font-size: 0.68rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--apagado);
}

.tarjeta strong {
  font-size: 1.55rem;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}

.tarjeta__rojo {
  color: #f87171;
}

.tarjeta small {
  font-size: 0.68rem;
  color: #64748b;
}

.bloque {
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.bloque h2 {
  font-size: 0.95rem;
}

.bloque__cabecera {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.barras {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.barras__alto {
  display: flex;
  justify-content: space-between;
  font-size: 0.78rem;
  margin-bottom: 0.25rem;
}

.barras__alto span:last-child {
  color: var(--apagado);
  font-variant-numeric: tabular-nums;
}

.barras__pista {
  height: 8px;
  background-color: #0b1324;
  border-radius: 999px;
  overflow: hidden;
}

.barras__pista span {
  display: block;
  height: 100%;
  border-radius: 999px;
  transition: width 0.3s ease;
}

.listado {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

.listado th {
  text-align: left;
  padding: 0.5rem 0.6rem;
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--apagado);
  border-bottom: 1px solid var(--borde);
}

.listado td {
  padding: 0.5rem 0.6rem;
  border-bottom: 1px solid rgb(36 51 82 / 0.5);
}

.listado__mono {
  font-family: ui-monospace, 'SFMono-Regular', Menlo, monospace;
  color: var(--apagado);
}
</style>
