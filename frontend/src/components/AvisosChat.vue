<script setup>
import { computed, onUnmounted, ref } from 'vue'
import { activarNotificacionesDelSistema, useChat } from '../composables/useChat.js'

const { total, deGerencia, recientes, permisoDelSistema, sinConexion, irAlChat } = useChat()

const abierto = ref(false)
const boton = ref(null)
const panel = ref(null)
const arriba = ref(64)

const etiqueta = computed(() => {
  if (!total.value) return 'Mensajes: sin mensajes nuevos'
  const gerencia = deGerencia.value ? `, ${deGerencia.value} de Gerencia` : ''
  return `Mensajes: ${total.value} sin leer${gerencia}`
})

const cerrar = () => {
  abierto.value = false
  document.removeEventListener('pointerdown', alTocarFuera)
  document.removeEventListener('keydown', alPulsarTecla)
}

const alTocarFuera = (evento) => {
  if (!panel.value?.contains(evento.target) && !boton.value?.contains(evento.target)) cerrar()
}

const alPulsarTecla = (evento) => {
  if (evento.key === 'Escape') cerrar()
}

// El panel es fijo para que no se salga de la pantalla cuando la barra se acomoda en teléfono.
const alternar = () => {
  if (abierto.value) return cerrar()
  arriba.value = Math.round(boton.value.getBoundingClientRect().bottom + 8)
  abierto.value = true
  document.addEventListener('pointerdown', alTocarFuera)
  document.addEventListener('keydown', alPulsarTecla)
}

const abrirFolio = (item) => {
  cerrar()
  irAlChat(item.id)
}

const minutosDesde = (valor) =>
  Math.max(1, Math.round((Date.now() - new Date(valor).getTime()) / 60000))

const esperaDe = (valor) => {
  const minutos = minutosDesde(valor)
  return minutos < 60 ? `${minutos} min` : `${Math.floor(minutos / 60)} h ${minutos % 60} min`
}

const horaDe = (valor) => {
  const fecha = new Date(valor)
  if (Number.isNaN(fecha.getTime())) return ''
  return fecha.toDateString() === new Date().toDateString()
    ? fecha.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })
    : fecha.toLocaleDateString('es-MX', { day: '2-digit', month: 'short' })
}

onUnmounted(cerrar)
</script>

<template>
  <div class="avisos">
    <button
      ref="boton"
      type="button"
      class="gio-boton gio-boton--secundario avisos__boton"
      :class="{ 'avisos__boton--pendiente': total, 'avisos__boton--gerencia': deGerencia }"
      :aria-label="etiqueta"
      :title="etiqueta"
      :aria-expanded="abierto"
      aria-haspopup="true"
      @click="alternar"
    >
      <svg
        viewBox="0 0 24 24"
        width="18"
        height="18"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
      <span v-if="total" class="avisos__cuenta" :class="{ 'avisos__cuenta--gerencia': deGerencia }">
        {{ total > 99 ? '99+' : total }}
      </span>
    </button>

    <div
      v-if="abierto"
      ref="panel"
      class="avisos__panel gio-panel"
      :style="{ top: `${arriba}px` }"
      role="dialog"
      aria-label="Mensajes sin leer"
    >
      <p class="gio-etiqueta avisos__titulo">Mensajes sin leer</p>
      <p v-if="sinConexion" class="avisos__nota avisos__nota--problema" role="alert">
        Sin conexión con el servidor: los mensajes nuevos no están llegando.
      </p>
      <div v-if="permisoDelSistema === 'default'" class="avisos__nota">
        <span>Reciba el aviso aunque GIO esté en otra pestaña o minimizado.</span>
        <button
          type="button"
          class="gio-boton gio-boton--secundario"
          @click="activarNotificacionesDelSistema"
        >
          Activar notificaciones
        </button>
      </div>
      <p v-else-if="permisoDelSistema === 'denied'" class="avisos__nota">
        Las notificaciones del sistema están bloqueadas para GIO en este navegador; se activan en
        los permisos del sitio.
      </p>
      <p v-if="!recientes.length" class="avisos__vacio">No hay mensajes nuevos.</p>
      <ul v-else class="avisos__lista">
        <li v-for="item in recientes" :key="item.id">
          <button
            type="button"
            class="avisos__item"
            :class="{ 'avisos__item--gerencia': item.de_gerencia }"
            @click="abrirFolio(item)"
          >
            <span v-if="item.de_gerencia" class="avisos__prioridad">
              Gerencia · {{ item.de_gerencia }} mensaje(s) prioritario(s)
            </span>
            <span v-else-if="item.sin_atender" class="avisos__olvidado">
              Sin atender · nadie lo ha leído en {{ esperaDe(item.sin_atender_desde) }}
            </span>
            <span class="avisos__fila">
              <strong class="avisos__folio">{{ item.folio }}</strong>
              <span class="avisos__nuevos">{{ item.sin_leer }} nuevo(s)</span>
            </span>
            <span class="avisos__empresa">{{ item.empresa || 'Sin empresa' }}</span>
            <span class="avisos__vista">
              <b>{{ item.ultimo.autor_nombre }}:</b> {{ item.ultimo.texto }}
            </span>
            <span class="avisos__hora">{{ horaDe(item.ultimo.creado_en) }}</span>
          </button>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.avisos {
  position: relative;
}

.avisos__boton {
  position: relative;
  padding: 0.5rem;
  width: 40px;
  height: 40px;
  border-radius: var(--radio-pildora);
}

.avisos__boton--pendiente {
  border-color: var(--acento);
  color: var(--acento-claro);
}

.avisos__boton--gerencia {
  border-color: var(--peligro);
  color: var(--rojo-vivo);
}

.avisos__cuenta--gerencia {
  background-color: var(--peligro);
}

.avisos__item--gerencia {
  padding-left: 8px;
  border-left: 3px solid var(--peligro);
}

.avisos__prioridad {
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--rojo-texto);
}

.avisos__olvidado {
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--ambar-texto);
}

.avisos__nota {
  margin: 0 0 8px;
  padding: 8px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  border: 1px solid var(--borde);
  font-size: 0.8125rem;
  color: var(--apagado);
}

.avisos__nota--problema {
  border-color: rgb(239 68 68 / 0.4);
  background: rgb(239 68 68 / 0.12);
  color: var(--rojo-texto);
}

.avisos__cuenta {
  position: absolute;
  top: -4px;
  right: -6px;
  min-width: 20px;
  height: 20px;
  padding: 0 5px;
  display: grid;
  place-items: center;
  border-radius: var(--radio-pildora);
  background-color: var(--acento);
  color: var(--sobre-acento);
  font-size: 0.6875rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.avisos__panel {
  position: fixed;
  right: 16px;
  width: min(380px, calc(100vw - 32px));
  max-height: min(70vh, 520px);
  overflow-y: auto;
  padding: 12px;
  z-index: 50;
  color: var(--texto);
}

.avisos__titulo {
  margin: 0 0 8px;
}

.avisos__vacio {
  margin: 0;
  padding: 16px 0;
  text-align: center;
  font-size: 0.875rem;
  color: var(--tenue);
}

.avisos__lista {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}
.avisos__lista li + li {
  border-top: 1px solid var(--borde);
}

.avisos__item {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 4px;
  background: none;
  border: none;
  text-align: left;
  color: var(--texto);
  cursor: pointer;
}
.avisos__item:hover {
  background-color: var(--resalte);
}

.avisos__fila {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.avisos__folio {
  font-family: ui-monospace, 'SFMono-Regular', Menlo, monospace;
  color: var(--acento-claro);
}

.avisos__nuevos {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--acento-claro);
}

.avisos__empresa {
  font-size: 0.8125rem;
  font-weight: 700;
}

.avisos__vista {
  font-size: 0.8125rem;
  color: var(--apagado);
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.avisos__hora {
  font-size: 0.6875rem;
  color: var(--tenue);
}
</style>
