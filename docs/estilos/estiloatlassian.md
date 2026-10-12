# estiloatlassian

Referencia de diseño catalogada para GIO, tomada del sistema visual de Atlassian (Jira, Confluence,
Trello). **No está aplicada**: el tema actual de GIO sigue siendo el de `frontend/src/assets/main.css`.
Se usa solo cuando se pida explícitamente "aplicar el estiloatlassian".

- Fuente original: [`fuentes/atlassian-DESIGN.md`](fuentes/atlassian-DESIGN.md) (copia sin modificar).
- Origen declarado en el archivo: https://www.atlassian.com
- Es una inspiración de estilo, no una marca: no se usan logotipos, nombres ni tipografías propietarias
  de Atlassian dentro de GIO.

## Idea central

Software empresarial que "desaparece" para que el equipo se concentre en el trabajo:

- **Contención**: paleta casi monocromática (negro casi puro + blanco) con **un solo acento**, azul
  marino apagado. Sin degradados, sin saturación, sin elementos decorativos.
- **Plano**: sin sombras ni capas; las tarjetas se separan con espacio en blanco, bordes finos y color.
- **Jerarquía por tipografía y tamaño**, no por color.
- **Rejilla de 4 px**: todo el espaciado sale de múltiplos de 4.
- **Movimiento rápido y discreto**: respuesta inmediata, sin animaciones que hagan esperar.
- **Accesible por defecto**: contrastes AAA y nunca comunicar un estado solo con color.

## Tokens

El archivo fuente se contradice entre su encabezado (YAML) y el texto. Se resolvió así:

| Token | Valor elegido | Uso | Nota |
| --- | --- | --- | --- |
| Primario | `#101214` | Barra de navegación, encabezados fuertes | Texto blanco encima (18.8:1) |
| Sobre primario | `#ffffff` | Texto e íconos sobre el primario | |
| Fondo | `#f8f8f8` | Fondo de la página | El YAML dice `#ffffff`; se toma el blanco cálido del texto para que los paneles blancos se distingan |
| Panel | `#ffffff` | Tarjetas, tablas, modales | |
| Superficie de selección | `#cfe1fd` | Fila o tarjeta seleccionada, resaltado | Del YAML; el texto decía `#000000`, que no tiene sentido en tema claro |
| Texto | `#292a2e` | Texto principal | 14.3:1 sobre blanco |
| Acento | `#1c2b42` | Botón principal, enlaces, foco | Azul marino apagado; 14.3:1 sobre blanco |
| Texto secundario | `#5e6066` | Etiquetas, metadatos | **Derivado**: el archivo da `#101214`, igual al primario. 6.3:1 sobre blanco (AA) |
| Borde decorativo | `#dcdfe4` | Separadores, contorno de tarjetas | **Derivado**: el archivo da `#ffffff`, invisible en tema claro |
| Borde de campos | `#8c8f97` | Inputs, selects | **Derivado**: 3.2:1, cumple el mínimo de 3:1 para controles |

Contrastes calculados con la fórmula WCAG 2.x. Los que trae el archivo (13.2, 9.1 y 15.3) son
aproximados, aunque sus conclusiones se sostienen.

**Colores de estado**: el estilo no define ninguno. En GIO se conservan los del semáforo
(`--ok`, `--alerta`, `--peligro`), con las variantes oscuras del tema claro actual para texto
(`#047857`, `#b45309`, `#b91c1c`, todas ≥ 5:1 sobre blanco), y siempre acompañados de texto o ícono.

### Tipografía

- Atlassian usa *Charlie Display* (títulos) y *Charlie Text* (cuerpo), que son propietarias. En GIO se
  usa la pila del sistema que ya tiene: `system-ui, -apple-system, 'Segoe UI', Roboto, …`.
- Escala de referencia: título de página 32 px / 700 / 1.19 · encabezado de sección 24 px / 400 /
  1.33 · cuerpo 14–15 px / 400 / 1.5. El YAML marca el cuerpo en 20 px y el texto en 12 px; el primero
  es tamaño de sitio de marketing y el segundo resulta pequeño en campo, así que para las tablas y
  tableros de GIO se usa 14–15 px, con el interlineado de 1.5 que pide el estilo.

### Espaciado

Base de 4 px. Escala: `4, 8, 12, 16, 20, 24, 28, 32`, y saltos de sección de `60, 64, 80`.

- 4–12 px: dentro de componentes (relleno de botones, separación de íconos).
- 16–32 px: entre campos, elementos de lista y relleno interno de tarjetas.
- 60–80 px: entre secciones grandes (poco usado en una app; útil en el login).

### Radios

`sm 3px` · `md 4px` (inputs, selects) · `lg 8px` (tarjetas, modales) · `xl 24px` ·
`pill 9999px` (botones y chips). GIO usa hoy `--radio: 10px` para todo.

### Sombras

Ninguna, o casi invisibles. La separación se logra con fondo `#f8f8f8` + panel `#ffffff` + borde
`#dcdfe4`.

### Movimiento

- Micro-interacciones (hover, pulsar, toggle): **75 ms**.
- Cambios de estado, abrir modales, navegar: **400 ms**.
- Entradas no críticas: **500 ms**.
- Curva: `cubic-bezier(0.4, 0, 0, 1)` (arranca rápido y frena suave).
- Con `prefers-reduced-motion`, duración 0 y curva lineal.

El YAML lista 250 / 500 / 750 ms con `ease-in-out`, que corresponde al sitio de marketing; para una
herramienta de trabajo se usan los valores del texto.

## Componentes

- **Navegación superior**: fondo primario `#101214`, texto blanco, la sección activa en blanco y las
  demás en blanco con opacidad.
- **Botón principal**: fondo acento `#1c2b42`, texto blanco, forma de píldora. **Secundario**: fondo
  blanco, borde `#8c8f97`, texto `#292a2e`.
- **Enlaces**: color acento, subrayado al pasar el cursor.
- **Campos**: fondo blanco, borde `#8c8f97`, radio 4 px.
- **Tarjetas del Kanban y tablas**: panel blanco, borde `#dcdfe4`, radio 8 px, sin sombra. Tarjeta
  seleccionada con fondo `#cfe1fd`.
- **Foco de teclado**: contorno sólido de 2 px en acento con 2 px de separación, visible en todo
  elemento navegable.
- **Áreas táctiles**: mínimo 44 × 44 px (importante en la vista móvil del técnico).

## Cómo aplicarlo en GIO

El tema se controla con variables CSS en `frontend/src/assets/main.css` y el atributo `data-theme` de
`<html>` (ver `useTema.js`). Correspondencia con el tema claro:

| Variable GIO | estiloatlassian |
| --- | --- |
| `--fondo` | `#f8f8f8` |
| `--panel`, `--campo` | `#ffffff` |
| `--panel-alto` | `#cfe1fd` |
| `--superficie` | `#f8f8f8` |
| `--barra` | `#101214` (con texto blanco) |
| `--borde` | `#dcdfe4` (y `#8c8f97` en campos) |
| `--texto`, `--texto-suave` | `#292a2e` |
| `--apagado`, `--tenue` | `#5e6066` |
| `--acento` | `#1c2b42` |
| `--radio` | `8px` (tarjetas) / `4px` (campos) |

**Pendiente de decidir antes de aplicarlo:**

1. El estilo solo define tema claro. GIO arranca en oscuro: hay que elegir entre derivar una versión
   oscura o dejar el estiloatlassian solo para el modo claro.
2. Si reemplaza al tema claro actual o se agrega como tema adicional seleccionable.
3. El acento `#1c2b42` es casi tan oscuro como el texto: los botones principales se distinguen por
   forma y relleno, no por color. Conviene revisarlo con los usuarios de Planta Interna.
