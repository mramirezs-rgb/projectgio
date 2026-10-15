# estilobmw

Referencia de diseño de GIO tomada del sitio corporativo de BMW. **Es el tema aplicado** en
`frontend/src/assets/main.css`: el tema claro sigue la referencia y el oscuro se deriva de sus bandas
azul marino.

- Fuente original: [`fuentes/bmw-DESIGN.md`](fuentes/bmw-DESIGN.md) (copia sin modificar).
- Es una inspiración de estilo, no una marca: GIO no usa logotipos, nombres ni la tipografía
  propietaria de BMW.

## Idea central

Interfaz corporativa, medida y "de ingeniería precisa":

- **Esquinas rectas** en botones, tarjetas, campos y modales. Lo circular queda solo para botones de
  ícono (cambio de tema) y la insignia GIO.
- **Un solo color de acción**: azul BMW `#1c69d4` en botones principales, enlaces y la sección activa
  de la barra.
- **Sin sombras**: la profundidad sale del contraste entre superficies y de bordes finos.
- **Tipografía con contraste de pesos**: títulos y botones en 700, texto descriptivo en Light 300 y
  etiquetas en MAYÚSCULAS con espaciado amplio.

## Tokens

| Variable GIO | Claro (referencia) | Oscuro (derivado) | Origen |
| --- | --- | --- | --- |
| `--fondo` | `#f7f7f7` | `#11161c` | surface-soft / navy más profundo |
| `--panel`, `--barra` | `#ffffff` | `#1a2129` | canvas / surface-dark |
| `--panel-alto` | `#ebebeb` | `#262e38` | surface-strong / surface-dark-elevated |
| `--superficie` | `#fafafa` | `#161c23` | surface-card |
| `--borde` | `#e6e6e6` | `#2e3742` | hairline |
| `--borde-campo` | `#8f8f8f` | `#6b7683` | **Derivado**: la referencia usa `#e6e6e6`, que no llega al 3:1 que piden los controles |
| `--texto` | `#262626` | `#f2f2f2` | ink / on-dark |
| `--texto-suave` | `#3c3c3c` | `#dddddd` | body |
| `--apagado` | `#6b6b6b` | `#bbbbbb` | muted / on-dark-soft |
| `--acento` | `#1c69d4` | `#1c69d4` | primary; texto blanco encima 5.2:1 |
| `--acento-hover` | `#0653b6` | `#0653b6` | primary-active |
| `--acento-claro` | `#1c69d4` | `#6ea8f0` | Enlaces y foco; en oscuro se aclara (7.1:1) |
| `--seleccion` | `#e8f0fb` | `#1d3554` | Tinte del azul |
| `--chip-activo` | `#262626` | `#f2f2f2` | filter-chip-active (tinta con texto invertido) |
| `--ok` / `--alerta` / `--peligro` | `#22c55e` / `#f59e0b` / `#dc2626` | igual | success / warning / error |
| `--radio`, `--radio-campo`, `--radio-boton` | `0` | `0` | rounded.none |
| `--radio-sm` | `2px` | `2px` | Pastillas de estatus y contadores |

Contrastes del oscuro sobre el panel `#1a2129`: texto 14.5:1, apagado 8.5:1, tenue 5.6:1.

## Tipografía

- BMW Type Next Latin es de licencia. Se usa **Inter** (variable), el sustituto que propone la
  referencia, empaquetada con `@fontsource-variable/inter` para que funcione sin conexión (PWA).
- Títulos y botones: 700. Botones con 0.5 px de espaciado.
- Etiquetas de campos y encabezados de tabla: 700, MAYÚSCULAS, 1.2 px de espaciado.
- Párrafos descriptivos: Light 300. Los avisos (`<p role="alert|status">`) quedan en 400 para leerse
  bien.
- No se usan los pesos 500 ni 600.

## Componentes

- **Barra superior**: 64 px, fondo del panel, borde inferior fino. Enlaces en 400; la sección activa
  pasa a 700 con subrayado azul de 2 px.
- **Botón principal**: azul, texto blanco, rectangular. **Secundario**: fondo del panel, borde de
  campo, texto en tinta.
- **Campos**: rectangulares; al enfocar, el borde se engrosa en tinta.
- **Conmutador Kanban/Tabla**: el activo usa `--chip-activo`.
- **Pestañas del folio**: la activa en tinta con subrayado de 2 px.
- **Tarjetas, columnas y modales**: rectangulares, sin sombra.

## Diferencias con la referencia

- Botones de 40 px de alto en escritorio (la referencia pide 48 px) para no inflar los filtros y las
  tablas; en la vista móvil del técnico se mantienen los botones táctiles de 56 px.
- No hay bandas "hero" ni fotografía: GIO es una herramienta de trabajo, no un sitio de producto.
- La franja tricolor M no se usa.
