import { createApp } from 'vue'
import { registerSW } from 'virtual:pwa-register'
import App from './App.vue'
import router from './router'
import { limpiarSesion, registrarCaducidadSesion } from './services/api.js'
import './assets/main.css'

registrarCaducidadSesion(() => {
  limpiarSesion()
  router.replace({ name: 'login', query: { expirada: '1' } })
})

const actualizarSW = registerSW({
  onNeedRefresh() {
    if (window.confirm('Hay una versión nueva de GIO disponible. ¿Recargar ahora?')) {
      actualizarSW(true)
    }
  },
})

createApp(App).use(router).mount('#app')
