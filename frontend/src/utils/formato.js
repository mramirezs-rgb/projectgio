export const formatearFecha = (valor, conHora = true) => {
  if (!valor) return '—'
  const fecha = new Date(valor)
  if (Number.isNaN(fecha.getTime())) return '—'
  return fecha.toLocaleString('es-MX', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    ...(conHora ? { hour: '2-digit', minute: '2-digit' } : {}),
  })
}

export const formatearHoras = (horas) => {
  if (horas === null || horas === undefined || horas === '') return '—'
  const total = Number(horas)
  if (Number.isNaN(total)) return '—'
  if (total < 24) return `${total.toFixed(1)} h`
  const dias = Math.floor(total / 24)
  const resto = total - dias * 24
  return `${dias}d ${resto.toFixed(0)}h`
}

export const formatearBytes = (bytes) => {
  const valor = Number(bytes) || 0
  if (valor < 1024) return `${valor} B`
  if (valor < 1024 * 1024) return `${(valor / 1024).toFixed(0)} KB`
  return `${(valor / (1024 * 1024)).toFixed(2)} MB`
}

const ESCAPAR_CSV = (valor) => {
  const texto = valor === null || valor === undefined ? '' : String(valor)
  return `"${texto.replace(/"/g, '""')}"`
}

export const descargarCSV = (nombreArchivo, cabeceras, filas) => {
  const lineas = [cabeceras.map(ESCAPAR_CSV).join(',')]
  for (const fila of filas) lineas.push(fila.map(ESCAPAR_CSV).join(','))
  const contenido = `﻿${lineas.join('\r\n')}`
  const blob = new Blob([contenido], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const enlace = document.createElement('a')
  enlace.href = url
  enlace.download = nombreArchivo
  document.body.appendChild(enlace)
  enlace.click()
  document.body.removeChild(enlace)
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export const marcaDeTiempo = () => {
  const ahora = new Date()
  const dos = (n) => String(n).padStart(2, '0')
  return (
    `${ahora.getFullYear()}${dos(ahora.getMonth() + 1)}${dos(ahora.getDate())}` +
    `_${dos(ahora.getHours())}${dos(ahora.getMinutes())}`
  )
}
