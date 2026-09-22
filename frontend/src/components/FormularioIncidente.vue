<script setup>
import { ref, watch } from 'vue';
import { createIncidente, updateIncidente } from '../services/api';

const props = defineProps({
  incidenteEditar: Object,
  tecnicos: Array,
  centrales: Array,
  mostrar: Boolean
});

const emit = defineEmits(['cerrar', 'recargar']);

const formInicial = {
  id: null, folio: '', empresa: '', incidente: '', referencia: '',
  area_operativa: '', central: '', tecnico_asignado: '', 
  tipo_servicio: '', estatus_io: 'PENDIENTE', dilacion_dias: 0, obs_usuario: ''
};

const form = ref({ ...formInicial });

// Sincronizar datos al abrir para editar
watch(() => props.incidenteEditar, (nuevoVal) => {
  if (nuevoVal) {
    form.value = { ...formInicial, ...nuevoVal };
  } else {
    form.value = { ...formInicial };
  }
}, { immediate: true });

const guardar = async () => {
  try {
    // CORRECCIÓN: Nombres exactos de PostgreSQL
    const payload = {
      folio: form.value.folio,
      empresa: form.value.empresa,
      incidente: form.value.incidente,
      referencia: form.value.referencia,
      area_operativa: form.value.area_operativa, // Corregido
      central: form.value.central,               // Guardado como texto
      tecnico_asignado: form.value.tecnico_asignado, // Corregido: texto, no número
      estatus_io: form.value.estatus_io,
      tipo_servicio: form.value.tipo_servicio,
      dilacion_dias: Number(form.value.dilacion_dias) || 0,
      obs_usuario: form.value.obs_usuario
    };

    if (form.value.id) {
      await updateIncidente(form.value.id, payload);
    } else {
      await createIncidente(payload);
    }

    emit('recargar');
    emit('cerrar');
  } catch (error) {
    alert('Error al guardar: ' + JSON.stringify(error.response?.data || error));
  }
};
</script>

<template>
  <div v-if="mostrar" class="modal-overlay">
    <div class="modal-box shadow-xl">
      <div class="modal-header">
        <h2>{{ form.id ? 'Editar Folio: ' + form.folio : 'Nuevo Folio' }}</h2>
        <button @click="emit('cerrar')" class="btn-close">✕</button>
      </div>

      <form @submit.prevent="guardar" class="modal-form">
        <div class="form-row-3">
          <div class="form-group">
            <label>Folio *</label>
            <input v-model="form.folio" type="text" required class="form-control" />
          </div>
          <div class="form-group">
            <label>Área Operativa</label>
            <input v-model="form.area_operativa" type="text" class="form-control" />
          </div>
          <div class="form-group">
            <label>Empresa</label>
            <input v-model="form.empresa" type="text" class="form-control" />
          </div>
        </div>

        <div class="form-row-2">
          <div class="form-group">
            <label>Técnico Asignado</label>
            <!-- CORRECCIÓN: Guardar el nombre en lugar del ID numérico -->
            <select v-model="form.tecnico_asignado" class="form-control">
              <option value="">-- Seleccionar --</option>
              <option v-for="t in tecnicos" :key="t.id" :value="t.nombre">{{ t.nombre }}</option>
            </select>
          </div>
          <div class="form-group">
            <label>Estatus I/O</label>
            <select v-model="form.estatus_io" class="form-control">
              <option value="ABIERTO">ABIERTO</option>
              <option value="EN PROCESO">EN PROCESO</option>
              <option value="PENDIENTE">PENDIENTE</option>
              <option value="ATENDIDO">ATENDIDO</option>
              <option value="CERRADO">CERRADO</option>
            </select>
          </div>
        </div>
        
        <div class="modal-footer">
          <button type="button" @click="emit('cerrar')" class="btn-cancel">Cancelar</button>
          <button type="submit" class="btn-submit">Guardar</button>
        </div>
      </form>
    </div>
  </div>
</template>