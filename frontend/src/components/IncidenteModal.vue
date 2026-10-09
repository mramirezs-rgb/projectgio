<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { ESTATUS, TRANSICIONES, etiquetaEstatus } from '../composables/useIncidentes.js'
import { getBitacora, getEvidencias, mensajeDeError } from '../services/api.js'
import { formatearFecha, formatearHoras } from '../utils/formato.js'
import EvidenciaUploader from './EvidenciaUploader.vue'

const props = defineProps({
  modelo: { type: Object, required: true },
  editando: { type: Boolean, default: false },
  centrales: { type: Array, default: () => [] },
  tecnicos: { type: Array, default: () => [] },
  evaluadores: { type: Array, default: () => [] },
  areas: { type: Array, default: () => [] },
  permisos: { type: Object, default: () => ({}) },
  rol: { type: String, default: '' },
  guardando: { type: Boolean, default: false },
})

const emit = defineEmits(['close', 'save', 'liquidar'])

const AREAS_BASE = [
  'PUEBLA',
  'PACHUCA',
  'VERACRUZ',
  'POZA RICA',
  'XALAPA',
  'TLAXCALA',
  'CORDOBA',
  'COATZACOALCOS',
]

const TIPOS_SERVICIO = [
  'BASICO',
  'ENLACES',
  'ENLACE DEDICADO',
  'INTERNET EMPRESARIAL',
  'DATOS VPN',
  'TRUNCAL SIP',
]

const CODIGOS_FALLO = [
  { id: 'F1', nombre: 'F1 — Familia de falla' },
  { id: 'COD4', nombre: 'COD4 — Causa raíz' },
  { id: 'CARLS', nombre: 'CARLS — Diagnóstico' },
  { id: 'COD5', nombre: 'COD5 — Acción correctiva' },
]

const form = ref({})
const tabActiva = ref('general')
const errores = ref({})
const evidencias = ref([])
const bitacora = ref([])
const cargandoAnexos = ref(false)
const problemaAnexos = ref('')

const esTecnico = computed(() => props.rol === 'TECNICO')
const esEvaluador = computed(() => props.rol === 'PI_EVALUADOR')
const visionGlobal = computed(() => !!props.permisos.vision_global)

const puedeEditarIdentificacion = computed(() => visionGlobal.value)
const puedeEditarAsignacion = computed(() => !!props.permisos.asignar)
const puedeEditarRed = computed(() => visionGlobal.value || esEvaluador.value)
const puedeEditarLiquidacion = computed(
  () => visionGlobal.value || esEvaluador.value || esTecnico.value,
)
const puedeCargarEvidencia = computed(
  () => props.editando && (visionGlobal.value || esTecnico.value),
)

const estatusOriginal = computed(() => props.modelo?.estatus || ESTATUS.PENDIENTE)

const estatusDisponibles = computed(() => {
  if (!props.editando) return [ESTATUS.PENDIENTE]
  const permitidos = props.modelo?.transiciones_validas?.length
    ? props.modelo.transiciones_validas
    : TRANSICIONES[estatusOriginal.value] || []
  return [estatusOriginal.value, ...permitidos]
})

const todasLasAreas = computed(() => {
  const nombres = props.areas.map((item) => item.nombre || item).filter(Boolean)
  const conjunto = new Set([...AREAS_BASE, ...nombres])
  if (form.value.area_operativa) conjunto.add(form.value.area_operativa)
  return [...conjunto].sort()
})

const centralesDisponibles = computed(() => {
  const nombres = props.centrales.map((item) => item.nombre || item).filter(Boolean)
  const conjunto = new Set(nombres)
  if (form.value.central) conjunto.add(form.value.central)
  return [...conjunto].sort()
})

const sinEvidencias = computed(() => evidencias.value.length === 0)

const puedeLiquidarAhora = computed(
  () =>
    props.editando &&
    estatusOriginal.value === ESTATUS.EN_PROCESO &&
    puedeEditarLiquidacion.value,
)

const idDe = (valor) => {
  if (valor === null || valor === undefined || valor === '') return null
  if (typeof valor === 'object') return valor.id ?? null
  const numero = Number(valor)
  return Number.isFinite(numero) ? numero : null
}

watch(
  () => props.modelo,
  (valor) => {
    if (!valor) return
    form.value = {
      ...valor,
      folio: String(valor.folio || '').trim(),
      area_operativa: String(valor.area_operativa || '').toUpperCase().trim(),
      central: String(valor.central || '').toUpperCase().trim(),
      estatus: valor.estatus || ESTATUS.PENDIENTE,
      estado_enlace: valor.estado_enlace || 'DESCONOCIDO',
      codigo_fallo: valor.codigo_fallo || '',
      tecnico: idDe(valor.tecnico),
      evaluador: idDe(valor.evaluador),
    }
    errores.value = {}
    tabActiva.value = 'general'
  },
  { immediate: true, deep: true },
)

watch(
  () => props.modelo?.id,
  (id) => {
    evidencias.value = props.modelo?.evidencias || []
    bitacora.value = []
    if (id) cargarAnexos()
  },
  { immediate: true },
)

const cargarAnexos = async () => {
  if (!props.modelo?.id) return
  cargandoAnexos.value = true
  problemaAnexos.value = ''
  try {
    const [resEvidencias, resBitacora] = await Promise.all([
      getEvidencias(props.modelo.id),
      getBitacora(props.modelo.id),
    ])
    evidencias.value = resEvidencias.data || []
    bitacora.value = resBitacora.data || []
  } catch (error) {
    problemaAnexos.value = mensajeDeError(error, 'No se pudieron cargar evidencias y bitácora.')
  } finally {
    cargandoAnexos.value = false
  }
}

const validar = () => {
  const fallos = {}
  if (!form.value.folio) fallos.folio = 'El folio es obligatorio.'
  if (!form.value.empresa) fallos.empresa = 'Indique la empresa o cliente.'
  if (!form.value.area_operativa) fallos.area_operativa = 'Seleccione el área operativa.'

  const destino = form.value.estatus
  if (
    (destino === ESTATUS.ASIGNADO || destino === ESTATUS.EN_PROCESO) &&
    !idDe(form.value.tecnico)
  ) {
    fallos.tecnico = 'Asigne un técnico antes de mover el folio a este estatus.'
  }
  if (destino === ESTATUS.LIQUIDADO && !String(form.value.diagnostico_final || '').trim()) {
    fallos.diagnostico_final = 'El diagnóstico final es obligatorio para liquidar.'
  }

  errores.value = fallos
  if (Object.keys(fallos).length) {
    tabActiva.value = fallos.diagnostico_final ? 'liquidacion' : 'general'
    return false
  }
  return true
}

const guardar = () => {
  if (!validar()) return
  emit('save', {
    ...form.value,
    tecnico: idDe(form.value.tecnico),
    evaluador: idDe(form.value.evaluador),
    area_operativa: String(form.value.area_operativa || '').toUpperCase().trim(),
    central: String(form.value.central || '').toUpperCase().trim(),
  })
}

const liquidar = () => {
  if (!String(form.value.diagnostico_final || '').trim()) {
    errores.value = { diagnostico_final: 'El diagnóstico final es obligatorio para liquidar.' }
    tabActiva.value = 'liquidacion'
    return
  }
  emit('liquidar', {
    id: props.modelo.id,
    diagnostico_final: String(form.value.diagnostico_final).trim(),
    cve_liq: form.value.cve_liq || '',
    desc_liq: form.value.desc_liq || '',
    codigo_fallo: form.value.codigo_fallo || '',
    estado_enlace: form.value.estado_enlace || 'UP',
  })
}

const alPulsarTecla = (evento) => {
  if (evento.key === 'Escape') emit('close')
}

onMounted(() => document.addEventListener('keydown', alPulsarTecla))
onUnmounted(() => document.removeEventListener('keydown', alPulsarTecla))
</script>

<template>
  <div class="velo" role="dialog" aria-modal="true" @click.self="emit('close')">
    <div class="caja gio-panel">
      <header class="caja__cabecera">
        <div class="caja__titulo">
          <span class="caja__marca">{{ editando ? 'FOLIO' : 'NUEVO' }}</span>
          <div>
            <h3>{{ editando ? form.folio || 'Sin folio' : 'Registro de folio' }}</h3>
            <p v-if="editando" class="caja__sub">
              <span class="gio-pastilla" :class="`gio-pastilla--${(estatusOriginal || '').toLowerCase()}`">
                {{ etiquetaEstatus(estatusOriginal) }}
              </span>
              <span class="gio-semaforo" :class="`gio-semaforo--${modelo.semaforo || 'normal'}`">
                {{ modelo.dilacion_dias ?? 0 }} días
              </span>
              <span class="caja__dato">
                {{
                  estatusOriginal === 'LIQUIDADO'
                    ? `MTTR ${formatearHoras(modelo.mttr_horas)}`
                    : `Abierto ${formatearHoras(modelo.horas_abierto)}`
                }}
              </span>
            </p>
          </div>
        </div>
        <button type="button" class="caja__cerrar" aria-label="Cerrar" @click="emit('close')">
          &times;
        </button>
      </header>

      <nav class="pestanas" aria-label="Secciones del folio">
        <button
          type="button"
          :class="['pestanas__btn', { 'pestanas__btn--activa': tabActiva === 'general' }]"
          @click="tabActiva = 'general'"
        >
          General
        </button>
        <button
          type="button"
          :class="['pestanas__btn', { 'pestanas__btn--activa': tabActiva === 'red' }]"
          @click="tabActiva = 'red'"
        >
          Datos de red
        </button>
        <button
          type="button"
          :class="['pestanas__btn', { 'pestanas__btn--activa': tabActiva === 'liquidacion' }]"
          @click="tabActiva = 'liquidacion'"
        >
          SISA y liquidación
        </button>
        <button
          v-if="editando"
          type="button"
          :class="['pestanas__btn', { 'pestanas__btn--activa': tabActiva === 'evidencias' }]"
          @click="tabActiva = 'evidencias'"
        >
          Evidencias ({{ evidencias.length }})
        </button>
        <button
          v-if="editando"
          type="button"
          :class="['pestanas__btn', { 'pestanas__btn--activa': tabActiva === 'bitacora' }]"
          @click="tabActiva = 'bitacora'"
        >
          Bitácora
        </button>
      </nav>

      <form class="caja__cuerpo" @submit.prevent="guardar">
        <div v-show="tabActiva === 'general'" class="rejilla">
          <div class="campo">
            <label class="gio-etiqueta" for="folio">Folio SISA *</label>
            <input
              id="folio"
              v-model.trim="form.folio"
              type="text"
              :disabled="!puedeEditarIdentificacion"
              placeholder="12578004"
            />
            <small v-if="errores.folio" class="campo__error">{{ errores.folio }}</small>
          </div>

          <div class="campo">
            <label class="gio-etiqueta" for="empresa">Empresa / Cliente *</label>
            <input
              id="empresa"
              v-model.trim="form.empresa"
              type="text"
              :disabled="!puedeEditarIdentificacion"
            />
            <small v-if="errores.empresa" class="campo__error">{{ errores.empresa }}</small>
          </div>

          <div class="campo">
            <label class="gio-etiqueta" for="referencia">Referencia de servicio</label>
            <input
              id="referencia"
              v-model.trim="form.referencia"
              type="text"
              :disabled="!puedeEditarIdentificacion"
            />
          </div>

          <div class="campo">
            <label class="gio-etiqueta" for="tipo_servicio">Tipo de servicio</label>
            <select
              id="tipo_servicio"
              v-model="form.tipo_servicio"
              :disabled="!puedeEditarIdentificacion"
            >
              <option value="">Seleccionar…</option>
              <option v-for="tipo in TIPOS_SERVICIO" :key="tipo" :value="tipo">{{ tipo }}</option>
            </select>
          </div>

          <div class="campo">
            <label class="gio-etiqueta" for="area">Área operativa *</label>
            <select id="area" v-model="form.area_operativa" :disabled="!puedeEditarIdentificacion">
              <option value="">Seleccionar área…</option>
              <option v-for="area in todasLasAreas" :key="area" :value="area">{{ area }}</option>
            </select>
            <small v-if="errores.area_operativa" class="campo__error">
              {{ errores.area_operativa }}
            </small>
          </div>

          <div class="campo">
            <label class="gio-etiqueta" for="central">COPE / Central</label>
            <input
              id="central"
              v-model.trim="form.central"
              type="text"
              list="lista-centrales"
              :disabled="!puedeEditarIdentificacion"
            />
            <datalist id="lista-centrales">
              <option v-for="central in centralesDisponibles" :key="central" :value="central" />
            </datalist>
          </div>

          <div class="campo">
            <label class="gio-etiqueta" for="tecnico">Técnico asignado (PE)</label>
            <select id="tecnico" v-model="form.tecnico" :disabled="!puedeEditarAsignacion">
              <option :value="null">Sin asignar</option>
              <option v-for="t in tecnicos" :key="t.id" :value="t.id">
                {{ t.nombre }} · {{ t.expediente }}
              </option>
            </select>
            <small v-if="errores.tecnico" class="campo__error">{{ errores.tecnico }}</small>
          </div>

          <div class="campo">
            <label class="gio-etiqueta" for="evaluador">Evaluador asignado (PI)</label>
            <select id="evaluador" v-model="form.evaluador" :disabled="!puedeEditarAsignacion">
              <option :value="null">Sin asignar</option>
              <option v-for="e in evaluadores" :key="e.id" :value="e.id">
                {{ e.nombre }} · {{ e.expediente }}
              </option>
            </select>
          </div>

          <div class="campo">
            <label class="gio-etiqueta" for="estatus">Estatus del folio</label>
            <select id="estatus" v-model="form.estatus" :disabled="!editando">
              <option v-for="valor in estatusDisponibles" :key="valor" :value="valor">
                {{ etiquetaEstatus(valor) }}
              </option>
            </select>
            <small class="campo__pista">
              Solo se ofrecen las transiciones válidas desde
              {{ etiquetaEstatus(estatusOriginal) }}.
            </small>
          </div>

          <div class="campo">
            <label class="gio-etiqueta" for="apertura">Fecha de apertura</label>
            <input
              id="apertura"
              :value="formatearFecha(form.fecha_apertura)"
              type="text"
              disabled
            />
          </div>

          <div class="campo campo--ancho">
            <label class="gio-etiqueta" for="descripcion">Síntoma reportado</label>
            <textarea
              id="descripcion"
              v-model="form.descripcion"
              rows="2"
              :disabled="!puedeEditarRed"
            ></textarea>
          </div>
        </div>

        <div v-show="tabActiva === 'red'" class="rejilla">
          <div class="campo campo--ancho">
            <label class="gio-etiqueta" for="dir">Dirección del sitio</label>
            <input id="dir" v-model.trim="form.dir_pta_a" type="text" :disabled="!puedeEditarRed" />
          </div>
          <div class="campo">
            <label class="gio-etiqueta" for="ips">IP de servicio / gestión</label>
            <input id="ips" v-model.trim="form.ips" type="text" :disabled="!puedeEditarRed" />
          </div>
          <div class="campo">
            <label class="gio-etiqueta" for="dslam">DSLAM / bastidor / puerto</label>
            <input id="dslam" v-model.trim="form.dslam" type="text" :disabled="!puedeEditarRed" />
          </div>
          <div class="campo">
            <label class="gio-etiqueta" for="red_sec">Red secundaria / par</label>
            <input
              id="red_sec"
              v-model.trim="form.red_secundaria"
              type="text"
              :disabled="!puedeEditarRed"
            />
          </div>
          <div class="campo">
            <label class="gio-etiqueta" for="enlace">Estado del enlace</label>
            <select id="enlace" v-model="form.estado_enlace" :disabled="!puedeEditarLiquidacion">
              <option value="DESCONOCIDO">Desconocido</option>
              <option value="UP">UP (en línea)</option>
              <option value="DOWN">DOWN (caído)</option>
            </select>
          </div>
          <div class="campo">
            <label class="gio-etiqueta" for="telefono">Teléfono del técnico</label>
            <input
              id="telefono"
              v-model.trim="form.telefono_tecnico"
              type="tel"
              :disabled="!puedeEditarRed"
            />
          </div>
          <div class="campo campo--ancho">
            <label class="gio-etiqueta" for="obs_sisa">Observaciones SISA</label>
            <textarea
              id="obs_sisa"
              v-model="form.observaciones_sisa"
              rows="3"
              :disabled="!puedeEditarRed"
            ></textarea>
          </div>
        </div>

        <div v-show="tabActiva === 'liquidacion'" class="rejilla">
          <div class="campo">
            <label class="gio-etiqueta" for="codigo_fallo">Código de fallo (catálogo SISA)</label>
            <select
              id="codigo_fallo"
              v-model="form.codigo_fallo"
              :disabled="!puedeEditarLiquidacion"
            >
              <option value="">Sin clasificar</option>
              <option v-for="codigo in CODIGOS_FALLO" :key="codigo.id" :value="codigo.id">
                {{ codigo.nombre }}
              </option>
            </select>
          </div>
          <div class="campo">
            <label class="gio-etiqueta" for="cve_liq">Clave de liquidación</label>
            <input
              id="cve_liq"
              v-model.trim="form.cve_liq"
              type="text"
              :disabled="!puedeEditarLiquidacion"
            />
          </div>
          <div class="campo">
            <label class="gio-etiqueta" for="f1">DESC F1 (familia)</label>
            <input id="f1" v-model.trim="form.desc_f1" type="text" :disabled="!puedeEditarRed" />
          </div>
          <div class="campo">
            <label class="gio-etiqueta" for="cod4">DESC COD4 (causa raíz)</label>
            <input
              id="cod4"
              v-model.trim="form.desc_cod4"
              type="text"
              :disabled="!puedeEditarLiquidacion"
            />
          </div>
          <div class="campo">
            <label class="gio-etiqueta" for="carls">DESC CARLS (diagnóstico)</label>
            <input
              id="carls"
              v-model.trim="form.desc_carls"
              type="text"
              :disabled="!puedeEditarLiquidacion"
            />
          </div>
          <div class="campo">
            <label class="gio-etiqueta" for="cod5">DESC COD5 (acción correctiva)</label>
            <input
              id="cod5"
              v-model.trim="form.desc_cod5"
              type="text"
              :disabled="!puedeEditarLiquidacion"
            />
          </div>
          <div class="campo campo--ancho">
            <label class="gio-etiqueta" for="desc_liq">Descripción de liquidación</label>
            <input
              id="desc_liq"
              v-model.trim="form.desc_liq"
              type="text"
              :disabled="!puedeEditarLiquidacion"
            />
          </div>
          <div class="campo campo--ancho">
            <label class="gio-etiqueta" for="diagnostico">
              Diagnóstico final (obligatorio para liquidar)
            </label>
            <textarea
              id="diagnostico"
              v-model="form.diagnostico_final"
              rows="4"
              :disabled="!puedeEditarLiquidacion"
              placeholder="Describa la causa, la reparación efectuada y las pruebas de restablecimiento."
            ></textarea>
            <small v-if="errores.diagnostico_final" class="campo__error">
              {{ errores.diagnostico_final }}
            </small>
          </div>
          <div class="campo campo--ancho">
            <label class="gio-etiqueta" for="obs_usuario">Bitácora OQU / notas internas</label>
            <textarea
              id="obs_usuario"
              v-model="form.obs_usuario"
              rows="2"
              :disabled="!puedeEditarRed"
            ></textarea>
          </div>
        </div>

        <div v-show="tabActiva === 'evidencias'">
          <p v-if="problemaAnexos" class="campo__error">{{ problemaAnexos }}</p>
          <EvidenciaUploader
            v-if="editando"
            :incidente-id="modelo.id"
            :evidencias="evidencias"
            :solo-lectura="!puedeCargarEvidencia"
            @cambio="cargarAnexos"
          />
        </div>

        <div v-show="tabActiva === 'bitacora'">
          <p v-if="cargandoAnexos" class="gio-cargando">Consultando bitácora…</p>
          <ol v-else-if="bitacora.length" class="historia">
            <li v-for="registro in bitacora" :key="registro.id" class="historia__item">
              <div class="historia__alto">
                <strong>{{ registro.accion_display }}</strong>
                <span>{{ formatearFecha(registro.registrado_en) }}</span>
              </div>
              <p class="historia__detalle">
                <span v-if="registro.campo">{{ registro.campo }}: </span>
                <span v-if="registro.valor_anterior">{{ registro.valor_anterior }} → </span>
                <span v-if="registro.valor_nuevo">{{ registro.valor_nuevo }}</span>
                <span v-if="registro.detalle"> {{ registro.detalle }}</span>
              </p>
              <small class="historia__autor">{{ registro.usuario_nombre }}</small>
            </li>
          </ol>
          <p v-else class="gio-vacio">Sin movimientos registrados.</p>
        </div>

        <footer class="caja__pie">
          <button type="button" class="gio-boton gio-boton--secundario" @click="emit('close')">
            Cerrar
          </button>
          <button
            v-if="puedeLiquidarAhora"
            type="button"
            class="gio-boton gio-boton--exito"
            :disabled="guardando || sinEvidencias"
            :title="sinEvidencias ? 'Cargue al menos una evidencia fotográfica' : ''"
            @click="liquidar"
          >
            Liquidar folio
          </button>
          <button type="submit" class="gio-boton gio-boton--primario" :disabled="guardando">
            {{ guardando ? 'Guardando…' : editando ? 'Guardar cambios' : 'Crear folio' }}
          </button>
        </footer>
      </form>
    </div>
  </div>
</template>

<style scoped>
.velo {
  position: fixed;
  inset: 0;
  background-color: rgb(2 6 23 / 0.8);
  backdrop-filter: blur(3px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  z-index: 100;
}

.caja {
  width: 100%;
  max-width: 880px;
  max-height: 92vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 24px 48px -12px rgb(0 0 0 / 0.6);
}

.caja__cabecera {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.9rem 1.2rem;
  background-color: #0a1222;
  border-bottom: 1px solid var(--borde);
}

.caja__titulo {
  display: flex;
  align-items: flex-start;
  gap: 0.7rem;
  min-width: 0;
}

.caja__marca {
  background-color: var(--acento);
  color: #fff;
  font-size: 0.65rem;
  font-weight: 800;
  letter-spacing: 0.06em;
  padding: 0.25rem 0.5rem;
  border-radius: 5px;
  margin-top: 0.2rem;
}

.caja__cabecera h3 {
  font-size: 1.05rem;
  font-family: ui-monospace, 'SFMono-Regular', Menlo, monospace;
}

.caja__sub {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
  margin: 0.4rem 0 0;
  font-size: 0.75rem;
}

.caja__dato {
  color: var(--apagado);
}

.caja__cerrar {
  background: none;
  border: none;
  color: var(--apagado);
  font-size: 1.6rem;
  line-height: 1;
  padding: 0 0.3rem;
}

.caja__cerrar:hover {
  color: var(--texto);
}

.pestanas {
  display: flex;
  background-color: #0a1222;
  border-bottom: 1px solid var(--borde);
  overflow-x: auto;
}

.pestanas__btn {
  flex: 1 0 auto;
  padding: 0.65rem 0.9rem;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--apagado);
  font-size: 0.8125rem;
  font-weight: 600;
  white-space: nowrap;
}

.pestanas__btn:hover {
  color: var(--texto);
}

.pestanas__btn--activa {
  color: var(--acento-claro);
  border-bottom-color: var(--acento-claro);
  background-color: rgb(56 189 248 / 0.06);
}

.caja__cuerpo {
  padding: 1.2rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1.2rem;
  flex: 1;
}

.rejilla {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.9rem;
}

.campo {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.campo--ancho {
  grid-column: 1 / -1;
}

.campo input:disabled,
.campo select:disabled,
.campo textarea:disabled {
  opacity: 0.6;
  background-color: #0a1222;
}

.campo__error {
  margin-top: 0.25rem;
  font-size: 0.72rem;
  color: #fca5a5;
}

.campo__pista {
  margin-top: 0.25rem;
  font-size: 0.68rem;
  color: #64748b;
}

.caja__pie {
  display: flex;
  justify-content: flex-end;
  gap: 0.7rem;
  flex-wrap: wrap;
  padding-top: 1rem;
  border-top: 1px solid var(--borde);
  margin-top: auto;
}

.historia {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.historia__item {
  background-color: #0a1222;
  border: 1px solid var(--borde);
  border-left: 3px solid var(--acento);
  border-radius: 8px;
  padding: 0.6rem 0.75rem;
}

.historia__alto {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  font-size: 0.78rem;
}

.historia__alto span {
  color: var(--apagado);
}

.historia__detalle {
  margin: 0.3rem 0;
  font-size: 0.78rem;
  color: var(--apagado);
  word-break: break-word;
}

.historia__autor {
  font-size: 0.68rem;
  color: #64748b;
}

@media (max-width: 680px) {
  .velo {
    padding: 0;
  }
  .caja {
    max-width: none;
    max-height: 100vh;
    height: 100vh;
    border-radius: 0;
    border: none;
  }
  .rejilla {
    grid-template-columns: 1fr;
  }
  .campo--ancho {
    grid-column: auto;
  }
}
</style>
