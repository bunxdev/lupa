# Lupa slim: resultado de la primera optimización

Fecha: 2026-09-15T20:21:19.503395+00:00. Plataforma probada: Linux amd64.
Imagen local: `debina/lupa:slim-testing`.
Índice OCI: `sha256:d7c94e9360e2b9d258b4cf659e586517a7b635a132e0e7b4694fb85d138cf6f6`.

## Espacio

| Medida | Lupa original | Lupa slim | Reducción |
|---|---:|---:|---:|
| Imagen, tamaño que reporta este Docker | 3.87 GB | 2.27 GB | 41.3% |
| Capas gzip de la imagen para el registro | 986.5 MB | 655.9 MB | 33.5% |
| Runtime, incluyendo perfiles y dependencias externas | 3.80 GB | 1.65 GB | 56.8% |

La imagen original es la base Selkies: descarga Bun, Chromium, headless-shell y
Playwright al arrancar. La nueva imagen ya incluye todo. Por eso la comparación
más representativa es el runtime completo. El volumen original ocupa
802.2 MB; el volumen de la candidata, después de las pruebas,
25.8 MB. Un perfil vacío arrancado sin red ocupó
11.5 MB.

Docker usa su almacén containerd y su tamaño reportado incluye contenido
comprimido y snapshots; no debe interpretarse como el tamaño de descarga. Las
capas gzip se obtuvieron del manifiesto OCI local, son la carga de capas prevista
para Docker Hub y no prueban que la imagen esté publicada. El runtime suma el
filesystem del contenedor, `/config` y las dependencias que la original monta
desde el host. Los datos de usuario y cachés de navegación crecerán con el uso.
La caché de BuildKit queda fuera de estas cifras y no forma parte de la imagen
que se descarga del registro.

## Validación

- Pruebas existentes de Lupa: **8 aprobadas**, incluida la integración CDP con
  Chromium real; **0 fallos**. Comprobación TypeScript aprobada.
- API y navegador: **15/15 comprobaciones aprobadas**:
  autenticación, aislamiento de contextos, PNG/JPEG, HTML, PDF, contenido,
  extensiones, teclado, ratón, descargas, CDP, cookies, audio y vídeo.
- Cliente Selkies real: **274 frames decodificados**,
  771125 bytes recibidos, audio con pico 0.532, clic remoto,
  escritura con mayúsculas, portapapeles y redimensionado
  1280×800 → 1120×740.
- Recreación: cookies, perfil de extensión y descargas conservados;
  **8.4 s** hasta disponibilidad en esa prueba.
- Perfil nuevo con `--network none`: arranque correcto, sin instalaciones.
- Autenticación Basic del escritorio: 401 sin credenciales y 200 con ellas.
- Bloqueo exclusivo del volumen `/config`: comprobado.
- Manifiesto PWA e icono: HTTP 200. El cliente no tuvo solicitudes HTTP fallidas.

El único aviso del cliente automatizado fue el permiso de Wake Lock, que el
navegador de pruebas no concede. No impidió vídeo, audio ni controles.
No se han medido micrófonos/gamepads físicos, GPU, ARM, calidad perceptual,
latencia por Internet ni todos los sitios web. La prueba de vídeo de página usa
VP8; no es una matriz exhaustiva de códecs. La API y sus rutas se conservan.

## Correcciones necesarias

1. Declarar paquetes y entorno que antes venían implícitos de la base general:
   D-Bus, `cvt`, rutas de ejecutables, configuración de audio y puerto de Selkies.
2. Restaurar el worker de portapapeles referenciado por el frontend del donante,
   y generar el manifiesto PWA y su icono.
3. Coordinar el apagado: desactivar los manejadores automáticos de señal de
   Playwright en esta imagen y dejar el cierre al servidor Lupa. Dos cierres
   concurrentes provocaban un cierre forzoso y pérdida de cookies recientes.
4. Limpiar locks de Chromium al recrear, bajo bloqueo exclusivo del volumen.

## Archivos

- `Dockerfiles/lupa/Dockerfile`: construcción por etapas y runtime mínimo.
- `lupa.yml`: despliegue local en API/CDP 3136 y escritorio 6180.
- `scripts/lupa/`: arranque, supervisión, pruebas y medición.
- `vendor/lupa/`: código y herramientas originales, con revisión documentada.
- `reports/functions.json`, `desktop.json`, `lifecycle.json`, `sizes.json`:
  resultados de las comprobaciones.

La imagen está construida localmente y preparada para etiquetarse y publicarse
en la cuenta de Docker Hub que se elija. Aún no se ha publicado.
