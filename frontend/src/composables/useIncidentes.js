import { ref, computed } from 'vue';
import { getIncidentes, getTecnicos, getCentrales } from '../services/api';

export function useIncidentes() {
  
  const cargando = ref(false);
  const incidentes = ref([]);
  const tecnicos = ref([]);
  const centrales = ref([]);

  const filtros = ref({
    folio: '',
    area_operativa: '',
    central: '',
    tecnico: '',
    estatus: ''
  });

  // KPI Seguros
  const kpiTotal = computed(() => Array.isArray(incidentes.value) ? incidentes.value.length : 0);
  const kpiDilacion = computed(() => {
    if (!Array.isArray(incidentes.value)) return 0;
    return incidentes.value.filter(i => (Number(i.dilacion_dias) || Number(i.dilacion) || 0) > 5).length;
  });

  const normalizarEstatus = (inc) => {
    if (!inc) return 'Abierto';
    
    // Normalizar a mayúsculas de forma segura
    const io = String(inc.estatus_io || inc.estatus || inc.estado || inc.status || '').trim().toUpperCase();
    const qp = String(inc.estatus_qp || inc.estado_enlace || '').trim().toUpperCase();

    if (['1', 'UP', 'OPERANDO', 'ATENDIDO', 'RESUELTO', 'SOLUCIONADO', 'OK'].includes(io) || ['1', 'UP', 'OPERANDO', 'ATENDIDO'].includes(qp)) {
      return 'Resuelto';
    }
    if (['0', 'DOWN', 'FALLA', 'EN PROCESO', 'PROCESO', 'ATENCION', 'EN ATENCION', 'ASIGNADO'].includes(io) || ['0', 'DOWN', 'FALLA', 'EN PROCESO'].includes(qp)) {
      return 'En Atención';
    }
    if (['PENDIENTE', 'ESPERA', 'HOLD', 'VALIDAR'].includes(io) || ['PENDIENTE', 'ESPERA'].includes(qp)) {
      return 'Pendiente';
    }
    if (['CERRADO', 'CANCELADO'].includes(io) || ['CERRADO'].includes(qp)) {
      return 'Cerrado';
    }

    return 'Abierto';
  };

  const areasDisponibles = computed(() => {
    if (!Array.isArray(incidentes.value)) return [];
    const areas = incidentes.value.map(i => i.area_operativa || i.area).filter(Boolean);
    return [...new Set(areas)];
  });

  // 1. CARGA DE CATÁLOGOS (Técnicos y Centrales) EN PARALELO Y PROTEGIDA
  const cargarCatalogos = async () => {
    try {
      // Usamos Promise.all pero capturamos errores individuales para que uno no rompa al otro
      const [resTec, resCen] = await Promise.all([
        getTecnicos().catch(err => { console.warn('Error getTecnicos:', err); return null; }),
        getCentrales().catch(err => { console.warn('Error getCentrales:', err); return null; })
      ]);

      // Procesar Técnicos (Como en tu BD vienen nulos, dependemos 100% de esta API)
      if (resTec) {
        const rawData = resTec.data?.results || resTec.data || resTec || [];
        const lista = Array.isArray(rawData) ? rawData : [];
        tecnicos.value = lista.map(u => ({
          id: u.id || u.pk || u.user_id,
          nombre: `${u.first_name || ''} ${u.last_name || ''}`.trim() || u.username || u.nombre || `Técnico ${u.id}`
        })).filter(t => t.id !== undefined);
      } else {
        tecnicos.value = [];
      }

      // Procesar Centrales
      if (resCen) {
        const rawData = resCen.data?.results || resCen.data || resCen || [];
        centrales.value = Array.isArray(rawData) ? rawData : [];
      } else {
        centrales.value = [];
      }
    } catch (error) {
      console.error("Error crítico en catálogos:", error);
    }
  };

  // 2. CARGA DE INCIDENTES PROTEGIDA
  const cargarIncidentes = async () => {
    cargando.value = true;
    try {
      const params = {};
      if (filtros.value.area_operativa) params.area_operativa = filtros.value.area_operativa;
      if (filtros.value.central) params.central = filtros.value.central;
      if (filtros.value.tecnico) params.tecnico_asignado = filtros.value.tecnico;
      if (filtros.value.estatus) params.estatus_io = filtros.value.estatus;

      const res = await getIncidentes(params);
      
      // Desenvolver la respuesta sin importar si el backend la pagina (results) o la envía directa
      const rawData = res?.data?.results || res?.data || res || [];
      incidentes.value = Array.isArray(rawData) ? rawData : [];
      
    } catch (error) {
      console.error('Error al consultar incidentes:', error);
      incidentes.value = [];
    } finally {
      cargando.value = false;
    }
  };

  // 3. KANBAN ROBUSTO CON TODAS LAS PROPIEDADES POSIBLES INYECTADAS
  const columnasKanban = computed(() => {
    const plantilla = [
      { id: 'Abierto', key: 'Abierto', titulo: 'Abierto', label: 'Abierto', color: '#3b82f6' },
      { id: 'En Atención', key: 'En Atención', titulo: 'En Atención', label: 'En Atención', color: '#eab308' },
      { id: 'Pendiente', key: 'Pendiente', titulo: 'Pendiente', label: 'Pendiente', color: '#f97316' },
      { id: 'Resuelto', key: 'Resuelto', titulo: 'Resuelto', label: 'Resuelto', color: '#10b981' },
      { id: 'Cerrado', key: 'Cerrado', titulo: 'Cerrado', label: 'Cerrado', color: '#64748b' }
    ];

    const mapa = {};
    plantilla.forEach(col => {
      mapa[col.id] = { ...col, items: [], cards: [], incidentes: [] };
    });

    const lista = Array.isArray(incidentes.value) ? incidentes.value : [];
    
    lista.forEach(inc => {
      const estatus = normalizarEstatus(inc);
      const col = mapa[estatus] || mapa['Abierto'];
      
      // Agregamos a todas las propiedades para evitar que el componente Kanban falle
      col.items.push(inc);
      col.cards.push(inc);
      col.incidentes.push(inc);
    });

    return Object.values(mapa);
  });

  return {
    cargando, incidentes, tecnicos, centrales, filtros, areasDisponibles,
    kpiTotal, kpiDilacion, columnasKanban,
    cargarCatalogos, cargarIncidentes, normalizarEstatus
  };
}