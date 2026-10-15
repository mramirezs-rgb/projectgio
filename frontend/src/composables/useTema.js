import { ref, watch } from 'vue'

const CLAVE = 'gio_tema'
const COLOR_BARRA = { dark: '#101214', light: '#101214' }

const leerGuardado = () => {
  try {
    const valor = localStorage.getItem(CLAVE)
    if (valor === 'dark' || valor === 'light') return valor
  } catch {
    // Almacenamiento bloqueado: se usa la preferencia del sistema.
  }
  return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

const aplicar = (valor) => {
  document.documentElement.dataset.theme = valor
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', COLOR_BARRA[valor])
}

// Estado compartido: todos los componentes ven el mismo tema.
const tema = ref(leerGuardado())
aplicar(tema.value)

watch(tema, (valor) => {
  aplicar(valor)
  try {
    localStorage.setItem(CLAVE, valor)
  } catch {
    // Sin almacenamiento el tema dura solo esta sesión.
  }
})

export function useTema() {
  const alternarTema = () => {
    tema.value = tema.value === 'dark' ? 'light' : 'dark'
  }
  return { tema, alternarTema }
}
