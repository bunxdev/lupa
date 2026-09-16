# Browser Use dentro de tu Lupa

El cliente conecta Browser Use 0.13.10 por CDP al Chromium visible de Lupa. Trabaja sobre la misma pestaña que `/live`, aunque haya otras pestañas con la misma URL. Selkies muestra los clics, la escritura y la navegación en directo.

Esta integración usa la **Actor API**: el asistente o los comandos deciden cada acción. No ejecuta `Agent`, no necesita una clave de un proveedor de modelos y no envía el contenido a un LLM. Referencia: [Actor de Browser Use](https://docs.browser-use.com/open-source/legacy/actor/basics).

## Probar desde este repositorio

Lupa debe estar iniciada con el código que incluye `/cdp`. Abre `http://localhost:6080` (o el puerto 6080 reenviado de tu entorno) y ejecuta:

```sh
python3 integrations/browser-use/run.py demo
```

La primera ejecución construye una imagen Python con Browser Use. El cliente comparte la red del contenedor Lupa para acceder a `127.0.0.1:3036`, sin depender de nombres de red o IPs del laboratorio. No instala ni inicia otro Chromium. Cada comando crea un contenedor de cliente temporal y lo elimina al terminar; la sesión de Lupa queda abierta.

El ejecutor obtiene el token configurado en Lupa, respetando `LUPA_API_TOKEN_FILE`, y lo pasa al cliente por stdin. No lo coloca en argumentos ni archivos. El socket Docker se utiliza sólo desde el host.

La demo abre una página local, escribe «Lupa», pulsa Saludar, marca una casilla, sigue un enlace y pulsa un botón al final. Comprueba el resultado y que los eventos de entrada sean `isTrusted`. El círculo rosa sigue los eventos de ratón de Chromium; es una ayuda visual, no el cursor del sistema operativo. Se retira al desconectarse el cliente.

## Control paso a paso

```sh
python3 integrations/browser-use/run.py open https://example.com
python3 integrations/browser-use/run.py inspect
python3 integrations/browser-use/run.py click 'a'
python3 integrations/browser-use/run.py scroll 500
python3 integrations/browser-use/run.py press Home
python3 integrations/browser-use/run.py screenshot /output/browser-use.png
```

Las capturas de `/output` aparecen en `downloads/` del host. `inspect` devuelve título, texto y controles de la página para elegir la siguiente acción. `click` y `fill` requieren un selector CSS que identifique un único elemento. Por ejemplo, después de abrir la demo:

```sh
python3 integrations/browser-use/run.py fill '#name' 'Mi Lupa'
python3 integrations/browser-use/run.py click '#greet'
```

Para un proyecto Compose distinto o una instancia específica:

```sh
python3 integrations/browser-use/run.py --container mi-lupa demo --pause 6
```

`--build` reconstruye la imagen. El código del cliente se monta desde este directorio en modo lectura; los cambios del script no requieren reconstruirla. El cliente conserva el viewport de la sesión visual y desconecta con `BrowserSession.stop()`.

## Usar Python directamente

Con Python 3.12 y la API de Lupa accesible:

```sh
python3 -m venv .venv-browser-use
.venv-browser-use/bin/pip install -r integrations/browser-use/requirements.txt
export LUPA_URL=http://127.0.0.1:3036
# Configura LUPA_API_TOKEN o LUPA_API_TOKEN_FILE en tu entorno.
.venv-browser-use/bin/python integrations/browser-use/client.py inspect
```

La URL de API debe apuntar a la raíz del servicio. Para HTTPS se usa `wss` al conectar CDP. Una sesión remota no necesita descargar navegadores mediante Playwright ni Browser Use.

## Contactos locales desde Google Maps

El recolector busca en la pestaña visible, alterna candidatos de las consultas y verifica dirección, categoría y teléfono público. Descarta teléfonos duplicados, fichas fuera del municipio y cierres permanentes. No requiere un modelo ni envía mensajes.

```sh
python3 integrations/browser-use/run.py leads \
  --query 'peluquerías en Zapopan' --query 'barberías en Zapopan' \
  --municipality Zapopan --limit 15 \
  --category peluquer --category barber --category belleza \
  --category hair --category beauty \
  --output /output/leads-peluquerias-barberias-zapopan-20260908
```

Cambia consultas, municipio, filtros y carpeta para otro giro. `--category` acepta fragmentos de categoría (cualquiera de los indicados); sin este argumento debes revisar manualmente la relevancia. La cantidad es el total, no la cantidad por consulta. Varias sucursales de una marca pueden aparecer si tienen teléfonos distintos.

Los resultados se guardan en `downloads/<carpeta>/`:

- `leads.csv`: Excel, UTF-8 con BOM y protección contra fórmulas.
- `leads.json`: datos estructurados y fuentes.
- `leads.html`: informe con filtro y enlaces a fichas y canales publicados.
- `state.json`: configuración, candidatos, avances, exclusiones y errores.

Para reanudar repite los argumentos y añade `--resume`. Si se encuentra un bloqueo o faltan contactos, se conservan resultados parciales y el comando termina con error. Maps puede cambiar sus selectores; un teléfono publicado no garantiza vigencia ni interés comercial.

El enriquecimiento se realiza después de revisar fuentes oficiales. Crea un JSON con objetos `{ "maps": "URL de leads.json", "email": {"value": "correo observado", "source": "URL fuente"}, "whatsapp": {"value": "enlace WhatsApp observado", "source": "URL fuente"} }`, omitiendo campos no localizados. Después:

```sh
python3 integrations/browser-use/export_leads.py downloads/CARPETA --enrichment downloads/CARPETA/enrichment.json
python3 -m unittest discover -s integrations/browser-use -p 'test_lead_data.py'
```

La skill [lupa-local-leads](../../skills/lupa-local-leads/SKILL.md) documenta el flujo completo. Para instalarla en Codex, copia su carpeta a `${CODEX_HOME:-$HOME/.codex}/skills/lupa-local-leads`; reinicia la sesión si no aparece. Mantén la copia sincronizada al modificar la versión del repo.

Puedes ampliar una ejecución con `--resume --limit 100` y añadir consultas: conserva municipio y filtros de categoría. Se mantienen los contactos guardados y se descubren candidatos nuevos. El límite no puede ser inferior a la cantidad ya guardada.

Abre el informe local en la sesión visible sin conectar Actor (que puede rechazar `file:`):

```sh
python3 integrations/browser-use/run.py report /output/CARPETA/leads.html
```

Si la revisión detecta un negocio fuera del giro pese a su categoría de Maps, exclúyelo conservando la trazabilidad:

```sh
python3 integrations/browser-use/export_leads.py downloads/CARPETA \
  --exclude-maps 'URL exacta de leads.json' \
  --reason 'Motivo verificado de exclusión' --review-source 'URL de la evidencia'
```

Después reanuda el recolector para cubrir el faltante. No ejecutes el exportador mientras el recolector esté escribiendo en la misma carpeta.
