<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ChatFolio from '../components/ChatFolio.vue'
import DesempenoCampo from '../components/DesempenoCampo.vue'
import EvidenciaUploader from '../components/EvidenciaUploader.vue'
import { useAuth } from '../composables/useAuth.js'
import { useChat } from '../composables/useChat.js'
import { ESTATUS, etiquetaEstatus } from '../composables/useIncidentes.js'
import {
  cancelarLiquidacion,
  getEvidencias,
  getIncidentes,
  liquidarIncidente,
  mensajeDeError,
  updateIncidente,
} from '../services/api.js'
import { confirmarAccion, mostrarError, mostrarExito, notificar } from '../utils/alerts.js'
import { formatearFecha, formatearHoras } from '../utils/formato.js'

const route = useRoute()
const router = useRouter()
const { usuario, permisos } = useAuth()
const { sinLeerDe } = useChat()

// Gerencia y Subgerencia no atienden folios en campo: aquí ven el desempeño de sus técnicos.
const supervision = computed(() => !!permisos.value.vision_global)

const cargando = ref(false)
const problema = ref('')
const folios = ref([])
const expandido = ref(null)
const evidencias = ref([])
const chatAbierto = ref(false)
const enviando = ref(false)
const filtro = ref('activos')

const ESTATUS_ACTIVOS = [ESTATUS.PENDIENTE, ESTATUS.ASIGNADO, ESTATUS.EN_PROCESO]
// Los liquidados se acumulan con los meses: solo se traen los más recientes.
const LIQUIDADOS_RECIENTES = 50
const totalLiquidados = ref(0)

const formLiquidacion = ref({ diagnostico_final: '', cve_liq: '', desc_liq: '', estado_enlace: 'UP' })

const visibles = computed(() => {
  if (filtro.value === 'liquidados') {
    return folios.value.filter((f) => f.estatus === ESTATUS.LIQUIDADO)
  }
  return folios.value.filter((f) => f.estatus !== ESTATUS.LIQUIDADO)
})

const conteos = computed(() => ({
  activos: folios.value.filter((f) => f.estatus !== ESTATUS.LIQUIDADO).length,
  liquidados: totalLiquidados.value,
  criticos: folios.value.filter(
    (f) => f.estatus !== ESTATUS.LIQUIDADO && f.semaforo === 'critico',
  ).length,
}))

const listaDe = (data) => (Array.isArray(data) ? data : data.results || [])

// Activos y liquidados se piden por separado: en una sola consulta con límite, el historial de
// liquidados acababa desplazando a los folios nuevos, que no aparecían en la lista.
const cargar = async () => {
  cargando.value = true
  problema.value = ''
  try {
    const activos = new URLSearchParams([
      ...ESTATUS_ACTIVOS.map((valor) => ['estatus', valor]),
      ['page_size', '500'],
      ['ordering', '-dilacion_dias'],
    ])
    const [resActivos, resLiquidados] = await Promise.all([
      getIncidentes(activos),
      getIncidentes({
        estatus: ESTATUS.LIQUIDADO,
        page_size: LIQUIDADOS_RECIENTES,
        ordering: '-fecha_cierre',
      }),
    ])
    const liquidados = listaDe(resLiquidados.data)
    totalLiquidados.value = resLiquidados.data.count ?? liquidados.length
    folios.value = [...listaDe(resActivos.data), ...liquidados]
  } catch (error) {
    problema.value = mensajeDeError(error, 'No se pudieron cargar los folios asignados.')
  } finally {
    cargando.value = false
  }
}

// La bandeja de mensajes llega con ?folio=<id>&chat=1 para abrir ese folio con su chat.
const abrirDesdeAviso = async () => {
  const id = Number(route.query.folio)
  if (!id) return
  const conChat = !!route.query.chat
  router.replace({ query: {} })
  const folio = folios.value.find((item) => item.id === id)
  if (!folio) return
  filtro.value = folio.estatus === ESTATUS.LIQUIDADO ? 'liquidados' : 'activos'
  if (expandido.value !== id) await alternar(folio)
  chatAbierto.value = conChat
  await nextTick()
  document.getElementById(`folio-${id}`)?.scrollIntoView({ block: 'start' })
}

onMounted(async () => {
  if (supervision.value) return
  await cargar()
  abrirDesdeAviso()
})

watch(
  () => route.query.folio,
  (folio) => {
    if (folio && folios.value.length) abrirDesdeAviso()
  },
)

const alternar = async (folio) => {
  chatAbierto.value = false
  if (expandido.value === folio.id) {
    expandido.value = null
    return
  }
  expandido.value = folio.id
  formLiquidacion.value = {
    diagnostico_final: folio.diagnostico_final || '',
    cve_liq: folio.cve_liq || '',
    desc_liq: folio.desc_liq || '',
    // Al cerrar lo normal es que el enlace quede restablecido; el técnico lo cambia si sigue caído.
    estado_enlace: 'UP',
  }
  await cargarEvidencias(folio.id)
}

const cargarEvidencias = async (id) => {
  try {
    const { data } = await getEvidencias(id)
    evidencias.value = data || []
  } catch {
    evidencias.value = []
  }
}

const reemplazar = (actualizado) => {
  const indice = folios.value.findIndex((f) => f.id === actualizado.id)
  if (indice === -1) return
  const anterior = folios.value[indice].estatus
  if (actualizado.estatus === ESTATUS.LIQUIDADO && anterior !== ESTATUS.LIQUIDADO) {
    totalLiquidados.value += 1
  } else if (anterior === ESTATUS.LIQUIDADO && actualizado.estatus !== ESTATUS.LIQUIDADO) {
    totalLiquidados.value = Math.max(0, totalLiquidados.value - 1)
  }
  folios.value.splice(indice, 1, { ...folios.value[indice], ...actualizado })
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

const deshacerLiquidacion = async (folio) => {
  const confirmado = await confirmarAccion(
    `Cancelar liquidación de ${folio.folio}`,
    'El folio volverá a Pendiente para corregirlo. Queda registrado en bitácora.',
    'Cancelar liquidación',
  )
  if (!confirmado) return

  enviando.value = true
  try {
    const { data } = await cancelarLiquidacion(folio.id)
    reemplazar(data)
    expandido.value = null
    notificar('Liquidación cancelada')
  } catch (error) {
    mostrarError('No se pudo cancelar la liquidación', mensajeDeError(error))
  } finally {
    enviando.value = false
  }
}

const telefono = (valor) => (valor ? `tel:${String(valor).replace(/[^\d+]/g, '')}` : null)
const mapa = (direccion) =>
  direccion ? `https://maps.google.com/?q=${encodeURIComponent(direccion)}` : null
</script>

<template>
  <DesempenoCampo v-if="supervision" />

  <div v-else class="campo">
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
        :id="`folio-${folio.id}`"
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
            <span v-if="sinLeerDe(folio.id)" class="tarjeta__mensajes">
              {{ sinLeerDe(folio.id) }} mensaje(s) nuevo(s)
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

          <button
            type="button"
            class="gio-boton gio-boton--secundario gio-boton--tactil"
            :aria-expanded="chatAbierto"
            @click="chatAbierto = !chatAbierto"
          >
            {{ chatAbierto ? 'Ocultar chat' : 'Chat con planta interna' }}
            <span v-if="!chatAbierto && sinLeerDe(folio.id)" class="detalle__aviso">
              {{ sinLeerDe(folio.id) }}
            </span>
          </button>
          <ChatFolio v-if="chatAbierto" :incidente-id="folio.id" />

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
              :disabled="enviando"
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
            <button
              v-if="folio.puede_cancelar_liquidacion"
              type="button"
              class="gio-boton gio-boton--peligro gio-boton--tactil"
              :disabled="enviando"
              @click="deshacerLiquidacion(folio)"
            >
              Cancelar liquidación (error de captura)
            </button>
            <p v-else-if="folio.bloqueado" class="detalle__pista">
              Folio liquidado. Solo Gerencia puede modificarlo.
            </p>
          </template>
        </section>
      </li>
    </ul>

    <p v-if="filtro === 'liquidados' && totalLiquidados > visibles.length" class="detalle__pista">
      Se muestran los {{ visibles.length }} liquidados más recientes de {{ totalLiquidados }}.
    </p>
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
  border-radius: var(--radio);
  background: rgb(239 68 68 / 0.12);
  border: 1px solid rgb(239 68 68 / 0.4);
  color: var(--rojo-texto);
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
  border-radius: var(--radio);
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
  background-color: var(--seleccion);
}

.resumen--critico strong {
  color: var(--rojo-vivo);
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
  color: var(--indigo-texto);
  font-weight: 700;
}

.tarjeta__mensajes {
  padding: 0 6px;
  font-size: 0.72rem;
  font-weight: 700;
  background-color: var(--acento);
  color: var(--sobre-acento);
}

.detalle__aviso {
  display: inline-grid;
  place-items: center;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: var(--radio-pildora);
  background-color: var(--acento);
  color: var(--sobre-acento);
  font-size: 0.72rem;
  font-variant-numeric: tabular-nums;
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
  background-color: var(--superficie);
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
  color: var(--tenue);
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

.detalle__pista {
  margin: 0;
  font-size: 0.78rem;
  color: var(--tenue);
}

.detalle__cerrado {
  margin: 0;
  font-size: 0.8125rem;
  color: var(--verde-texto);
  font-weight: 700;
}

.detalle__diagnostico {
  margin: 0;
  font-size: 0.875rem;
  color: var(--apagado);
  background-color: var(--campo);
  border: 1px solid var(--borde);
  border-radius: var(--radio);
  padding: 0.65rem 0.75rem;
  white-space: pre-line;
}

@media (max-width: 420px) {
  .detalle__pareja {
    grid-template-columns: 1fr;
  }
}
</style>
