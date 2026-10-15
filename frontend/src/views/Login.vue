<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { rutaInicialPara, useAuth } from '../composables/useAuth.js'

const route = useRoute()
const router = useRouter()
const { iniciarSesion, cargando, errorLogin } = useAuth()

const expediente = ref('')
const password = ref('')
const aviso = ref('')

onMounted(() => {
  if (route.query.expirada) aviso.value = 'Su sesión expiró. Vuelva a identificarse.'
})

const enviar = async () => {
  aviso.value = ''
  if (!expediente.value.trim() || !password.value) return
  try {
    const usuario = await iniciarSesion(expediente.value, password.value)
    const destino = route.query.redirigir || rutaInicialPara(usuario?.rol)
    await router.replace(destino)
  } catch {
    password.value = ''
  }
}
</script>

<template>
  <div class="acceso">
    <section class="acceso__tarjeta gio-panel">
      <header class="acceso__cabecera">
        <span class="acceso__insignia">GIO</span>
        <h1>Sistema GIO</h1>
        <p>Gestión de Incidencias y Enlace Operativo — CASE Puebla</p>
      </header>

      <form class="acceso__forma" @submit.prevent="enviar">
        <p v-if="aviso" class="acceso__aviso" role="status">{{ aviso }}</p>
        <p v-if="errorLogin" class="acceso__error" role="alert">{{ errorLogin }}</p>

        <div>
          <label class="gio-etiqueta" for="expediente">Expediente</label>
          <input
            id="expediente"
            v-model="expediente"
            type="text"
            inputmode="text"
            autocomplete="username"
            autocapitalize="characters"
            spellcheck="false"
            placeholder="OQU-8821"
            required
          />
        </div>

        <div>
          <label class="gio-etiqueta" for="password">Contraseña</label>
          <input
            id="password"
            v-model="password"
            type="password"
            autocomplete="current-password"
            placeholder="••••••••"
            required
          />
        </div>

        <button
          type="submit"
          class="gio-boton gio-boton--primario gio-boton--tactil"
          :disabled="cargando"
        >
          {{ cargando ? 'Autenticando…' : 'Iniciar sesión' }}
        </button>
      </form>

      <footer class="acceso__pie">
        Acceso restringido al personal de Planta Interna y Planta Externa. Si olvidó su contraseña,
        solicite el restablecimiento a la Gerencia.
      </footer>
    </section>
  </div>
</template>

<style scoped>
.acceso {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 20px;
  background-color: var(--fondo);
}

.acceso__tarjeta {
  width: 100%;
  max-width: 400px;
  padding: 32px;
}

.acceso__cabecera {
  text-align: center;
  margin-bottom: 1.5rem;
}

.acceso__insignia {
  display: grid;
  place-items: center;
  width: 54px;
  height: 54px;
  margin: 0 auto 0.85rem;
  border-radius: var(--radio);
  background: var(--barra);
  color: var(--sobre-barra);
  font-weight: 800;
  letter-spacing: 0.05em;
}

.acceso__cabecera h1 {
  font-size: 1.5rem;
}

.acceso__cabecera p {
  margin: 0.35rem 0 0;
  font-size: 0.8125rem;
  color: var(--apagado);
}

.acceso__forma {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.acceso__aviso,
.acceso__error {
  margin: 0;
  padding: 0.6rem 0.75rem;
  border-radius: var(--radio);
  font-size: 0.8125rem;
  white-space: pre-line;
}

.acceso__aviso {
  background: rgb(245 158 11 / 0.12);
  border: 1px solid rgb(245 158 11 / 0.4);
  color: var(--ambar-texto);
}

.acceso__error {
  background: rgb(239 68 68 / 0.12);
  border: 1px solid rgb(239 68 68 / 0.4);
  color: var(--rojo-texto);
}

.acceso__pie {
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--borde);
  font-size: 0.72rem;
  color: var(--tenue);
  text-align: center;
}
</style>
