<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { rutaInicialPara, useAuth } from '../composables/useAuth.js'
import { mensajeDeError, restablecerPassword, solicitarRecuperacion } from '../services/api.js'

const route = useRoute()
const router = useRouter()
const { iniciarSesion, cargando, errorLogin } = useAuth()

const AVISOS = {
  expirada: 'Su sesión expiró. Vuelva a identificarse.',
  restablecida: 'Contraseña actualizada. Ya puede iniciar sesión con la nueva.',
}

const expediente = ref('')
const password = ref('')
const aviso = ref('')

// Tres pantallas: entrar, pedir el enlace por correo y crear la contraseña con ese enlace.
const pidiendoEnlace = ref(false)
const modo = computed(() => {
  if (route.name === 'restablecer') return 'restablecer'
  return pidiendoEnlace.value ? 'recuperar' : 'entrar'
})

const enviando = ref(false)
const problema = ref('')
const respuestaEnlace = ref('')
const nueva = ref('')
const confirmacion = ref('')

watch(
  () => route.query,
  (query) => {
    const clave = Object.keys(AVISOS).find((nombre) => query[nombre])
    aviso.value = clave ? AVISOS[clave] : ''
  },
  { immediate: true },
)

// Las reglas de contraseña llegan en `password_nueva`; se muestran sin el nombre del campo.
const textoDeError = (error, respaldo) => {
  const detalle = error?.response?.data?.password_nueva
  return Array.isArray(detalle) ? detalle.join(' ') : mensajeDeError(error, respaldo)
}

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

const irARecuperar = async () => {
  pidiendoEnlace.value = true
  problema.value = ''
  respuestaEnlace.value = ''
  aviso.value = ''
  if (route.name !== 'login') await router.replace({ name: 'login' })
}

const volverAEntrar = async () => {
  pidiendoEnlace.value = false
  problema.value = ''
  respuestaEnlace.value = ''
  if (route.name !== 'login') await router.replace({ name: 'login' })
}

const pedirEnlace = async () => {
  if (!expediente.value.trim()) return
  enviando.value = true
  problema.value = ''
  try {
    const { data } = await solicitarRecuperacion(expediente.value.trim())
    respuestaEnlace.value = data.detail
  } catch (error) {
    problema.value = mensajeDeError(error, 'No se pudo enviar el correo.')
  } finally {
    enviando.value = false
  }
}

const guardarNueva = async () => {
  problema.value = ''
  if (nueva.value.length < 8) {
    problema.value = 'La contraseña debe tener al menos 8 caracteres.'
    return
  }
  if (nueva.value !== confirmacion.value) {
    problema.value = 'Las dos contraseñas no coinciden.'
    return
  }
  enviando.value = true
  try {
    await restablecerPassword({
      uid: route.params.uid,
      token: route.params.token,
      password_nueva: nueva.value,
    })
    nueva.value = ''
    confirmacion.value = ''
    await router.replace({ name: 'login', query: { restablecida: '1' } })
  } catch (error) {
    problema.value = textoDeError(error, 'No se pudo guardar la contraseña.')
  } finally {
    enviando.value = false
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

      <form v-if="modo === 'entrar'" class="acceso__forma" @submit.prevent="enviar">
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
        <button type="button" class="acceso__enlace" @click="irARecuperar">
          ¿Olvidó su contraseña?
        </button>
      </form>

      <form v-else-if="modo === 'recuperar'" class="acceso__forma" @submit.prevent="pedirEnlace">
        <h2 class="acceso__titulo">Recuperar contraseña</h2>

        <template v-if="respuestaEnlace">
          <p class="acceso__aviso acceso__aviso--ok" role="status">{{ respuestaEnlace }}</p>
          <button
            type="button"
            class="gio-boton gio-boton--primario gio-boton--tactil"
            @click="volverAEntrar"
          >
            Volver a iniciar sesión
          </button>
        </template>

        <template v-else>
          <p class="acceso__texto">
            Escriba su expediente. Le enviaremos un enlace al correo de recuperación que registró
            en GIO para que cree una nueva contraseña.
          </p>
          <p v-if="problema" class="acceso__error" role="alert">{{ problema }}</p>
          <div>
            <label class="gio-etiqueta" for="rec-expediente">Expediente</label>
            <input
              id="rec-expediente"
              v-model="expediente"
              type="text"
              autocomplete="username"
              autocapitalize="characters"
              spellcheck="false"
              placeholder="OQU-8821"
              required
            />
          </div>
          <button
            type="submit"
            class="gio-boton gio-boton--primario gio-boton--tactil"
            :disabled="enviando"
          >
            {{ enviando ? 'Enviando…' : 'Enviar enlace' }}
          </button>
          <button type="button" class="acceso__enlace" @click="volverAEntrar">
            Volver a iniciar sesión
          </button>
        </template>
      </form>

      <form v-else class="acceso__forma" @submit.prevent="guardarNueva">
        <h2 class="acceso__titulo">Nueva contraseña</h2>
        <p class="acceso__texto">
          Use al menos 8 caracteres. No use solo números ni algo parecido a su nombre o expediente.
        </p>
        <p v-if="problema" class="acceso__error" role="alert">{{ problema }}</p>
        <div>
          <label class="gio-etiqueta" for="nueva">Nueva contraseña</label>
          <input
            id="nueva"
            v-model="nueva"
            type="password"
            autocomplete="new-password"
            minlength="8"
            required
          />
        </div>
        <div>
          <label class="gio-etiqueta" for="confirmacion">Repita la contraseña</label>
          <input
            id="confirmacion"
            v-model="confirmacion"
            type="password"
            autocomplete="new-password"
            minlength="8"
            required
          />
        </div>
        <button
          type="submit"
          class="gio-boton gio-boton--primario gio-boton--tactil"
          :disabled="enviando"
        >
          {{ enviando ? 'Guardando…' : 'Guardar contraseña' }}
        </button>
        <button type="button" class="acceso__enlace" @click="irARecuperar">
          Pedir un enlace nuevo
        </button>
      </form>

      <footer class="acceso__pie">
        Acceso restringido al personal de Planta Interna y Planta Externa. Si no registró un correo
        de recuperación, solicite el cambio de contraseña a la Gerencia.
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
  border-radius: var(--radio-pildora);
  background: var(--acento);
  color: var(--sobre-acento);
  font-weight: 700;
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

.acceso__aviso--ok {
  background: rgb(34 197 94 / 0.12);
  border-color: rgb(34 197 94 / 0.4);
  color: var(--verde-texto);
}

.acceso__titulo {
  margin: 0;
  font-size: 1rem;
}

.acceso__texto {
  margin: 0;
  font-size: 0.8125rem;
  color: var(--apagado);
}

.acceso__enlace {
  align-self: center;
  padding: 0.25rem;
  border: none;
  background: none;
  color: var(--acento-claro);
  font-size: 0.8125rem;
  cursor: pointer;
}
.acceso__enlace:hover {
  text-decoration: underline;
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
