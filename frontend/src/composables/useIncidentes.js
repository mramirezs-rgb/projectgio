import { ref, computed } from 'vue';
import { getIncidentes, getTecnicos, getCentrales } from '../services/api';

export function useIncidentes() {
  const cargando = ref(false);
  const incidentes = ref([]);
  const tecnicos = ref([]);
  const centrales = ref([]);
  
  const filtros = ref({
    tecnico: '',
    central: '',
    estatus: ''
  });

  const kpiTotal = computed(() => incidentes.value.length);
  const kpiDilacion = computed(() => 
    incidentes.value.filter(i => (i.dilacion_dias || i.dilacion || 0) > 5).length
  );

  const cargarCatalogos = async () => {
    try {
      const [resTec, resCen] = await Promise.all([getTecnicos(), getCentrales()]);
      tecnicos.value = resTec.data.results || resTec.data;
      centrales.value = resCen.data.results || resCen.data;
    } catch (error) {
      console.error("Error cargando catálogos:", error);
    }
  };

  const cargarIncidentes = async () => {
    cargando.value = true;
    try {
      const paramsLimpios = {};
      if (filtros.value.tecnico) paramsLimpios.tecnico_asignado = filtros.value.tecnico;
      if (filtros.value.central) paramsLimpios.central = filtros.value.central;
      if (filtros.value.estatus) paramsLimpios.estatus_io = filtros.value.estatus;

      const res = await getIncidentes(paramsLimpios);
      const data = res.data;
      incidentes.value = Array.isArray(data.results) ? data.results : (Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('Error al consultar incidentes:', error);
      incidentes.value = [];
    } finally {
      cargando.value = false;
    }
  };

  const columnasKanban = computed(() => {
    const estados = [
      { key: 'Abierto', label: 'Abierto', color: '#3b82f6', match: ['abierto', 'open', 'nuevo'] },
      { key: 'En Atención', label: 'En Atención', color: '#eab308', match: ['proceso', 'atencion', 'atención', 'asignado'] },
      { key: 'Pendiente', label: 'Pendiente', color: '#f97316', match: ['pendiente', 'hold', 'validar'] },
      { key: 'Resuelto', label: 'Resuelto', color: '#10b981', match: ['resuelto', 'atendido', 'solucionado'] },
      { key: 'Cerrado', label: 'Cerrado', color: '#64748b', match: ['cerrado', 'cancelado'] }
    ];

    return estados.map(col => {
      const items = incidentes.value.filter(inc => {
        const estatus = (inc.estatus_io || '').toLowerCase();
        return col.match.some(m => estatus.includes(m));
      });
      return { ...col, items };
    });
  });

  return {
    cargando, incidentes, tecnicos, centrales, filtros,
    kpiTotal, kpiDilacion, columnasKanban,
    cargarCatalogos, cargarIncidentes
  };
}