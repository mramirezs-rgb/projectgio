import { ref } from 'vue'

export const LIMITE_BYTES = 500 * 1024
const DIMENSION_MAXIMA = 1600
const CALIDADES = [0.82, 0.7, 0.6, 0.5, 0.42, 0.35, 0.28]
const TIPOS_ADMITIDOS = ['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif']

const soportaWebp = () => {
  try {
    return document.createElement('canvas').toDataURL('image/webp').startsWith('data:image/webp')
  } catch {
    return false
  }
}

const cargarBitmap = async (archivo) => {
  if ('createImageBitmap' in window) {
    try {
      return await createImageBitmap(archivo, { imageOrientation: 'from-image' })
    } catch {
      /* se intenta con HTMLImageElement */
    }
  }
  const url = URL.createObjectURL(archivo)
  try {
    return await new Promise((resolve, reject) => {
      const imagen = new Image()
      imagen.onload = () => resolve(imagen)
      imagen.onerror = () => reject(new Error('El archivo no es una imagen legible.'))
      imagen.src = url
    })
  } finally {
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
}

const dibujar = (fuente, ancho, alto) => {
  const lienzo = document.createElement('canvas')
  lienzo.width = ancho
  lienzo.height = alto
  const contexto = lienzo.getContext('2d')
  contexto.imageSmoothingEnabled = true
  contexto.imageSmoothingQuality = 'high'
  contexto.drawImage(fuente, 0, 0, ancho, alto)
  return lienzo
}

const aBlob = (lienzo, tipo, calidad) =>
  new Promise((resolve, reject) => {
    lienzo.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error('No se pudo codificar la imagen.'))),
      tipo,
      calidad,
    )
  })

export const comprimirImagen = async (archivo, { limite = LIMITE_BYTES } = {}) => {
  if (!archivo) throw new Error('No se recibió ningún archivo.')
  if (archivo.type && !TIPOS_ADMITIDOS.includes(archivo.type)) {
    throw new Error('Formato no admitido. Tome la foto con la cámara o elija un JPG/PNG.')
  }

  const bitmap = await cargarBitmap(archivo)
  const anchoOriginal = bitmap.width
  const altoOriginal = bitmap.height
  const tipoSalida = soportaWebp() ? 'image/webp' : 'image/jpeg'
  const extension = tipoSalida === 'image/webp' ? 'webp' : 'jpg'

  let escala = Math.min(1, DIMENSION_MAXIMA / Math.max(anchoOriginal, altoOriginal))
  let mejor = null

  for (let intento = 0; intento < 4; intento += 1) {
    const ancho = Math.max(320, Math.round(anchoOriginal * escala))
    const alto = Math.max(320, Math.round(altoOriginal * escala))
    const lienzo = dibujar(bitmap, ancho, alto)

    for (const calidad of CALIDADES) {
      const blob = await aBlob(lienzo, tipoSalida, calidad)
      mejor = { blob, ancho, alto, calidad }
      if (blob.size <= limite) {
        if (bitmap.close) bitmap.close()
        return finalizar(archivo, mejor, extension, tipoSalida, anchoOriginal, altoOriginal)
      }
    }
    escala *= 0.75
  }

  if (bitmap.close) bitmap.close()
  if (!mejor || mejor.blob.size > limite) {
    throw new Error(
      `No fue posible reducir la imagen por debajo de ${Math.round(limite / 1024)} KB. ` +
        'Tome la foto con menor resolución.',
    )
  }
  return finalizar(archivo, mejor, extension, tipoSalida, anchoOriginal, altoOriginal)
}

const finalizar = (original, mejor, extension, tipo, anchoOriginal, altoOriginal) => {
  const nombre = (original.name || 'evidencia').replace(/\.[^.]+$/, '')
  const archivo = new File([mejor.blob], `${nombre}.${extension}`, {
    type: tipo,
    lastModified: Date.now(),
  })
  return {
    archivo,
    bytesOriginales: original.size || 0,
    bytesFinales: archivo.size,
    ahorro:
      original.size > 0 ? Math.round((1 - archivo.size / original.size) * 100) : 0,
    dimensionOriginal: `${anchoOriginal}×${altoOriginal}`,
    dimensionFinal: `${mejor.ancho}×${mejor.alto}`,
    calidad: mejor.calidad,
  }
}

export function useCompresionImagen() {
  const comprimiendo = ref(false)
  const ultimoResultado = ref(null)

  const procesar = async (archivo, opciones) => {
    comprimiendo.value = true
    try {
      const resultado = await comprimirImagen(archivo, opciones)
      ultimoResultado.value = resultado
      return resultado
    } finally {
      comprimiendo.value = false
    }
  }

  return { comprimiendo, ultimoResultado, procesar, LIMITE_BYTES }
}
