<script setup>
import { onMounted, ref, watch } from 'vue'
import {
  getEvaluadores,
  getTurnos,
  guardarTurnos,
  mensajeDeError,
  repartirTurnos,
} from '../services/api.js'
import {
  confirmarAccion,
  mostrarAdvertencia,
  mostrarError,
  mostrarExito,
} from '../utils/alerts.js'

const OPCIONES_TURNO = [
  { id: 'MATUTINO', nombre: 'Matutino' },
  { id: 'VESPERTINO', nombre: 'Vespertino' },
  { id: 'NOCTURNO', nombre: 'Nocturno' },
]

const hoyISO = () => {
  const ahora = new Date()
  const dos = (numero) => String(numero).padStart(2, '0')
  return `${ahora.getFullYear()}-${dos(ahora.getMonth() + 1)}-${dos(ahora.getDate())}`
}

const fecha = ref(hoyISO())
const evaluadores = ref([])
const turnoPorEvaluador = ref({})
const cargando = ref(false)
const guardando = ref(false)
const repartiendo = ref(false)
const problema = ref('')
const limite = ref('')
const resultado = ref(null)

const cargarEvaluadores = async () => {
  try {
    const { data } = await getEvaluadores()
    evaluadores.value = Array.isArray(data) ? data : data.results || []
  } catch (error) {
    problema.value = mensajeDeError(error, 'No se pudo cargar el personal de planta interna.')
  }
}

const cargarTurnos = async () => {
  cargando.value = true
  problema.value = ''
  resultado.value = null
  try {
    const { data } = await getTurnos(fecha.value)
    const asignados = Object.fromEntries(data.map((turno) => [turno.evaluador, turno.turno]))
    turnoPorEvaluador.value = Object.fromEntries(
      evaluadores.value.map((evaluador) => [evaluador.id, asignados[evaluador.id] || '']),
    )
  } catch (error) {
    problema.value = mensajeDeError(error, 'No se pudieron cargar los turnos del día.')
  } finally {
    cargando.value = false
  }
}

onMounted(async () => {
  await cargarEvaluadores()
  await cargarTurnos()
})

watch(fecha, cargarTurnos)

const guardar = async () => {
  const asignaciones = Object.entries(turnoPorEvaluador.value)
    .filter(([, turno]) => turno)
    .map(([evaluador, turno]) => ({ evaluador: Number(evaluador), turno }))
  guardando.value = true
  try {
    await guardarTurnos({ fecha: fecha.value, asignaciones })
    mostrarExito(
      'Turnos guardados',
      asignaciones.length
        ? `${asignaciones.length} técnico(s) de planta interna en turno.`
        : 'Ningún técnico quedó en turno para esta fecha.',
    )
  } catch (error) {
    mostrarError('No se pudieron guardar los turnos', mensajeDeError(error))
  } finally {
    guardando.value = false
  }
}

const repartir = async () => {
  const confirmado = await confirmarAccion(
    'Repartir folios del día',
    'Los folios abiertos sin técnico de planta interna se repartirán en partes iguales entre los técnicos en turno de la fecha. Se usan los turnos guardados.',
    'Repartir',
  )
  if (!confirmado) return

  repartiendo.value = true
  try {
    const { data } = await repartirTurnos({
      fecha: fecha.value,
      limite: limite.value ? Number(limite.value) : 0,
    })
    resultado.value = data
    if (data.evaluadores_de_turno === 0) {
      mostrarAdvertencia('Sin técnicos en turno', 'Guarde primero los turnos de la fecha.')
    } else {
      mostrarExito('Folios repartidos', `${data.asignados} folio(s) asignados.`)
    }
  } catch (error) {
    mostrarError('No se pudo repartir', mensajeDeError(error))
  } finally {
    repartiendo.value = false
  }
}

const nombreEvaluador = (expediente) =>
  evaluadores.value.find((e) => e.expediente === expediente)?.nombre || expediente
</script>

<template>
  <div class="turnos">
    <header class="turnos__cabecera">
      <div>
        <h1>Turnos de planta interna</h1>
        <p>Asigne los turnos del día y reparta los folios entre los técnicos en turno.</p>
      </div>
    </header>

    <section class="gio-panel bloque">
      <div class="bloque__fila">
        <div class="campo">
          <label class="gio-etiqueta" for="fecha-turno">Fecha</label>
          <input id="fecha-turno" v-model="fecha" type="date" />
        </div>
      </div>

      <p v-if="problema" class="turnos__error" role="alert">{{ problema }}</p>
      <p v-else-if="cargando" class="gio-cargando">Consultando turnos…</p>
      <p v-else-if="!evaluadores.length" class="gio-vacio">
        No hay técnicos de planta interna registrados.
      </p>

      <table v-else class="listado">
        <thead>
          <tr>
            <th>Técnico</th>
            <th>Expediente</th>
            <th>Área</th>
            <th>Turno</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="evaluador in evaluadores" :key="evaluador.id">
            <td>{{ evaluador.nombre }}</td>
            <td class="listado__mono">{{ evaluador.expediente }}</td>
            <td>{{ evaluador.area_operativa || 'Sin área' }}</td>
            <td>
              <select
                v-model="turnoPorEvaluador[evaluador.id]"
                :aria-label="`Turno de ${evaluador.nombre}`"
              >
                <option value="">Sin turno</option>
                <option v-for="opcion in OPCIONES_TURNO" :key="opcion.id" :value="opcion.id">
                  {{ opcion.nombre }}
                </option>
              </select>
            </td>
          </tr>
        </tbody>
      </table>

      <div v-if="evaluadores.length" class="bloque__acciones">
        <button
          type="button"
          class="gio-boton gio-boton--primario"
          :disabled="guardando || cargando"
          @click="guardar"
        >
          {{ guardando ? 'Guardando…' : 'Guardar turnos' }}
        </button>
      </div>
    </section>

    <section class="gio-panel bloque">
      <h2>Reparto de folios</h2>
      <p class="bloque__ayuda">
        Cada folio abierto sin técnico de planta interna, de la fecha elegida o anterior, se asigna
        al técnico en turno con menos carga. Cuando hay zonas, el técnico solo recibe folios de su
        área (o de cualquiera si no tiene área).
      </p>
      <div class="bloque__fila">
        <div class="campo">
          <label class="gio-etiqueta" for="limite-reparto">Cantidad máxima de folios</label>
          <input
            id="limite-reparto"
            v-model="limite"
            type="number"
            min="1"
            placeholder="Todos"
          />
        </div>
        <button
          type="button"
          class="gio-boton gio-boton--primario"
          :disabled="repartiendo"
          @click="repartir"
        >
          {{ repartiendo ? 'Repartiendo…' : 'Repartir folios del día' }}
        </button>
      </div>

      <div v-if="resultado && resultado.evaluadores_de_turno > 0" class="resultado">
        <p>
          <strong>{{ resultado.asignados }}</strong> folio(s) asignados ·
          {{ resultado.evaluadores_de_turno }} técnico(s) en turno
          <span v-if="resultado.sin_zona">· {{ resultado.sin_zona }} sin técnico de su zona</span>
        </p>
        <ul v-if="Object.keys(resultado.por_evaluador).length">
          <li v-for="(cantidad, expediente) in resultado.por_evaluador" :key="expediente">
            {{ nombreEvaluador(expediente) }}: {{ cantidad }}
          </li>
        </ul>
      </div>
    </section>
  </div>
</template>

<style scoped>
.turnos {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-width: 960px;
  margin: 0 auto;
  padding-bottom: 2rem;
}

.turnos__cabecera h1 {
  font-size: 1.25rem;
}

.turnos__cabecera p {
  margin: 0.15rem 0 0;
  font-size: 0.8125rem;
  color: var(--apagado);
}

.turnos__error {
  margin: 0;
  padding: 0.7rem 0.85rem;
  border-radius: 8px;
  background: rgb(239 68 68 / 0.12);
  border: 1px solid rgb(239 68 68 / 0.4);
  color: var(--rojo-texto);
  font-size: 0.8125rem;
}

.bloque {
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.bloque h2 {
  font-size: 1rem;
}

.bloque__ayuda {
  margin: 0;
  font-size: 0.8125rem;
  color: var(--apagado);
}

.bloque__fila {
  display: flex;
  align-items: flex-end;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.bloque__acciones {
  display: flex;
  justify-content: flex-end;
}

.campo {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  min-width: 180px;
}

.resultado {
  border-top: 1px solid var(--borde);
  padding-top: 0.75rem;
  font-size: 0.875rem;
}

.resultado ul {
  margin: 0.5rem 0 0;
  padding-left: 1.2rem;
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
