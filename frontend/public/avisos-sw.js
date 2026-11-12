// Se carga dentro del service worker de GIO: al tocar una notificación del sistema de un mensaje
// nuevo, lleva a la ventana de GIO (o abre una) directo al chat de ese folio.
self.addEventListener('notificationclick', (evento) => {
  evento.notification.close()
  const destino = evento.notification.data?.url || '/'
  evento.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(async (ventanas) => {
      const ventana = ventanas[0]
      if (!ventana) return self.clients.openWindow(destino)
      await ventana.focus()
      return ventana.navigate ? ventana.navigate(destino) : undefined
    }),
  )
})
