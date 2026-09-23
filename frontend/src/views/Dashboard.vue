<script setup>
import { ref, onMounted } from 'vue';
import { createIncidente, updateIncidente } from '../services/api';
import { useIncidentes } from '../composables/useIncidentes';
import KanbanBoard from '../components/KanbanBoard.vue';
import TablaIncidentes from '../components/TablaIncidentes.vue';
import IncidenteModal from '../components/IncidenteModal.vue';

const vista = ref('kanban');
const mostrarFormulario = ref(false);
const editando = ref(false);

const formInicial = { 
  id: null, folio: '', empresa: '', referencia: '', tipo_servicio: '',
  area_operativa: '', central: null, tecnico_asignado: null, estatus_io: 'ABIERTO',
  dilacion_dias: 0, 
  dir_pta_a: '',      // 👈 Nombre real en Django (Dirección Sitio / Enlace)
  ips: '',            // 👈 Nombre real en Django (IP de Servicio)
  direccion: '',      // Alias de compatibilidad
  ip_servicio: '',    // Alias de compatibilidad
  dslam: '', red_secundaria: '', estado_enlace: 'DESCONOCIDO', 
  desc_f1: '', desc_cod4: '', desc_carls: '', desc_cod5: '', 
  cve_liq: '', desc_liq: '', obs_usuario: ''
};

const formActual = ref({ ...formInicial });

const { 
  cargando, incidentes, tecnicos, centrales, filtros, areasDisponibles,
  kpiTotal, kpiDilacion, columnasKanban, cargarCatalogos, cargarIncidentes 
} = useIncidentes();

onMounted(() => {
  cargarCatalogos();
  cargarIncidentes();
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
    // Mapeo unificado para estatus_io
    estatus_io: inc.estatus_io || inc.estatus || inc.estado || 'ABIERTO',
    area_operativa: inc.area_operativa || inc.area || '',
    dilacion_dias: inc.dilacion_dias || inc.dilacion || 0,
    tecnico_asignado: inc.tecnico_asignado || inc.tecnico_nombre || null,
    dir_pta_a: inc.dir_pta_a || inc.direccion || '',
    ips: inc.ips || inc.ip_servicio || '',
    direccion: inc.dir_pta_a || inc.direccion || '',
    ip_servicio: inc.ips || inc.ip_servicio || ''
  };
  editando.value = true;
  mostrarFormulario.value = true;
};

const procesarGuardado = async (payload) => {
  try {
    const datosEnvio = {
      ...payload,
      // Se garantiza el nombre exacto de la columna en Django
      estatus_io: payload.estatus_io || payload.estatus || 'ABIERTO',
      dir_pta_a: payload.dir_pta_a || payload.direccion || '',
      ips: payload.ips || payload.ip_servicio || '',
      estatus_qp: inc.estatus_qp || inc.estado_enlace || 'DESCONOCIDO'
    };

    if (editando.value) {
      await updateIncidente(datosEnvio.id, datosEnvio);
    } else {
      await createIncidente(datosEnvio);
    }
    mostrarFormulario.value = false;
    cargarIncidentes();
    alert('¡Registro guardado exitosamente!');
  } catch (error) {
    console.error('Error en el servidor:', error.response?.data || error);
    alert('Error al guardar en la base de datos. Verifica la respuesta del servidor.');
  }
};

const exportarCSV = () => {
  if (incidentes.value.length === 0) {
    alert('No hay datos disponibles para exportar.');
    return;
  }

  const cabeceras = ['Folio', 'Empresa', 'Referencia', 'Tipo Servicio', 'Area Operativa', 'Central', 'Tecnico', 'Estatus', 'Dilacion Dias', 'Dirección Sitio', 'IP Servicio'];
  
  const filas = incidentes.value.map(inc => [
    `"${inc.folio || ''}"`,
    `"${inc.empresa || ''}"`,
    `"${inc.referencia || ''}"`,
    `"${inc.tipo_servicio || ''}"`,
    `"${inc.area_operativa || ''}"`,
    `"${inc.central || ''}"`,
    `"${inc.tecnico_asignado || ''}"`,
    `"${inc.estatus_io || ''}"`,
    inc.dilacion_dias || 0,
    `"${inc.dir_pta_a || inc.direccion || ''}"`,
    `"${inc.ips || inc.ip_servicio || ''}"`
  ]);

  const contenidoCSV = 'data:text/csv;charset=utf-8,' 
    + [cabeceras.join(','), ...filas.map(e => e.join(','))].join('\n');

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
      </div>

      <div class="header-right">
        <button @click="abrirNuevo" class="btn btn-primary-gio">+ Nuevo Folio</button>
        <button @click="exportarCSV" class="btn btn-primary-gio">- Exportar Reporte</button>
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
          
          <!-- Filtro Área Operativa -->
          <select v-model="filtros.area_operativa" @change="cargarIncidentes" class="filter-select">
            <option value="">Área: Todas</option>
            <option v-for="area in areasDisponibles" :key="area" :value="area">{{ area }}</option>
          </select>

          <!-- Filtro COPE / Central -->
          <select v-model="filtros.central" @change="cargarIncidentes" class="filter-select">
            <option value="">COPE: Todos</option>
            <option v-for="c in centrales" :key="c.id" :value="c.nombre">{{ c.nombre }}</option>
          </select>

          <!-- Filtro Técnico -->
          <select v-model="filtros.tecnico" @change="cargarIncidentes" class="filter-select">
            <option value="">Técnico: Todos</option>
            <option v-for="t in tecnicos" :key="t.id" :value="t.nombre">{{ t.nombre }}</option>
          </select>

          <!-- Filtro Estatus -->
          <select v-model="filtros.estatus" @change="cargarIncidentes" class="filter-select">
            <option value="">Estado: Todos</option>
            <option value="ABIERTO">Abierto</option>
            <option value="EN PROCESO">En Proceso</option>
            <option value="PENDIENTE">Pendiente</option>
            <option value="ATENDIDO">Atendido</option>
            <option value="CERRADO">Cerrado</option>
          </select>
        </div>

        <div class="view-toggle">
          <button @click="vista = 'tabla'" :class="['toggle-btn', { active: vista === 'tabla' }]">Tabla</button>
          <button @click="vista = 'kanban'" :class="['toggle-btn', { active: vista === 'kanban' }]">Kanban</button>
        </div>
      </section>

      <section v-if="cargando" class="loading-state">Cargando datos...</section>

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

    <IncidenteModal 
      v-if="mostrarFormulario"
      :centrales="centrales" 
      :editando="editando" 
      :modelo="formActual" 
      :tecnicos="tecnicos" 
      @close="mostrarFormulario = false" 
      @save="procesarGuardado" 
    />
  </div>
</template>