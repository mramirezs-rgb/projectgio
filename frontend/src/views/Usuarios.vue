<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  createUsuario,
  desactivarUsuario,
  getCatalogos,
  getUsuarios,
  mensajeDeError,
  updateUsuario,
} from '../services/api.js'
import { confirmarAccion, mostrarError, mostrarExito, notificar } from '../utils/alerts.js'
import { formatearFecha } from '../utils/formato.js'

const FORM_VACIO = {
  id: null,
  expediente: '',
  first_name: '',
  last_name: '',
  email: '',
  telefono: '',
  rol: 'TECNICO',
  area_operativa: '',
  is_active: true,
  password: '',
}

const cargando = ref(false)
const guardando = ref(false)
const problema = ref('')
const usuarios = ref([])
const roles = ref([])
const areas = ref([])
const busqueda = ref('')
const formulario = ref({ ...FORM_VACIO })
const modalAbierto = ref(false)
const editando = computed(() => !!formulario.value.id)

const cargar = async () => {
  cargando.value = true
  problema.value = ''
  try {
    const { data } = await getUsuarios({ search: busqueda.value || undefined, page_size: 200 })
    usuarios.value = Array.isArray(data) ? data : data.results || []
  } catch (error) {
    problema.value = mensajeDeError(error, 'No se pudo consultar el catálogo de usuarios.')
  } finally {
    cargando.value = false
  }
}

onMounted(async () => {
  try {
    const { data } = await getCatalogos()
    roles.value = data.roles || []
    areas.value = data.areas || []
  } catch {
    roles.value = []
    areas.value = []
  }
  await cargar()
})

let temporizador = null
const buscarConRetardo = () => {
  clearTimeout(temporizador)
  temporizador = setTimeout(cargar, 350)
}

const abrirNuevo = () => {
  formulario.value = { ...FORM_VACIO }
  modalAbierto.value = true
}

const abrirEditar = (usuario) => {
  formulario.value = { ...FORM_VACIO, ...usuario, password: '' }
  modalAbierto.value = true
}

const guardar = async () => {
  const datos = { ...formulario.value }
  if (!datos.expediente.trim()) {
    mostrarError('Datos incompletos', 'El expediente es obligatorio.')
    return
  }
  if (!editando.value && !datos.password) {
    mostrarError('Datos incompletos', 'Defina una contraseña inicial para el nuevo usuario.')
    return
  }
  if (!datos.password) delete datos.password
  delete datos.id
  delete datos.nombre
  delete datos.rol_display
  delete datos.folios_asignados
  delete datos.last_login
  delete datos.date_joined

  guardando.value = true
  try {
    if (editando.value) {
      await updateUsuario(formulario.value.id, datos)
      notificar('Usuario actualizado')
    } else {
      await createUsuario(datos)
      mostrarExito('Usuario creado', `${datos.expediente} ya puede iniciar sesión en GIO.`)
    }
    modalAbierto.value = false
    await cargar()
  } catch (error) {
    mostrarError('No se pudo guardar el usuario', mensajeDeError(error))
  } finally {
    guardando.value = false
  }
}

const alternarActivo = async (usuario) => {
  if (usuario.is_active) {
    const confirmado = await confirmarAccion(
      'Dar de baja',
      `${usuario.expediente} dejará de poder iniciar sesión. Sus folios históricos se conservan.`,
      'Dar de baja',
    )
    if (!confirmado) return
    try {
      await desactivarUsuario(usuario.id)
      notificar('Usuario dado de baja')
      await cargar()
    } catch (error) {
      mostrarError('No se pudo dar de baja', mensajeDeError(error))
    }
    return
  }
  try {
    await updateUsuario(usuario.id, { is_active: true })
    notificar('Usuario reactivado')
    await cargar()
  } catch (error) {
    mostrarError('No se pudo reactivar', mensajeDeError(error))
  }
}
</script>

<template>
  <div class="usuarios">
    <header class="usuarios__cabecera">
      <div>
        <h1>Usuarios del sistema</h1>
        <p>Altas, bajas y cambios de rol. Operación exclusiva de Gerencia.</p>
      </div>
      <div class="usuarios__acciones">
        <input
          v-model.trim="busqueda"
          type="search"
          placeholder="Buscar por expediente o nombre…"
          aria-label="Buscar usuario"
          @input="buscarConRetardo"
        />
        <button type="button" class="gio-boton gio-boton--primario" @click="abrirNuevo">
          Nuevo usuario
        </button>
      </div>
    </header>

    <p v-if="problema" class="usuarios__error" role="alert">{{ problema }}</p>
    <p v-else-if="cargando" class="gio-cargando">Consultando usuarios…</p>

    <div v-else class="usuarios__caja gio-panel">
      <table class="listado">
        <thead>
          <tr>
            <th>Expediente</th>
            <th>Nombre</th>
            <th>Rol</th>
            <th>Área</th>
            <th>Folios activos</th>
            <th>Último acceso</th>
            <th>Estado</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="usuarios.length === 0">
            <td colspan="8" class="gio-vacio">No se encontraron usuarios.</td>
          </tr>
          <tr v-for="usuario in usuarios" :key="usuario.id" :class="{ inactivo: !usuario.is_active }">
            <td class="listado__mono">{{ usuario.expediente }}</td>
            <td>{{ usuario.nombre }}</td>
            <td>{{ usuario.rol_display }}</td>
            <td>{{ usuario.area_operativa || '—' }}</td>
            <td>{{ usuario.folios_asignados ?? 0 }}</td>
            <td class="listado__fecha">{{ formatearFecha(usuario.last_login) }}</td>
            <td>
              <span class="gio-pastilla" :class="usuario.is_active ? 'gio-pastilla--liquidado' : 'gio-pastilla--pendiente'">
                {{ usuario.is_active ? 'Activo' : 'Baja' }}
              </span>
            </td>
            <td class="listado__acciones">
              <button
                type="button"
                class="gio-boton gio-boton--secundario"
                @click="abrirEditar(usuario)"
              >
                Editar
              </button>
              <button
                type="button"
                class="gio-boton"
                :class="usuario.is_active ? 'gio-boton--peligro' : 'gio-boton--secundario'"
                @click="alternarActivo(usuario)"
              >
                {{ usuario.is_active ? 'Baja' : 'Reactivar' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="modalAbierto" class="velo" role="dialog" aria-modal="true" @click.self="modalAbierto = false">
      <form class="caja gio-panel" @submit.prevent="guardar">
        <header class="caja__cabecera">
          <h2>{{ editando ? `Editar ${formulario.expediente}` : 'Nuevo usuario' }}</h2>
          <button type="button" class="caja__cerrar" aria-label="Cerrar" @click="modalAbierto = false">
            &times;
          </button>
        </header>

        <div class="caja__cuerpo">
          <div>
            <label class="gio-etiqueta" for="u-exp">Expediente *</label>
            <input
              id="u-exp"
              v-model.trim="formulario.expediente"
              type="text"
              autocapitalize="characters"
              placeholder="OQU-8821"
              required
            />
          </div>
          <div>
            <label class="gio-etiqueta" for="u-rol">Rol *</label>
            <select id="u-rol" v-model="formulario.rol" required>
              <option v-for="rol in roles" :key="rol.id" :value="rol.id">{{ rol.nombre }}</option>
            </select>
          </div>
          <div>
            <label class="gio-etiqueta" for="u-nombre">Nombre(s)</label>
            <input id="u-nombre" v-model.trim="formulario.first_name" type="text" />
          </div>
          <div>
            <label class="gio-etiqueta" for="u-apellido">Apellidos</label>
            <input id="u-apellido" v-model.trim="formulario.last_name" type="text" />
          </div>
          <div>
            <label class="gio-etiqueta" for="u-area">Área operativa</label>
            <select id="u-area" v-model="formulario.area_operativa">
              <option value="">Sin asignar</option>
              <option v-for="area in areas" :key="area.id" :value="area.id">{{ area.nombre }}</option>
            </select>
          </div>
          <div>
            <label class="gio-etiqueta" for="u-tel">Teléfono</label>
            <input id="u-tel" v-model.trim="formulario.telefono" type="tel" />
          </div>
          <div>
            <label class="gio-etiqueta" for="u-email">Correo</label>
            <input id="u-email" v-model.trim="formulario.email" type="email" />
          </div>
          <div>
            <label class="gio-etiqueta" for="u-pass">
              {{ editando ? 'Nueva contraseña (opcional)' : 'Contraseña inicial *' }}
            </label>
            <input
              id="u-pass"
              v-model="formulario.password"
              type="password"
              autocomplete="new-password"
              placeholder="Mínimo 8 caracteres"
            />
          </div>
        </div>

        <footer class="caja__pie">
          <button type="button" class="gio-boton gio-boton--secundario" @click="modalAbierto = false">
            Cancelar
          </button>
          <button type="submit" class="gio-boton gio-boton--primario" :disabled="guardando">
            {{ guardando ? 'Guardando…' : editando ? 'Guardar cambios' : 'Crear usuario' }}
          </button>
        </footer>
      </form>
    </div>
  </div>
</template>

<style scoped>
.usuarios {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.usuarios__cabecera {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.usuarios__cabecera h1 {
  font-size: 1.3rem;
}

.usuarios__cabecera p {
  margin: 0.2rem 0 0;
  font-size: 0.78rem;
  color: var(--apagado);
}

.usuarios__acciones {
  display: flex;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.usuarios__acciones input {
  min-width: 240px;
}

.usuarios__error {
  margin: 0;
  padding: 0.7rem 0.85rem;
  border-radius: 8px;
  background: rgb(239 68 68 / 0.12);
  border: 1px solid rgb(239 68 68 / 0.4);
  color: #fca5a5;
  font-size: 0.8125rem;
}

.usuarios__caja {
  overflow-x: auto;
}

.listado {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

.listado th {
  text-align: left;
  background-color: #0a1222;
  padding: 0.65rem 0.8rem;
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--apagado);
  border-bottom: 1px solid var(--borde);
  white-space: nowrap;
}

.listado td {
  padding: 0.55rem 0.8rem;
  border-bottom: 1px solid rgb(36 51 82 / 0.5);
}

.listado tbody tr:hover {
  background-color: rgb(36 51 82 / 0.3);
}

.inactivo {
  opacity: 0.55;
}

.listado__mono {
  font-family: ui-monospace, 'SFMono-Regular', Menlo, monospace;
  font-weight: 600;
  color: var(--acento-claro);
}

.listado__fecha {
  color: var(--apagado);
  white-space: nowrap;
  font-size: 0.75rem;
}

.listado__acciones {
  display: flex;
  gap: 0.4rem;
}

.listado__acciones .gio-boton {
  padding: 0.3rem 0.65rem;
  font-size: 0.72rem;
}

.velo {
  position: fixed;
  inset: 0;
  background-color: rgb(2 6 23 / 0.8);
  backdrop-filter: blur(3px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  z-index: 100;
}

.caja {
  width: 100%;
  max-width: 640px;
  max-height: 92vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.caja__cabecera {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.9rem 1.2rem;
  background-color: #0a1222;
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
  padding: 1.2rem;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.85rem;
  overflow-y: auto;
}

.caja__pie {
  display: flex;
  justify-content: flex-end;
  gap: 0.7rem;
  padding: 1rem 1.2rem;
  border-top: 1px solid var(--borde);
}

@media (max-width: 640px) {
  .caja__cuerpo {
    grid-template-columns: 1fr;
  }
}
</style>
