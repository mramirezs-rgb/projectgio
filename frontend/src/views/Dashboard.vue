<script setup>
import { computed, onMounted, ref } from 'vue'
import IncidenteModal from '../components/IncidenteModal.vue'
import KanbanBoard from '../components/KanbanBoard.vue'
import TablaIncidentes from '../components/TablaIncidentes.vue'
import { useAuth } from '../composables/useAuth.js'
import { COLUMNAS_KANBAN, ESTATUS, etiquetaEstatus, useIncidentes } from '../composables/useIncidentes.js'
import {
  asignarMasivo,
  createIncidente,
  liquidarIncidente,
  mensajeDeError,
  updateIncidente,
} from '../services/api.js'
import {
  confirmarAccion,
  mostrarAdvertencia,
  mostrarError,
  mostrarExito,
  notificar,
} from '../utils/alerts.js'
import { descargarCSV, formatearFecha, formatearHoras, marcaDeTiempo } from '../utils/formato.js'

const { usuario, rol, permisos } = useAuth()
const {
  cargando,
  incidentes,
  tecnicos,
  evaluadores,
  centrales,
  areas,
  filtros,
  paginacion,
  totalPaginas,
  columnasKanban,
  kpis,
  cargarCatalogos,
  cargarIncidentes,
  aplicarFiltros,
  aplicarFiltrosConRetardo,
  limpiarFiltros,
  irAPagina,
  reemplazarIncidente,
} = useIncidentes()

const FORM_VACIO = {
  id: null,
  folio: '',
  empresa: '',
  referencia: '',
  tipo_servicio: '',
  area_operativa: '',
  central: '',
  tecnico: null,
  evaluador: null,
  estatus: ESTATUS.PENDIENTE,
  estado_enlace: 'DESCONOCIDO',
  codigo_fallo: '',
  descripcion: '',
  diagnostico_final: '',
  obs_usuario: '',
  observaciones_sisa: '',
  dir_pta_a: '',
  ips: '',
  dslam: '',
  red_secundaria: '',
  telefono_tecnico: '',
  desc_f1: '',
  desc_cod4: '',
  desc_carls: '',
  desc_cod5: '',
  cve_liq: '',
  desc_liq: '',
}

const vista = ref('kanban')
const modalAbierto = ref(false)
const editando = ref(false)
const guardando = ref(false)
const formActual = ref({ ...FORM_VACIO })
const seleccion = ref([])
const tecnicoMasivo = ref('')

const seleccionados = computed(() =>
  incidentes.value.filter((item) => seleccion.value.includes(item.id)),
)

const rangoMostrado = computed(() => {
  if (!paginacion.total) return '0'
  const desde = (paginacion.pagina - 1) * paginacion.tamano + 1
  const hasta = Math.min(paginacion.pagina * paginacion.tamano, paginacion.total)
  return `${desde}–${hasta} de ${paginacion.total}`
})

onMounted(async () => {
  await cargarCatalogos()
  try {
    await cargarIncidentes()
  } catch (error) {
    mostrarError('No se pudieron cargar los folios', mensajeDeError(error))
  }
})

const abrirNuevo = () => {
  formActual.value = { ...FORM_VACIO }
  editando.value = false
  modalAbierto.value = true
}

const abrirEditar = (incidente) => {
  formActual.value = { ...FORM_VACIO, ...incidente }
  editando.value = true
  modalAbierto.value = true
}

const guardar = async (datos) => {
  guardando.value = true
  try {
    if (editando.value) {
      const { data } = await updateIncidente(datos.id, datos)
      reemplazarIncidente(data)
      notificar('Folio actualizado')
    } else {
      await createIncidente(datos)
      mostrarExito('Folio creado', `El folio ${datos.folio} quedó registrado como pendiente.`)
      await cargarIncidentes()
    }
    modalAbierto.value = false
  } catch (error) {
    mostrarError('No se pudo guardar el folio', mensajeDeError(error))
  } finally {
    guardando.value = false
  }
}

const liquidar = async (datos) => {
  guardando.value = true
  try {
    const { data } = await liquidarIncidente(datos.id, datos)
    reemplazarIncidente(data)
    modalAbierto.value = false
    mostrarExito('Folio liquidado', `MTTR registrado: ${formatearHoras(data.mttr_horas)}.`)
  } catch (error) {
    mostrarError('No se pudo liquidar el folio', mensajeDeError(error))
  } finally {
    guardando.value = false
  }
}

const moverEnTablero = async ({ incidente, estatus }) => {
  if (estatus === ESTATUS.LIQUIDADO) {
    abrirEditar(incidente)
    mostrarAdvertencia(
      'Liquidación con evidencia',
      'Para liquidar un folio se requiere diagnóstico final y al menos una evidencia fotográfica.',
    )
    return
  }
  const anterior = incidente.estatus
  reemplazarIncidente({ ...incidente, estatus })
  try {
    const { data } = await updateIncidente(incidente.id, { estatus })
    reemplazarIncidente(data)
    notificar(`${incidente.folio} → ${etiquetaEstatus(estatus)}`)
  } catch (error) {
    reemplazarIncidente({ ...incidente, estatus: anterior })
    mostrarError('No se pudo mover el folio', mensajeDeError(error))
  }
}

const asignarSeleccion = async () => {
  if (!tecnicoMasivo.value || seleccionados.value.length === 0) return
  const tecnico = tecnicos.value.find((t) => String(t.id) === String(tecnicoMasivo.value))
  const confirmado = await confirmarAccion(
    'Reasignación masiva',
    `Se asignarán ${seleccionados.value.length} folio(s) a ${tecnico?.nombre || 'el técnico elegido'}.`,
    'Asignar',
  )
  if (!confirmado) return
  try {
    const { data } = await asignarMasivo({
      folios: seleccionados.value.map((item) => item.folio),
      tecnico: Number(tecnicoMasivo.value),
    })
    seleccion.value = []
    tecnicoMasivo.value = ''
    await cargarIncidentes()
    mostrarExito('Folios reasignados', `${data.actualizados} folio(s) actualizados.`)
  } catch (error) {
    mostrarError('No se pudo reasignar', mensajeDeError(error))
  }
}

const exportar = () => {
  if (incidentes.value.length === 0) {
    mostrarAdvertencia('Sin datos', 'No hay folios en la vista actual para exportar.')
    return
  }
  descargarCSV(
    `GIO_Incidencias_${marcaDeTiempo()}.csv`,
    [
      'Folio',
      'Empresa',
      'Referencia',
      'Tipo de servicio',
      'Area operativa',
      'Central',
      'Tecnico',
      'Evaluador',
      'Estatus',
      'Estado del enlace',
      'Dilacion (dias)',
      'Apertura',
      'Cierre',
      'MTTR (horas)',
      'Evidencias',
      'Direccion',
      'IP',
    ],
    incidentes.value.map((inc) => [
      inc.folio,
      inc.empresa,
      inc.referencia,
      inc.tipo_servicio,
      inc.area_operativa,
      inc.central,
      inc.tecnico_nombre,
      inc.evaluador_nombre,
      etiquetaEstatus(inc.estatus),
      inc.estado_enlace,
      inc.dilacion_dias ?? 0,
      formatearFecha(inc.fecha_apertura),
      formatearFecha(inc.fecha_cierre),
      inc.mttr_horas ?? '',
      inc.total_evidencias ?? 0,
      inc.dir_pta_a,
      inc.ips,
    ]),
  )
  notificar('Reporte CSV descargado')
}

const ordenar = async (campo) => {
  filtros.ordering = campo
  await aplicarFiltros()
}
</script>

<template>
  <div class="panel">
    <section class="indicadores">
      <article class="indicador gio-panel">
        <span class="indicador__titulo">Folios visibles</span>
        <strong class="indicador__valor">{{ kpis.total ?? 0 }}</strong>
        <small>{{ rangoMostrado }} en pantalla</small>
      </article>
      <article
        v-for="columna in COLUMNAS_KANBAN"
        :key="columna.id"
        class="indicador gio-panel"
        :style="{ borderTopColor: columna.color }"
      >
        <span class="indicador__titulo">{{ columna.titulo }}</span>
        <strong class="indicador__valor">
          {{
            columna.id === 'PENDIENTE'
              ? kpis.pendientes
              : columna.id === 'ASIGNADO'
                ? kpis.asignados
                : columna.id === 'EN_PROCESO'
                  ? kpis.en_proceso
                  : kpis.liquidados
          }}
        </strong>
      </article>
      <article class="indicador indicador--alerta gio-panel">
        <span class="indicador__titulo">
          Dilación ≥ {{ kpis.umbral_dilacion_dias ?? 5 }} días
        </span>
        <strong class="indicador__valor indicador__valor--rojo">{{ kpis.en_dilacion ?? 0 }}</strong>
        <small>{{ kpis.criticos ?? 0 }} en nivel crítico</small>
      </article>
      <article class="indicador gio-panel">
        <span class="indicador__titulo">MTTR promedio</span>
        <strong class="indicador__valor">{{ formatearHoras(kpis.mttr_horas_promedio) }}</strong>
        <small v-if="kpis.pendientes_exportar">
          {{ kpis.pendientes_exportar }} por exportar a SISA
        </small>
      </article>
    </section>

    <section class="filtros gio-panel">
      <div class="filtros__grupo">
        <div class="filtros__campo filtros__campo--busqueda">
          <label class="gio-etiqueta" for="buscar">Buscar</label>
          <input
            id="buscar"
            v-model.trim="filtros.search"
            type="search"
            placeholder="Folio, empresa, referencia, IP…"
            @input="aplicarFiltrosConRetardo()"
            @keyup.enter="aplicarFiltros"
          />
        </div>
        <div class="filtros__campo">
          <label class="gio-etiqueta" for="f-estatus">Estatus</label>
          <select id="f-estatus" v-model="filtros.estatus" @change="aplicarFiltros">
            <option value="">Todos</option>
            <option v-for="columna in COLUMNAS_KANBAN" :key="columna.id" :value="columna.id">
              {{ columna.titulo }}
            </option>
          </select>
        </div>
        <div class="filtros__campo">
          <label class="gio-etiqueta" for="f-area">Área</label>
          <select id="f-area" v-model="filtros.area_operativa" @change="aplicarFiltros">
            <option value="">Todas</option>
            <option v-for="area in areas" :key="area.id" :value="area.nombre">
              {{ area.nombre }}
            </option>
          </select>
        </div>
        <div class="filtros__campo">
          <label class="gio-etiqueta" for="f-central">COPE / Central</label>
          <select id="f-central" v-model="filtros.central" @change="aplicarFiltros">
            <option value="">Todas</option>
            <option v-for="central in centrales" :key="central.id" :value="central.nombre">
              {{ central.nombre }}
            </option>
          </select>
        </div>
        <div class="filtros__campo">
          <label class="gio-etiqueta" for="f-tecnico">Técnico</label>
          <select id="f-tecnico" v-model="filtros.tecnico" @change="aplicarFiltros">
            <option value="">Todos</option>
            <option v-for="t in tecnicos" :key="t.id" :value="t.id">{{ t.nombre }}</option>
          </select>
        </div>
        <div v-if="permisos.vision_global" class="filtros__campo">
          <label class="gio-etiqueta" for="f-evaluador">Evaluador</label>
          <select id="f-evaluador" v-model="filtros.evaluador" @change="aplicarFiltros">
            <option value="">Todos</option>
            <option v-for="e in evaluadores" :key="e.id" :value="e.id">{{ e.nombre }}</option>
          </select>
        </div>
        <div class="filtros__campo">
          <label class="gio-etiqueta" for="f-enlace">Enlace</label>
          <select id="f-enlace" v-model="filtros.estado_enlace" @change="aplicarFiltros">
            <option value="">Todos</option>
            <option value="UP">UP</option>
            <option value="DOWN">DOWN</option>
            <option value="DESCONOCIDO">Desconocido</option>
          </select>
        </div>
        <div class="filtros__campo">
          <label class="gio-etiqueta" for="f-dilacion">Dilación mínima</label>
          <input
            id="f-dilacion"
            v-model="filtros.dilacion_min"
            type="number"
            min="0"
            placeholder="0"
            @change="aplicarFiltros"
          />
        </div>
      </div>

      <div class="filtros__acciones">
        <button type="button" class="gio-boton gio-boton--secundario" @click="limpiarFiltros">
          Limpiar filtros
        </button>
        <button
          v-if="permisos.crear_folio"
          type="button"
          class="gio-boton gio-boton--primario"
          @click="abrirNuevo"
        >
          Nuevo folio
        </button>
        <button
          v-if="permisos.exportar"
          type="button"
          class="gio-boton gio-boton--secundario"
          @click="exportar"
        >
          Exportar CSV
        </button>
        <div class="conmutador" role="group" aria-label="Tipo de vista">
          <button
            type="button"
            :class="['conmutador__btn', { 'conmutador__btn--activo': vista === 'kanban' }]"
            @click="vista = 'kanban'"
          >
            Kanban
          </button>
          <button
            type="button"
            :class="['conmutador__btn', { 'conmutador__btn--activo': vista === 'tabla' }]"
            @click="vista = 'tabla'"
          >
            Tabla
          </button>
        </div>
      </div>
    </section>

    <section
      v-if="vista === 'tabla' && permisos.asignar && seleccion.length"
      class="masiva gio-panel"
    >
      <span>{{ seleccion.length }} folio(s) seleccionados</span>
      <select v-model="tecnicoMasivo" aria-label="Técnico destino">
        <option value="">Elegir técnico…</option>
        <option v-for="t in tecnicos" :key="t.id" :value="t.id">
          {{ t.nombre }} · {{ t.expediente }}
        </option>
      </select>
      <button
        type="button"
        class="gio-boton gio-boton--primario"
        :disabled="!tecnicoMasivo"
        @click="asignarSeleccion"
      >
        Reasignar
      </button>
      <button type="button" class="gio-boton gio-boton--secundario" @click="seleccion = []">
        Cancelar
      </button>
    </section>

    <p v-if="cargando" class="gio-cargando">Consultando folios…</p>

    <KanbanBoard
      v-else-if="vista === 'kanban'"
      :columnas="columnasKanban"
      :puede-mover="permisos.asignar || permisos.liquidar"
      @editar="abrirEditar"
      @mover="moverEnTablero"
    />

    <TablaIncidentes
      v-else
      :incidentes="incidentes"
      :orden-actual="filtros.ordering"
      :seleccion="seleccion"
      :seleccionable="permisos.asignar"
      @editar="abrirEditar"
      @ordenar="ordenar"
      @actualizar:seleccion="seleccion = $event"
    />

    <nav v-if="!cargando && totalPaginas > 1" class="paginas" aria-label="Paginación">
      <button
        type="button"
        class="gio-boton gio-boton--secundario"
        :disabled="paginacion.pagina <= 1"
        @click="irAPagina(paginacion.pagina - 1)"
      >
        Anterior
      </button>
      <span class="paginas__texto">
        Página {{ paginacion.pagina }} de {{ totalPaginas }} · {{ rangoMostrado }}
      </span>
      <button
        type="button"
        class="gio-boton gio-boton--secundario"
        :disabled="paginacion.pagina >= totalPaginas"
        @click="irAPagina(paginacion.pagina + 1)"
      >
        Siguiente
      </button>
    </nav>

    <IncidenteModal
      v-if="modalAbierto"
      :modelo="formActual"
      :editando="editando"
      :centrales="centrales"
      :tecnicos="tecnicos"
      :evaluadores="evaluadores"
      :areas="areas"
      :permisos="permisos"
      :rol="rol || usuario?.rol || ''"
      :guardando="guardando"
      @close="modalAbierto = false"
      @save="guardar"
      @liquidar="liquidar"
    />
  </div>
</template>

<style scoped>
.panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.indicadores {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 0.75rem;
}

.indicador {
  padding: 0.75rem 0.9rem;
  border-top: 3px solid var(--borde);
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.indicador--alerta {
  border-top-color: var(--peligro);
}

.indicador__titulo {
  font-size: 0.68rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--apagado);
}

.indicador__valor {
  font-size: 1.65rem;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}

.indicador__valor--rojo {
  color: #f87171;
}

.indicador small {
  font-size: 0.68rem;
  color: #64748b;
}

.filtros {
  padding: 0.9rem;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.filtros__grupo {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 0.7rem;
}

.filtros__campo--busqueda {
  grid-column: span 2;
  min-width: 220px;
}

.filtros__acciones {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.6rem;
}

.conmutador {
  display: flex;
  margin-left: auto;
  border: 1px solid var(--borde);
  border-radius: 8px;
  overflow: hidden;
}

.conmutador__btn {
  background: transparent;
  border: none;
  color: var(--apagado);
  padding: 0.5rem 0.9rem;
  font-size: 0.8125rem;
  font-weight: 600;
}

.conmutador__btn--activo {
  background-color: var(--acento);
  color: #fff;
}

.masiva {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  flex-wrap: wrap;
  padding: 0.7rem 0.9rem;
  border-color: rgb(37 99 235 / 0.5);
  font-size: 0.8125rem;
}

.masiva select {
  max-width: 280px;
}

.paginas {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.paginas__texto {
  font-size: 0.8125rem;
  color: var(--apagado);
}

@media (max-width: 700px) {
  .filtros__campo--busqueda {
    grid-column: auto;
  }
  .conmutador {
    margin-left: 0;
    width: 100%;
  }
  .conmutador__btn {
    flex: 1;
  }
}
</style>
