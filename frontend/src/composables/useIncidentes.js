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

const FOLIOS_POR_COLUMNA = 50

export const TRANSICIONES = {
  [ESTATUS.PENDIENTE]: [ESTATUS.ASIGNADO, ESTATUS.EN_PROCESO],
  [ESTATUS.ASIGNADO]: [ESTATUS.EN_PROCESO, ESTATUS.PENDIENTE],
  [ESTATUS.EN_PROCESO]: [ESTATUS.ASIGNADO, ESTATUS.LIQUIDADO],
  [ESTATUS.LIQUIDADO]: [ESTATUS.EN_PROCESO, ESTATUS.PENDIENTE],
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
  // Catálogos completos: los usa el formulario del folio, que debe poder mostrar cualquier responsable.
  const tecnicos = ref([])
  const evaluadores = ref([])
  const centrales = ref([])
  const areas = ref([])
  const metricas = ref(null)

  // Catálogos de los filtros del tablero: se acotan a la zona elegida.
  const tecnicosZona = ref([])
  const evaluadoresZona = ref([])
  const centralesZona = ref([])

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

  // La tabla pagina toda la lista (20 por página). El kanban pagina cada columna por separado:
  // si compartiera la página de la tabla, un folio antiguo que cambia de estatus quedaría fuera
  // de la columna aunque las métricas sí lo cuenten.
  const modo = ref('kanban')
  const paginacion = reactive({ pagina: 1, tamano: 20, total: 0 })
  const kanban = reactive({})

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
    await actualizarZona()
  }

  const areaDeCentral = (nombre) =>
    centrales.value.find((central) => central.nombre === nombre)?.area || ''

  // La zona sale del área elegida o, si solo hay COPE/central, del área a la que pertenece.
  // Las centrales se acotan solo por el área explícita: así puede cambiarse de central.
  const actualizarZona = async () => {
    const areaPersonal = filtros.area_operativa || areaDeCentral(filtros.central)
    const [resTecnicos, resEvaluadores, resCentrales] = await Promise.allSettled([
      areaPersonal ? getTecnicos({ area: areaPersonal }) : Promise.resolve(null),
      areaPersonal ? getEvaluadores({ area: areaPersonal }) : Promise.resolve(null),
      filtros.area_operativa
        ? getCentrales({ area: filtros.area_operativa })
        : Promise.resolve(null),
    ])
    tecnicosZona.value = resTecnicos.value ? listaDe(resTecnicos.value) : tecnicos.value
    evaluadoresZona.value = resEvaluadores.value
      ? listaDe(resEvaluadores.value)
      : evaluadores.value
    centralesZona.value = resCentrales.value ? listaDe(resCentrales.value) : centrales.value

    // Si la selección ya no pertenece a la zona, se limpia para no filtrar por algo invisible.
    if (filtros.central && !centralesZona.value.some((c) => c.nombre === filtros.central)) {
      filtros.central = ''
    }
    if (
      filtros.tecnico &&
      !tecnicosZona.value.some((t) => String(t.id) === String(filtros.tecnico))
    ) {
      filtros.tecnico = ''
    }
    if (
      filtros.evaluador &&
      !evaluadoresZona.value.some((e) => String(e.id) === String(filtros.evaluador))
    ) {
      filtros.evaluador = ''
    }
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

  const cargarColumna = async (estatus, pagina) => {
    const { data } = await getIncidentes({
      ...parametros(),
      estatus,
      page: pagina,
      page_size: FOLIOS_POR_COLUMNA,
    })
    const lista = Array.isArray(data) ? data : data.results || []
    return { lista, total: Array.isArray(data) ? lista.length : data.count || 0 }
  }

  const cargarKanban = async () => {
    const estatus = filtros.estatus ? [filtros.estatus] : COLUMNAS_KANBAN.map((c) => c.id)
    const columnas = await Promise.all(estatus.map((valor) => cargarColumna(valor, 1)))
    for (const clave of Object.keys(kanban)) delete kanban[clave]
    estatus.forEach((valor, indice) => {
      kanban[valor] = { pagina: 1, total: columnas[indice].total }
    })
    incidentes.value = columnas.flatMap((columna) => columna.lista)
    paginacion.total = columnas.reduce((suma, columna) => suma + columna.total, 0)
  }

  const cargarMasColumna = async (estatus) => {
    const estado = kanban[estatus]
    if (!estado) return
    const { lista, total } = await cargarColumna(estatus, estado.pagina + 1)
    const vistos = new Set(incidentes.value.map((item) => item.id))
    incidentes.value = [...incidentes.value, ...lista.filter((item) => !vistos.has(item.id))]
    estado.pagina += 1
    estado.total = total
  }

  const cargarIncidentes = async ({ conMetricas = true } = {}) => {
    cargando.value = true
    error.value = null
    try {
      if (modo.value === 'kanban') {
        await cargarKanban()
      } else {
        const { data } = await getIncidentes(parametros())
        incidentes.value = Array.isArray(data) ? data : data.results || []
        paginacion.total = Array.isArray(data) ? incidentes.value.length : data.count || 0
      }
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
    await actualizarZona()
    await aplicarFiltros()
  }

  const reemplazarIncidente = (actualizado) => {
    const indice = incidentes.value.findIndex((item) => item.id === actualizado.id)
    if (indice === -1) return
    const anterior = incidentes.value[indice].estatus
    if (actualizado.estatus && actualizado.estatus !== anterior) {
      if (kanban[anterior]) kanban[anterior].total = Math.max(0, kanban[anterior].total - 1)
      if (kanban[actualizado.estatus]) kanban[actualizado.estatus].total += 1
    }
    incidentes.value.splice(indice, 1, { ...incidentes.value[indice], ...actualizado })
  }

  const columnasKanban = computed(() =>
    COLUMNAS_KANBAN.map((columna) => {
      const items = incidentes.value.filter((item) => item.estatus === columna.id)
      const total = Math.max(kanban[columna.id]?.total ?? 0, items.length)
      return { ...columna, items, total, hayMas: items.length < total }
    }),
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
    tecnicosZona,
    evaluadoresZona,
    centralesZona,
    metricas,
    filtros,
    modo,
    paginacion,
    totalPaginas,
    columnasKanban,
    kpis,
    cargarCatalogos,
    actualizarZona,
    cargarIncidentes,
    cargarMasColumna,
    cargarMetricas,
    aplicarFiltros,
    aplicarFiltrosConRetardo,
    limpiarFiltros,
    irAPagina,
    reemplazarIncidente,
  }
}
