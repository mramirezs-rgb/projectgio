<script setup>
const props = defineProps({
  columnas: {
    type: Array,
    required: true
  }
});

const emit = defineEmits(['editar']);
</script>

<template>
  <div class="kanban-container">
    <div v-for="col in columnas" :key="col.key" class="kanban-column">
      <header class="column-header" :style="{ borderTopColor: col.color }">
        <span class="column-title">{{ col.label }}</span>
        <span class="column-count">{{ col.items.length }}</span>
      </header>

      <div class="column-body">
        <div 
          v-for="item in col.items" 
          :key="item.id || item.folio" 
          class="kanban-card"
          @click="emit('editar', item)"
        >
          <div class="card-top">
            <span class="card-folio">{{ item.folio }}</span>
            <span 
              v-if="(item.dilacion_dias || 0) > 5" 
              class="card-alert" 
              title="Dilación mayor a 5 días"
            >
               {{ item.dilacion_dias }}d
            </span>
          </div>

          <h4 class="card-empresa">{{ item.empresa }}</h4>

          <div class="card-meta">
            <span> {{ item.central || item.area_operativa || 'S/A' }}</span>
            <span> {{ item.tecnico_asignado || 'Sin Asignar' }}</span>
          </div>

          <footer class="card-footer">
            <span class="card-servicio">{{ item.tipo_servicio || 'Servicio' }}</span>
            <span v-if="item.estado_enlace" :class="['enlace-pill', item.estado_enlace.toLowerCase()]">
              {{ item.estado_enlace }}
            </span>
          </footer>
        </div>

        <div v-if="col.items.length === 0" class="empty-column">
          Sin folios
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.kanban-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 1rem;
  align-items: start;
}

.kanban-column {
  background-color: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 220px);
}

.column-header {
  padding: 0.8rem 1rem;
  background-color: #0f172a;
  border-top: 4px solid #3b82f6;
  border-bottom: 1px solid #334155;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
}

.column-title {
  font-weight: 700;
  font-size: 0.9rem;
  color: #f8fafc;
}

.column-count {
  background-color: #334155;
  color: #cbd5e1;
  font-size: 0.75rem;
  font-weight: 700;
  padding: 0.15rem 0.5rem;
  border-radius: 10px;
}

.column-body {
  padding: 0.8rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
}

.kanban-card {
  background-color: #0f172a;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 0.8rem;
  cursor: pointer;
  transition: transform 0.15s, border-color 0.15s;
}

.kanban-card:hover {
  transform: translateY(-2px);
  border-color: #38bdf8;
}

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.4rem;
}

.card-folio {
  font-weight: 700;
  color: #38bdf8;
  font-size: 0.85rem;
}

.card-alert {
  background-color: rgba(239, 68, 68, 0.2);
  color: #f87171;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  border: 1px solid #ef4444;
}

.card-empresa {
  margin: 0 0 0.5rem 0;
  font-size: 0.95rem;
  color: #f8fafc;
}

.card-meta {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  font-size: 0.75rem;
  color: #94a3b8;
  margin-bottom: 0.6rem;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 1px solid #1e293b;
  padding-top: 0.5rem;
  font-size: 0.7rem;
}

.card-servicio {
  color: #64748b;
}

.enlace-pill {
  font-weight: 800;
  padding: 0.05rem 0.3rem;
  border-radius: 3px;
}

.enlace-pill.up { color: #34d399; }
.enlace-pill.down { color: #f87171; }

.empty-column {
  text-align: center;
  color: #475569;
  font-size: 0.8rem;
  padding: 1.5rem 0;
}
</style>