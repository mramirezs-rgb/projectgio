<script setup>
import { ref, watch } from 'vue';

const props = defineProps({
  modelo: {
    type: Object,
    required: true,
    default: () => ({})
  },
  editando: {
    type: Boolean,
    default: false
  },
  centrales: {
    type: Array,
    default: () => []
  },
  tecnicos: {
    type: Array,
    default: () => []
  }
});

const emit = defineEmits(['close', 'save']);

// Estado local del formulario clonado desde las props
const form = ref({ ...props.modelo });

// Control de la pestaña activa en el modal
const tabActiva = ref('general');

watch(
  () => props.modelo,
  (val) => {
    form.value = { ...val };
  },
  { deep: true }
);

const guardar = () => {
  emit('save', form.value);
};

const cerrar = () => {
  emit('close');
};
</script>

<template>
  <div class="modal-overlay" @click.self="cerrar">
    <div class="modal-container">
      <header class="modal-header">
        <div class="header-title">
          <span class="badge-tag">{{ editando ? 'EDICIÓN' : 'REGISTRO' }}</span>
          <h3>{{ editando ? `Folio: ${form.folio || 'S/N'}` : 'Nuevo Folio de Incidencia' }}</h3>
        </div>
        <button class="btn-close" @click="cerrar">&times;</button>
      </header>

      <!-- NAVEGACIÓN POR PESTAÑAS -->
      <nav class="modal-tabs">
        <button 
          type="button" 
          :class="['tab-btn', { active: tabActiva === 'general' }]" 
          @click="tabActiva = 'general'"
        >
          General y Asignación
        </button>
        <button 
          type="button" 
          :class="['tab-btn', { active: tabActiva === 'tecnico' }]" 
          @click="tabActiva = 'tecnico'"
        >
          Datos Técnicos de Red
        </button>
        <button 
          type="button" 
          :class="['tab-btn', { active: tabActiva === 'sisa' }]" 
          @click="tabActiva = 'sisa'"
        >
          SISA y Liquidación
        </button>
      </nav>

      <form @submit.prevent="guardar" class="modal-body">
        <!-- PESTAÑA 1: DATOS GENERALES -->
        <div v-show="tabActiva === 'general'" class="form-grid">
          <div class="form-group">
            <label>Folio SISA / Ticket *</label>
            <input v-model="form.folio" type="text" placeholder="Ej. FOL-2026-001" required />
          </div>

          <div class="form-group">
            <label>Empresa / Cliente *</label>
            <input v-model="form.empresa" type="text" placeholder="Nombre de la empresa" required />
          </div>

          <div class="form-group">
            <label>Referencia de Servicio</label>
            <input v-model="form.referencia" type="text" placeholder="Ej. REF-992812" />
          </div>

          <div class="form-group">
            <label>Tipo de Servicio</label>
            <select v-model="form.tipo_servicio">
              <option value="">Seleccionar...</option>
              <option value="ENLACE_DEDICADO">Enlace Dedicado</option>
              <option value="INTERNET_EMPRESARIAL">Internet Empresarial</option>
              <option value="DATOS_VPN">VPN / Red Privada</option>
              <option value="TRUNCAL_SIP">Truncal SIP / Telefonía</option>
            </select>
          </div>

          <div class="form-group">
            <label>Área Operativa *</label>
            <select v-model="form.area_operativa" required>
              <option value="">Seleccionar Área...</option>
              <option value="Puebla">Puebla</option>
              <option value="Pachuca">Pachuca</option>
              <option value="Veracruz">Veracruz</option>
              <option value="Poza Rica">Poza Rica</option>
              <option value="Jalapa">Jalapa</option>
              <option value="Tlaxcala">Tlaxcala</option>
              <option value="Córdoba">Córdoba</option>
              <option value="Coatzacoalcos">Coatzacoalcos</option>
            </select>
          </div>

          <div class="form-group">
            <label>COPE / Central *</label>
            <select v-model="form.central" required>
              <option :value="null">Seleccionar Central...</option>
              <option v-for="c in centrales" :key="c.id || c.nombre" :value="c.nombre">
                {{ c.nombre }}
              </option>
            </select>
          </div>

          <div class="form-group">
            <label>Técnico Asignado (PE)</label>
            <select v-model="form.tecnico_asignado">
              <option :value="null">Sin Asignar</option>
              <option v-for="t in tecnicos" :key="t.id || t.nombre" :value="t.nombre">
                {{ t.nombre }}
              </option>
            </select>
          </div>

          <div class="form-group">
            <label>Estatus I/O</label>
            <select v-model="form.estatus_io">
              <option value="ABIERTO">Abierto</option>
              <option value="EN PROCESO">En Atención</option>
              <option value="PENDIENTE">Pendiente Material</option>
              <option value="ATENDIDO">Resuelto / Atendido</option>
              <option value="CERRADO">Cerrado</option>
            </select>
          </div>

          <div class="form-group">
            <label>Dilación (Días)</label>
            <input v-model.number="form.dilacion_dias" type="number" min="0" />
          </div>
        </div>

        <!-- PESTAÑA 2: DATOS TÉCNICOS DE RED -->
        <div v-show="tabActiva === 'tecnico'" class="form-grid">
          <div class="form-group full-width">
            <label>Dirección del Sitio / Enlace</label>
            <input v-model="modelo.dir_pta_a" type="text" placeholder="Av. Reforma #123, Col. Centro, Puebla" />
          </div>

          <div class="form-group">
            <label>Dirección IP de Servicio / Gestión</label>
            <input v-model="modelo.ips" type="text" placeholder="Ej. 189.240.12.45" />
          </div>

          <div class="form-group">
            <label>DSLAM / Bastidor / Puerto</label>
            <input v-model="form.dslam" type="text" placeholder="Ej. DSLAM-PB-02 / B-04 / P-12" />
          </div>

          <div class="form-group">
            <label>Red Secundaria / Par</label>
            <input v-model="form.red_secundaria" type="text" placeholder="Ej. CABLE 12 / PAR 45" />
          </div>

          <div class="form-group">
            <label>Estado del Enlace</label>
            <select v-model="modelo.estatus_qp">
              <option value="DESCONOCIDO">Desconocido</option>
              <option value="UP">UP (Activo / En Línea)</option>
              <option value="DOWN">DOWN (Caído / Falla)</option>
            </select>
          </div>
        </div>

        <!-- PESTAÑA 3: CLASIFICACIÓN SISA Y LIQUIDACIÓN -->
        <div v-show="tabActiva === 'sisa'" class="form-grid">
          <div class="form-group">
            <label>DESC F1 (Familia Falla)</label>
            <input v-model="form.desc_f1" type="text" placeholder="Ej. SIN TONO / CORTE FISICO" />
          </div>

          <div class="form-group">
            <label>DESC COD4 (Causa Raíz)</label>
            <input v-model="form.desc_cod4" type="text" placeholder="Ej. FIBRA OPTICA ATENUADA" />
          </div>

          <div class="form-group">
            <label>DESC CARLS (Diagnóstico)</label>
            <input v-model="form.desc_carls" type="text" placeholder="Ej. DAÑO EN TRAMO EXTERNO" />
          </div>

          <div class="form-group">
            <label>DESC COD5 (Acción Correctiva)</label>
            <input v-model="form.desc_cod5" type="text" placeholder="Ej. REEMPLAZO DE PUERTO / EMPALME" />
          </div>

          <div class="form-group">
            <label>Clave Liquidación (CVE LIQ)</label>
            <input v-model="form.cve_liq" type="text" placeholder="Ej. LIQ-01" />
          </div>

          <div class="form-group">
            <label>Descripción Liquidación (DESC LIQ)</label>
            <input v-model="form.desc_liq" type="text" placeholder="Ej. SERVICIO RESTABLECIDO Y PROBADO" />
          </div>

          <div class="form-group full-width">
            <label>Observaciones SISA / Bitácora OQU</label>
            <textarea v-model="form.obs_usuario" rows="3" placeholder="Ingresa notas técnicas adicionales o seguimiento del operador..."></textarea>
          </div>
        </div>

        <!-- PIE DEL MODAL (BOTONES DE ACCIÓN) -->
        <footer class="modal-footer">
          <button type="button" class="btn btn-secondary" @click="cerrar">Cancelar</button>
          <button type="submit" class="btn btn-primary-gio">
            {{ editando ? 'Guardar Cambios' : 'Crear Folio' }}
          </button>
        </footer>
      </form>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background-color: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(4px);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal-container {
  background-color: #1e293b;
  border: 1px solid #334155;
  border-radius: 12px;
  width: 90%;
  max-width: 800px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
  overflow: hidden;
  color: #f8fafc;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  background-color: #0f172a;
  border-bottom: 1px solid #334155;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.badge-tag {
  background-color: #2563eb;
  color: #fff;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.25rem;
}

.btn-close {
  background: transparent;
  border: none;
  color: #94a3b8;
  font-size: 1.75rem;
  cursor: pointer;
}

.btn-close:hover {
  color: #fff;
}

/* TABS */
.modal-tabs {
  display: flex;
  background-color: #0f172a;
  border-bottom: 1px solid #334155;
}

.tab-btn {
  flex: 1;
  padding: 0.75rem 1rem;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: #94a3b8;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn:hover {
  color: #cbd5e1;
}

.tab-btn.active {
  color: #38bdf8;
  border-bottom-color: #38bdf8;
  background-color: rgba(56, 189, 248, 0.05);
}

/* FORMULARIO Y GRID */
.modal-body {
  padding: 1.5rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.form-group.full-width {
  grid-column: span 2;
}

.form-group label {
  font-size: 0.8rem;
  font-weight: 600;
  color: #94a3b8;
}

.form-group input,
.form-group select,
.form-group textarea {
  background-color: #0f172a;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 0.6rem 0.8rem;
  color: #f8fafc;
  font-size: 0.9rem;
  outline: none;
  transition: border-color 0.2s;
}

.form-group input:focus,
.form-group select:focus,
.form-group textarea:focus {
  border-color: #38bdf8;
}

/* FOOTER */
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #334155;
}

.btn {
  padding: 0.6rem 1.2rem;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  border: none;
}

.btn-secondary {
  background-color: #334155;
  color: #f1f5f9;
}

.btn-secondary:hover {
  background-color: #475569;
}

.btn-primary-gio {
  background-color: #2563eb;
  color: #ffffff;
}

.btn-primary-gio:hover {
  background-color: #1d4ed8;
}

@media (max-width: 640px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
  .form-group.full-width {
    grid-column: span 1;
  }
}
</style>