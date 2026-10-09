<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ROLES, useAuth } from './composables/useAuth.js'
import { confirmarAccion } from './utils/alerts.js'

const route = useRoute()
const router = useRouter()
const { estaAutenticado, usuario, rol, permisos, cerrarSesion } = useAuth()

const ETIQUETAS_ROL = {
  [ROLES.TECNICO]: 'Planta Externa',
  [ROLES.PI_EVALUADOR]: 'Evaluador PI',
  [ROLES.PI_SUB]: 'Subgerencia PI',
  [ROLES.ADMIN]: 'Gerencia',
}

const enlaces = computed(() => {
  const items = []
  if (rol.value !== ROLES.TECNICO) items.push({ nombre: 'tablero', texto: 'Tablero' })
  if (rol.value === ROLES.TECNICO || permisos.value.vision_global)
    items.push({ nombre: 'campo', texto: 'Campo' })
  if (permisos.value.vision_global) items.push({ nombre: 'metricas', texto: 'Métricas' })
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
        <button type="button" class="gio-boton gio-boton--secundario" @click="salir">Salir</button>
      </div>
    </header>

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
  gap: 0.75rem 1.25rem;
  padding: 0.6rem 1rem;
  background-color: #060c18;
  border-bottom: 1px solid var(--borde);
  position: sticky;
  top: 0;
  z-index: 40;
}

.barra__marca {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  min-width: 0;
}

.insignia {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 9px;
  background: linear-gradient(140deg, #2563eb, #38bdf8);
  color: #fff;
  font-weight: 800;
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
  color: var(--apagado);
}

.barra__nav {
  display: flex;
  gap: 0.25rem;
  flex: 1 1 auto;
  overflow-x: auto;
}

.barra__enlace {
  padding: 0.45rem 0.85rem;
  border-radius: 8px;
  color: var(--apagado);
  text-decoration: none;
  font-size: 0.8125rem;
  font-weight: 600;
  white-space: nowrap;
}
.barra__enlace:hover {
  background-color: var(--panel-alto);
  color: var(--texto);
}
.barra__enlace--activo {
  background-color: rgb(37 99 235 / 0.18);
  color: var(--acento-claro);
}

.barra__usuario {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.barra__identidad {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  line-height: 1.2;
}
.barra__nombre {
  font-size: 0.8125rem;
  font-weight: 600;
}
.barra__rol {
  font-size: 0.6875rem;
  color: var(--acento-claro);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.contenido {
  flex: 1;
  padding: 1rem;
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
    padding: 0.5rem 0.75rem;
  }
  .barra__titulos strong {
    font-size: 0.78rem;
  }
  .barra__identidad {
    display: none;
  }
  .contenido {
    padding: 0.75rem;
  }
}
</style>
