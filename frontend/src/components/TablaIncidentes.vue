<script setup>
defineProps({
  incidentes: {
    type: Array,
    required: true,
    default: () => []
  }
});

defineEmits(['editar']);
</script>

<template>
  <section class="table-container">
    <table class="styled-table">
      <thead>
        <tr>
          <th>Folio</th>
          <th>Empresa</th>
          <th>Área Operativa</th>
          <th>Técnico Asignado</th>
          <th>Dilación</th>
          <th>Estatus I/O</th>
          <th class="text-center">Acciones</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="inc in incidentes" :key="inc.id || inc.folio">
          <td class="folio-text">{{ inc.folio }}</td>
          <td>{{ inc.empresa || 'N/A' }}</td>
          <td>{{ inc.area_operativa || 'N/A' }}</td>
          <td>{{ inc.tecnico_asignado || inc.tecnico_nombre || 'Sin Asignar' }}</td>
          <td>
            <span :class="{ 'red-text fw-bold': (inc.dilacion_dias || 0) > 5 }">
              {{ inc.dilacion_dias || 0 }} días
            </span>
          </td>
          <td>
            <span class="table-status">
              {{ inc.estatus_io || 'PENDIENTE' }}
            </span>
          </td>
          <td class="text-center">
            <button @click="$emit('editar', inc)" class="btn-sm-edit">
              Editar
            </button>
          </td>
        </tr>
        <tr v-if="incidentes.length === 0">
          <td colspan="7" class="text-center no-data">
            No se encontraron incidencias registradas.
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>