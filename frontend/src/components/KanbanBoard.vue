<script setup>
defineProps({
  columnas: Array
});
defineEmits(['editar']);

const getInitials = (nombre) => {
  if (!nombre) return 'PA';
  const parts = nombre.trim().split(' ');
  return parts.length >= 2 ? (parts[0][0] + parts[1][0]).toUpperCase() : parts[0].substring(0, 2).toUpperCase();
};
</script>

<template>
  <div class="kanban-wrapper">
    <div class="kanban-board">
      <div v-for="col in columnas" :key="col.key" class="kanban-column">
        <div class="column-header" :style="{ borderTopColor: col.color }">
          <div class="column-title">
            <span class="dot" :style="{ backgroundColor: col.color }"></span>
            <h3>{{ col.label }}</h3>
          </div>
          <span class="count-pill">{{ col.items.length }}</span>
        </div>
        <div class="column-cards">
          <div 
            v-for="card in col.items" 
            :key="card.id" 
            class="kanban-card"
            :class="{ 'border-danger': (card.dilacion_dias || card.dilacion || 0) > 3 }"
            @click="$emit('editar', card)"
          >
            <div class="card-top">
              <span class="folio-code">{{ card.folio }}</span>
              <div class="status-tags">
                <span class="tag tag-down">• {{ card.estatus_qp || 'DOWN' }}</span>
                <span class="tag tag-days">{{ card.dilacion_dias || card.dilacion || 0 }} días</span>
              </div>
            </div>
            <div class="card-client">{{ card.empresa || 'Cliente Comercial' }}</div>
            <div class="card-cope">COPE: <strong>{{ card.cope || card.central_nombre || 'N/A' }}</strong></div>
            <div class="card-footer">
              <div class="tech-info">
                <span class="tech-avatar">{{ getInitials(card.tecnico_asignado || card.tecnico_nombre) }}</span>
                <span class="tech-name">{{ card.tecnico_asignado || card.tecnico_nombre || 'Por Asignar' }}</span>
              </div>
              <span class="arrow-icon">›</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>