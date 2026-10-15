<script setup>
import { onMounted, ref, watch } from 'vue'
import { getAreas, getDesempeno, mensajeDeError } from '../services/api.js'
import { formatearHoras } from '../utils/formato.js'

const areas = ref([])
const area = ref('')
const datos = ref(null)
const cargando = ref(false)
const problema = ref('')

const cargar = async () => {
  cargando.value = true
  problema.value = ''
  try {
    const { data } = await getDesempeno(area.value ? { area: area.value } : {})
    datos.value = data
  } catch (error) {
    problema.value = mensajeDeError(error, 'No se pudo cargar el desempeño de campo.')
  } finally {
    cargando.value = false
  }
}

onMounted(async () => {
  try {
    const { data } = await getAreas()
    areas.value = Array.isArray(data) ? data : data.results || []
  } catch {
    areas.value = []
  }
  await cargar()
})

watch(area, cargar)

const dilacion = (valor) => (valor === null || valor === undefined ? '—' : `${valor} días`)
</script>

<template>
  <section class="desempeno">
    <header class="desempeno__cabecera">
      <div>
        <h1>Desempeño de campo</h1>
        <p>Carga y resultados de los técnicos de planta externa y de planta interna.</p>
      </div>
      <div class="desempeno__controles">
        <select v-model="area" aria-label="Filtrar por área">
          <option value="">Todas las áreas</option>
          <option v-for="a in areas" :key="a.id" :value="a.nombre">{{ a.nombre }}</option>
        </select>
        <button
          type="button"
          class="gio-boton gio-boton--secundario"
          :disabled="cargando"
          @click="cargar"
        >
          {{ cargando ? 'Actualizando…' : 'Actualizar' }}
        </button>
      </div>
    </header>

    <p v-if="problema" class="desempeno__error" role="alert">{{ problema }}</p>
    <p v-else-if="cargando && !datos" class="gio-cargando">Consultando desempeño…</p>

    <template v-if="datos">
      <section class="gio-panel bloque">
        <h2>Técnicos de planta externa</h2>
        <div class="tabla-contenedor">
          <table class="listado">
            <thead>
              <tr>
                <th>Técnico</th>
                <th>Zona</th>
                <th>Abiertos</th>
                <th>En proceso</th>
                <th>Críticos</th>
                <th>Liquidados</th>
                <th>Liquidados hoy</th>
                <th>MTTR prom.</th>
                <th>Dilación prom.</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!datos.tecnicos_planta_externa.length">
                <td colspan="9" class="gio-vacio">Sin técnicos de planta externa en esta zona.</td>
              </tr>
              <tr v-for="fila in datos.tecnicos_planta_externa" :key="fila.id">
                <td>
                  {{ fila.nombre }}
                  <small class="desempeno__expediente">{{ fila.expediente }}</small>
                </td>
                <td>{{ fila.area_operativa || 'Sin área' }}</td>
                <td>{{ fila.abiertos }}</td>
                <td>{{ fila.en_proceso }}</td>
                <td>{{ fila.criticos }}</td>
                <td>{{ fila.liquidados }}</td>
                <td>{{ fila.liquidados_hoy }}</td>
                <td>{{ formatearHoras(fila.mttr_horas_promedio) }}</td>
                <td>{{ dilacion(fila.dilacion_promedio_dias) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="gio-panel bloque">
        <h2>Técnicos de planta interna</h2>
        <div class="tabla-contenedor">
          <table class="listado">
            <thead>
              <tr>
                <th>Técnico</th>
                <th>Zona</th>
                <th>Abiertos</th>
                <th>En proceso</th>
                <th>Críticos</th>
                <th>Liquidados</th>
                <th>Liquidados hoy</th>
                <th>MTTR prom.</th>
                <th>Dilación prom.</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!datos.tecnicos_planta_interna.length">
                <td colspan="9" class="gio-vacio">Sin técnicos de planta interna en esta zona.</td>
              </tr>
              <tr v-for="fila in datos.tecnicos_planta_interna" :key="fila.id">
                <td>
                  {{ fila.nombre }}
                  <small class="desempeno__expediente">{{ fila.expediente }}</small>
                </td>
                <td>{{ fila.area_operativa || 'Sin área' }}</td>
                <td>{{ fila.abiertos }}</td>
                <td>{{ fila.en_proceso }}</td>
                <td>{{ fila.criticos }}</td>
                <td>{{ fila.liquidados }}</td>
                <td>{{ fila.liquidados_hoy }}</td>
                <td>{{ formatearHoras(fila.mttr_horas_promedio) }}</td>
                <td>{{ dilacion(fila.dilacion_promedio_dias) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </section>
</template>

<style scoped>
.desempeno {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding-bottom: 2rem;
}

.desempeno__cabecera {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.desempeno__cabecera h1 {
  font-size: 1.25rem;
}

.desempeno__cabecera p {
  margin: 0.15rem 0 0;
  font-size: 0.8125rem;
  color: var(--apagado);
}

.desempeno__controles {
  display: flex;
  gap: 0.6rem;
  align-items: center;
  flex-wrap: wrap;
}

.desempeno__error {
  margin: 0;
  padding: 0.7rem 0.85rem;
  border-radius: var(--radio);
  background: rgb(239 68 68 / 0.12);
  border: 1px solid rgb(239 68 68 / 0.4);
  color: var(--rojo-texto);
  font-size: 0.8125rem;
}

.desempeno__expediente {
  display: block;
  font-family: ui-monospace, 'SFMono-Regular', Menlo, monospace;
  color: var(--tenue);
}

.bloque {
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.bloque h2 {
  font-size: 1rem;
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
  padding: 0.5rem 0.6rem;
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--apagado);
  border-bottom: 1px solid var(--borde);
  white-space: nowrap;
}

.listado td {
  padding: 0.5rem 0.6rem;
  border-bottom: 1px solid var(--linea);
}
</style>
