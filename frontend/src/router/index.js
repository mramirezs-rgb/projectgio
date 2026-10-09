import { createRouter, createWebHistory } from 'vue-router'
import { ROLES, rutaInicialPara, useAuth } from '../composables/useAuth.js'

const rutas = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/Login.vue'),
    meta: { publica: true },
  },
  {
    path: '/tablero',
    name: 'tablero',
    component: () => import('../views/Dashboard.vue'),
    meta: { roles: [ROLES.PI_EVALUADOR, ROLES.PI_SUB, ROLES.ADMIN] },
  },
  {
    path: '/campo',
    name: 'campo',
    component: () => import('../views/CampoMovil.vue'),
    meta: { roles: [ROLES.TECNICO, ROLES.PI_SUB, ROLES.ADMIN] },
  },
  {
    path: '/metricas',
    name: 'metricas',
    component: () => import('../views/Metricas.vue'),
    meta: { roles: [ROLES.PI_SUB, ROLES.ADMIN] },
  },
  {
    path: '/usuarios',
    name: 'usuarios',
    component: () => import('../views/Usuarios.vue'),
    meta: { roles: [ROLES.ADMIN] },
  },
  { path: '/', redirect: () => ({ name: 'tablero' }) },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes: rutas,
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach((destino) => {
  const { estaAutenticado, rol, esGerencia } = useAuth()

  if (destino.meta.publica) {
    return estaAutenticado.value ? rutaInicialPara(rol.value) : true
  }

  if (!estaAutenticado.value) {
    return { name: 'login', query: { redirigir: destino.fullPath } }
  }

  const permitidos = destino.meta.roles
  if (permitidos && !permitidos.includes(rol.value) && !esGerencia.value) {
    return rutaInicialPara(rol.value)
  }

  return true
})

export default router
