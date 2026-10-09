<script setup>
import { etiquetaEstatus } from '../composables/useIncidentes.js'
import { formatearFecha, formatearHoras } from '../utils/formato.js'

const props = defineProps({
  incidentes: { type: Array, default: () => [] },
  ordenActual: { type: String, default: '-fecha_apertura' },
  seleccion: { type: Array, default: () => [] },
  seleccionable: { type: Boolean, default: false },
})

const emit = defineEmits(['editar', 'ordenar', 'actualizar:seleccion'])

const COLUMNAS = [
  { clave: 'folio', texto: 'Folio', ordenable: true },
  { clave: 'empresa', texto: 'Cliente / Empresa', ordenable: false },
  { clave: 'area_operativa', texto: 'Área / Central', ordenable: false },
  { clave: 'estado_enlace', texto: 'Enlace', ordenable: false },
  { clave: 'tecnico', texto: 'Técnico (PE)', ordenable: false },
  { clave: 'dilacion_dias', texto: 'Dilación', ordenable: true },
  { clave: 'estatus', texto: 'Estatus', ordenable: true },
  { clave: 'fecha_apertura', texto: 'Apertura', ordenable: true },
  { clave: 'mttr', texto: 'MTTR', ordenable: false },
]

const alternarOrden = (clave) => {
  const siguiente = props.ordenActual === clave ? `-${clave}` : clave
  emit('ordenar', siguiente)
}

const indicador = (clave) => {
  if (props.ordenActual === clave) return '▲'
  if (props.ordenActual === `-${clave}`) return '▼'
  return ''
}

const estaSeleccionado = (id) => props.seleccion.includes(id)

const alternarFila = (id) => {
  const nueva = estaSeleccionado(id)
    ? props.seleccion.filter((item) => item !== id)
    : [...props.seleccion, id]
  emit('actualizar:seleccion', nueva)
}

const alternarTodo = (evento) => {
  emit('actualizar:seleccion', evento.target.checked ? props.incidentes.map((i) => i.id) : [])
}
</script>

<template>
  <div class="tabla-caja gio-panel">
    <table class="tabla">
      <thead>
        <tr>
          <th v-if="seleccionable" class="tabla__casilla">
            <input
              type="checkbox"
              :checked="incidentes.length > 0 && seleccion.length === incidentes.length"
              :aria-label="'Seleccionar todos los folios visibles'"
              @change="alternarTodo"
            />
          </th>
          <th
            v-for="columna in COLUMNAS"
            :key="columna.clave"
            :aria-sort="
              ordenActual === columna.clave
                ? 'ascending'
                : ordenActual === `-${columna.clave}`
                  ? 'descending'
                  : 'none'
            "
          >
            <button
              v-if="columna.ordenable"
              type="button"
              class="tabla__orden"
              @click="alternarOrden(columna.clave)"
            >
              {{ columna.texto }} <span class="tabla__flecha">{{ indicador(columna.clave) }}</span>
            </button>
            <span v-else>{{ columna.texto }}</span>
          </th>
          <th>Acciones</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="incidentes.length === 0">
          <td :colspan="seleccionable ? COLUMNAS.length + 2 : COLUMNAS.length + 1" class="gio-vacio">
            No se encontraron folios con los filtros aplicados.
          </td>
        </tr>
        <tr
          v-for="inc in incidentes"
          :key="inc.id"
          :class="{ 'tabla__fila--marcada': estaSeleccionado(inc.id) }"
        >
          <td v-if="seleccionable" class="tabla__casilla">
            <input
              type="checkbox"
              :checked="estaSeleccionado(inc.id)"
              :aria-label="`Seleccionar folio ${inc.folio}`"
              @change="alternarFila(inc.id)"
            />
          </td>
          <td>
            <span class="tabla__folio">{{ inc.folio }}</span>
            <small v-if="inc.referencia" class="tabla__sub">{{ inc.referencia }}</small>
          </td>
          <td>
            <span class="tabla__fuerte">{{ inc.empresa || 'Sin empresa' }}</span>
            <small class="tabla__sub">{{ inc.tipo_servicio || 'Servicio estándar' }}</small>
          </td>
          <td>
            <span class="tabla__fuerte">{{ inc.area_operativa || 'Sin área' }}</span>
            <small class="tabla__sub">{{ inc.central || 'Sin central' }}</small>
          </td>
          <td>
            <span
              class="gio-enlace"
              :class="`gio-enlace--${(inc.estado_enlace || 'desconocido').toLowerCase()}`"
            >
              {{ inc.estado_enlace || 'N/D' }}
            </span>
          </td>
          <td>{{ inc.tecnico_nombre || 'Sin asignar' }}</td>
          <td>
            <span class="gio-semaforo" :class="`gio-semaforo--${inc.semaforo || 'normal'}`">
              {{ inc.dilacion_dias ?? 0 }} d
            </span>
          </td>
          <td>
            <span class="gio-pastilla" :class="`gio-pastilla--${(inc.estatus || '').toLowerCase()}`">
              {{ etiquetaEstatus(inc.estatus) }}
            </span>
          </td>
          <td class="tabla__fecha">{{ formatearFecha(inc.fecha_apertura) }}</td>
          <td class="tabla__fecha">
            {{ inc.estatus === 'LIQUIDADO' ? formatearHoras(inc.mttr_horas) : formatearHoras(inc.horas_abierto) }}
          </td>
          <td>
            <button
              type="button"
              class="gio-boton gio-boton--secundario tabla__accion"
              @click="emit('editar', inc)"
            >
              Abrir
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.tabla-caja {
  overflow-x: auto;
}

.tabla {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 0.8125rem;
}

.tabla th {
  background-color: #0a1222;
  color: var(--apagado);
  padding: 0.7rem 0.85rem;
  font-weight: 600;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  border-bottom: 1px solid var(--borde);
  white-space: nowrap;
  position: sticky;
  top: 0;
  z-index: 1;
}

.tabla td {
  padding: 0.6rem 0.85rem;
  border-bottom: 1px solid rgb(36 51 82 / 0.6);
  vertical-align: middle;
}

.tabla tbody tr:hover {
  background-color: rgb(36 51 82 / 0.35);
}

.tabla__fila--marcada {
  background-color: rgb(37 99 235 / 0.12);
}

.tabla__casilla {
  width: 36px;
  text-align: center;
}

.tabla__casilla input {
  width: 16px;
  height: 16px;
  padding: 0;
  accent-color: var(--acento);
}

.tabla__orden {
  background: none;
  border: none;
  padding: 0;
  color: inherit;
  font: inherit;
  text-transform: inherit;
  letter-spacing: inherit;
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}

.tabla__orden:hover {
  color: var(--acento-claro);
}

.tabla__flecha {
  font-size: 0.6rem;
  color: var(--acento-claro);
}

.tabla__folio {
  display: block;
  font-family: ui-monospace, 'SFMono-Regular', Menlo, monospace;
  font-weight: 700;
  color: var(--acento-claro);
}

.tabla__fuerte {
  display: block;
  font-weight: 600;
}

.tabla__sub {
  display: block;
  color: #64748b;
  font-size: 0.7rem;
}

.tabla__fecha {
  color: var(--apagado);
  white-space: nowrap;
  font-size: 0.75rem;
}

.tabla__accion {
  padding: 0.35rem 0.7rem;
  font-size: 0.75rem;
}
</style>
