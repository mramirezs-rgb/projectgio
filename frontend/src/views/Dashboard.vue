<script setup>
import { ref, onMounted } from 'vue';
import { createIncidente, updateIncidente } from '../services/api';
import { useIncidentes } from '../composables/useIncidentes';
import { useAuth } from '../composables/useAuth';
import KanbanBoard from '../components/KanbanBoard.vue';
import TablaIncidentes from '../components/TablaIncidentes.vue';
import IncidenteModal from '../components/IncidenteModal.vue';
import '../assets/dashboardstyle.css'
import { mostrarExito, mostrarError } from '../utils/alerts.js';
const { 
  usuario, 
  esTecnico, 
  esGerencia, 
  puedeCrearFolio 
} = useAuth();
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
  evaluador: null,
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
  cargando, incidentes, tecnicos, evaluadores, centrales, filtros, areasDisponibles,
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
  let evaluadorId = null;
  if (inc.evaluador && typeof inc.evaluador === 'object') {
    evaluadorId = inc.evaluador.id;
  } else if (inc.evaluador) {
    evaluadorId = inc.evaluador;
  }
  formActual.value = { 
    ...formInicial, 
    ...inc,
    area_operativa: String(inc.area_operativa || inc.area || '').toUpperCase().trim(),
    dilacion_dias: inc.dilacion_dias || inc.dilacion || 0,
    tecnico: tecnicoId,
    evaluador: evaluadorId,
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
    let evaluadorAsignado = null;
    if (payload.evaluador && typeof payload.evaluador === 'object') {
      evaluadorAsignado = payload.evaluador.id;
    } else if (payload.evaluador) {
      evaluadorAsignado = parseInt(payload.evaluador, 10);
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
      tecnico: Number.isInteger(tecnicoAsignado) && tecnicoAsignado > 0 ? tecnicoAsignado : null,
      evaluador: Number.isInteger(evaluadorAsignado) && evaluadorAsignado > 0 ? evaluadorAsignado : null
    };
    if (editando.value) {
      await updateIncidente(payload.id, datosEnvio);
    } else {
      await createIncidente(datosEnvio);
    }
    mostrarFormulario.value = false;
    await cargarIncidentes();
    mostrarExito('¡Folio Actualizado!', 'Los cambios del incidente se guardaron correctamente.');
  } catch (error) {
    mostrarError('Error de guardado', 'No se pudo conectar con el servidor para guardar los datos.');
    const detalleError = error.response?.data ? JSON.stringify(error.response.data, null, 2) : error.message;
    alert(`No se pudo guardar. Verifica los datos.\nDetalle: ${detalleError}`);
  }
};
const exportarCSV = () => {
  if (incidentes.value.length === 0) {
    alert('No hay datos disponibles para exportar.');
    return;}
  const cabeceras = ['Folio', 'Empresa', 'Referencia', 'Tipo Servicio', 'Area Operativa', 'Central', 'Técnico', 'Evaluador', 'Estatus IO', 'Estado Enlace', 'Dilación Días', 'Dirección', 'IP'];
  const filas = incidentes.value.map(inc => [
    `"${inc.folio || ''}"`,
    `"${inc.empresa || ''}"`,
    `"${inc.referencia || ''}"`,
    `"${inc.tipo_servicio || ''}"`,
    `"${inc.area_operativa || ''}"`,
    `"${inc.central || ''}"`,
    `"${inc.tecnico_nombre || inc.tecnico?.username || inc.tecnico || ''}"`,
    `"${inc.evaluador_nombre || inc.evaluador?.username || inc.evaluador || ''}"`,
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
  }, 350);
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
        <div class="user-chip" v-if="usuario">
          <span>USUARIO: {{ usuario.nombre || usuario.username }}</span>
          <span class="role-tag">{{ usuario.rol || 'Sin indentificar' }}</span>
        </div>
      </div>
      <div class="header-right">
        <button v-if="puedeCrearFolio" @click="abrirNuevo" class="btn btn-primary-gio">
          + Nuevo Folio
        </button>        
        <button v-if="esGerencia" @click="exportarCSV" class="btn btn-primary-gio">
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
      <section class="filter-bar">
        <div class="filters-left">
          <span class="filter-label">Buscar:</span>          
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
              ✕ Cerrar
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
    <IncidenteModal 
      v-if="mostrarFormulario"
      :centrales="centrales" 
      :tecnicos="tecnicos"
      :evaluadores="evaluadores"
      :areas="areasDisponibles"
      :editando="editando" 
      :modelo="formActual" 
      @close="mostrarFormulario = false" 
      @save="procesarGuardado" 
    />
  </div>
</template>