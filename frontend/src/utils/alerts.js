import Swal from 'sweetalert2';

const GioSwal = Swal.mixin({
  customClass: {
    confirmButton: 'px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium mx-1',
    cancelButton: 'px-4 py-2 bg-gray-500 text-white rounded-lg hover:bg-gray-600 font-medium mx-1',
    popup: 'rounded-2xl shadow-2xl border border-gray-100',
  },
  buttonsStyling: false,
});

export const mostrarExito = (titulo, mensaje = '') => {
  return GioSwal.fire({
    icon: 'success',
    title: titulo,
    text: mensaje,
    timer: 2500,
    showConfirmButton: false,
    timerProgressBar: true,
  });
};

export const mostrarError = (titulo, mensaje = '') => {
  return GioSwal.fire({
    icon: 'error',
    title: titulo,
    text: mensaje,
    confirmButtonText: 'Aceptar',
  });
};

export const mostrarAdvertencia = (titulo, mensaje = '') => {
  return GioSwal.fire({
    icon: 'warning',
    title: titulo,
    text: mensaje,
    confirmButtonText: 'Entendido',
  });
};

export const confirmarAccion = async (titulo, mensaje) => {
  const result = await GioSwal.fire({
    icon: 'question',
    title: titulo,
    text: mensaje,
    showCancelButton: true,
    confirmButtonText: 'Sí, continuar',
    cancelButtonText: 'Cancelar',
  });
  return result.isConfirmed;
};