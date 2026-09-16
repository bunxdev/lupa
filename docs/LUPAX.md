# LupaX — estado y decisiones, 16 de septiembre de 2026

## Qué contiene esta rama

`lupax` parte de `testing`. Conserva Lupa, el laboratorio de navegadores, Browser Use,
la recolección de contactos y añade el MCP estándar y una copia reproducible de
las recetas de Lupa slim desarrolladas en `bunxdev/debina`.

- `app/`: API Bun/TypeScript + Playwright, CDP autenticado y sesión visible.
- `lab/`: Obscura, Lightpanda, BrowserOS y agent-browser con Compose/scripts.
- `integrations/browser-use/`: control de la sesión y prospección; el ejecutor reconoce Bun nativo o instalado en `/config`.
- `integrations/mcp/`: 21 herramientas MCP stdio y clientes de prueba.
- `deploy/slim/`: Dockerfiles, Compose, fuente vendorizada y evidencia de optimización.

La copia slim conserva el snapshot indicado en `vendor/lupa/UPSTREAM` y las
adaptaciones probadas; no es un enlace automático al `app/` de esta rama.
Los scripts históricos de medición contienen rutas absolutas de esta máquina:
los JSON guardados son evidencia histórica, no una promesa de reproducción sin adaptar esas rutas.

## Funciones que debemos conservar

API: salud, capturas PNG/JPEG, HTML, PDF, JavaScript, contenido y ejecución de
extensiones. Sesión live: navegación, clic/teclado/ratón, cookies, descargas,
perfil persistente y extensiones. CDP comparte el navegador live; las operaciones
HTTP aisladas usan contextos separados. Los scripts de evaluación son cuerpos de
función (`return document.title;`). Selkies proporciona imagen, audio,
portapapeles y redimensionado para el uso remoto.

## Lupa slim y Docker Hub

Imagen probada: `bunxdev/lupa:slim-20260915`, **linux/amd64**.
Digest: `sha256:d7c94e9360e2b9d258b4cf659e586517a7b635a132e0e7b4694fb85d138cf6f6`.
Se verificó publicación, descarga y arranque. 656 MB aproximadamente en capas
comprimidas; 2,27 GB según Docker local frente a 3,87 GB de la base original.
El ahorro de runtime observado fue aproximadamente 57%; son medidas diferentes.

Usa Debian slim, componentes seleccionados de Selkies y un único Chromium completo
para headed y headless. Dependencias incluidas: arranca sin descargarlas de nuevo.
Se resolvieron el cierre ordenado de Playwright para persistir cookies, dependencias
de redimensionado y recursos del portapapeles de Selkies. Los informes en
`deploy/slim/reports/` registran alcance y límites (sin validar ARM/GPU/micrófono físico).
El MCP se ejecuta por separado: la imagen publicada no lo incluye.

## Comparación secuencial de navegadores

Los navegadores se probaron uno por uno, deteniendo el anterior. RAM observada
tras tareas cortas: Lupa slim 783 MiB; Obscura 60 MiB; Lightpanda 27 MiB;
BrowserOS 1,32 GiB; agent-browser 483 MiB. No son máximos ni servicios equivalentes.

- Obscura 0.2.2: JS, formularios, cookies, canvas, PNG/PDF; pierde localStorage al recargar, reproducido tres veces con Playwright. Experimental para tareas acotadas.
- Lightpanda nightly 9448+baf45f03e: muy ligero para DOM/datos; PNG/PDF textuales, canvas sin equivalencia visual. Posible servicio opcional, no sustituto completo.
- BrowserOS 0.50.3: pruebas comunes y backend CDP correctos; ideas de orquestación/MCP, no reducción de recursos. Agentes con LLM no evaluados.
- agent-browser 0.37.1: útil para snapshots y acciones semánticas; se probó con su propio Chromium. Integración directa con el CDP Bearer de Lupa pendiente.

La recomendación sigue siendo Chromium como base y motores alternativos bajo demanda.

## MCP y prueba real de OpenCode

MCP stdio en Bun/TypeScript: salud, inspección, navegación visible, interacción,
cookies, contenido, JS, capturas, PDF y extensiones. Imágenes como contenido MCP;
PDF como archivos y recursos. Las sesiones live son compartidas: evitar agentes
navegando simultáneamente. Secretos por entorno/archivo; no están en Git.

Pruebas: cuatro casos de protocolo, comprobación TypeScript y cliente stdio contra
Lupa real (navegación, clic/escritura, JS, PNG/PDF y resources/read).
OpenCode invocó realmente `lupa_lupa_health` y `lupa_lupa_live_inspect` y leyó
"10 contactos · Guadalajara". No fue solo una comprobación de conexión.

Después hizo 12 llamadas MCP para investigar orcas. Google mostró CAPTCHA;
continuó con DuckDuckGo y NOAA. El informe necesitó revisión editorial: navegar
correctamente no garantiza que todas las conclusiones del modelo sean correctas.
Los registros y contactos son datos de ejecución locales excluidos de Git.
Codex quedó registrado localmente; un catálogo de herramientas ya cargado necesita
recarga/nueva sesión. Claude Code tiene configuración preparada pero no se probó
su cliente, que no estaba instalado. stdio no es una URL para conectores web.

## Acceso y red de esta instalación

Lupa slim: API/CDP local `3136`; escritorio HTTPS local `6180` (destino contenedor
`3001`). Selkies necesita un contexto seguro fuera de localhost. El servicio usa
un certificado autofirmado. La instancia está en una VPS NAT de TierHive:
`0.0.0.0` no publica un puerto no asignado por el proveedor.
El usuario confirmó acceso público al escritorio por `https://149.56.240.225:3177/`.
Ese puerto es del escritorio, no del MCP ni de la API. No extrapolar a otras instalaciones.
Para nuevos despliegues usar loopback por defecto y configurar autenticación antes
de exponer terminales o escritorio. Nunca publicar el socket Docker ni un shell anónimo.

## Paneles evaluados (no integrados)

`browser-use/web-ui`: Gradio, tareas, modelos, pausa/reanudación, investigación y
configuración MCP/CDP. Fija Browser Use 0.1.48 frente a 0.13.10 de nuestra integración.
Su Dockerfile incorpora Chromium/Xvfb/noVNC: no añadirlo entero para duplicar el escritorio.
Interesan sus controles y flujos; autenticación CDP y compatibilidad deben probarse.

`nyaweb/buntty`: terminal Bun con sesiones por ruta, reconexión e historial en
memoria. No equivale a un gestor estructurado de tareas. Requiere autenticación,
límites y permisos adecuados; el original expone shell sin autenticación y monta
Docker. No se encontró licencia en el árbol revisado: confirmar permiso de
reutilización antes de incorporar código. Bun.Terminal es POSIX; una versión
nativa Windows requeriría otro backend. Dentro de Debian puede mantenerse Linux.

## Decisión: Voxy, proyecto independiente

Voxy será QEMU + Debian mínimo, con futuro soporte para Docker y aplicaciones Linux.
Lupa será una aplicación sobre Voxy. El primer hito es solo Debian arrancando,
red, SSH, persistencia y apagado limpio. Docker, Lupa, panel e instaladores siguen
como trabajo futuro en el checklist de Voxy.

Arquitectura prevista: lanzador nativo → QEMU → Debian → Docker → aplicaciones.
Aceleración según plataforma: KVM/Linux, HVF/macOS, WHPX/Windows. Las imágenes
Debian x86-64 y ARM64 serán distintas; emular otra CPU no equivale a virtualización
acelerada. La imagen actual de Lupa amd64 no garantiza soporte ARM64.

Se gana reutilización y aislamiento operativo, a costa de RAM, disco y arranque
adicionales. Carpetas compartidas, GPU/USB, suspensión y actualizaciones requieren
pruebas específicas. QEMU/VM no implica soporte universal de cualquier programa.
La alternativa nativa Lupa Desktop permanece como opción futura; no se mantendrá
un fork de Chromium en esta fase. Tauri es candidato para lanzador/instaladores,
no una decisión implementada ni un reemplazo automático de Chromium.

## Criterios y preferencias

- Usar `uv` si hace falta Python.
- Probar navegadores/VM de uno en uno para no sobrecargar la máquina.
- Separar resultados probados, propuestas y pendientes; no confundir salud local con acceso público.
- MCP estándar para varios clientes; OpenCode no es un requisito obligatorio de Lupa.
- Modelos gratuitos son opcionales, sujetos al proveedor; no basar el producto en reinstalaciones o rotación de IP para eludir cuotas.
- No incluir claves, perfiles, cookies, volúmenes ni informes personales en Git/imágenes.
- Versionar fuentes, fijar dependencias y verificar persistencia al actualizar.

## Fuentes

- https://github.com/bunxdev/lupa
- https://github.com/bunxdev/debina
- https://github.com/browser-use/web-ui
- https://github.com/nyaweb/buntty
- https://www.qemu.org/docs/master/system/introduction.html
- https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging
- https://bun.sh/reference/bun/Spawn/SpawnOptions/terminal
- https://tierhive.com/blog/tierhive-howto/tierhive-vps-ports

### Base ARM aportada para Voxy

El usuario aportó [bunxdev/qemu-debian-arm](https://github.com/bunxdev/qemu-debian-arm).
Su Debian 12 ARM64 arranca directamente kernel + initramfs, usa ext4 sin particiones,
SSH por clave suministrada por `fw_cfg` y crecimiento del disco al arrancar.
Voxy incorpora este proyecto como submódulo fijado a un commit para reutilizar
sus scripts y la Release v0.1.1 verificada, junto a una referencia Debian 13 amd64
con KVM. La versión ARM actual usa TCG; aceleración ARM nativa y empaquetado
para Windows/macOS siguen pendientes. Las pruebas nuevas se documentan en Voxy.
