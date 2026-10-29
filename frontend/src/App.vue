<script setup>
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AvisosChat from './components/AvisosChat.vue'
import BotonTema from './components/BotonTema.vue'
import MiCuenta from './components/MiCuenta.vue'
import { ROLES, useAuth } from './composables/useAuth.js'
import { detenerAvisosDeChat, iniciarAvisosDeChat } from './composables/useChat.js'
import { confirmarAccion } from './utils/alerts.js'

const route = useRoute()
const router = useRouter()
const { estaAutenticado, usuario, rol, permisos, cerrarSesion } = useAuth()

watch(
  estaAutenticado,
  (activo) => (activo ? iniciarAvisosDeChat() : detenerAvisosDeChat()),
  { immediate: true },
)

const ETIQUETAS_ROL = {
  [ROLES.TECNICO]: 'Técnico de planta externa',
  [ROLES.PI_EVALUADOR]: 'Técnico',
  [ROLES.PI_SUB]: 'Subgerencia PI',
  [ROLES.ADMIN]: 'Gerencia',
}

const enlaces = computed(() => {
  const items = []
  if (rol.value !== ROLES.TECNICO) items.push({ nombre: 'tablero', texto: 'Tablero' })
  if (rol.value === ROLES.TECNICO || permisos.value.vision_global)
    items.push({ nombre: 'campo', texto: 'Campo' })
  if (permisos.value.vision_global) items.push({ nombre: 'metricas', texto: 'Métricas' })
  if (permisos.value.asignar) items.push({ nombre: 'turnos', texto: 'Turnos' })
  if (permisos.value.gestionar_usuarios) items.push({ nombre: 'usuarios', texto: 'Usuarios' })
  return items
})

const salir = async () => {
  if (!(await confirmarAccion('Cerrar sesión', '¿Desea salir del sistema GIO?', 'Sí, salir'))) return
  cerrarSesion()
  router.replace({ name: 'login' })
}
</script>

<template>
  <div class="app-raiz">
    <header v-if="estaAutenticado" class="barra">
      <div class="barra__marca">
        <span class="insignia">GIO</span>
        <div class="barra__titulos">
          <strong>Gestión de Incidencias y Enlace Operativo</strong>
          <small>CASE Puebla</small>
        </div>
      </div>

      <nav class="barra__nav" aria-label="Secciones">
        <RouterLink
          v-for="enlace in enlaces"
          :key="enlace.nombre"
          :to="{ name: enlace.nombre }"
          class="barra__enlace"
          :class="{ 'barra__enlace--activo': route.name === enlace.nombre }"
        >
          {{ enlace.texto }}
        </RouterLink>
      </nav>

      <div class="barra__usuario">
        <div class="barra__identidad">
          <span class="barra__nombre">{{ usuario?.nombre || usuario?.expediente }}</span>
          <span class="barra__rol">{{ ETIQUETAS_ROL[rol] || rol }}</span>
        </div>
        <AvisosChat />
        <MiCuenta />
        <BotonTema />
        <button type="button" class="gio-boton gio-boton--secundario" @click="salir">Salir</button>
      </div>
    </header>

    <BotonTema v-else class="tema-flotante" />

    <main :class="estaAutenticado ? 'contenido' : 'contenido contenido--limpio'">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.app-raiz {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.barra {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 20px;
  min-height: 64px;
  padding: 8px 24px;
  background-color: var(--barra);
  color: var(--sobre-barra);
  border-bottom: 1px solid var(--barra-borde);
  position: sticky;
  top: 0;
  z-index: 40;
}

.barra__marca {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.insignia {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: var(--radio-pildora);
  background: var(--acento);
  color: var(--sobre-acento);
  font-weight: 700;
  font-size: 0.8rem;
  letter-spacing: 0.04em;
  flex-shrink: 0;
}

.barra__titulos {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.barra__titulos strong {
  font-size: 0.875rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.barra__titulos small {
  font-size: 0.7rem;
  color: var(--sobre-barra-apagado);
}

.barra__nav {
  display: flex;
  gap: 4px;
  flex: 1 1 auto;
  overflow-x: auto;
}

.barra__enlace {
  padding: 12px;
  border-radius: 0;
  color: var(--sobre-barra-apagado);
  text-decoration: none;
  font-size: 0.875rem;
  font-weight: 400;
  letter-spacing: 0.3px;
  white-space: nowrap;
}
.barra__enlace:hover {
  color: var(--sobre-barra);
  text-decoration: none;
}
.barra__enlace--activo {
  color: var(--sobre-barra);
  font-weight: 700;
  box-shadow: inset 0 -2px 0 var(--acento);
}

.barra__usuario {
  display: flex;
  align-items: center;
  gap: 12px;
}

.barra__identidad {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  line-height: 1.2;
}
.barra__nombre {
  font-size: 0.8125rem;
  font-weight: 700;
}
.barra__rol {
  font-size: 0.6875rem;
  color: var(--sobre-barra-apagado);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.tema-flotante {
  position: fixed;
  top: 12px;
  right: 12px;
  z-index: 40;
  background-color: var(--panel);
}

.contenido {
  flex: 1;
  padding: 16px 24px 24px;
  max-width: 1600px;
  width: 100%;
  margin: 0 auto;
}

.contenido--limpio {
  padding: 0;
  max-width: none;
}

@media (max-width: 700px) {
  .barra {
    padding: 8px 12px;
  }
  .barra__titulos strong {
    font-size: 0.78rem;
  }
  .barra__identidad {
    display: none;
  }
  .contenido {
    padding: 12px;
  }
}
</style>
