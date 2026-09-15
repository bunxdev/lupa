# Laboratorio de navegadores

Cinco servicios dentro de Lupa, preparados en la rama `testing` para Linux x86_64.
Se sigue la estructura de [nyaweb/micro](https://github.com/nyaweb/micro):
Compose, imágenes base, scripts montados y servicios con reinicio automático.
Los binarios y perfiles se conservan en volúmenes Docker. Obscura, Lightpanda y
agent-browser usan la red del host con listeners locales. Los escritorios de
Lupa y BrowserOS usan la red de Compose y publican sus puertos en loopback.

## Arranque

Desde la raíz del repositorio:

```sh
# Sólo para una instalación nueva; conserva el .env si ya existe.
cp -n .env.example .env
# Configura LUPA_API_TOKEN con el resultado de: openssl rand -hex 32
./lab/lab up -d
./lab/lab logs -f
./lab/lab ps
```

El primer arranque instala paquetes y descarga navegadores, por lo que tarda
varios minutos. `Up` por sí solo no significa que la instalación haya terminado.
Las descargas necesitan acceso a Debian, GitHub, npm y los servidores de Playwright.

| Servicio | Acceso desde esta máquina | Componente |
|---|---|---|
| Lupa | http://127.0.0.1:3036/health | API; las operaciones requieren Bearer |
| Lupa escritorio | http://127.0.0.1:6080 | Chromium visible mediante Selkies |
| Obscura | ws://127.0.0.1:9231 | Motor Rust, CDP |
| Lightpanda | ws://127.0.0.1:9232 | Motor Zig, CDP |
| BrowserOS escritorio | http://127.0.0.1:6081 | BrowserOS Linux completo mediante Selkies |
| BrowserOS CDP | http://127.0.0.1:9233/json/version | Descubrimiento CDP; WebSocket en el mismo puerto |
| agent-browser | http://127.0.0.1:4848 | Dashboard de sesiones y vista en directo |

Los enlaces de loopback se abren en la máquina que ejecuta Docker. Para verlos
desde tu ordenador, usa el reenvío de puertos de tu entorno o un túnel SSH:

```sh
ssh -N -L 6080:127.0.0.1:6080 -L 6081:127.0.0.1:6081 -L 4848:127.0.0.1:4848 usuario@servidor
```

### Uso

```sh
./lab/lab exec agent-browser agent-browser open https://example.com
./lab/lab exec agent-browser agent-browser snapshot
./lab/lab exec agent-browser agent-browser get title

# Sólo parar; conserva contenedores, paquetes y perfiles.
./lab/lab stop
./lab/lab start

# Recrear y volver a iniciar; conserva volúmenes, reinstala paquetes del sistema.
./lab/lab up -d

# Eliminar contenedores y red; conserva volúmenes.
./lab/lab down
```

`./lab/lab` es un atajo para `docker compose -f docker-compose.yml -f lab/compose.yml`.
Admite también `logs`, `restart`, `exec`, etc. El Compose original sigue pudiendo
iniciar sólo Lupa. Evita `down -v` si necesitas conservar sesiones y cachés.

BrowserOS es la edición con soporte Linux, no BrowserOS neo. Se instala su
paquete oficial completo, no sólo el backend ni un Chromium de sustitución.
La sesión visual y CDP funcionan sin una clave de modelos; para usar su agente
con IA debes configurar un proveedor en BrowserOS. El chat de agent-browser
requiere su propia configuración de proveedor, pero sus comandos y dashboard
funcionan sin ella. El backend integrado de BrowserOS usa CDP interno en 9100
y su HTTP en 9200 dentro del contenedor; los servicios internos no requieren
puertos adicionales del host. BrowserOS puede actualizar sus componentes
integrados automáticamente dentro del perfil persistente. Obscura y Lightpanda son motores headless y se utilizan por
CDP; sus capacidades de renderizado no equivalen necesariamente a Chromium.

### Versiones

- [Obscura](https://github.com/h4ckf0r0day/obscura): `v0.2.2`, binario oficial con renderizado.
- [Lightpanda](https://github.com/lightpanda-io/browser): `1.0.0-nightly.9448+baf45f03e`, fijado por SHA-256 en `compose.yml`.
- [BrowserOS](https://github.com/browseros-ai/BrowserOS): `0.50.3`, paquete `.deb` amd64 oficial.
- [agent-browser](https://github.com/vercel-labs/agent-browser): npm `0.37.1`, con Chromium de Debian.
- Lupa: código de esta rama y `app/bun.lock`.

Lightpanda publica un enlace nightly mutable. Si cambia y se necesita instalar
en un volumen nuevo, la comprobación SHA-256 fallará explícitamente: revisa la
nueva release antes de actualizar `LIGHTPANDA_SHA256`. Un volumen ya preparado
reutiliza su binario verificado. Los paquetes APT se resuelven al instalar.

## Comprobación funcional

Con los cinco servicios listos, desde la raíz:

```sh
bun install --cwd lab --frozen-lockfile
bun run lab/smoke.ts
```

La prueba sirve temporalmente una página en el puerto 18090. Comprueba título,
ejecución de JavaScript y cambios en el DOM en los motores CDP; con
agent-browser utiliza clic y lectura mediante su CLI. También prueba la API,
la autenticación y CDP de Lupa, y la respuesta HTTP de los dos escritorios y el
dashboard, además del health del backend integrado de BrowserOS. Escribe el resultado y capturas en `lab/.artifacts/`, ignorado por Git.
La respuesta HTTP de Selkies no demuestra reproducción de vídeo/audio WebRTC;
la comprobación audiovisual se hace entrando en el escritorio.

Los servicios son un laboratorio local de confianza. Obscura permite red privada
para las pruebas locales y los endpoints CDP permiten controlar su navegador.
La API de Lupa usa el token del `.env`; no se versionan secretos ni perfiles.
