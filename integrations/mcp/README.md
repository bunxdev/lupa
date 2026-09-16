# Lupa MCP

Servidor MCP estándar por **stdio**, hecho con Bun/TypeScript y el SDK oficial.
Conecta Codex, OpenCode, Claude Code, Claude Desktop y otros clientes locales a
una instancia existente de Lupa. No inicia Chromium ni abre puertos; reutiliza
la API autenticada. Los comandos `lupa_live_*` controlan la sesión que se ve en
Selkies. Los demás trabajos usan los contextos aislados de Lupa.

## Instalar y arrancar

```sh
cd integrations/mcp
bun install --frozen-lockfile
LUPA_URL=http://127.0.0.1:3136 bun --env-file=/ruta/privada/lupa.env run src/index.ts
```

El archivo privado debe contener `LUPA_API_TOKEN` o `LUPA_API_TOKEN_FILE`.
Se puede proporcionar cualquiera directamente en el entorno. El archivo de token
contiene solo el secreto; tiene prioridad sobre `LUPA_API_TOKEN`.
No escribas tokens en configuraciones compartidas. stdout se reserva al protocolo MCP.

| Variable | Valor predeterminado |
|---|---|
| `LUPA_URL` | `http://127.0.0.1:3036` (slim de esta máquina: `3136`) |
| `LUPA_API_TOKEN` | Obligatorio si no hay archivo de token |
| `LUPA_API_TOKEN_FILE` | Archivo de token opcional |
| `LUPA_MCP_OUTPUT_DIR` | `~/.local/share/lupa-mcp/artifacts` |
| `LUPA_MCP_TIMEOUT_MS` | `60000`, rango 1000–300000 |

## Clientes

Sustituye las rutas absolutas por las de tu instalación. En esta máquina el
archivo privado es `/root/debian/.env` y el servidor está en
`/root/lupa/integrations/mcp/src/index.ts`.

### OpenCode

Añade a `~/.config/opencode/opencode.jsonc`, conservando sus otras opciones:

```json
{
  "mcp": {
    "lupa": {
      "type": "local",
      "command": ["/root/.bun/bin/bun", "--env-file=/root/debian/.env", "run", "/root/lupa/integrations/mcp/src/index.ts"],
      "environment": {"LUPA_URL": "http://127.0.0.1:3136"},
      "enabled": true,
      "timeout": 15000
    }
  }
}
```

Comprueba con `opencode mcp list`. Ejemplo de petición:
«Usa lupa para investigar talleres de reparación en Guadalajara. Revisa las
fuentes, recopila los teléfonos públicos y no envíes mensajes».

### Codex

```sh
codex mcp add lupa --env LUPA_URL=http://127.0.0.1:3136 -- \
  /root/.bun/bin/bun --env-file=/root/debian/.env run /root/lupa/integrations/mcp/src/index.ts
codex mcp get lupa
```

Abre una sesión nueva o recarga los MCP del cliente para cargar la configuración.
Registrar el servidor en disco no añade herramientas retroactivamente a una
conversación cuyo catálogo ya estaba cargado.

### Claude Code / Claude Desktop

Configuración estándar `mcpServers` (en `.mcp.json` del proyecto para Claude Code,
o en `claude_desktop_config.json` para Desktop):

```json
{
  "mcpServers": {
    "lupa": {
      "command": "/root/.bun/bin/bun",
      "args": ["--env-file=/root/debian/.env", "run", "/root/lupa/integrations/mcp/src/index.ts"],
      "env": {"LUPA_URL": "http://127.0.0.1:3136"}
    }
  }
}
```

Claude Code también permite registro de usuario con `claude mcp add --transport
stdio --scope user --env LUPA_URL=http://127.0.0.1:3136 lupa -- ...` seguido del
comando Bun anterior. La configuración de usuario de esta máquina se preparó en
`~/.claude.json`; Claude no estaba instalado, por lo que no se afirma una prueba
con su cliente. Para Desktop en otra computadora debes ejecutar el servidor allí
con acceso a la API por túnel SSH, o usar SSH como comando stdio que ejecute Bun
en esta máquina. Estas rutas `/root/...` no existen en tu computadora personal.

Esta versión implementa stdio; no es una URL MCP para conectores web que exijan
Streamable HTTP. La URL del escritorio Selkies tampoco es un endpoint MCP.

## Herramientas (21)

- Estado: `lupa_health`, `lupa_live_status`, `lupa_cdp_info`.
- Navegación visible: `lupa_live_open`, `lupa_live_close`, `lupa_live_inspect`.
- Interacción: `lupa_live_click`, `lupa_live_type`, `lupa_live_key`,
  `lupa_live_mouse_click`, `lupa_live_mouse_move`, `lupa_live_eval`.
- Sesión: `lupa_live_cookies`, `lupa_live_add_cookies`, `lupa_live_screenshot`.
- Trabajos aislados: `lupa_content`, `lupa_eval`, `lupa_screenshot`, `lupa_render`,
  `lupa_pdf`, `lupa_extension_run`.

`inspect` devuelve texto visible y selectores de hasta 100 controles. No pretende
ser el árbol de accesibilidad completo; no atraviesa iframes ni shadow DOM. Para
casos complejos usa evaluación JS, capturas o CDP. En los scripts JS se escribe
un cuerpo de función: `return document.title;`, no solo `document.title`.

Las imágenes se devuelven como contenido MCP de tipo image y archivo local.
Los PDF se guardan con permisos 0600 y se devuelven como resource_link. Se pueden
leer mediante `resources/read`; las URI `lupa://artifacts/...` duran la sesión MCP,
mientras los archivos permanecen en disco hasta que se borren. El texto se limita
a 100000 caracteres y las respuestas HTTP a 32 MiB. Los archivos no se purgan
automáticamente. `extension_run` devuelve el JSON de la API, incluido base64 si
se solicita captura, sujeto al límite de texto.

Las sesiones live se comparten: dos clientes pueden interferir si navegan a la
vez. Cerrar el MCP solo desconecta el cliente; `lupa_live_close` cierra el navegador
compartido. Las páginas son contenido no confiable y no deben tomarse como
instrucciones del usuario. El token concede las mismas capacidades que la API.

## Verificación

```sh
bun test
bun run typecheck
# Prueba real: mueve temporalmente la pestaña live y restaura su URL al terminar.
LUPA_URL=http://127.0.0.1:3136 bun --env-file=/root/debian/.env run src/smoke.ts
```

La prueba real usa un cliente MCP por stdio sin LLM: descubrimiento, salud,
navegación, inspección, clic/escritura, JS visible y aislado, PNG, PDF y lectura
MCP de archivos. No requiere Python; si se añade un componente Python, usar `uv`.

Fuentes de integración: [SDK MCP](https://ts.sdk.modelcontextprotocol.io/server),
[OpenCode](https://opencode.ai/docs/mcp-servers/),
[Codex](https://developers.openai.com/codex/mcp/),
[Claude Code](https://code.claude.com/docs/en/mcp).

### Uso desde una sesión que todavía no cargó el MCP

El cliente de consola utiliza el mismo protocolo, sin abrir otro navegador:

```sh
LUPA_URL=http://127.0.0.1:3136 bun --env-file=/root/debian/.env run src/call.ts lupa_live_inspect '{}'
```

Sin nombre de herramienta lista las herramientas disponibles. El tercer argumento
es un objeto JSON de parámetros. Las capturas incluyen base64 en esta salida;
redirige el resultado a un archivo cuando necesites procesarlas.
