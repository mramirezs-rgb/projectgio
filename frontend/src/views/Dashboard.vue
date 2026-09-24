<script setup>
import { ref, onMounted, computed } from 'vue';
import { createIncidente, updateIncidente } from '../services/api';
import { useIncidentes } from '../composables/useIncidentes';
import { useAuth } from '../composables/useAuth'; // Agregado para roles
import KanbanBoard from '../components/KanbanBoard.vue';
import TablaIncidentes from '../components/TablaIncidentes.vue';
import IncidenteModal from '../components/IncidenteModal.vue';

// Autenticación y Roles
const { usuario, cerrarSesion } = useAuth();
const esAdmin = computed(() => usuario.value?.rol === 'ADMIN' || usuario.value?.is_superuser);
const esTecnico = computed(() => usuario.value?.rol === 'TECNICO');

const vista = ref('kanban');
const mostrarFormulario = ref(false);
const editando = ref(false);

// Estructura inicial alineada al models.py de Django
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
  estatus_qp: 'DESCONOCIDO', // Sustituye a estado_enlace
  dilacion_dias: 0, 
  dir_pta_a: '',             // Dirección
  ips: '',                   // IP de servicio
  obs_usuario: ''
};

const formActual = ref({ ...formInicial });

const { 
  cargando, incidentes, tecnicos, centrales, filtros, areasDisponibles,
  kpiTotal, kpiDilacion, columnasKanban, cargarCatalogos, cargarIncidentes 
} = useIncidentes();

onMounted(async () => {
  // COMENTA ESTAS LÍNEAS TEMPORALMENTE
  // if (esTecnico.value && usuario.value?.id) {
  //   filtros.value.tecnico = usuario.value.id;
  // }
  await cargarCatalogos();
  await cargarIncidentes();
});

const abrirNuevo = () => {
  formActual.value = { ...formInicial };
  editando.value = false;
  mostrarFormulario.value = true;
};

const abrirEditar = (inc) => {
  formActual.value = { 
    ...formInicial, 
    ...inc,
    // Mapeo seguro para editar
    area_operativa: inc.area_operativa || inc.area || '',
    dilacion_dias: inc.dilacion_dias || inc.dilacion || 0,
    tecnico: inc.tecnico?.id || inc.tecnico || null,
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
    // Sanitización exhaustiva para cumplir con rules de models.py de Django
    const tecnicoId = Number(payload.tecnico);
    const datosEnvio = {
      folio: payload.folio,
      empresa: payload.empresa || '',
      referencia: payload.referencia || '',
      tipo_servicio: payload.tipo_servicio || '',
      area_operativa: payload.area_operativa || '',
      central: payload.central || 'SIN CENTRAL', // Evitar nulos si no permite blank
      dilacion_dias: parseInt(payload.dilacion_dias, 10) || 0, // Forzar Integer
      dir_pta_a: payload.dir_pta_a || '',
      ips: payload.ips || '',
      estatus_io: payload.estatus_io || 'ABIERTO',
      estatus_qp: payload.estatus_qp || '',
      obs_usuario: payload.obs_usuario || '',
      tecnico: Number.isInteger(tecnicoId) && tecnicoId > 0 ? tecnicoId : null // Forzar ForeignKey
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
          <span class="filter-label">Filtrar:</span>
          
          <select v-model="filtros.area_operativa" @change="cargarIncidentes" class="filter-select">
            <option value="">Área: Todas</option>
            <option v-for="area in areasDisponibles" :key="area" :value="area">{{ area }}</option>
          </select>

          <select v-model="filtros.central" @change="cargarIncidentes" class="filter-select">
            <option value="">COPE: Todos</option>
            <option v-for="c in centrales" :key="c.id" :value="c.nombre">{{ c.nombre }}</option>
          </select>

          <!-- Filtro Técnico (Bloqueado/Oculto si es Técnico) -->
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
         Cargando datos...
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
      :editando="editando" 
      :modelo="formActual" 
      @close="mostrarFormulario = false" 
      @save="procesarGuardado" 
    />
  </div>
</template>

<style scoped>
/* Estilos adicionales sugeridos para la cabecera de autenticación */
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
/* Asegúrate de mantener el resto de tus estilos habituales debajo de esto */
</style>