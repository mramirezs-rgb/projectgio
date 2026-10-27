<script setup>
import { computed, onUnmounted, ref } from 'vue'
import { useAuth } from '../composables/useAuth.js'
import { cambiarPassword, guardarCorreoRecuperacion, mensajeDeError } from '../services/api.js'
import { notificar } from '../utils/alerts.js'

const { usuario, aplicarPerfil } = useAuth()

const abierto = ref(false)
// Qué formulario se está guardando: 'password', 'correo' o ninguno.
const guardando = ref('')
const sinCorreo = computed(() => !usuario.value?.email)
const etiqueta = computed(() =>
  sinCorreo.value
    ? 'Mi cuenta: contraseña y correo de recuperación (falta registrar el correo)'
    : 'Mi cuenta: contraseña y correo de recuperación',
)

const formPassword = ref({ actual: '', nueva: '', confirmacion: '' })
const erroresPassword = ref({})
const formCorreo = ref({ email: '', actual: '' })
const erroresCorreo = ref({})

// El servidor responde los errores por campo (password_actual, password_nueva, email).
const errorPorCampo = (error, respaldo) => {
  const datos = error?.response?.data
  if (datos && typeof datos === 'object' && !datos.detail) {
    return Object.fromEntries(
      Object.entries(datos).map(([campo, valor]) => [campo, [].concat(valor).join(' ')]),
    )
  }
  return { general: mensajeDeError(error, respaldo) }
}

const alPulsarTecla = (evento) => {
  if (evento.key === 'Escape') cerrar()
}

const abrir = () => {
  formPassword.value = { actual: '', nueva: '', confirmacion: '' }
  formCorreo.value = { email: usuario.value?.email || '', actual: '' }
  erroresPassword.value = {}
  erroresCorreo.value = {}
  abierto.value = true
  document.addEventListener('keydown', alPulsarTecla)
}

const cerrar = () => {
  abierto.value = false
  document.removeEventListener('keydown', alPulsarTecla)
}

const guardarPassword = async () => {
  const { actual, nueva, confirmacion } = formPassword.value
  const fallos = {}
  if (!actual) fallos.password_actual = 'Escriba su contraseña actual.'
  if (nueva.length < 8) fallos.password_nueva = 'Use al menos 8 caracteres.'
  else if (nueva !== confirmacion) fallos.confirmacion = 'Las dos contraseñas no coinciden.'
  erroresPassword.value = fallos
  if (Object.keys(fallos).length) return

  guardando.value = 'password'
  try {
    await cambiarPassword({ password_actual: actual, password_nueva: nueva })
    notificar('Contraseña actualizada')
    cerrar()
  } catch (error) {
    erroresPassword.value = errorPorCampo(error, 'No se pudo cambiar la contraseña.')
  } finally {
    guardando.value = ''
  }
}

const guardarCorreo = async () => {
  if (!formCorreo.value.actual) {
    erroresCorreo.value = { password_actual: 'Escriba su contraseña actual para confirmar.' }
    return
  }
  erroresCorreo.value = {}
  guardando.value = 'correo'
  try {
    const { data } = await guardarCorreoRecuperacion({
      email: formCorreo.value.email.trim(),
      password_actual: formCorreo.value.actual,
    })
    aplicarPerfil(data)
    notificar(data.email ? 'Correo de recuperación guardado' : 'Correo de recuperación eliminado')
    cerrar()
  } catch (error) {
    erroresCorreo.value = errorPorCampo(error, 'No se pudo guardar el correo.')
  } finally {
    guardando.value = ''
  }
}

onUnmounted(() => document.removeEventListener('keydown', alPulsarTecla))
</script>

<template>
  <button
    type="button"
    class="gio-boton gio-boton--secundario cuenta__boton"
    :aria-label="etiqueta"
    :title="etiqueta"
    aria-haspopup="dialog"
    @click="abrir"
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
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
    <span v-if="sinCorreo" class="cuenta__punto" aria-hidden="true"></span>
  </button>

  <!-- Fuera de la barra superior para que el velo cubra toda la pantalla. -->
  <Teleport to="body">
    <div
      v-if="abierto"
      class="velo"
      role="dialog"
      aria-modal="true"
      aria-labelledby="cuenta-titulo"
      @click.self="cerrar"
    >
      <div class="caja gio-panel">
        <header class="caja__cabecera">
          <h2 id="cuenta-titulo">Mi cuenta · {{ usuario?.expediente }}</h2>
          <button type="button" class="caja__cerrar" aria-label="Cerrar" @click="cerrar">
            &times;
          </button>
        </header>

        <div class="caja__cuerpo">
          <form class="seccion" @submit.prevent="guardarPassword">
            <h3 class="gio-etiqueta">Cambiar contraseña</h3>
            <p v-if="erroresPassword.general" class="seccion__error" role="alert">
              {{ erroresPassword.general }}
            </p>
            <div>
              <label class="gio-etiqueta" for="cuenta-actual">Contraseña actual</label>
              <input
                id="cuenta-actual"
                v-model="formPassword.actual"
                type="password"
                autocomplete="current-password"
              />
              <small v-if="erroresPassword.password_actual" class="seccion__error">
                {{ erroresPassword.password_actual }}
              </small>
            </div>
            <div>
              <label class="gio-etiqueta" for="cuenta-nueva">Nueva contraseña</label>
              <input
                id="cuenta-nueva"
                v-model="formPassword.nueva"
                type="password"
                autocomplete="new-password"
                placeholder="Mínimo 8 caracteres"
              />
              <small v-if="erroresPassword.password_nueva" class="seccion__error">
                {{ erroresPassword.password_nueva }}
              </small>
            </div>
            <div>
              <label class="gio-etiqueta" for="cuenta-confirmacion">Repita la nueva contraseña</label>
              <input
                id="cuenta-confirmacion"
                v-model="formPassword.confirmacion"
                type="password"
                autocomplete="new-password"
              />
              <small v-if="erroresPassword.confirmacion" class="seccion__error">
                {{ erroresPassword.confirmacion }}
              </small>
            </div>
            <button type="submit" class="gio-boton gio-boton--primario" :disabled="!!guardando">
              {{ guardando === 'password' ? 'Guardando…' : 'Cambiar contraseña' }}
            </button>
          </form>

          <form class="seccion" @submit.prevent="guardarCorreo">
            <h3 class="gio-etiqueta">Correo de recuperación</h3>
            <p class="seccion__pista">
              Si olvida su contraseña, a este correo le llega el enlace para crear una nueva.
            </p>
            <p v-if="sinCorreo" class="seccion__aviso">Aún no tiene correo de recuperación.</p>
            <p v-if="erroresCorreo.general" class="seccion__error" role="alert">
              {{ erroresCorreo.general }}
            </p>
            <div>
              <label class="gio-etiqueta" for="cuenta-correo">Correo</label>
              <input
                id="cuenta-correo"
                v-model="formCorreo.email"
                type="email"
                autocomplete="email"
                placeholder="nombre@empresa.com.mx"
              />
              <small v-if="erroresCorreo.email" class="seccion__error">
                {{ erroresCorreo.email }}
              </small>
            </div>
            <div>
              <label class="gio-etiqueta" for="cuenta-confirmar">Contraseña actual</label>
              <input
                id="cuenta-confirmar"
                v-model="formCorreo.actual"
                type="password"
                autocomplete="current-password"
              />
              <small v-if="erroresCorreo.password_actual" class="seccion__error">
                {{ erroresCorreo.password_actual }}
              </small>
            </div>
            <button type="submit" class="gio-boton gio-boton--primario" :disabled="!!guardando">
              {{ guardando === 'correo' ? 'Guardando…' : 'Guardar correo' }}
            </button>
          </form>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.cuenta__boton {
  position: relative;
  padding: 0.5rem;
  width: 40px;
  height: 40px;
  border-radius: var(--radio-pildora);
}

/* Recordatorio discreto mientras no haya correo de recuperación. */
.cuenta__punto {
  position: absolute;
  top: 0;
  right: 0;
  width: 10px;
  height: 10px;
  border-radius: var(--radio-pildora);
  background-color: var(--alerta);
  box-shadow: 0 0 0 2px var(--barra);
}

.velo {
  position: fixed;
  inset: 0;
  background-color: var(--velo);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  z-index: 100;
}

.caja {
  width: 100%;
  max-width: 460px;
  max-height: 92vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  color: var(--texto);
}

.caja__cabecera {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.9rem 1.2rem;
  background-color: var(--superficie);
  border-bottom: 1px solid var(--borde);
}

.caja__cabecera h2 {
  font-size: 1rem;
}

.caja__cerrar {
  background: none;
  border: none;
  color: var(--apagado);
  font-size: 1.6rem;
  line-height: 1;
}

.caja__cuerpo {
  overflow-y: auto;
}

.seccion {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  padding: 1.2rem;
}

.seccion + .seccion {
  border-top: 1px solid var(--borde);
}

.seccion h3 {
  margin: 0;
}

.seccion .gio-boton {
  align-self: flex-end;
}

.seccion__pista,
.seccion__aviso {
  margin: 0;
  font-size: 0.8125rem;
}

.seccion__pista {
  color: var(--apagado);
}

.seccion__aviso {
  color: var(--ambar-texto);
}

.seccion__error {
  display: block;
  margin: 0.25rem 0 0;
  font-size: 0.78rem;
  color: var(--rojo-texto);
}
</style>
