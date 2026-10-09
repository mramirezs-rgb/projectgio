import Swal from 'sweetalert2'

const GioSwal = Swal.mixin({
  background: '#101a2e',
  color: '#e8eefc',
  customClass: {
    popup: 'gio-swal',
    title: 'gio-swal__title',
    htmlContainer: 'gio-swal__texto',
    confirmButton: 'gio-swal__btn gio-swal__btn--primario',
    cancelButton: 'gio-swal__btn gio-swal__btn--secundario',
    denyButton: 'gio-swal__btn gio-swal__btn--peligro',
  },
  buttonsStyling: false,
  reverseButtons: true,
})

export const mostrarExito = (titulo, mensaje = '') =>
  GioSwal.fire({
    icon: 'success',
    title: titulo,
    text: mensaje,
    timer: 2200,
    timerProgressBar: true,
    showConfirmButton: false,
  })

export const mostrarError = (titulo, mensaje = '') =>
  GioSwal.fire({
    icon: 'error',
    title: titulo,
    html: mensaje ? `<pre class="gio-swal__detalle">${escapar(mensaje)}</pre>` : '',
    confirmButtonText: 'Aceptar',
  })

export const mostrarAdvertencia = (titulo, mensaje = '') =>
  GioSwal.fire({ icon: 'warning', title: titulo, text: mensaje, confirmButtonText: 'Entendido' })

export const mostrarInfo = (titulo, mensaje = '') =>
  GioSwal.fire({ icon: 'info', title: titulo, text: mensaje, confirmButtonText: 'Cerrar' })

export const confirmarAccion = async (titulo, mensaje, textoConfirmar = 'Sí, continuar') => {
  const { isConfirmed } = await GioSwal.fire({
    icon: 'question',
    title: titulo,
    text: mensaje,
    showCancelButton: true,
    confirmButtonText: textoConfirmar,
    cancelButtonText: 'Cancelar',
    focusCancel: true,
  })
  return isConfirmed
}

export const pedirTexto = async (titulo, etiqueta, valorInicial = '') => {
  const { isConfirmed, value } = await GioSwal.fire({
    title: titulo,
    input: 'textarea',
    inputLabel: etiqueta,
    inputValue: valorInicial,
    inputAttributes: { 'aria-label': etiqueta, rows: '4' },
    showCancelButton: true,
    confirmButtonText: 'Guardar',
    cancelButtonText: 'Cancelar',
    inputValidator: (texto) => (texto && texto.trim() ? null : 'Este campo es obligatorio.'),
  })
  return isConfirmed ? String(value).trim() : null
}

export const notificar = (titulo, icono = 'success') =>
  GioSwal.fire({
    toast: true,
    position: 'top-end',
    icon: icono,
    title: titulo,
    showConfirmButton: false,
    timer: 2600,
    timerProgressBar: true,
  })

function escapar(texto) {
  return String(texto)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}
