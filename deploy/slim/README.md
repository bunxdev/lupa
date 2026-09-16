# debina

Recetas Docker basadas en Debian slim. Los servicios originales siguen en
`debian.yml`, `neofetch.yml` y `Dockerfiles/debian/Dockerfile`.

## Lupa con menos espacio

`lupa.yml` construye una imagen autocontenida con la API de Lupa, CDP autenticado,
Chromium persistente y el escritorio Selkies con vídeo, audio, teclado, ratón,
portapapeles, redimensionado y transferencia de archivos.

El código de Lupa procede del commit registrado en `vendor/lupa/UPSTREAM`.
Las adaptaciones del navegador permiten elegir `channel: chromium` para las
operaciones headless y delegar las señales de apagado al cierre ordenado de Lupa. Así utiliza el mismo binario completo que la sesión visual;
Playwright conserva contextos independientes por trabajo.

El [informe de medición y pruebas](reports/OPTIMIZATION.md) registra el resultado
de esta primera optimización.

### Arranque

```bash
cp -n .env.example .env
openssl rand -hex 32
# Pega el resultado en LUPA_API_TOKEN dentro de .env.
mkdir -p .runtime/extensions .runtime/downloads
docker compose -p debina-lupa -f lupa.yml up -d --build --wait
```

Los puertos predeterminados permiten probarla junto a la Lupa original:

| Función | Acceso local |
|---|---|
| API | http://127.0.0.1:3136 |
| Escritorio | http://127.0.0.1:6180 |
| CDP | ws://127.0.0.1:3136/cdp |
| Descubrimiento CDP | http://127.0.0.1:3136/cdp/json/version |

API y CDP usan `Authorization: Bearer <LUPA_API_TOKEN>`. `/health` y `/selftest`
son públicos, como en Lupa. El escritorio admite `SELKIES_USER` y
`SELKIES_PASSWORD`. Hay HTTPS interno en 3001 con certificado persistente; puede
publicarse mediante un override, por ejemplo `127.0.0.1:6181:3001`.

Para acceder desde otro ordenador, reenvía los puertos por SSH o usa el reenvío
de puertos de tu entorno. La publicación predeterminada está en loopback.

```bash
docker compose -p debina-lupa -f lupa.yml ps
docker compose -p debina-lupa -f lupa.yml logs -f
docker compose -p debina-lupa -f lupa.yml stop
docker compose -p debina-lupa -f lupa.yml start
```

### Qué cambia para reducir espacio

- Debian 13 slim y paquetes de ejecución con `--no-install-recommends`. Debian 13
  coincide con Python 3.13 y las bibliotecas nativas del Selkies fijado; la receta
  original de `debina` basada en Debian 12 permanece independiente.
- Construcción por etapas: del donante LinuxServer se copian el runtime y el
  frontend de Selkies, su Xvfb con redimensionado y los componentes de entrada.
  Las capas completas del donante no forman parte de la imagen final.
- Un Chromium completo para modo visible y nuevo modo headless; se evita instalar
  `chromium-headless-shell` por separado.
- Bun, Playwright, Chromium y Selkies quedan dentro de la imagen. El primer
  arranque funciona sin Internet y no ejecuta APT, npm, pip ni descargas.
- Se conservan fuentes Noto, CJK y emoji, bibliotecas multimedia, PulseAudio,
  Openbox, terminal, selector de extensiones y archivos del perfil.
- `/config` contiene sesiones, configuración y datos del usuario. No oculta una
  segunda instalación de los ejecutables para aparentar una imagen pequeña.
- La imagen final excluye Docker-in-Docker, compiladores y herramientas de
  construcción de la base general; son ajenos a las funciones documentadas de
  Lupa. El escritorio usa X11, igual que la configuración original.

El nuevo headless es un modo de Chromium distinto de `headless-shell`; las
pruebas validan las funciones de Lupa, no identidad píxel a píxel para cualquier
sitio. No se afirma que este sea el mínimo teórico posible. La receta mantiene
las fuentes y bibliotecas que permiten conservar el alcance funcional.

### Persistencia y extensiones

- Volumen `debina-lupa_lupa_config`: `/config`, perfiles live y por extensión.
- `.runtime/downloads`: descargas guardadas en el host.
- `.runtime/extensions/<nombre>/manifest.json`: extensiones desempaquetadas.
- `lupa` dentro del contenedor permite reabrir la sesión; `lupa close` y
  `lupa status` gestionan la sesión. También hay entrada en el menú de Openbox.

Un cierre ordenado deja que la API cierre Chromium antes de parar X y audio.
Un bloqueo exclusivo impide que dos contenedores de esta receta compartan
`/config` simultáneamente. Al recrear el contenedor se limpian únicamente los
locks obsoletos de Chromium, conservando cookies y perfiles.

Para migrar un perfil existente, detén la instancia propietaria y monta una copia
de su `/config` en un volumen nuevo, con PUID/PGID compatibles. No compartas un
perfil activo con la Lupa original: ésta no implementa el nuevo bloqueo. Mantén
la copia original para poder volver atrás. No hace falta migrar Bun ni la caché
de Playwright, porque la nueva imagen ya los incluye.

La API también admite `LUPA_API_TOKEN_FILE` mediante un archivo montado en sólo
lectura; tiene prioridad sobre la variable, como en Lupa. `LUPA_MAX_BODY_BYTES`,
`PUID`, `PGID` y los puertos se configuran en `.env` o con un override Compose.

### Comprobar funciones y tamaño

```bash
# Usa esta instancia de pruebas; abre/cierra su sesión y monta una extensión de prueba.
./scripts/lupa/test.sh
# Recreación, persistencia y arranque con red desactivada:
bun run scripts/lupa/lifecycle.ts
# Comparación con la instancia original lupa-lupa-1:
python3 scripts/lupa/measure.py
```

Los resultados están en `reports/`. La prueba del escritorio usa un cliente
Chromium real: decodifica el stream de Selkies, mide audio recibido, envía clics
y teclas y comprueba portapapeles y cambio de resolución. El clipboard se prueba
mediante el mismo mensaje que emite el panel de Selkies. No se mide calidad
perceptual, latencia WAN ni micrófonos/gamepads físicos. Las pruebas verifican
la configuración X11/CPU en Linux amd64; ARM y GPU requieren pruebas propias.

### Imagen para Docker Hub

```bash
# Sustituye TU_USUARIO por tu cuenta de Docker Hub.
LUPA_IMAGE=TU_USUARIO/lupa:slim docker compose -p debina-lupa -f lupa.yml build
# Tras revisar la imagen:
docker login
docker push TU_USUARIO/lupa:slim
```

Una vez publicada, otro equipo sólo necesita `docker run` o un Compose con
`image: TU_USUARIO/lupa:slim`, los puertos, el token y los volúmenes. No necesita
el repositorio Lupa ni instalar dependencias al arrancar. La construcción local
sí descarga la imagen donante y deja caché de BuildKit, que se mide por separado
y no se descarga al consumir la imagen final.

### Procedencia

- Lupa: https://github.com/bunxdev/lupa, commit en `vendor/lupa/UPSTREAM`.
- LinuxServer Selkies: digest OCI fijado en `Dockerfiles/lupa/Dockerfile`.
- Selkies: https://github.com/selkies-project/selkies, revisión
  `348bc4f61da66198573e7e57db9a266aca1991d5` utilizada por el donante.
- `clipboard-worker-8s-IQrUv.js` es el `clipboard-worker.js` sin modificar de esa
  revisión de Selkies (MPL-2.0). Se incluye en la ruta esperada por el frontend,
  pues el donante empaqueta la referencia al worker pero omite el archivo.
- Playwright y sus dependencias quedan fijados en `vendor/lupa/app/bun.lock`.
- Las bibliotecas conservan sus licencias y metadatos de distribución. Los
  paquetes Debian se resuelven al construir; las dos imágenes base usan digest.

### Imagen publicada en Docker Hub

Publicada para `linux/amd64`: `bunxdev/lupa:slim-20260915`.
El archivo `lupa.hub.yml` fija también el digest verificado para reproducibilidad.
Con `.env` configurado como arriba:

```bash
docker compose -p debina-lupa -f lupa.yml -f lupa.hub.yml pull
docker compose -p debina-lupa -f lupa.yml -f lupa.hub.yml up -d --no-build --wait
```

Consulta [la comparación secuencial de navegadores](reports/browsers/ANALYSIS.md).
