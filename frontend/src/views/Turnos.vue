<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import {
  getEvaluadores,
  getTurnos,
  mensajeDeError,
  programarTurnos,
  repartirTurnos,
} from '../services/api.js'
import {
  confirmarAccion,
  mostrarAdvertencia,
  mostrarError,
  mostrarExito,
} from '../utils/alerts.js'

const NOMBRES_DIA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
const ABREVIADOS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']

// Fechas como texto AAAA-MM-DD en hora local, para no depender de la zona horaria.
const dos = (numero) => String(numero).padStart(2, '0')
const aTexto = (fecha) => `${fecha.getFullYear()}-${dos(fecha.getMonth() + 1)}-${dos(fecha.getDate())}`
const aFecha = (texto) => {
  const [anio, mes, dia] = texto.split('-').map(Number)
  return new Date(anio, mes - 1, dia)
}
const sumarDias = (texto, dias) => {
  const fecha = aFecha(texto)
  fecha.setDate(fecha.getDate() + dias)
  return aTexto(fecha)
}
const lunesDe = (texto) => sumarDias(texto, -((aFecha(texto).getDay() + 6) % 7))
const diaSemana = (texto) => (aFecha(texto).getDay() + 6) % 7

const hoy = aTexto(new Date())

const evaluadores = ref([])
const turnos = ref([])
const semana = ref(lunesDe(hoy))
const cargando = ref(false)
const guardando = ref(false)
const repartiendo = ref(false)
const problema = ref('')
const seleccion = ref([])

const nuevoDia = (indice) => ({
  modo: indice === 6 ? 'igual' : 'base',
  inicio: '15:00',
  fin: '23:00',
})

const formulario = reactive({
  desde: semana.value,
  hasta: sumarDias(semana.value, 6),
  inicio: '06:00',
  fin: '14:00',
  dias: NOMBRES_DIA.map((_, indice) => nuevoDia(indice)),
})

const fechaReparto = ref(hoy)
const limite = ref('')
const resultado = ref(null)

const diasSemana = computed(() =>
  ABREVIADOS.map((nombre, indice) => {
    const fecha = sumarDias(semana.value, indice)
    const [, mes, dia] = fecha.split('-')
    return { fecha, etiqueta: `${nombre} ${dia}/${mes}`, esHoy: fecha === hoy }
  }),
)

const turnoDe = computed(() => {
  const mapa = new Map()
  for (const turno of turnos.value) mapa.set(`${turno.evaluador}|${turno.fecha}`, turno)
  return (evaluadorId, fecha) => mapa.get(`${evaluadorId}|${fecha}`)
})

const todosSeleccionados = computed(
  () => evaluadores.value.length > 0 && seleccion.value.length === evaluadores.value.length,
)

const alternarTodos = () => {
  seleccion.value = todosSeleccionados.value ? [] : evaluadores.value.map((e) => e.id)
}

const cargarSemana = async () => {
  cargando.value = true
  problema.value = ''
  try {
    const { data } = await getTurnos({ desde: semana.value, hasta: sumarDias(semana.value, 6) })
    turnos.value = data
  } catch (error) {
    problema.value = mensajeDeError(error, 'No se pudieron cargar los turnos de la semana.')
  } finally {
    cargando.value = false
  }
}

const moverSemana = async (dias) => {
  semana.value = dias === 0 ? lunesDe(hoy) : sumarDias(semana.value, dias)
  formulario.desde = semana.value
  formulario.hasta = sumarDias(semana.value, 6)
  await cargarSemana()
}

onMounted(async () => {
  try {
    const { data } = await getEvaluadores()
    evaluadores.value = Array.isArray(data) ? data : data.results || []
  } catch (error) {
    problema.value = mensajeDeError(error, 'No se pudo cargar el personal de planta interna.')
  }
  await cargarSemana()
})

// Al pulsar una celda se prepara la edición de ese técnico en ese día.
const editarCelda = (evaluador, fecha) => {
  const actual = turnoDe.value(evaluador.id, fecha)
  seleccion.value = [evaluador.id]
  formulario.desde = fecha
  formulario.hasta = fecha
  formulario.dias.forEach((dia, indice) => {
    dia.modo = 'igual'
    if (indice === diaSemana(fecha)) {
      dia.modo = 'otro'
      dia.inicio = actual?.hora_inicio || formulario.inicio
      dia.fin = actual?.hora_fin || formulario.fin
    }
  })
  document.getElementById('programacion')?.scrollIntoView({ behavior: 'smooth' })
}

const restablecerDias = () => {
  formulario.dias.forEach((dia, indice) => Object.assign(dia, nuevoDia(indice)))
}

const horariosDelFormulario = () =>
  formulario.dias.map((dia) => {
    if (dia.modo === 'igual') return null
    if (dia.modo === 'descanso') return { descanso: true }
    if (dia.modo === 'base') return { hora_inicio: formulario.inicio, hora_fin: formulario.fin }
    return { hora_inicio: dia.inicio, hora_fin: dia.fin }
  })

const describirHorario = (horario) => {
  if (!horario) return 'sin cambios'
  if (horario.descanso) return 'descanso'
  return `${horario.hora_inicio}–${horario.hora_fin}`
}

const guardar = async () => {
  if (!seleccion.value.length) {
    mostrarAdvertencia('Sin técnicos', 'Marque al menos un técnico de planta interna.')
    return
  }
  const horarios = horariosDelFormulario()
  if (horarios.every((horario) => horario === null)) {
    mostrarAdvertencia('Nada que guardar', 'Todos los días están en "Sin cambios".')
    return
  }
  const resumen = NOMBRES_DIA.map((nombre, i) => `${nombre}: ${describirHorario(horarios[i])}`)
    .join(' · ')
  const confirmado = await confirmarAccion(
    `Programar ${seleccion.value.length} técnico(s)`,
    `Del ${formulario.desde} al ${formulario.hasta}. ${resumen}`,
    'Guardar horarios',
  )
  if (!confirmado) return

  guardando.value = true
  try {
    const { data } = await programarTurnos({
      evaluadores: seleccion.value,
      desde: formulario.desde,
      hasta: formulario.hasta,
      horarios,
    })
    mostrarExito(
      'Horarios guardados',
      `${data.guardados} turno(s) guardados` +
        (data.eliminados ? ` y ${data.eliminados} día(s) de descanso.` : '.'),
    )
    await cargarSemana()
  } catch (error) {
    mostrarError('No se pudieron guardar los horarios', mensajeDeError(error))
  } finally {
    guardando.value = false
  }
}

const repartir = async () => {
  const confirmado = await confirmarAccion(
    'Repartir folios del día',
    'Los folios abiertos sin técnico de planta interna se repartirán en partes iguales entre los técnicos con turno en esa fecha.',
    'Repartir',
  )
  if (!confirmado) return

  repartiendo.value = true
  try {
    const { data } = await repartirTurnos({
      fecha: fechaReparto.value,
      limite: limite.value ? Number(limite.value) : 0,
    })
    resultado.value = data
    if (data.evaluadores_de_turno === 0) {
      mostrarAdvertencia('Sin técnicos en turno', 'No hay técnicos con horario en esa fecha.')
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
      <h1>Turnos de planta interna</h1>
      <p>Horarios por técnico y día. Pulse una celda para editarla o programe varios a la vez.</p>
    </header>

    <section class="gio-panel bloque">
      <div class="bloque__fila bloque__fila--entre">
        <h2>Semana del {{ diasSemana[0].etiqueta }} al {{ diasSemana[6].etiqueta }}</h2>
        <div class="navegacion">
          <button type="button" class="gio-boton gio-boton--secundario" @click="moverSemana(-7)">
            ← Anterior
          </button>
          <button type="button" class="gio-boton gio-boton--secundario" @click="moverSemana(0)">
            Esta semana
          </button>
          <button type="button" class="gio-boton gio-boton--secundario" @click="moverSemana(7)">
            Siguiente →
          </button>
        </div>
      </div>

      <p v-if="problema" class="turnos__error" role="alert">{{ problema }}</p>
      <p v-else-if="!evaluadores.length" class="gio-vacio">
        No hay técnicos de planta interna registrados.
      </p>

      <div v-else class="tabla-contenedor">
        <table class="cuadricula" :class="{ 'cuadricula--cargando': cargando }">
          <thead>
            <tr>
              <th class="cuadricula__marca">
                <input
                  type="checkbox"
                  :checked="todosSeleccionados"
                  aria-label="Seleccionar todos"
                  @change="alternarTodos"
                />
              </th>
              <th>Técnico</th>
              <th
                v-for="dia in diasSemana"
                :key="dia.fecha"
                :class="{ 'cuadricula__hoy': dia.esHoy }"
              >
                {{ dia.etiqueta }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="evaluador in evaluadores" :key="evaluador.id">
              <td class="cuadricula__marca">
                <input
                  v-model="seleccion"
                  type="checkbox"
                  :value="evaluador.id"
                  :aria-label="`Seleccionar a ${evaluador.nombre}`"
                />
              </td>
              <td class="cuadricula__tecnico">
                {{ evaluador.nombre }}
                <small>{{ evaluador.expediente }} · {{ evaluador.area_operativa || 'Sin área' }}</small>
              </td>
              <td
                v-for="dia in diasSemana"
                :key="dia.fecha"
                :class="{ 'cuadricula__hoy': dia.esHoy }"
              >
                <button
                  type="button"
                  class="celda"
                  :class="{ 'celda--vacia': !turnoDe(evaluador.id, dia.fecha) }"
                  :title="`Editar ${evaluador.nombre} el ${dia.etiqueta}`"
                  @click="editarCelda(evaluador, dia.fecha)"
                >
                  <template v-if="turnoDe(evaluador.id, dia.fecha)">
                    {{ turnoDe(evaluador.id, dia.fecha).hora_inicio }}–{{
                      turnoDe(evaluador.id, dia.fecha).hora_fin
                    }}
                    <span
                      v-if="turnoDe(evaluador.id, dia.fecha).cruza_medianoche"
                      class="celda__nota"
                      >+1 día</span
                    >
                  </template>
                  <template v-else>—</template>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section id="programacion" class="gio-panel bloque">
      <h2>Programar horarios</h2>
      <p class="bloque__ayuda">
        {{ seleccion.length }} técnico(s) seleccionado(s) en la tabla. El horario se aplica a
        cada día del rango según su día de la semana.
      </p>

      <div class="bloque__fila">
        <div class="campo">
          <label class="gio-etiqueta" for="prog-desde">Desde</label>
          <input id="prog-desde" v-model="formulario.desde" type="date" />
        </div>
        <div class="campo">
          <label class="gio-etiqueta" for="prog-hasta">Hasta</label>
          <input id="prog-hasta" v-model="formulario.hasta" type="date" :min="formulario.desde" />
        </div>
        <div class="campo">
          <label class="gio-etiqueta" for="prog-inicio">Horario base: entrada</label>
          <input id="prog-inicio" v-model="formulario.inicio" type="time" step="900" />
        </div>
        <div class="campo">
          <label class="gio-etiqueta" for="prog-fin">Salida</label>
          <input id="prog-fin" v-model="formulario.fin" type="time" step="900" />
        </div>
      </div>

      <ul class="dias">
        <li v-for="(dia, indice) in formulario.dias" :key="indice" class="dias__fila">
          <span class="dias__nombre">{{ NOMBRES_DIA[indice] }}</span>
          <select v-model="dia.modo" :aria-label="`Horario del ${NOMBRES_DIA[indice]}`">
            <option value="base">Horario base</option>
            <option value="otro">Otro horario</option>
            <option value="descanso">Descanso</option>
            <option value="igual">Sin cambios</option>
          </select>
          <template v-if="dia.modo === 'otro'">
            <input
              v-model="dia.inicio"
              type="time"
              step="900"
              :aria-label="`Entrada del ${NOMBRES_DIA[indice]}`"
            />
            <span>a</span>
            <input
              v-model="dia.fin"
              type="time"
              step="900"
              :aria-label="`Salida del ${NOMBRES_DIA[indice]}`"
            />
          </template>
          <span v-else-if="dia.modo === 'base'" class="dias__resumen">
            {{ formulario.inicio }}–{{ formulario.fin }}
          </span>
        </li>
      </ul>

      <div class="bloque__acciones">
        <button type="button" class="gio-boton gio-boton--secundario" @click="restablecerDias">
          Restablecer días
        </button>
        <button
          type="button"
          class="gio-boton gio-boton--primario"
          :disabled="guardando"
          @click="guardar"
        >
          {{ guardando ? 'Guardando…' : 'Guardar horarios' }}
        </button>
      </div>
    </section>

    <section class="gio-panel bloque">
      <h2>Reparto de folios</h2>
      <p class="bloque__ayuda">
        Cada folio abierto sin técnico de planta interna, de la fecha elegida o anterior, se asigna
        al técnico con turno ese día que tenga menos carga. Un técnico con área solo recibe folios
        de esa área.
      </p>
      <div class="bloque__fila">
        <div class="campo">
          <label class="gio-etiqueta" for="fecha-reparto">Fecha</label>
          <input id="fecha-reparto" v-model="fechaReparto" type="date" />
        </div>
        <div class="campo">
          <label class="gio-etiqueta" for="limite-reparto">Cantidad máxima de folios</label>
          <input id="limite-reparto" v-model="limite" type="number" min="1" placeholder="Todos" />
        </div>
        <button
          type="button"
          class="gio-boton gio-boton--primario"
          :disabled="repartiendo"
          @click="repartir"
        >
          {{ repartiendo ? 'Repartiendo…' : 'Repartir folios' }}
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
  max-width: 1200px;
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
  border-radius: var(--radio);
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

.bloque__fila--entre {
  justify-content: space-between;
  align-items: center;
}

.bloque__acciones {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
}

.navegacion {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.campo {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  min-width: 150px;
}

.tabla-contenedor {
  overflow-x: auto;
}

.cuadricula {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

.cuadricula--cargando {
  opacity: 0.55;
}

.cuadricula th {
  text-align: left;
  padding: 0.5rem 0.4rem;
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--apagado);
  border-bottom: 1px solid var(--borde);
  white-space: nowrap;
}

.cuadricula td {
  padding: 0.35rem 0.4rem;
  border-bottom: 1px solid var(--linea);
  vertical-align: middle;
}

.cuadricula__marca {
  width: 2rem;
}

.cuadricula__tecnico {
  min-width: 170px;
}

.cuadricula__tecnico small {
  display: block;
  color: var(--tenue);
  font-size: 0.7rem;
}

.cuadricula__hoy {
  background-color: var(--resalte);
}

.celda {
  width: 100%;
  min-width: 92px;
  padding: 0.4rem 0.3rem;
  border: 1px solid var(--borde);
  border-radius: var(--radio-campo);
  background-color: var(--superficie);
  color: var(--texto);
  font-variant-numeric: tabular-nums;
  font-size: 0.78rem;
  white-space: nowrap;
}

.celda:hover {
  border-color: var(--acento-claro);
}

.celda--vacia {
  color: var(--tenue);
  background-color: transparent;
}

.celda__nota {
  display: block;
  font-size: 0.65rem;
  color: var(--apagado);
}

.dias {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.dias__fila {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
  font-size: 0.8125rem;
}

.dias__nombre {
  width: 90px;
  font-weight: 700;
}

.dias__fila select {
  max-width: 180px;
}

.dias__fila input[type='time'] {
  max-width: 130px;
}

.dias__resumen {
  color: var(--apagado);
  font-variant-numeric: tabular-nums;
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
</style>
