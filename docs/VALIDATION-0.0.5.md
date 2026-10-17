# Validación de Lupa 0.0.5

Trabajo iniciado el 17 de octubre de 2026 UTC (16 de octubre en México). Se usan
contenedores y perfiles dedicados en un VPS Debian con 2 vCPU, 3922 MiB de RAM
sin swap, Docker 29.9.1 y Compose 5.6.0. No se navega el perfil de trabajo del
usuario. Los datasets y respuestas de Maps se conservan fuera del repositorio.

## Resultado y estado de publicación

0.0.5 se publica como **pre-release**. La batería completa no termina sin fallos;
se conservan las ejecuciones originales y las comprobaciones enfocadas.

| Comprobación | Estándar | Multistage |
|---|---|---|
| API/CDP de la batería final | 9/9, 55 aserciones | 8/9; CDP aislado posterior 1/1, 25 aserciones |
| Funciones | 15/15 | 15/15 |
| Regresiones de colectores instalados como `abc` | 25, más 1 DOM omitida en modo offline | 25, más 1 DOM omitida en modo offline |
| DOM real con fixtures | Pasa | Pasa |
| Persistencia, exclusión de volumen, arranque sin red y autenticación | Pasa en candidata final | Pasa en candidata de navegación `43731cb` |
| Escritorio completo | Falla el texto exacto: `Selkies input oK` | La primera batería falla en coordenadas; con ventana nativa falla la misma mayúscula |
| Audio, vídeo, clic, portapapeles, resolución y repintado | Pasan | Pasan en la comprobación con ventana nativa |

La matriz HTTP aprobó 7/7; la UI aprobó 4/6. Fallaron la extracción de Mérida
y la consulta vacía posterior. Las comprobaciones enfocadas de teclado se
registran por separado; no sustituyen las baterías completas fallidas.

Las candidatas finales `0.0.5-rc.3` y `0.0.5-multistage-rc.4` contienen el
runtime de `c63f4a0`. Los cambios posteriores corrigen el laboratorio y documentan
resultados. Antes de publicar se comparan las capas del runtime final con las
de estas candidatas, y se verifican revisión OCI y digests en DockerHub.

## Versiones instaladas

Las dos candidatas contienen las mismas versiones principales:

| Componente | Estándar y multistage |
|---|---|
| Sistema | Debian GNU/Linux 13 (trixie) |
| Bun | 1.4.2 |
| Playwright | 1.59.1 |
| Chromium | Google Chrome for Testing 147.0.7727.15 |
| Python | 3.13.5 |

La diferencia está en la receta y procedencia de las capas: runtime histórico
frente a reconstrucción desde las bases fijadas y los paquetes APT disponibles.

## Correcciones verificadas

- Las dos implementaciones bloquean la carpeta de salida con `flock` durante la
  recolección. Las regresiones prueban contención entre procesos y liberación
  después de una excepción y de SIGKILL; el archivo del bloqueo se conserva
  para evitar carreras entre inodos distintos.
- HTTP distingue la envoltura conocida de una búsqueda vacía de un cambio de
  formato. La ausencia del campo de resultados, por sí sola, sigue siendo error.
- UI reconoce el panel de búsqueda vacía sin esperar un feed inexistente.
- La imagen normaliza permisos de archivos de ejecución incluso cuando el
  checkout tiene archivos 600 y directorios 700. Los colectores instalados se
  prueban como `abc`, sin red, no mediante copias externas del código.

Los 21 casos de regresión de los colectores pasan en Python 3.11 y 3.13 en
[CI](https://github.com/bunxdev/lupa/actions/runs/39006163701). La prueba DOM es
optativa y se ejecuta por separado contra Chromium.

## Matriz HTTP instalada

La candidata estándar ejecutó `/opt/lupa/qwen/qwen_leads_fast.py`, con el
laboratorio `qwen/validate_live.py --collector-dir /opt/lupa/qwen`. Cada búsqueda
positiva recoge 3 contactos y reanuda hasta 5; se solicitan 20 fichas al feed.

| Consulta | Inicial | Reanudación | Teléfonos únicos al final |
|---|---:|---:|---:|
| Farmacias en Guadalajara | 3 | 5 | 5 |
| Ferreterías en Monterrey | 3 | 5 | 5 |
| Panaderías en Mérida, Yucatán | 3 | 5 | 5 |

La consulta sin coincidencias `zzlupafixture005xqvkt` devuelve 0 contactos,
`discovery_complete: true` y ningún error. El código de salida es 1 porque no
alcanza el contacto solicitado: un resultado parcial vacío es distinto de un
error de formato. Una consulta inventada seguida de una ciudad puede devolver
una ficha geográfica; no se usa esa respuesta como prueba de búsqueda vacía.

La candidata multistage pasó también una comprobación HTTP de farmacias en
Guadalajara (3 contactos, reanudación hasta 5, cinco teléfonos únicos) y la
búsqueda vacía. Ambas variantes aprobaron los 21 casos de regresión instalados
y la ejecución de la CLI como `abc`.

## Runtime multistage: resultados iniciales

La instalación con volumen vacío alcanzó el estado saludable. Pasaron las ocho
pruebas de API/CDP (49 aserciones), incluida la sesión compartida, reconexión,
cookies y eventos de teclado. La prueba CDP duró unos 73 segundos en este host.

La batería funcional inicial aprobó 13/15 casos. La primera evaluación headless
y la captura/reproducción de vídeo devolvieron HTTP 500. Ambos casos pasaron al
repetir **solo esas comprobaciones con el fixture original**, sin cambiar el
runtime. Un diagnóstico adicional comprobó canvas, aislamiento de cookies,
arranque de un navegador headless nuevo y reproducción de vídeo. La causa
concreta de esos dos HTTP 500 no quedó aislada; las repeticiones no borran los
fallos originales ni garantizan ausencia de intermitencias bajo carga.

En la primera prueba del escritorio a 60 FPS funcionaron vídeo (581 llamadas de
decodificación), audio (pico 0.53), clic remoto y portapapeles. Fallaron el texto
exacto del teclado, por repeticiones de teclas, y el cambio de resolución dentro
de la espera fija. Otra ejecución terminó al destruirse el contexto del visor;
el servidor registró `keepalive ping timeout` y el dashboard incluye recarga
tras desconexión.

El laboratorio ahora envía pulsaciones y liberaciones juntas, sin mantener una
tecla pulsada durante una ida y vuelta de CDP; espera el texto y la resolución
observados. Mantiene las aserciones de contenido exacto, sonido, vídeo y cambio
de tamaño. También registra las fases de avance y los FPS configurados.

La prueba de ciclo de vida aprobó persistencia de cookies, perfil de extensión y
archivo descargado, exclusión del volumen, arranque saludable con perfil vacío
sin red y autenticación HTTP del escritorio. La recreación tardó 49.94 segundos;
el perfil nuevo ocupó 12,494,750 bytes. La prueba DOM en Chromium aprobó las
comprobaciones de feed, ficha, cierre permanente, bloqueo y panel vacío.

### Escritorio con límite configurado de 15 FPS

Tras recrear la instancia con `SELKIES_FRAMERATE=15` y el laboratorio actualizado,
las comprobaciones de entrada y transmisión del escritorio aprobaron:

| Comprobación | Resultado |
|---|---|
| Vídeo | 305 llamadas de decodificación |
| Audio | Pico de señal 0.512 |
| Clic remoto | `REMOTE CLICK OK` |
| Teclado | `Selkies input OK`, sin repeticiones |
| Portapapeles | `Clipboard OK` |
| Resolución | 1280×800 → 1120×740 |

La captura inicial se tomó durante el repintado después de cambiar el tamaño.
El laboratorio añade una espera visual de una región del fondo del fixture
antes de capturar el fotograma final, además de comprobar las dimensiones.

15 FPS es la configuración solicitada, no una medición de rendimiento sostenido.
El valor predeterminado de la imagen y de Compose sigue siendo 60. El informe
conserva las ejecuciones iniciales; esta aprobación corresponde a la configuración
indicada y no acredita estabilidad a 60 FPS en este VPS.

## Condiciones del laboratorio

La ejecución inicial de 0.0.4 tuvo 7 pruebas de aplicación aprobadas y un timeout
CDP a 30 segundos. Las funciones aprobaron 14/15 comprobaciones; la ejecución
con perfil aislado de extensión y la captura de escritorio excedieron el mismo
margen. Estos fallos no se convierten retroactivamente en aprobaciones.

Se observó contención del hipervisor: muestras de CPU steal entre 71 y 84 %.
Las nuevas ejecuciones usan `LUPA_TEST_TIMEOUT_MS=90000`, registrado en los
informes. Este ajuste solo afecta a los clientes del laboratorio, no a los
límites del servicio. Los tiempos medidos aquí no son una referencia de
rendimiento normal.

## Alcance

La matriz es una prueba pequeña de integración y reanudación, no una garantía
de exhaustividad o estabilidad de Google Maps. El feed HTTP no pagina ni
comprueba cierres comerciales. Los checkpoints identificados de 0.0.4 siguen
siendo compatibles; los antiguos sin versión requieren una carpeta nueva.
Las imágenes de esta release son Linux AMD64; multistage no significa multiarch.

## Navegación DOM para Maps

La matriz UI de la candidata inicial obtuvo 1/3 contactos en Guadalajara y 0/3
en Monterrey y Mérida, con HTTP 500 de la API; el panel vacío sí terminó sin
errores. El servidor registró timeouts y errores de navegación. `/live` esperaba
siempre el evento `load`, aunque el colector necesita el DOM y sus selectores.

Se añadió `waitFor` a `/live`, manteniendo `load` por defecto. El cliente UI pide
`domcontentloaded`. Su polling tolera HTTP 500 transitorios de la API local,
comprueba bloqueos en cada intento y mantiene el plazo; 401, 403 y 429 se
propagan inmediatamente. Cuatro nuevas regresiones HTTP verifican recuperación,
autenticación/bloqueos, plazo y contrato de navegación: 25 regresiones en total.
La integración CDP incluye una imagen cuya respuesta permanece retenida para
comprobar que la opción DOM devuelve el control antes de terminar esa descarga.

Las 25 regresiones de la revisión de navegación pasaron en Python 3.11 y 3.13
en [CI](https://github.com/bunxdev/lupa/actions/runs/39013217704), junto con las
pruebas de la capa de datos compartida. También pasó `bun run typecheck` y las
ocho pruebas locales de API; la integración real de Chromium se ejecuta en el VPS.

## Revisión del laboratorio de escritorio y vídeo

La candidata de navegación aprobó las nueve pruebas de API/CDP (55 aserciones),
incluida la navegación DOM con una respuesta de imagen retenida. Las funciones
aprobaron 14/15: volvió a fallar el fixture que grababa vídeo durante una pausa
fija. Se sustituyó por una espera de chunks codificados y de un fotograma
presentado, conservando las comprobaciones de avance, anchura y decodificación.
La comprobación enfocada pasó con cinco fotogramas, 4325 bytes y cuatro chunks.

Con 15 FPS, la nueva prueba detectó repintado correcto tras redimensionar
(píxel observado `[17, 34, 49]` frente al fondo `[17, 34, 51]`), pero volvió a
observar repeticiones del teclado. La ejecución enfocada con `xset r off` pasó:
320 decodificaciones, pico de audio 0.502, texto exacto, clic, portapapeles y
1280×800 → 1120×740. La imagen expone ahora `LUPA_KEY_REPEAT=off` para aplicar
ese ajuste al arrancar; el valor predeterminado sigue siendo `on`. Desactivarlo
impide también la repetición intencional al mantener una tecla pulsada.

Las comprobaciones enfocadas no convierten la batería inicial en una ejecución
sin fallos. Los informes conservan las condiciones y resultados de cada corrida.

## Matriz UI con navegación DOM

Se ejecuta el colector instalado de la revisión `43731cb`, cuyo código UI es
idéntico al de la candidata final `c63f4a0`. La nueva matriz conserva carpetas
separadas de las ejecuciones anteriores.

| Consulta | Inicial | Reanudación | Teléfonos únicos al final | Errores registrados |
|---|---:|---:|---:|---|
| Farmacias en Guadalajara | 3 | 5 | 5 | HTTP 500; el servidor registró timeout; el colector siguió con otras fichas |
| Ferreterías en Monterrey | 3 | 5 | 5 | Ninguno |
| Panaderías en Mérida | 0/3 | No ejecutada tras el fallo | 0 | Cinco HTTPError consecutivos; salida 1 con CollectionError y checkpoint guardado |

El código HTTP y sus dependencias de extracción no cambiaron desde la revisión
`855ddef` que aprobó la matriz HTTP; el adjunto incluye sus identificadores de
contenido Git. Las comprobaciones UI corresponden a la revisión de navegación,
no a la candidata inicial que produjo resultados incompletos.

Mérida descubrió 20 candidatas, pero sus cinco primeras comprobaciones de
detalle devolvieron errores HTTP y activaron el límite de fallos consecutivos.
El resultado UI de esta consulta no queda validado en el VPS. No se repite
indefinidamente ni se sustituye este fallo por la aprobación de la variante HTTP.
Los logs del servidor registraron timeouts, pero no se aisló la causa de cada
HTTP 500. Queda pendiente diagnosticar y validar este caso en una ejecución
posterior; no se atribuye toda la incidencia exclusivamente a la CPU.

La consulta vacía posterior también falló con HTTPError y
`discovery_complete: false`: esta ejecución no verificó su resultado vacío.
La matriz UI termina con **4/6 comprobaciones aprobadas**. Las pruebas DOM y
las consultas vacías anteriores sí pasaron, pero no sustituyen estos dos fallos
de la matriz final. La matriz HTTP mantiene **7/7** comprobaciones aprobadas.

## Aislamiento del viewport del laboratorio

En la batería final multistage pasaron las 15 comprobaciones funcionales. El
escritorio comprobó audio, vídeo, resolución y repintado, pero sus clics no
alcanzaron los controles y el texto quedó vacío, pese a la repetición X11
desactivada. La batería funcional anterior había fijado un viewport emulado de
1024×768; el cálculo de coordenadas del escritorio requiere la ventana nativa.
El laboratorio reinicia ahora su sesión dedicada antes del fixture de escritorio
y registra las dimensiones internas, externas y de pantalla usadas para cada
control. Este cambio solo afecta al laboratorio, no a las sesiones del usuario.

La batería final de API multistage obtuvo 8/9: falló `/live/click` en la
integración CDP, con el límite interno de cinco segundos. La comprobación CDP
aislada posterior pasó (1 prueba, 25 aserciones, unos 104 segundos totales), sin
cambiar ese límite. La batería funcional aprobó 15/15, incluido teclado/ratón
y CDP compartido. El fallo inicial permanece registrado; la causa concreta
de esa intermitencia no quedó aislada. Durante esta fase, una muestra de un
segundo registró 69,7 % de CPU steal.

Al reiniciar con viewport nativo pasaron clic, foco, portapapeles, audio, vídeo,
redimensionado y repintado. Las dimensiones registradas fueron 1280×800 de
pantalla y 1280×713 del contenido, con 87 píxeles de interfaz del navegador.
El teclado quedó en `Selkies input oK`, por lo que la prueba completa siguió
fallando. Se cambia el laboratorio para esperar cada pulsación y liberación
en orden, incluidas las transiciones de Shift; no se relaja la comparación
de mayúsculas. La repetición X11 desactivada evita repetir una tecla mientras
se espera la ida y vuelta de CDP.

## Comprobaciones finales de teclado aislado

El fixture con eventos CDP secuenciales recibió `Selkies input OK` en multistage,
con una `O` nativa y `Shift` activo. Un segundo fixture usando
`page.keyboard.down`, `press` y `up` de Playwright pasó en ambas imágenes,
conservando la misma comparación exacta y observando eventos de teclado fiables
(`isTrusted`). El laboratorio de escritorio utiliza ahora esta API de Playwright
para gestionar modificadores y ubicación de teclas.

Estos fixtures usan una página estática y no reproducen simultáneamente toda
la carga animada de la batería completa. Por tanto, sus aprobaciones no prueban
que haya desaparecido la intermitencia observada bajo esa carga. Se adjuntan
ambos fixtures, sus hashes y sus resultados; las baterías completas fallidas se
conservan. La publicación permanece como pre-release.

La candidata estándar terminó con 9/9 de API/CDP, 15/15 de funciones, DOM y
ciclo de vida aprobados; el escritorio completo falló solo en la mayúscula.
Su recreación tardó 51,04 segundos. Ambas imágenes aprobaron los 25 casos
instalados y la CLI como `abc`. Sus versiones instaladas se volvieron a medir
en las candidatas finales y coinciden con la tabla de este informe.
