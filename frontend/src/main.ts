import { createApp } from 'vue'
import App from './App.vue'
import './assets/main.css' // Archivo con el reset de CSS y scrollbar
import { registerSW } from 'virtual:pwa-register'

registerSW({ immediate: true })

const app = createApp(App)
app.mount('#app')