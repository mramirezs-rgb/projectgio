<script setup>
import { computed } from 'vue'
import { useChat } from '../composables/useChat.js'

// Franja fija bajo la barra: a diferencia del aviso emergente, no desaparece hasta que los
// mensajes se leen, así no se pierden si nadie estaba mirando cuando llegaron.
const { total, deGerencia, sinAtender, sinConexion, foliosConMensajes, recientes, irAlChat } =
  useChat()

const texto = computed(() => {
  const partes = [
    `Tiene ${total.value} ${total.value === 1 ? 'mensaje' : 'mensajes'} sin leer en ` +
      `${foliosConMensajes.value} ${foliosConMensajes.value === 1 ? 'folio' : 'folios'}`,
  ]
  if (deGerencia.value) partes.push(`${deGerencia.value} de Gerencia`)
  if (sinAtender.value) partes.push(`${sinAtender.value} que nadie ha atendido`)
  return partes.join(' · ')
})

const abrir = () => {
  const primero = recientes.value[0]
  if (primero) irAlChat(primero.id)
}
</script>

<template>
  <p v-if="sinConexion" class="franja franja--problema" role="alert">
    Sin conexión con el servidor: los mensajes nuevos no están llegando. Revise la red; GIO sigue
    intentando.
  </p>
  <div
    v-else-if="total"
    class="franja"
    :class="{ 'franja--gerencia': deGerencia }"
    role="status"
  >
    <span>{{ texto }}</span>
    <button type="button" class="franja__boton" @click="abrir">Ver mensajes</button>
  </div>
</template>

<style scoped>
.franja {
  margin: 0;
  padding: 8px 24px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 6px 16px;
  background-color: var(--acento);
  color: var(--sobre-acento);
  font-size: 0.8125rem;
  font-weight: 700;
}

.franja--gerencia,
.franja--problema {
  background-color: var(--peligro);
}

.franja__boton {
  padding: 4px 12px;
  background: none;
  border: 1px solid currentColor;
  color: inherit;
  font: inherit;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-size: 0.72rem;
  cursor: pointer;
}

@media (max-width: 640px) {
  .franja {
    padding: 8px 16px;
  }
}
</style>
