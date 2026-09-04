# Lupa

Lupa es un servicio de automatización de Chromium con API HTTP y una sesión visual persistente transmitida por Selkies WebRTC. Incluye audio, perfiles persistentes, descargas al host, carga de extensiones, captura de pantalla y contenido, render de HTML, PDF, evaluación JavaScript y controles de sesión en vivo.

![Autotest de video y audio](docs/screenshots/selftest-20260503-014754.png)

## Arquitectura

- `ghcr.io/linuxserver/baseimage-selkies:debiantrixie`: escritorio, nginx, Selkies, PulseAudio, openbox y s6-overlay.
- Bun y TypeScript: API HTTP.
- Playwright Chromium: navegador headless para trabajos aislados y contexto persistente headed para `/live`.
- `/config`: volumen persistente con binarios, cache de Playwright, preferencias y perfiles.
- `/extensions`: overlay de extensiones desempaquetadas, montado read-only.
- `/config/Downloads`: bind mount de descargas recuperables desde el host.

## Requisitos

- Docker Engine con el plugin Compose.
- Al menos 2 GiB libres para la imagen y las dependencias del primer arranque.
- Un token aleatorio de 32 caracteres como mínimo. Se recomienda generar 32 bytes:

```sh
cp .env.example .env
openssl rand -hex 32
```

Coloque el resultado en `LUPA_API_TOKEN` dentro de `.env`. El archivo está ignorado por Git. Lupa rechaza el arranque si falta el token o es evidentemente débil.

## Build Y Arranque

La imagen base se obtiene del registry y los scripts idempotentes de `custom-cont-init.d/` instalan Bun, dependencias del sistema y Chromium. Bun, navegadores y perfiles quedan cacheados en el volumen `/config`; el primer arranque es considerablemente más lento que los siguientes.

```sh
docker compose pull
docker compose up -d
docker compose logs -f lupa
curl http://127.0.0.1:3036/health
```

Para actualizar dependencias declaradas por la aplicación en una instancia levantada:

```sh
docker compose exec lupa bash -lc 'cd /app && bun install --frozen-lockfile'
```

No se necesita publicar ningún puerto para que los procesos del contenedor se comuniquen. Compose escucha por defecto sólo en `127.0.0.1` del host.

## Variables

| Variable | Predeterminado | Uso |
|---|---:|---|
| `LUPA_API_TOKEN` | vacío | Bearer obligatorio; mínimo 32 caracteres y 8 caracteres distintos. |
| `LUPA_API_TOKEN_FILE` | vacío | Alternativa read-only a la variable; contiene el token. Tiene prioridad. Requiere montar el archivo mediante un override Compose. |
| `LUPA_MAX_BODY_BYTES` | `5242880` | Límite de JSON, entre 1 KiB y 16 MiB. |
| `LUPA_API_BIND` | `127.0.0.1` | Dirección del host donde se publica la API. |
| `LUPA_API_PORT` | `3036` | Puerto de API en el host. |
| `SELKIES_BIND` | `127.0.0.1` | Dirección del host donde se publica Selkies. |
| `SELKIES_PORT` | `6080` | Puerto Selkies en el host. |
| `SELKIES_USER` | `lupa` | Usuario de acceso a Selkies. |
| `SELKIES_PASSWORD` | vacío | Password de Selkies. Defínalo antes de ampliar el bind. |
| `LUPA_HOSTNAME` | `lupa` | Hostname interno del contenedor. |
| `PUID`, `PGID` | `911` | Identidad usada por la imagen base. |

Al ejecutar la aplicación fuera de Compose, `API_HOST` vale `127.0.0.1` y `PORT` vale `3000`. Compose usa `API_HOST=0.0.0.0` sólo dentro de la red aislada del contenedor y restringe la publicación del host a loopback.

## Autenticación

`GET /health` y `GET /selftest` son públicos. `/selftest` debe ser navegable directamente desde la sesión headed para comprobar multimedia. Todo endpoint restante, incluidos estado, cookies y capturas live, requiere:

```text
Authorization: Bearer <LUPA_API_TOKEN>
```

Ejemplo:

```sh
set -a; . ./.env; set +a
curl -X POST http://127.0.0.1:3036/screenshot \
  -H "Authorization: Bearer $LUPA_API_TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"url":"https://example.com","fullPage":true}' \
  --output example.png
```

## Endpoints

Todos los cuerpos indicados son objetos JSON con `Content-Type: application/json`.

| Método | Ruta | Cuerpo principal | Respuesta |
|---|---|---|---|
| `GET` | `/health` | ninguno | `{ "ok": true }` |
| `GET` | `/selftest` | ninguno | Página pública de prueba de video y WebAudio. |
| `POST` | `/screenshot` | `{ url, viewport?, fullPage?, format?, selector?, waitFor? }` | PNG o JPEG. |
| `POST` | `/render` | `{ html, viewport?, fullPage?, format? }` | PNG o JPEG. |
| `POST` | `/pdf` | `{ url, format?, landscape? }` | PDF. |
| `POST` | `/eval` | `{ url, script }` | Resultado, consola y errores de página. |
| `POST` | `/content` | `{ url }` | HTML final de la página. |
| `POST` | `/extension/run` | `{ extension, url, script?, screenshot?, waitFor?, fresh?, viewport? }` | Resultado y captura base64 opcional. |
| `POST` | `/live` | `{ url, viewport? }` | Abre la URL en la sesión visual persistente. |
| `GET` | `/live` | ninguno | Estado y URL de la sesión. |
| `POST` | `/live/close` | ninguno | Cierra el contexto live. |
| `POST` | `/live/eval` | `{ script }` | Evalúa JavaScript en la página live. |
| `POST` | `/live/click` | `{ selector }` | Click por selector. |
| `POST` | `/live/mouse-click` | `{ x, y, button? }` | Click por coordenadas. |
| `POST` | `/live/mouse-move` | `{ x, y }` | Mueve el cursor. |
| `POST` | `/live/type` | `{ text }` | Escribe texto. |
| `POST` | `/live/key` | `{ key }` | Envía una tecla Playwright. |
| `POST` | `/live/screenshot` | ninguno | PNG del viewport actual. |
| `GET` | `/live/cookies` | ninguno | Cookies del contexto live. |
| `POST` | `/live/cookies/add` | `{ cookies }` | Añade entre 1 y 200 cookies Playwright. |

`viewport` admite enteros entre 64x64 y 7680x4320. Los scripts tienen un máximo adicional de 256 KiB. El límite total de cuerpo evita cargas sin cota, pero sigue permitiendo renderizados HTML grandes.

## Sesión Visual Y Audio

Abra una página y después visite Selkies:

```sh
curl -X POST http://127.0.0.1:3036/live \
  -H "Authorization: Bearer $LUPA_API_TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"url":"http://127.0.0.1:3036/selftest"}'

xdg-open http://127.0.0.1:6080/
```

Selkies transmite el display con redimensionado, teclado, ratón, portapapeles y audio. El servicio s6 prepara un sink PulseAudio antes de Chromium para que WebAudio funcione incluso si el cliente WebRTC se conecta después.

Para proteger la interfaz, defina `SELKIES_USER` y un `SELKIES_PASSWORD` fuerte. Si se publica fuera de loopback, use además un proxy de confianza con TLS y controles de acceso; WebRTC puede necesitar configuración de red adicional según el entorno.

## Persistencia, Extensiones Y Descargas

- El volumen Compose `lupa_config` conserva `/config`, incluido `live-profile`, `ext-profiles`, Bun y la cache de Chromium.
- `./extensions:/extensions:ro` es el punto de overlay reservado. Añada extensiones privadas como `extensions/<nombre>/manifest.json`; sus contenidos están ignorados por Git.
- `/extension/run` sólo acepta nombres `[A-Za-z0-9_-]` y usa un perfil independiente por extensión.
- La sesión live descubre todas las extensiones válidas al crear su contexto. Use `/live/close` y vuelva a abrirla para recargar cambios.
- `./downloads:/config/Downloads` conserva las descargas fuera del volumen y está ignorado por Git.

No incluya extensiones privadas, perfiles, descargas ni `.env` en imágenes o publicaciones. Para mounts externos, cree un archivo Compose override local sin versionarlo y mantenga los destinos `/extensions`, `/config` y `/config/Downloads`.

## Despliegue Side-by-side

Use nombres de proyecto y puertos distintos. Al no fijar `container_name`, Compose separa contenedores y volúmenes automáticamente:

```sh
LUPA_API_TOKEN="$(openssl rand -hex 32)" \
LUPA_API_PORT=3136 SELKIES_PORT=6180 \
docker compose -p lupa-secondary up -d
```

No use el mismo directorio de descargas o extensiones privadas si las instancias deben quedar aisladas; configure overrides separados.

## Seguridad

- Mantenga API y Selkies en loopback salvo necesidad explícita.
- Trate `/eval`, `/live/eval`, `/render` y las extensiones como ejecución de contenido no confiable.
- El token no se escribe en logs ni en respuestas. Los errores internos se reducen a tipo genérico para no registrar URLs o datos de página.
- El token protege la API, no sustituye TLS cuando cruza una red.
- La API puede alcanzar URLs visibles desde el contenedor. Aplique filtrado de egress si usuarios no confiables pueden enviar trabajos para limitar SSRF.
- Chromium usa `--no-sandbox` por compatibilidad con el contenedor. No considere el navegador una frontera de aislamiento fuerte.
- Revise permisos de `downloads`, extensiones y volumen persistente, donde pueden existir cookies y sesiones.

## Pruebas

```sh
docker compose exec lupa bash -lc 'cd /app && bun test && bunx tsc --noEmit'
docker compose config --quiet
git diff --check
```

El autotest manual está en `http://127.0.0.1:3036/selftest`: comprueba reproducción de video y genera tonos con WebAudio. Para una prueba completa, ábralo mediante `/live`, entre en Selkies y confirme imagen y audio.

Consulte [Camino.md](Camino.md) para la evolución técnica y decisiones de compatibilidad.
