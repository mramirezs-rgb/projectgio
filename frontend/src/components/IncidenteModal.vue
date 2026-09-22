<script setup>
import { ref, watch } from 'vue';

const props = defineProps({
  modelo: Object,
  editando: Boolean,
  tecnicos: Array,
  centrales: Array
});
const emit = defineEmits(['close', 'save']);

const form = ref({});

watch(() => props.modelo, (newVal) => {
  form.value = { ...newVal };
}, { immediate: true, deep: true });

const guardar = () => {
  const payload = {
    id: form.value.id,
    folio: form.value.folio,
    incidente: form.value.incidente || null,
    empresa: form.value.empresa,
    area_operativa: form.value.area_operativa || null,
    referencia: form.value.referencia || null,
    tipo_servicio: form.value.tipo_servicio || null,
    central: form.value.central || null,
    tecnico_asignado: form.value.tecnico_asignado || null,
    estatus_io: form.value.estatus_io || 'PENDIENTE',
    dilacion_dias: parseInt(form.value.dilacion_dias) || 0,
    obs_usuario: form.value.obs_usuario || null,
    actualizado_por_gio: true
  };
  emit('save', payload);
};
</script>

<template>
  <div class="modal-overlay">
    <div class="modal-box shadow-xl">
      <div class="modal-header">
        <div class="modal-header-title">
          <h2>{{ editando ? 'Editar Folio: ' + form.folio : 'Nuevo Folio de Incidencia' }}</h2>
        </div>
        <button type="button" @click="$emit('close')" class="btn-close">✕</button>
      </div>

      <form @submit.prevent="guardar" class="modal-form">
        <div class="form-section">
          <h3 class="section-heading">1. DATOS PRINCIPALES</h3>
          <div class="form-row-3">
            <div class="form-group">
              <label>Folio *</label>
              <input v-model="form.folio" type="text" class="form-control" required />
            </div>
            <div class="form-group">
              <label>Empresa / Cliente *</label>
              <input v-model="form.empresa" type="text" class="form-control" required />
            </div>
            <div class="form-group">
              <label>Incidente</label>
              <input v-model="form.incidente" type="text" class="form-control" />
            </div>
          </div>
          <div class="form-row-3">
            <div class="form-group">
              <label>Área Operativa</label>
              <input v-model="form.area_operativa" type="text" class="form-control" />
            </div>
            <div class="form-group">
              <label>Tipo de Servicio</label>
              <input v-model="form.tipo_servicio" type="text" class="form-control" />
            </div>
            <div class="form-group">
              <label>Referencia</label>
              <input v-model="form.referencia" type="text" class="form-control" />
            </div>
          </div>
        </div>

        <div class="form-section">
          <h3 class="section-heading">2. ASIGNACIÓN</h3>
          <div class="form-row-2">
            <div class="form-group">
              <label>Central / COPE</label>
              <select v-model="form.central" class="form-control">
                <option :value="null">-- Seleccionar --</option>
                <option v-for="c in centrales" :key="c.id" :value="c.nombre">{{ c.nombre }}</option>
              </select>
            </div>
            <div class="form-group">
              <label>Técnico Asignado</label>
              <select v-model="form.tecnico_asignado" class="form-control">
                <option :value="null">-- Seleccionar --</option>
                <option v-for="t in tecnicos" :key="t.id" :value="t.nombre">{{ t.nombre }}</option>
              </select>
            </div>
          </div>
        </div>

        <div class="form-section">
          <h3 class="section-heading">3. ESTATUS</h3>
          <div class="form-row-2">
            <div class="form-group">
              <label>Estatus I/O *</label>
              <select v-model="form.estatus_io" class="form-control" required>
                <option value="ABIERTO">ABIERTO</option>
                <option value="EN PROCESO">EN PROCESO</option>
                <option value="PENDIENTE">PENDIENTE</option>
                <option value="ATENDIDO">ATENDIDO</option>
                <option value="CERRADO">CERRADO</option>
              </select>
            </div>
            <div class="form-group">
              <label>Dilación (Días)</label>
              <input v-model="form.dilacion_dias" type="number" min="0" class="form-control" />
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <button type="button" @click="$emit('close')" class="btn-cancel">Cancelar</button>
          <button type="submit" class="btn-submit">✓ {{ editando ? 'Guardar Cambios' : 'Crear Folio' }}</button>
        </div>
      </form>
    </div>
  </div>
</template>