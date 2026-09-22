<script setup>
const props = defineProps({
  incidentes: {
    type: Array,
    default: () => []
  }
});

const emit = defineEmits(['editar', 'ver-bitacora']);

const obtenerClaseEstatus = (estatus) => {
  const est = (estatus || '').toLowerCase();
  if (est.includes('abierto')) return 'badge-abierto';
  if (est.includes('proceso') || est.includes('atencion')) return 'badge-proceso';
  if (est.includes('pendiente')) return 'badge-pendiente';
  if (est.includes('atendido') || est.includes('resuelto')) return 'badge-resuelto';
  if (est.includes('cerrado')) return 'badge-cerrado';
  return 'badge-default';
};

const obtenerClaseEnlace = (estado) => {
  if (estado === 'UP') return 'enlace-up';
  if (estado === 'DOWN') return 'enlace-down';
  return 'enlace-unknown';
};
</script>

<template>
  <div class="tabla-container">
    <table class="gio-table">
      <thead>
        <tr>
          <th>Folio</th>
          <th>Cliente / Empresa</th>
          <th>Área / Central</th>
          <th>Enlace</th>
          <th>Técnico (PE)</th>
          <th>Dilación</th>
          <th>Estatus I/O</th>
          <th>Acciones</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="incidentes.length === 0">
          <td colspan="8" class="empty-state">No se encontraron folios registrados.</td>
        </tr>
        <tr v-for="inc in incidentes" :key="inc.id || inc.folio">
          <td class="col-folio">
            <span class="folio-text">{{ inc.folio || 'N/A' }}</span>
            <small v-if="inc.referencia" class="ref-subtext">{{ inc.referencia }}</small>
          </td>

          <td>
            <div class="empresa-info">
              <span class="empresa-nombre">{{ inc.empresa }}</span>
              <small class="servicio-tipo">{{ inc.tipo_servicio || 'Servicio Estándar' }}</small>
            </div>
          </td>

          <td>
            <div class="ubicacion-info">
              <span class="area-tag">{{ inc.area_operativa || 'Sin Área' }}</span>
              <small class="central-text">{{ inc.central || 'Sin Central' }}</small>
            </div>
          </td>

          <td>
            <span :class="['enlace-badge', obtenerClaseEnlace(inc.estado_enlace)]">
              {{ inc.estado_enlace || 'N/D' }}
            </span>
          </td>

          <td>
            <span class="tecnico-name">
              {{ inc.tecnico_asignado || 'Sin Asignar' }}
            </span>
          </td>

          <td>
            <span :class="['dilacion-pill', { 'alerta-dilacion': (inc.dilacion_dias || 0) > 5 }]">
              {{ inc.dilacion_dias || 0 }} días
            </span>
          </td>

          <td>
            <span :class="['status-badge', obtenerClaseEstatus(inc.estatus_io)]">
              {{ inc.estatus_io || 'ABIERTO' }}
            </span>
          </td>

          <td>
            <div class="acciones-group">
              <button @click="emit('editar', inc)" class="btn-action edit" title="Editar Folio">
                ✏️
              </button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.tabla-container {
  background-color: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  overflow-x: auto;
}

.gio-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 0.875rem;
  color: #f8fafc;
}

.gio-table th {
  background-color: #0f172a;
  color: #94a3b8;
  padding: 0.85rem 1rem;
  font-weight: 600;
  border-bottom: 1px solid #334155;
  white-space: nowrap;
}

.gio-table td {
  padding: 0.85rem 1rem;
  border-bottom: 1px solid #334155;
  vertical-align: middle;
}

.gio-table tbody tr:hover {
  background-color: rgba(51, 65, 85, 0.4);
}

.empty-state {
  text-align: center;
  color: #64748b;
  padding: 2rem !important;
}

/* ESTILOS DE CELDAS */
.folio-text {
  font-weight: 700;
  color: #38bdf8;
  display: block;
}

.ref-subtext {
  color: #64748b;
  font-size: 0.75rem;
}

.empresa-info {
  display: flex;
  flex-direction: column;
}

.empresa-nombre {
  font-weight: 600;
}

.servicio-tipo {
  color: #94a3b8;
  font-size: 0.75rem;
}

.ubicacion-info {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.area-tag {
  color: #cbd5e1;
  font-size: 0.8rem;
  font-weight: 600;
}

.central-text {
  color: #64748b;
  font-size: 0.75rem;
}

/* ENLACE UP / DOWN */
.enlace-badge {
  font-size: 0.7rem;
  font-weight: 800;
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
}

.enlace-up {
  background-color: rgba(16, 185, 129, 0.2);
  color: #34d399;
  border: 1px solid #10b981;
}

.enlace-down {
  background-color: rgba(239, 68, 68, 0.2);
  color: #f87171;
  border: 1px solid #ef4444;
}

.enlace-unknown {
  background-color: #334155;
  color: #94a3b8;
}

/* DILACIÓN */
.dilacion-pill {
  padding: 0.2rem 0.5rem;
  border-radius: 12px;
  background-color: #334155;
  color: #cbd5e1;
  font-size: 0.75rem;
  font-weight: 600;
}

.dilacion-pill.alerta-dilacion {
  background-color: rgba(239, 68, 68, 0.2);
  color: #f87171;
  border: 1px solid #ef4444;
}

/* BADGES DE ESTATUS */
.status-badge {
  padding: 0.25rem 0.6rem;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
}

.badge-abierto { background-color: rgba(59, 130, 246, 0.2); color: #60a5fa; }
.badge-proceso { background-color: rgba(234, 179, 8, 0.2); color: #facc15; }
.badge-pendiente { background-color: rgba(249, 115, 22, 0.2); color: #fb923c; }
.badge-resuelto { background-color: rgba(16, 185, 129, 0.2); color: #4ade80; }
.badge-cerrado { background-color: rgba(100, 116, 139, 0.2); color: #94a3b8; }

/* ACCIONES */
.acciones-group {
  display: flex;
  gap: 0.5rem;
}

.btn-action {
  background: transparent;
  border: 1px solid #334155;
  border-radius: 4px;
  padding: 0.3rem 0.5rem;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-action:hover {
  background-color: #334155;
}
</style>