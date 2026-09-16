# Comparación secuencial para Lupa — 2026-09-15

## Publicación

Imagen publicada en [Docker Hub](https://hub.docker.com/r/bunxdev/lupa/tags): `bunxdev/lupa:slim-20260915`, plataforma `linux/amd64`.
Digest remoto comprobado con `docker buildx imagetools inspect`:
`sha256:d7c94e9360e2b9d258b4cf659e586517a7b635a132e0e7b4694fb85d138cf6f6`.
Coincide con la imagen local probada. Capas comprimidas: 655,9 MB; tamaño reportado localmente por Docker: 2,27 GB. No son la misma medida. No se publicó ARM64.

## Método y límites

Se detuvieron Lupa original, Lupa slim y los cuatro navegadores alternativos. Se inició un único contenedor de navegador por turno y se detuvo antes del siguiente. Los contenedores ajenos al laboratorio siguieron funcionando.

Misma página HTTP local, con JavaScript, fetch JSON, formulario, canvas rojo y almacenamiento. Cinco navegaciones con el proceso ya arrancado; mediana de `goto` hasta `load`. Puppeteer por CDP para Lupa/Obscura/Lightpanda/BrowserOS; CLI con `docker exec` para agent-browser. Su tiempo incluye cliente y proceso CLI y **no es una comparación pura de motores**. Lupa y BrowserOS incluyen escritorio y servicios adicionales; los otros se ejecutan headless. No igualamos tamaños de ventana ni vaciamos perfiles o cachés del sistema. No representan rendimiento en sitios complejos.

RAM: muestras `docker stats --no-stream`, a los tres segundos de disponibilidad y al terminar las operaciones, antes de cerrar la pestaña. La primera muestra puede incluir trabajo de arranque; no es reposo estabilizado. No son máximos de RAM; los porcentajes de CPU en el JSON son instantáneos, no coste total. La navegación HTTPS adicional usa example.com y no forma parte de la mediana.

| Servicio | RAM tras arranque | RAM tras pruebas | Mediana local |
|---|---:|---:|---:|
| lupa | 760.2MiB | 783.1MiB | 172 ms |
| obscura | 22.54MiB | 60.05MiB | 43 ms |
| lightpanda | 7.672MiB | 26.97MiB | 19 ms |
| browseros | 1.275GiB | 1.32GiB | 172 ms |
| agent-browser | 468.3MiB | 482.6MiB | 625 ms |

## Resultados y aportaciones

### Lupa slim

Pasó JavaScript/fetch, escritura y clic reales, canvas (píxel RGBA 255,0,0,255), cookies y localStorage tras recargar, PNG, PDF y HTTPS. CDP autenticado operativo. Se conserva como referencia Chromium 147.0.7727.15. Las pruebas previas específicas de Lupa cubren además API, aislamiento, extensiones, perfiles persistentes, descargas y Selkies con vídeo, audio, teclado y portapapeles: ver `../OPTIMIZATION.md`, `../functions.json`, `../desktop.json` y `../lifecycle.json`.

### Obscura 0.2.2

Pasó DOM/JS/fetch, formulario, canvas, cookie, PNG, PDF y HTTPS. La imagen conserva fondo y canvas; difiere el aspecto del botón nativo frente a Chromium. **localStorage desaparece al recargar**. Reproducido después con Playwright en tres iteraciones: lectura inmediata correcta, lectura tras recarga `null`. Conexión Playwright, contexto nuevo, página y clic por rol funcionan. Su cadena CDP `Chrome/145.0.0.0` no identifica el motor real: Obscura no es Chromium.

Aporta un candidato ligero para extracción y tareas acotadas con renderizado. No lo pondría como motor predeterminado de Lupa: perder localStorage puede romper sesiones y aplicaciones web. Antes de integrarlo: corregir o resolver ese fallo, ampliar corpus real y mantener retorno explícito a Chromium.

### Lightpanda nightly 9448+baf45f03e

Pasó DOM/JS/fetch, formulario, cookies/localStorage, HTTPS y generación de PNG/PDF. Playwright conecta, crea contextos y hace clic por rol. Canvas devolvió píxeles transparentes en vez de rojos. Revisión visual del PNG: título y texto, sin fondo CSS ni canvas ni formulario visual equivalente. **Generar un archivo no implica representar la página como Chromium**. Su cadena CDP `Chrome/124.0.6367.29` es compatibilidad protocolaria, no su versión real.

Aporta la opción más pequeña de esta prueba para extracción de texto/DOM y automatizaciones compatibles. Conviene como servicio opcional bajo demanda para `/content` o trabajos de datos. No sustituye la sesión visual, capturas fieles, multimedia ni extensiones de Lupa. La documentación oficial describe precisamente [capturas de disposición textual](https://lightpanda.io/docs/reference/python), sin fidelidad a imágenes, fuentes o colores CSS.

### BrowserOS 0.50.3 / Chromium 151.0.8160.137

Pasó todos los casos comunes. El backend integrado respondió `status: ok, cdpConnected: true`. Fue el servicio de mayor RAM de esta ronda: 1,32 GiB tras las pruebas. No se realizaron tareas con modelos de pago ni se midió éxito de su agente IA.

Su aportación principal está en la orquestación y herramientas MCP, descritas en el [repositorio oficial](https://github.com/browseros-ai/BrowserOS). Para Lupa evaluaría una capa de herramientas sobre su API/CDP existente. Incorporar el navegador completo no ayuda al objetivo de aligerar la imagen.

### agent-browser 0.37.1

Pasó navegación, JS/fetch, rellenado/clic, cookies/localStorage, PNG y PDF. `snapshot -i` produjo referencias de controles: textbox Nombre `e2`, botón Enviar `e3`. Una prueba adicional verifica el píxel del canvas y HTTPS (ver `agent-extra.json`). Es una CLI que controla Chromium; el consumo medido incluye ese Chromium, daemon y dashboard, no solo el ejecutable.

Es la aportación más directa al manejo por agentes: snapshots, selectores semánticos y acciones sobre referencias. La [CLI oficial](https://github.com/vercel-labs/agent-browser) permite conectar por CDP. Para incorporarla a Lupa conviene reutilizar su Chromium ya abierto y resolver expresamente la autenticación Bearer del WebSocket: esta ronda probó su navegador propio, **no validó esa integración autenticada**. No recomendaría empaquetar otro Chromium.

## Recomendación

1. Mantener Lupa slim con Chromium como base completa.
2. Evaluar primero snapshots y acciones semánticas de agent-browser reutilizando CDP; medir después el incremento real de RAM y espacio de esa integración.
3. Ofrecer Lightpanda bajo demanda para extracción; definir una lista explícita de operaciones compatibles y recurrir a Chromium si falla.
4. Mantener Obscura experimental hasta resolver localStorage y validar aplicaciones reales.
5. Tomar de BrowserOS ideas de herramientas/MCP; su distribución completa no es una mejora de tamaño.

Estas son propuestas basadas en las pruebas, no integraciones ya instaladas en la imagen publicada. No se probaron anti-bot/CAPTCHA, cuentas reales, cargas largas, GPU, ARM ni capacidad de razonamiento de agentes con LLM.

## Evidencias y reproducción

- `results.json`: pruebas comunes, cinco latencias por servicio y muestras Docker.
- `playwright.json`: segunda ronda y reproducción de almacenamiento.
- `agent-extra.json`: canvas y HTTPS con la CLI.
- PNG/PDF locales en esta carpeta, excluidos de git; se revisaron visualmente los PNG de Lupa, Obscura y Lightpanda. PDF validado como archivo generado, no como fidelidad visual completa.
- Scripts en `../../tests/browsers/`, ejecutados con Bun en esta máquina y dependencias existentes de `/root/lupa/lab` y `vendor/lupa/app`. Son herramientas del laboratorio local, no una suite portable independiente.

Antes de repetir, detener todos los contenedores de navegador del laboratorio. Cada script arranca y detiene los servicios que prueba; al terminar arranca Lupa slim. Estado final previsto: solo Lupa slim encendido entre los navegadores, evitando mantenerlos todos en RAM.
