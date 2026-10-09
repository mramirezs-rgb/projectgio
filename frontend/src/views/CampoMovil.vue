<script setup>
import { computed, onMounted, ref } from 'vue'
import EvidenciaUploader from '../components/EvidenciaUploader.vue'
import { useAuth } from '../composables/useAuth.js'
import { ESTATUS, etiquetaEstatus } from '../composables/useIncidentes.js'
import {
  getEvidencias,
  getIncidentes,
  liquidarIncidente,
  mensajeDeError,
  updateIncidente,
} from '../services/api.js'
import { confirmarAccion, mostrarError, mostrarExito, notificar } from '../utils/alerts.js'
import { formatearFecha, formatearHoras } from '../utils/formato.js'

const { usuario, permisos } = useAuth()

const cargando = ref(false)
const problema = ref('')
const folios = ref([])
const expandido = ref(null)
const evidencias = ref([])
const cargandoEvidencias = ref(false)
const enviando = ref(false)
const filtro = ref('activos')

const formLiquidacion = ref({ diagnostico_final: '', cve_liq: '', desc_liq: '', estado_enlace: 'UP' })

const visibles = computed(() => {
  if (filtro.value === 'liquidados') {
    return folios.value.filter((f) => f.estatus === ESTATUS.LIQUIDADO)
  }
  return folios.value.filter((f) => f.estatus !== ESTATUS.LIQUIDADO)
})

const conteos = computed(() => ({
  activos: folios.value.filter((f) => f.estatus !== ESTATUS.LIQUIDADO).length,
  liquidados: folios.value.filter((f) => f.estatus === ESTATUS.LIQUIDADO).length,
  criticos: folios.value.filter(
    (f) => f.estatus !== ESTATUS.LIQUIDADO && f.semaforo === 'critico',
  ).length,
}))

const cargar = async () => {
  cargando.value = true
  problema.value = ''
  try {
    const { data } = await getIncidentes({
      page_size: 200,
      ordering: '-dilacion_dias',
      ...(permisos.value.vision_global && usuario.value?.rol !== 'TECNICO'
        ? { sin_tecnico: false }
        : {}),
    })
    folios.value = Array.isArray(data) ? data : data.results || []
  } catch (error) {
    problema.value = mensajeDeError(error, 'No se pudieron cargar los folios asignados.')
  } finally {
    cargando.value = false
  }
}

onMounted(cargar)

const alternar = async (folio) => {
  if (expandido.value === folio.id) {
    expandido.value = null
    return
  }
  expandido.value = folio.id
  formLiquidacion.value = {
    diagnostico_final: folio.diagnostico_final || '',
    cve_liq: folio.cve_liq || '',
    desc_liq: folio.desc_liq || '',
    estado_enlace: folio.estado_enlace === 'DOWN' ? 'UP' : folio.estado_enlace || 'UP',
  }
  await cargarEvidencias(folio.id)
}

const cargarEvidencias = async (id) => {
  cargandoEvidencias.value = true
  try {
    const { data } = await getEvidencias(id)
    evidencias.value = data || []
  } catch {
    evidencias.value = []
  } finally {
    cargandoEvidencias.value = false
  }
}

const reemplazar = (actualizado) => {
  const indice = folios.value.findIndex((f) => f.id === actualizado.id)
  if (indice !== -1) folios.value.splice(indice, 1, { ...folios.value[indice], ...actualizado })
}

const iniciarAtencion = async (folio) => {
  enviando.value = true
  try {
    const { data } = await updateIncidente(folio.id, { estatus: ESTATUS.EN_PROCESO })
    reemplazar(data)
    notificar('Folio marcado en proceso')
  } catch (error) {
    mostrarError('No se pudo actualizar', mensajeDeError(error))
  } finally {
    enviando.value = false
  }
}

const liquidar = async (folio) => {
  const diagnostico = formLiquidacion.value.diagnostico_final.trim()
  if (diagnostico.length < 15) {
    mostrarError(
      'Diagnóstico insuficiente',
      'Describa la causa y la reparación efectuada (mínimo 15 caracteres).',
    )
    return
  }
  if (evidencias.value.length === 0) {
    mostrarError('Falta evidencia', 'Cargue al menos una fotografía antes de liquidar el folio.')
    return
  }
  const confirmado = await confirmarAccion(
    `Liquidar ${folio.folio}`,
    'Se registrará la hora de cierre y se calculará el MTTR. Esta acción queda en bitácora.',
    'Liquidar',
  )
  if (!confirmado) return

  enviando.value = true
  try {
    const { data } = await liquidarIncidente(folio.id, {
      ...formLiquidacion.value,
      diagnostico_final: diagnostico,
    })
    reemplazar(data)
    expandido.value = null
    mostrarExito('Folio liquidado', `MTTR registrado: ${formatearHoras(data.mttr_horas)}.`)
  } catch (error) {
    mostrarError('No se pudo liquidar', mensajeDeError(error))
  } finally {
    enviando.value = false
  }
}

const telefono = (valor) => (valor ? `tel:${String(valor).replace(/[^\d+]/g, '')}` : null)
const mapa = (direccion) =>
  direccion ? `https://maps.google.com/?q=${encodeURIComponent(direccion)}` : null
</script>

<template>
  <div class="campo">
    <header class="campo__cabecera">
      <div>
        <h1>Mis folios</h1>
        <p>{{ usuario?.nombre || usuario?.expediente }}</p>
      </div>
      <button
        type="button"
        class="gio-boton gio-boton--secundario"
        :disabled="cargando"
        @click="cargar"
      >
        {{ cargando ? 'Cargando…' : 'Actualizar' }}
      </button>
    </header>

    <div class="campo__resumen">
      <button
        type="button"
        :class="['resumen', { 'resumen--activo': filtro === 'activos' }]"
        @click="filtro = 'activos'"
      >
        <strong>{{ conteos.activos }}</strong>
        <span>Por atender</span>
      </button>
      <button
        type="button"
        :class="['resumen', { 'resumen--activo': filtro === 'liquidados' }]"
        @click="filtro = 'liquidados'"
      >
        <strong>{{ conteos.liquidados }}</strong>
        <span>Liquidados</span>
      </button>
      <div class="resumen resumen--critico">
        <strong>{{ conteos.criticos }}</strong>
        <span>Críticos</span>
      </div>
    </div>

    <p v-if="problema" class="campo__error" role="alert">{{ problema }}</p>
    <p v-else-if="cargando" class="gio-cargando">Consultando folios asignados…</p>
    <p v-else-if="visibles.length === 0" class="gio-vacio">
      {{ filtro === 'activos' ? 'No tiene folios pendientes de atención.' : 'Aún no hay folios liquidados.' }}
    </p>

    <ul v-else class="tarjetas">
      <li
        v-for="folio in visibles"
        :key="folio.id"
        class="tarjeta gio-panel"
        :class="`tarjeta--${folio.semaforo || 'normal'}`"
      >
        <button type="button" class="tarjeta__encabezado" @click="alternar(folio)">
          <div class="tarjeta__identidad">
            <span class="tarjeta__folio">{{ folio.folio }}</span>
            <span class="gio-pastilla" :class="`gio-pastilla--${(folio.estatus || '').toLowerCase()}`">
              {{ etiquetaEstatus(folio.estatus) }}
            </span>
          </div>
          <h2 class="tarjeta__empresa">{{ folio.empresa || 'Sin empresa' }}</h2>
          <div class="tarjeta__linea">
            <span class="gio-semaforo" :class="`gio-semaforo--${folio.semaforo || 'normal'}`">
              {{ folio.dilacion_dias ?? 0 }} días
            </span>
            <span
              class="gio-enlace"
              :class="`gio-enlace--${(folio.estado_enlace || 'desconocido').toLowerCase()}`"
            >
              {{ folio.estado_enlace }}
            </span>
            <span v-if="folio.total_evidencias" class="tarjeta__evidencias">
              {{ folio.total_evidencias }} evidencia(s)
            </span>
          </div>
          <p class="tarjeta__sitio">{{ folio.central || folio.area_operativa || 'Sin central' }}</p>
        </button>

        <section v-if="expandido === folio.id" class="detalle">
          <dl class="detalle__datos">
            <div v-if="folio.dir_pta_a">
              <dt>Dirección</dt>
              <dd>
                <a :href="mapa(folio.dir_pta_a)" target="_blank" rel="noopener">
                  {{ folio.dir_pta_a }}
                </a>
              </dd>
            </div>
            <div v-if="folio.ips">
              <dt>IP</dt>
              <dd>{{ folio.ips }}</dd>
            </div>
            <div v-if="folio.dslam">
              <dt>DSLAM</dt>
              <dd>{{ folio.dslam }}</dd>
            </div>
            <div v-if="folio.red_secundaria">
              <dt>Red secundaria</dt>
              <dd>{{ folio.red_secundaria }}</dd>
            </div>
            <div>
              <dt>Apertura</dt>
              <dd>{{ formatearFecha(folio.fecha_apertura) }}</dd>
            </div>
            <div v-if="folio.descripcion || folio.desc_f1">
              <dt>Síntoma</dt>
              <dd>{{ folio.descripcion || folio.desc_f1 }}</dd>
            </div>
          </dl>

          <a
            v-if="folio.telefono_tecnico"
            :href="telefono(folio.telefono_tecnico)"
            class="gio-boton gio-boton--secundario gio-boton--tactil"
          >
            Llamar a central: {{ folio.telefono_tecnico }}
          </a>

          <template v-if="folio.estatus === ESTATUS.ASIGNADO || folio.estatus === ESTATUS.PENDIENTE">
            <button
              type="button"
              class="gio-boton gio-boton--primario gio-boton--tactil"
              :disabled="enviando"
              @click="iniciarAtencion(folio)"
            >
              Iniciar atención en sitio
            </button>
          </template>

          <template v-if="folio.estatus === ESTATUS.EN_PROCESO">
            <EvidenciaUploader
              :incidente-id="folio.id"
              :evidencias="evidencias"
              @cambio="cargarEvidencias(folio.id)"
            />

            <div class="detalle__forma">
              <div>
                <label class="gio-etiqueta" :for="`diag-${folio.id}`">Diagnóstico final *</label>
                <textarea
                  :id="`diag-${folio.id}`"
                  v-model="formLiquidacion.diagnostico_final"
                  rows="4"
                  placeholder="Causa encontrada, reparación efectuada y pruebas de restablecimiento."
                ></textarea>
              </div>
              <div class="detalle__pareja">
                <div>
                  <label class="gio-etiqueta" :for="`cve-${folio.id}`">Clave liq.</label>
                  <input :id="`cve-${folio.id}`" v-model.trim="formLiquidacion.cve_liq" type="text" />
                </div>
                <div>
                  <label class="gio-etiqueta" :for="`enlace-${folio.id}`">Enlace al cerrar</label>
                  <select :id="`enlace-${folio.id}`" v-model="formLiquidacion.estado_enlace">
                    <option value="UP">UP (restablecido)</option>
                    <option value="DOWN">DOWN (sigue caído)</option>
                  </select>
                </div>
              </div>
              <div>
                <label class="gio-etiqueta" :for="`descliq-${folio.id}`">Descripción liq.</label>
                <input
                  :id="`descliq-${folio.id}`"
                  v-model.trim="formLiquidacion.desc_liq"
                  type="text"
                />
              </div>
            </div>

            <button
              type="button"
              class="gio-boton gio-boton--exito gio-boton--tactil"
              :disabled="enviando || cargandoEvidencias"
              @click="liquidar(folio)"
            >
              {{ enviando ? 'Enviando…' : 'Liquidar folio' }}
            </button>
          </template>

          <template v-if="folio.estatus === ESTATUS.LIQUIDADO">
            <p class="detalle__cerrado">
              Liquidado el {{ formatearFecha(folio.fecha_cierre) }} · MTTR
              {{ formatearHoras(folio.mttr_horas) }}
            </p>
            <p class="detalle__diagnostico">{{ folio.diagnostico_final }}</p>
            <EvidenciaUploader
              :incidente-id="folio.id"
              :evidencias="evidencias"
              solo-lectura
              @cambio="cargarEvidencias(folio.id)"
            />
          </template>
        </section>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.campo {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
  max-width: 720px;
  margin: 0 auto;
  padding-bottom: 2rem;
}

.campo__cabecera {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.campo__cabecera h1 {
  font-size: 1.25rem;
}

.campo__cabecera p {
  margin: 0.15rem 0 0;
  font-size: 0.8125rem;
  color: var(--apagado);
}

.campo__error {
  margin: 0;
  padding: 0.7rem 0.85rem;
  border-radius: 8px;
  background: rgb(239 68 68 / 0.12);
  border: 1px solid rgb(239 68 68 / 0.4);
  color: #fca5a5;
  font-size: 0.8125rem;
}

.campo__resumen {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.6rem;
}

.resumen {
  background-color: var(--panel);
  border: 1px solid var(--borde);
  border-radius: 10px;
  padding: 0.7rem 0.5rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.1rem;
  color: var(--texto);
  min-height: 64px;
}

.resumen strong {
  font-size: 1.5rem;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.resumen span {
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--apagado);
}

.resumen--activo {
  border-color: var(--acento-claro);
  background-color: rgb(56 189 248 / 0.1);
}

.resumen--critico strong {
  color: #f87171;
}

.tarjetas {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.tarjeta {
  border-left: 4px solid var(--borde);
  overflow: hidden;
}

.tarjeta--alerta {
  border-left-color: var(--alerta);
}
.tarjeta--critico {
  border-left-color: var(--peligro);
}
.tarjeta--cerrado {
  border-left-color: var(--ok);
}

.tarjeta__encabezado {
  width: 100%;
  background: none;
  border: none;
  text-align: left;
  padding: 0.9rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  color: var(--texto);
  min-height: 72px;
}

.tarjeta__identidad {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
}

.tarjeta__folio {
  font-family: ui-monospace, 'SFMono-Regular', Menlo, monospace;
  font-weight: 700;
  font-size: 1rem;
  color: var(--acento-claro);
}

.tarjeta__empresa {
  font-size: 1.0625rem;
  line-height: 1.25;
}

.tarjeta__linea {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.tarjeta__evidencias {
  font-size: 0.72rem;
  color: #a5b4fc;
  font-weight: 600;
}

.tarjeta__sitio {
  margin: 0;
  font-size: 0.8125rem;
  color: var(--apagado);
}

.detalle {
  border-top: 1px solid var(--borde);
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  background-color: #0a1222;
}

.detalle__datos {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  font-size: 0.875rem;
}

.detalle__datos div {
  display: flex;
  flex-direction: column;
}

.detalle__datos dt {
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #64748b;
}

.detalle__datos dd {
  margin: 0;
  word-break: break-word;
}

.detalle__datos a {
  color: var(--acento-claro);
}

.detalle__forma {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.detalle__pareja {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.6rem;
}

.detalle__cerrado {
  margin: 0;
  font-size: 0.8125rem;
  color: #6ee7b7;
  font-weight: 600;
}

.detalle__diagnostico {
  margin: 0;
  font-size: 0.875rem;
  color: var(--apagado);
  background-color: #0b1324;
  border: 1px solid var(--borde);
  border-radius: 8px;
  padding: 0.65rem 0.75rem;
  white-space: pre-line;
}

@media (max-width: 420px) {
  .detalle__pareja {
    grid-template-columns: 1fr;
  }
}
</style>
