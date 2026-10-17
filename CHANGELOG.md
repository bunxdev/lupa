# Changelog

## 0.0.5

- Añade `waitFor` a `/live`, conservando `load` por defecto; el colector UI espera el DOM y tolera HTTP 500 transitorios durante su polling, sin reintentar autenticación ni bloqueos.
- Reconoce búsquedas vacías reales de Maps: panel sin feed en UI y envoltura JSON sin lista en HTTP. Un formato desconocido sigue siendo un error.
- Bloquea la carpeta de salida durante toda la ejecución de cada colector; evita escritores simultáneos y libera el bloqueo al terminar o morir el proceso.
- Añade una matriz real optativa de tres municipios/giros, reanudación y resultados vacíos, con informe agregado separado de datasets privados.
- Normaliza los permisos de los archivos copiados a las imágenes y corrige la copia de fixtures del laboratorio para checkouts creados con `umask 077`.
- Permite configurar y registrar el margen de espera de las pruebas mediante `LUPA_TEST_TIMEOUT_MS`, sin modificar los límites del servicio.
- Expone `SELKIES_FRAMERATE` en Compose (60 por defecto) y mejora la observación de teclado y resolución del laboratorio en hosts lentos.
- Añade `LUPA_KEY_REPEAT=off` para desactivar repeticiones X11 en escritorios con latencia; conserva `on` por defecto. El laboratorio espera vídeo y repintado observables en lugar de pausas fijas.
- Añade la distribución `0.0.5-multistage`, construida desde etapas independientes de Selkies, Bun/Chromium y Debian slim; [recetas y validación](docs/BUILD-IMAGES.md).

Las pruebas, condiciones del VPS y resultados están en el [informe de validación](docs/VALIDATION-0.0.5.md).

La paginación HTTP y la migración de checkpoints antiguos sin identificar siguen pendientes. Los checkpoints versionados de 0.0.4 son compatibles; para estados anteriores sin versión se debe iniciar una carpeta nueva.

## 0.0.4

- Integra los dos colectores Maps de `qwen`, sin sus conjuntos de contactos.
- Checkpoints versionados por método antes de la primera petición, por lote y ante errores/interrupciones.
- Reanuda consultas pendientes y candidatos guardados; rechaza estados de otro método o anteriores sin identificar.
- Corrige búsquedas de una/dos fichas y distingue resultados vacíos, bloqueos y cambios de formato.
- Conserva la fecha de consulta del feed y marca el cierre comercial como no verificado en HTTP directo.
- Evita que redirecciones de la API propaguen el token Bearer; detiene el trabajo ante bloqueo/consentimiento.
- Incluye los colectores Python estándar en `/opt/lupa/qwen/` de la imagen AMD64.
- Pruebas de regresión, comprobación DOM en Chromium y comparación real de ambos métodos; [informe](docs/MAPS-0.0.4.md).

El endpoint HTTP de Maps sigue siendo experimental, sin paginación ni garantía de exhaustividad. No se modificó el núcleo del navegador de 0.0.3.

## 0.0.3

Comparación: `v0.0.2...v0.0.3`. Integra MCP y el despliegue slim de `lupax`.

- Servidor MCP stdio con 21 herramientas, inspección de controles y recursos PNG/PDF.
- Imagen `bunxdev/lupa:0.0.3` para Linux AMD64, derivada del runtime publicado
  `slim-20260915` por digest y con versión/revisión OCI explícitas.
- Código de navegador único para API tradicional e imagen slim; Chromium completo
  también sirve las operaciones headless y permite apagado ordenado del perfil.
- Puerto de escritorio Compose corregido a HTTP, conforme a la documentación.
- Límite de escritura MCP alineado con la API (65536 caracteres), con regresión probada.
- Prueba de escritorio compatible con autenticación configurada.
- Guía de teclado, foco, pestañas y Vimium basada en la revisión de las skills locales.

La imagen incluye sus dependencias y arranca sin red. El MCP se instala en el
cliente; consulta [docs/RELEASES.md](docs/RELEASES.md). La rama `qwen` y sus datos
quedan fuera de esta release.

## 0.0.2

Comparación: `v0.0.1...v0.0.2`. Integra la evolución publicada en `testing`.

- CDP autenticado por HTTP y WebSocket sobre la misma sesión visible de Lupa.
- Descubrimiento CDP, conexiones simultáneas y reconexión tras cerrar la sesión.
- Integración Browser Use y recolección/exportación de contactos con filtros,
  deduplicación, reanudación y escape de HTML y fórmulas de hojas de cálculo.
- Laboratorio Docker y resultados históricos de comparación de navegadores.
- Conserva la API HTTP, cookies, descargas, extensiones y escritorio Selkies.

Esta versión se ejecuta desde el código fuente con `docker compose up -d`.
Requiere `LUPA_API_TOKEN`, como 0.0.1. API y escritorio se publican en loopback.
El primer arranque instala dependencias y Chromium; necesita acceso a Internet.
No corresponde a una nueva imagen `bunxdev/lupa:0.0.2`: la imagen publicada
`slim-20260915` se incorpora al proceso de distribución en 0.0.3.

## 0.0.1

Publicación inicial: API HTTP con Bearer, validación y límites de peticiones,
sesión persistente Chromium y escritorio Selkies. La etiqueta pública apunta
al historial publicado en GitHub, no al historial local anterior a la publicación.
