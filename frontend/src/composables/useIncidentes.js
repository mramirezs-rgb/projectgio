import { ref, computed } from 'vue';
import { getIncidentes, getTecnicos, getEvaluadores, getCentrales } from '../services/api';

export function useIncidentes() {
  
  const cargando = ref(false);
  const incidentes = ref([]);
  const tecnicos = ref([]);
  const evaluadores = ref([]);
  const centrales = ref([]);

  const filtros = ref({
    folio: '',
    area_operativa: '',
    central: '',
    tecnico: '',
    evaluador: '',
    estatus: ''
  });

  const kpiTotal = computed(() => Array.isArray(incidentes.value) ? incidentes.value.length : 0);
  const kpiDilacion = computed(() => {
    if (!Array.isArray(incidentes.value)) return 0;
    return incidentes.value.filter(i => (Number(i.dilacion_dias) || Number(i.dilacion) || 0) > 5).length;
  });

  const normalizarEstatus = (inc) => {
    if (!inc) return 'Abierto';
    
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

  // 1. CARGA DE CATÁLOGOS (Incluye Evaluadores PI)
  const cargarCatalogos = async () => {
    try {
      const [resTec, resEval, resCen] = await Promise.all([
        getTecnicos().catch(err => { console.warn('Error getTecnicos:', err); return null; }),
        getEvaluadores().catch(err => { console.warn('Error getEvaluadores:', err); return null; }),
        getCentrales().catch(err => { console.warn('Error getCentrales:', err); return null; })
      ]);

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

      if (resEval) {
        const rawData = resEval.data?.results || resEval.data || resEval || [];
        const lista = Array.isArray(rawData) ? rawData : [];
        evaluadores.value = lista.map(u => ({
          id: u.id || u.pk || u.user_id,
          nombre: `${u.first_name || ''} ${u.last_name || ''}`.trim() || u.username || u.nombre || `Evaluador ${u.id}`
        })).filter(e => e.id !== undefined);
      } else {
        evaluadores.value = [];
      }

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

  // 2. CARGA DE INCIDENTES CON ENRIQUECIMIENTO DE TÉCNICOS Y EVALUADORES
  const cargarIncidentes = async () => {
    cargando.value = true;
    try {
      const params = {};
      if (filtros.value.folio) params.search = filtros.value.folio;
      if (filtros.value.area_operativa) params.area_operativa = filtros.value.area_operativa;
      if (filtros.value.central) params.central = filtros.value.central;
      if (filtros.value.tecnico) params.tecnico = filtros.value.tecnico; 
      if (filtros.value.evaluador) params.evaluador = filtros.value.evaluador; 
      if (filtros.value.estatus) params.estatus_io = filtros.value.estatus;

      const res = await getIncidentes(params);
      const rawData = res?.data?.results || res?.data || res || [];
      const lista = Array.isArray(rawData) ? rawData : [];

      incidentes.value = lista.map(inc => {
        let nombreTecnico = inc.tecnico_nombre;
        if (!nombreTecnico) {
          if (typeof inc.tecnico === 'object' && inc.tecnico) {
            nombreTecnico = inc.tecnico.first_name || inc.tecnico.nombre || inc.tecnico.username;
          } else if (inc.tecnico) {
            const match = tecnicos.value.find(t => Number(t.id) === Number(inc.tecnico));
            if (match) nombreTecnico = match.nombre;
          }
        }

        let nombreEvaluador = inc.evaluador_nombre;
        if (!nombreEvaluador) {
          if (typeof inc.evaluador === 'object' && inc.evaluador) {
            nombreEvaluador = inc.evaluador.first_name || inc.evaluador.nombre || inc.evaluador.username;
          } else if (inc.evaluador) {
            const match = evaluadores.value.find(e => Number(e.id) === Number(inc.evaluador));
            if (match) nombreEvaluador = match.nombre;
          }
        }

        return {
          ...inc,
          tecnico_nombre: nombreTecnico || 'Sin Asignar',
          evaluador_nombre: nombreEvaluador || 'Sin Asignar'
        };
      });

    } catch (error) {
      console.error('Error al consultar incidentes:', error);
      incidentes.value = [];
    } finally {
      cargando.value = false;
    }
  };

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
      
      col.items.push(inc);
      col.cards.push(inc);
      col.incidentes.push(inc);
    });

    return Object.values(mapa);
  });

  return {
    cargando, incidentes, tecnicos, evaluadores, centrales, filtros, areasDisponibles,
    kpiTotal, kpiDilacion, columnasKanban,
    cargarCatalogos, cargarIncidentes, normalizarEstatus
  };
}