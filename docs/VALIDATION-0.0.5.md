# Validación de Lupa 0.0.5

Trabajo iniciado el 17 de octubre de 2026 UTC (16 de octubre en México). Se usan
contenedores y perfiles dedicados en un VPS Debian con 2 vCPU, 3922 MiB de RAM
sin swap, Docker 29.9.1 y Compose 5.6.0. No se navega el perfil de trabajo del
usuario. Los datasets y respuestas de Maps se conservan fuera del repositorio.

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
