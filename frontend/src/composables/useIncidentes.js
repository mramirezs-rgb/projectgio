import { computed, reactive, ref } from 'vue'
import {
  getAreas,
  getCentrales,
  getEvaluadores,
  getIncidentes,
  getMetricas,
  getTecnicos,
} from '../services/api.js'

export const ESTATUS = {
  PENDIENTE: 'PENDIENTE',
  ASIGNADO: 'ASIGNADO',
  EN_PROCESO: 'EN_PROCESO',
  LIQUIDADO: 'LIQUIDADO',
}

export const COLUMNAS_KANBAN = [
  { id: ESTATUS.PENDIENTE, titulo: 'Pendiente', color: '#f97316' },
  { id: ESTATUS.ASIGNADO, titulo: 'Asignado', color: '#3b82f6' },
  { id: ESTATUS.EN_PROCESO, titulo: 'En proceso', color: '#eab308' },
  { id: ESTATUS.LIQUIDADO, titulo: 'Liquidado', color: '#10b981' },
]

export const TRANSICIONES = {
  [ESTATUS.PENDIENTE]: [ESTATUS.ASIGNADO, ESTATUS.EN_PROCESO],
  [ESTATUS.ASIGNADO]: [ESTATUS.EN_PROCESO, ESTATUS.PENDIENTE],
  [ESTATUS.EN_PROCESO]: [ESTATUS.ASIGNADO, ESTATUS.LIQUIDADO],
  [ESTATUS.LIQUIDADO]: [ESTATUS.EN_PROCESO],
}

export const etiquetaEstatus = (valor) =>
  COLUMNAS_KANBAN.find((columna) => columna.id === valor)?.titulo || valor || '—'

const listaDe = (respuesta) => {
  const datos = respuesta?.data
  if (Array.isArray(datos)) return datos
  if (Array.isArray(datos?.results)) return datos.results
  return []
}

export function useIncidentes() {
  const cargando = ref(false)
  const error = ref(null)
  const incidentes = ref([])
  const tecnicos = ref([])
  const evaluadores = ref([])
  const centrales = ref([])
  const areas = ref([])
  const metricas = ref(null)

  const filtros = reactive({
    search: '',
    estatus: '',
    area_operativa: '',
    central: '',
    tecnico: '',
    evaluador: '',
    estado_enlace: '',
    dilacion_min: '',
    ordering: '-fecha_apertura',
  })

  const paginacion = reactive({ pagina: 1, tamano: 50, total: 0 })

  const totalPaginas = computed(() =>
    Math.max(1, Math.ceil((paginacion.total || 0) / paginacion.tamano)),
  )

  const parametros = () => {
    const params = { page: paginacion.pagina, page_size: paginacion.tamano }
    for (const [clave, valor] of Object.entries(filtros)) {
      if (valor !== '' && valor !== null && valor !== undefined) params[clave] = valor
    }
    return params
  }

  const cargarCatalogos = async () => {
    const [resTecnicos, resEvaluadores, resCentrales, resAreas] = await Promise.allSettled([
      getTecnicos(),
      getEvaluadores(),
      getCentrales(),
      getAreas(),
    ])
    tecnicos.value = resTecnicos.status === 'fulfilled' ? listaDe(resTecnicos.value) : []
    evaluadores.value = resEvaluadores.status === 'fulfilled' ? listaDe(resEvaluadores.value) : []
    centrales.value = resCentrales.status === 'fulfilled' ? listaDe(resCentrales.value) : []
    areas.value = resAreas.status === 'fulfilled' ? listaDe(resAreas.value) : []
  }

  const cargarMetricas = async () => {
    const params = { ...parametros() }
    delete params.page
    delete params.page_size
    delete params.ordering
    try {
      const { data } = await getMetricas(params)
      metricas.value = data
    } catch {
      metricas.value = null
    }
  }

  const cargarIncidentes = async ({ conMetricas = true } = {}) => {
    cargando.value = true
    error.value = null
    try {
      const { data } = await getIncidentes(parametros())
      incidentes.value = Array.isArray(data) ? data : data.results || []
      paginacion.total = Array.isArray(data) ? incidentes.value.length : data.count || 0
      if (conMetricas) await cargarMetricas()
    } catch (problema) {
      incidentes.value = []
      paginacion.total = 0
      error.value = problema
      throw problema
    } finally {
      cargando.value = false
    }
  }

  const irAPagina = async (pagina) => {
    const destino = Math.min(Math.max(1, pagina), totalPaginas.value)
    if (destino === paginacion.pagina) return
    paginacion.pagina = destino
    await cargarIncidentes({ conMetricas: false })
  }

  const aplicarFiltros = async () => {
    paginacion.pagina = 1
    await cargarIncidentes()
  }

  let temporizador = null
  const aplicarFiltrosConRetardo = (ms = 350) => {
    clearTimeout(temporizador)
    temporizador = setTimeout(() => {
      aplicarFiltros()
    }, ms)
  }

  const limpiarFiltros = async () => {
    Object.assign(filtros, {
      search: '',
      estatus: '',
      area_operativa: '',
      central: '',
      tecnico: '',
      evaluador: '',
      estado_enlace: '',
      dilacion_min: '',
      ordering: '-fecha_apertura',
    })
    await aplicarFiltros()
  }

  const reemplazarIncidente = (actualizado) => {
    const indice = incidentes.value.findIndex((item) => item.id === actualizado.id)
    if (indice === -1) return
    incidentes.value.splice(indice, 1, { ...incidentes.value[indice], ...actualizado })
  }

  const columnasKanban = computed(() =>
    COLUMNAS_KANBAN.map((columna) => ({
      ...columna,
      items: incidentes.value.filter((item) => item.estatus === columna.id),
    })),
  )

  const kpis = computed(() => {
    const fuente = metricas.value
    if (fuente) return fuente
    const lista = incidentes.value
    return {
      total: paginacion.total || lista.length,
      pendientes: lista.filter((i) => i.estatus === ESTATUS.PENDIENTE).length,
      asignados: lista.filter((i) => i.estatus === ESTATUS.ASIGNADO).length,
      en_proceso: lista.filter((i) => i.estatus === ESTATUS.EN_PROCESO).length,
      liquidados: lista.filter((i) => i.estatus === ESTATUS.LIQUIDADO).length,
      en_dilacion: lista.filter((i) => i.semaforo === 'alerta' || i.semaforo === 'critico').length,
      criticos: lista.filter((i) => i.semaforo === 'critico').length,
      mttr_horas_promedio: null,
      pendientes_exportar: null,
    }
  })

  return {
    cargando,
    error,
    incidentes,
    tecnicos,
    evaluadores,
    centrales,
    areas,
    metricas,
    filtros,
    paginacion,
    totalPaginas,
    columnasKanban,
    kpis,
    cargarCatalogos,
    cargarIncidentes,
    cargarMetricas,
    aplicarFiltros,
    aplicarFiltrosConRetardo,
    limpiarFiltros,
    irAPagina,
    reemplazarIncidente,
  }
}
