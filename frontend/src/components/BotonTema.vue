<script setup>
import { computed } from 'vue'
import { useTema } from '../composables/useTema.js'

const { tema, alternarTema } = useTema()

const etiqueta = computed(() =>
  tema.value === 'dark' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro',
)
</script>

<template>
  <button
    type="button"
    class="gio-boton gio-boton--secundario boton-tema"
    :aria-label="etiqueta"
    :title="etiqueta"
    @click="alternarTema"
  >
    <!-- Sol: se muestra en modo oscuro para pasar a claro -->
    <svg
      v-if="tema === 'dark'"
      viewBox="0 0 24 24"
      width="18"
      height="18"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="4" />
      <path
        d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"
      />
    </svg>
    <!-- Luna: se muestra en modo claro para pasar a oscuro -->
    <svg
      v-else
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
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  </button>
</template>

<style scoped>
.boton-tema {
  padding: 0.5rem;
  width: 40px;
  height: 40px;
  border-radius: var(--radio-pildora);
}
</style>
