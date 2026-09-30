<script setup>
import { ref, onMounted, computed } from 'vue';
import { createIncidente, updateIncidente } from '../services/api';
import { useIncidentes } from '../composables/useIncidentes';
import { useAuth } from '../composables/useAuth';
import KanbanBoard from '../components/KanbanBoard.vue';
import TablaIncidentes from '../components/TablaIncidentes.vue';
import IncidenteModal from '../components/IncidenteModal.vue';

const { usuario, cerrarSesion } = useAuth();
const esAdmin = computed(() => usuario.value?.rol === 'ADMIN' || usuario.value?.is_superuser);
const esTecnico = computed(() => usuario.value?.rol === 'TECNICO');

const vista = ref('kanban');
const mostrarFormulario = ref(false);
const editando = ref(false);

const formInicial = { 
  id: null, 
  folio: '', 
  empresa: '', 
  referencia: '', 
  tipo_servicio: '',
  area_operativa: '', 
  central: '', 
  tecnico: null, 
  estatus_io: 'ABIERTO',
  estatus_qp: 'DESCONOCIDO',
  dilacion_dias: 0, 
  dir_pta_a: '',
  ips: '',
  dslam: '',              
  red_secundaria: '',     
  desc_f1: '',            
  desc_cod4: '',          
  desc_carls: '',         
  desc_cod5: '',          
  cve_liq: '',            
  desc_liq: '',           
  obs_usuario: ''
};

const formActual = ref({ ...formInicial });

const { 
  cargando, incidentes, tecnicos, centrales, filtros, areasDisponibles,
  kpiTotal, kpiDilacion, columnasKanban, cargarCatalogos, cargarIncidentes 
} = useIncidentes();

onMounted(async () => {
   if (esTecnico.value && usuario.value?.id) {
     filtros.value.tecnico = usuario.value.id;
  }
  await cargarCatalogos();
  await cargarIncidentes();
});

const abrirNuevo = () => {
  formActual.value = { ...formInicial };
  editando.value = false;
  mostrarFormulario.value = true;
};

const abrirEditar = (inc) => {
  let tecnicoId = null;
  if (inc.tecnico && typeof inc.tecnico === 'object') {
    tecnicoId = inc.tecnico.id;
  } else if (inc.tecnico) {
    tecnicoId = inc.tecnico;
  }

  formActual.value = { 
    ...formInicial, 
    ...inc,
    area_operativa: String(inc.area_operativa || inc.area || '').toUpperCase().trim(),
    dilacion_dias: inc.dilacion_dias || inc.dilacion || 0,
    tecnico: tecnicoId,
    dir_pta_a: inc.dir_pta_a || inc.direccion || '',
    ips: inc.ips || inc.ip_servicio || '',
    estatus_io: inc.estatus_io || 'ABIERTO',
    estatus_qp: inc.estatus_qp || inc.estado_enlace || 'DESCONOCIDO'
  };
  editando.value = true;
  mostrarFormulario.value = true;
};

const procesarGuardado = async (payload) => {
  try {
    let tecnicoAsignado = null;
    if (payload.tecnico && typeof payload.tecnico === 'object') {
      tecnicoAsignado = payload.tecnico.id;
    } else if (payload.tecnico) {
      tecnicoAsignado = parseInt(payload.tecnico, 10);
    }
    
    const datosEnvio = {
      folio: payload.folio,
      empresa: payload.empresa || '',
      referencia: payload.referencia || '',
      tipo_servicio: payload.tipo_servicio || '',
      area_operativa: String(payload.area_operativa || '').toUpperCase().trim(),
      central: payload.central || 'SIN CENTRAL',
      dilacion_dias: parseInt(payload.dilacion_dias, 10) || 0,
      dir_pta_a: payload.dir_pta_a || '',
      ips: payload.ips || '',
      red_secundaria: payload.red_secundaria || '',           
      dslam: payload.dslam || '',                             
      desc_f1: payload.desc_f1 || '',                         
      desc_cod4: payload.desc_cod4 || '',                     
      desc_carls: payload.desc_carls || '',                   
      desc_cod5: payload.desc_cod5 || '',                     
      cve_liq: payload.cve_liq || '',                         
      desc_liq: payload.desc_liq || '',                       
      estatus_io: payload.estatus_io || 'ABIERTO',
      estatus_qp: payload.estatus_qp || '',
      obs_usuario: payload.obs_usuario || '',
      tecnico: Number.isInteger(tecnicoAsignado) && tecnicoAsignado > 0 ? tecnicoAsignado : null
    };

    if (editando.value) {
      await updateIncidente(payload.id, datosEnvio);
    } else {
      await createIncidente(datosEnvio);
    }
    mostrarFormulario.value = false;
    await cargarIncidentes();
    alert('¡Registro guardado exitosamente!');
  } catch (error) {
    console.error('Error al guardar:', error.response?.data || error);
    const detalleError = error.response?.data ? JSON.stringify(error.response.data, null, 2) : error.message;
    alert(`No se pudo guardar. Verifica los datos.\nDetalle: ${detalleError}`);
  }
};

const exportarCSV = () => {
  if (incidentes.value.length === 0) {
    alert('No hay datos disponibles para exportar.');
    return;
  }
  const cabeceras = ['Folio', 'Empresa', 'Referencia', 'Tipo Servicio', 'Area Operativa', 'Central', 'Tecnico', 'Estatus IO', 'Estado Enlace', 'Dilacion Dias', 'Direccion', 'IP'];
  const filas = incidentes.value.map(inc => [
    `"${inc.folio || ''}"`,
    `"${inc.empresa || ''}"`,
    `"${inc.referencia || ''}"`,
    `"${inc.tipo_servicio || ''}"`,
    `"${inc.area_operativa || ''}"`,
    `"${inc.central || ''}"`,
    `"${inc.tecnico_nombre || inc.tecnico?.username || inc.tecnico || ''}"`,
    `"${inc.estatus_io || ''}"`,
    `"${inc.estatus_qp || ''}"`,
    inc.dilacion_dias || 0,
    `"${inc.dir_pta_a || ''}"`,
    `"${inc.ips || ''}"`
  ]);
  const contenidoCSV = 'data:text/csv;charset=utf-8,' + [cabeceras.join(','), ...filas.map(e => e.join(','))].join('\n');
  const encodedUri = encodeURI(contenidoCSV);
  const link = document.createElement('a');
  link.setAttribute('href', encodedUri);
  link.setAttribute('download', `Reporte_Incidencias_GIO_${new Date().toISOString().slice(0,10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};
let timerBusqueda = null;

const onFolioInput = () => {
  clearTimeout(timerBusqueda);
  timerBusqueda = setTimeout(() => {
    cargarIncidentes();
  }, 350); // Ejecuta la búsqueda 350ms después de que el usuario deja de escribir
};

const limpiarFolio = () => {
  filtros.value.folio = '';
  cargarIncidentes();
};
</script>

<template>
  <div class="gio-app">
    <header class="top-bar">
      <div class="brand-group">
        <div class="logo-badge">GIO</div>
        <h1 class="system-title">SISTEMA DE GESTIÓN DE INCIDENCIAS</h1>
        
        <!-- Indicador de Usuario y Rol -->
        <div class="user-chip" v-if="usuario">
          <span>👤 {{ usuario.nombre || usuario.username }}</span>
          <span class="role-tag">{{ usuario.rol || 'ADMIN' }}</span>
        </div>
      </div>

      <div class="header-right">
        <!-- Oculto para Rol TÉCNICO -->
        <button v-if="!esTecnico" @click="abrirNuevo" class="btn btn-primary-gio">
          + Nuevo Folio
        </button>
        
        <!-- Exclusivo para Rol ADMIN -->
        <button v-if="esAdmin" @click="exportarCSV" class="btn btn-primary-gio">
          - Exportar Reporte
        </button>

      </div>
    </header>

    <main class="dashboard-body">
      <section class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-header"><span class="kpi-title">TOTAL FOLIOS</span></div>
          <div class="kpi-value">{{ kpiTotal }}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-header">
            <span class="kpi-title">DILACIÓN > 5 DÍAS</span>
            <span class="kpi-badge badge-red-text">ALERTA</span>
          </div>
          <div class="kpi-value red-text">{{ kpiDilacion }}</div>
        </div>
      </section>

            <!-- BARRA UNIFICADA DE FILTROS -->
      <section class="filter-bar">
        <div class="filters-left">
          <span class="filter-label">Buscar:</span>
          
          <!-- NUEVA BARRA DE BÚSQUEDA POR FOLIO -->
          <div class="search-box">
            <span class="search-icon"></span>
            <input 
              v-model="filtros.folio" 
              @input="onFolioInput"
              @keyup.enter="cargarIncidentes"
              type="text" 
              placeholder="Folio (ej. 12578004)..." 
              class="filter-input"
            />
            <button 
              v-if="filtros.folio" 
              @click="limpiarFolio" 
              class="btn-clear-folio" 
              type="button"
            >
              ✕
            </button>
          </div>

          <span class="filter-label ms-2">Filtrar:</span>

          <select v-model="filtros.area_operativa" @change="cargarIncidentes" class="filter-select">
            <option value="">Área: Todas</option>
            <option v-for="area in areasDisponibles" :key="area" :value="area">{{ area }}</option>
          </select>

          <select v-model="filtros.central" @change="cargarIncidentes" class="filter-select">
            <option value="">COPE: Todos</option>
            <option v-for="c in centrales" :key="c.id" :value="c.nombre">{{ c.nombre }}</option>
          </select>

          <select v-if="!esTecnico" v-model="filtros.tecnico" @change="cargarIncidentes" class="filter-select">
            <option value="">Técnico: Todos</option>
            <option v-for="t in tecnicos" :key="t.id" :value="t.id">{{ t.nombre }}</option>
          </select>

          <select v-model="filtros.estatus" @change="cargarIncidentes" class="filter-select">
            <option value="">Estado: Todos</option>
            <option value="ABIERTO">Abierto</option>
            <option value="EN PROCESO">En Atención</option>
            <option value="PENDIENTE">Pendiente</option>
            <option value="RESUELTO">Resuelto</option>
            <option value="CERRADO">Cerrado</option>
          </select>
        </div>
        
        <div class="view-toggle">
          <button @click="vista = 'tabla'" :class="['toggle-btn', { active: vista === 'tabla' }]">Tabla</button>
          <button @click="vista = 'kanban'" :class="['toggle-btn', { active: vista === 'kanban' }]">Kanban</button>
        </div>
      </section>

      <section v-if="cargando" class="loading-state">
         
      </section>

      <KanbanBoard 
        v-else-if="vista === 'kanban'" 
        :columnas="columnasKanban" 
        @editar="abrirEditar"
      />

      <TablaIncidentes 
        v-else 
        :incidentes="incidentes" 
        @editar="abrirEditar"
      />
    </main>

    <!-- Pasa tecnicos y centrales al Modal -->
    <IncidenteModal 
      v-if="mostrarFormulario"
      :centrales="centrales" 
      :tecnicos="tecnicos"
      :areas="areasDisponibles"
      :editando="editando" 
      :modelo="formActual" 
      @close="mostrarFormulario = false" 
      @save="procesarGuardado" 
    />
  </div>
</template>

<style scoped>
/* Estilos adicionales sugeridos para la cabecera de autenticación */
.dashboard-container {
  width: 100%;
  max-width: 100%;
  padding: 1rem;
  box-sizing: border-box;
}

/* Header flexible */
.dashboard-header {
  display: flex;
  flex-wrap: wrap; /* Permite que los elementos bajen de línea en móvil */
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  width: 100%;
}

/* Grid de métricas / tarjetas KPI */
.metrics-grid, .stats-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); /* Adaptable */
  gap: 1rem;
  width: 100%;
}

/* Barra de filtros y búsquedas */
.filters-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  width: 100%;
}

.filters-bar input,
.filters-bar select {
  flex: 1 1 200px;
  min-width: 0; 
}

.kanban-wrapper, .tabla-wrapper {
  width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
.user-chip {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background-color: #1e293b;
  padding: 0.3rem 0.8rem;
  border-radius: 20px;
  border: 1px solid #334155;
  font-size: 0.85rem;
  color: #e2e8f0;
  margin-left: 1rem;
}
.role-tag {
  background-color: #2563eb;
  color: #ffffff;
  font-size: 0.7rem;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  font-weight: 700;
}
.btn-logout {
  background-color: #ef4444;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
  transition: background-color 0.2s;
}
.btn-logout:hover {
  background-color: #dc2626;
}
.search-box {
  position: relative;
  display: flex;
  align-items: center;
}

.search-icon {
  position: absolute;
  left: 8px;
  font-size: 0.8rem;
  pointer-events: none;
  opacity: 0.6;
}

.filter-input {
  padding: 0.4rem 1.8rem 0.4rem 1.8rem;
  border-radius: 6px;
  border: 1px solid #334155;
  background-color: #1e293b;
  color: #f8fafc;
  font-size: 0.85rem;
  outline: none;
  width: 180px;
  transition: border-color 0.2s, width 0.2s;
}

.filter-input:focus {
  border-color: #2563eb;
  width: 220px;
}

.btn-clear-folio {
  position: absolute;
  right: 6px;
  background: none;
  border: none;
  color: #94a3b8;
  cursor: pointer;
  font-size: 0.75rem;
  padding: 2px 4px;
}

.btn-clear-folio:hover {
  color: #f8fafc;
}

.ms-2 {
  margin-left: 0.75rem;
}

@media (max-width: 768px) {
  .header-container,
  .top-bar,
  .dashboard-header {
    flex-direction: column;
    align-items: stretch;
    gap: 0.75rem;
    padding: 0.75rem;
  }

  .header-title-group {
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: center;
  }

  .user-info-actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    gap: 0.5rem;
  }

  .btn-nuevo-folio,
  .btn-primary {
    width: 100%;
    text-align: center;
    justify-content: center;
  }

  .kpi-container,
  .stats-grid {
    grid-template-columns: 1fr;
    gap: 0.75rem;
  }

  .filtros-container,
  .search-filter-bar {
    flex-direction: column;
    align-items: stretch;
    gap: 0.75rem;
  }

  .filtros-group {
    flex-direction: column;
    width: 100%;
    gap: 0.5rem;
  }

  .filtros-container input,
  .filtros-container select {
    width: 100% !important;
    max-width: 100%;
  }

  .kanban-board {
    display: flex;
    overflow-x: auto;
    scroll-snap-type: x mandatory;
    gap: 1rem;
    padding-bottom: 1rem;
  }

  .kanban-column {
    min-width: 85vw;
    scroll-snap-align: start;
  }
}
</style>