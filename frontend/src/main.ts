import { createApp } from 'vue'
import { registerSW } from 'virtual:pwa-register'
import App from './App.vue'
import router from './router'
import { useAuth } from './composables/useAuth.js'
import { registrarCaducidadSesion } from './services/api.js'
import '@fontsource-variable/inter/wght.css'
import './assets/main.css'

// cerrarSesion también olvida el usuario en memoria; si solo se borrara el almacenamiento, el router
// seguiría viendo la sesión activa y regresaría del login al tablero sin permitir entrar de nuevo.
registrarCaducidadSesion(() => {
  useAuth().cerrarSesion()
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
