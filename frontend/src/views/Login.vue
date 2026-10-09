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
  padding: 1.25rem;
  background:
    radial-gradient(circle at 15% 15%, rgb(37 99 235 / 0.18), transparent 45%),
    radial-gradient(circle at 85% 80%, rgb(56 189 248 / 0.12), transparent 40%),
    var(--fondo);
}

.acceso__tarjeta {
  width: 100%;
  max-width: 400px;
  padding: 1.75rem;
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
  border-radius: 14px;
  background: linear-gradient(140deg, #2563eb, #38bdf8);
  color: #fff;
  font-weight: 800;
  letter-spacing: 0.05em;
}

.acceso__cabecera h1 {
  font-size: 1.35rem;
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
  border-radius: 8px;
  font-size: 0.8125rem;
  white-space: pre-line;
}

.acceso__aviso {
  background: rgb(245 158 11 / 0.12);
  border: 1px solid rgb(245 158 11 / 0.4);
  color: #fcd34d;
}

.acceso__error {
  background: rgb(239 68 68 / 0.12);
  border: 1px solid rgb(239 68 68 / 0.4);
  color: #fca5a5;
}

.acceso__pie {
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--borde);
  font-size: 0.72rem;
  color: #64748b;
  text-align: center;
}
</style>
