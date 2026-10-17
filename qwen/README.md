# Colectores de Google Maps — Lupa 0.0.4

Dos clientes Python 3 de biblioteca estándar, derivados de la rama `qwen` y revisados para 0.0.4. Ambos reutilizan `integrations/browser-use/lead_data.py`; conserva la estructura del checkout. No hay una copia `qwen/lead_data.py`.

| Método | Comando | Qué consulta |
|---|---|---|
| UI mediante Lupa | `python3 qwen/qwen_leads.py` | Feed y fichas visibles por `/live` y `/live/eval` |
| HTTP experimental | `python3 qwen/qwen_leads_fast.py` | Feed del endpoint interno de Maps, sin navegador |

El método UI navega la pestaña gestionada por Lupa y puede cambiar el foco de esa instancia. Usa un perfil dedicado; no lo ejecutes sobre una sesión de trabajo activa.

## Prueba pequeña

```sh
# HTTP directo; no necesita Lupa ni un token.
python3 qwen/qwen_leads_fast.py \
  --query 'veterinarias en Zapopan' --municipality Zapopan \
  --category veterin --limit 3 --count 20 --output /ruta/privada/maps-http

# UI: configura el token de una instancia dedicada, sin escribirlo en el comando.
export LUPA_URL=http://127.0.0.1:3136
export LUPA_API_TOKEN_FILE=/ruta/privada/token
python3 qwen/qwen_leads.py \
  --query 'veterinarias en Zapopan' --municipality Zapopan \
  --category veterin --limit 3 --output /ruta/privada/maps-ui
```

También se admite `LUPA_API_TOKEN`; el archivo tiene prioridad. La UI conserva la opción `LUPA_CONTAINER` para obtener el token desde ese contenedor. El destino del token y `LUPA_URL` deben ser la misma instancia. La API no sigue redirecciones.

`--query` y `--category` son repetibles. El límite solicitado es de 1–200 contactos; no es una garantía. El feed HTTP permite pedir 20–100 fichas por consulta con `--count` (50 por defecto), sin paginación. La UI intenta reunir hasta `max(20, min(50, limit*2))` tarjetas por consulta, espera tres iteraciones sin novedades y limita el scroll a 30 iteraciones. Las consultas se recorren en el orden indicado.

## Reanudar

```sh
python3 qwen/qwen_leads_fast.py \
  --query 'veterinarias en Zapopan' --municipality Zapopan \
  --category veterin --limit 5 --count 20 --output /ruta/privada/maps-http --resume
```

- Usa el mismo método, municipio, categorías, idioma y país. Conserva las consultas anteriores; puedes añadir otras y aumentar el límite. No reduzcas el límite por debajo de los contactos guardados.
- Cada método tiene su propio `state.json`, con `schema_version: 1` e identificador `collector`. Los estados antiguos sin identificar y los de otro método se rechazan sin modificarlos. Inicia otra carpeta para esas corridas; los archivos anteriores se conservan.
- Hay un checkpoint antes de la primera petición, después de cada lote/consulta y tras cada ficha. Una interrupción con Ctrl+C o un error guarda lo reunido; el proceso no promete recuperar una respuesta que todavía no llegó.
- La vía HTTP reusa las candidatas guardadas y solo vuelve a consultar las búsquedas pendientes. Aumentar `--count` vuelve a descubrir candidatos; no refresca los contactos ya aceptados. La fecha del feed se conserva al aceptar una ficha guardada.
- Si no se alcanza el objetivo, el comando termina con código distinto de cero y deja exportaciones parciales. Cinco fallos consecutivos de detalle detienen el trabajo; las fichas fallidas quedan pendientes para reintentar.
- Usa un solo proceso por carpeta de salida. El JSON se reemplaza de forma atómica, pero no hay coordinación entre escritores concurrentes.

## Datos y límites

Se exportan `leads.json`, `leads.csv` y `leads.html`, además del checkpoint. Se filtra por municipio confirmado en la dirección, categoría y teléfono público; se deduplica por Maps, teléfono o nombre+dirección. La capa compartida escapa HTML y fórmulas CSV. Los datos no se contactan ni se califican y los teléfonos no se verifican por llamada.

La vía HTTP depende de `maps_pb.txt` y posiciones internas del JSON. **Es experimental**: un cambio de Google puede romperla. No se prometen velocidad, estabilidad ni extracción exhaustiva. Una lista vacía es un resultado vacío; HTML, 403/429 o una estructura desconocida detienen la ejecución. No intenta resolver CAPTCHAs ni eludir consentimientos. Si el formato cambia, revisa la respuesta y la plantilla en una sesión de pruebas antes de modificar los índices.

El feed no comprueba el cierre comercial: exporta `closure_status: unverified` y una nota visible. La UI descarta el texto de cierre permanente reconocido en la ficha; `not_marked_closed` significa que no detectó ese indicador, no una garantía de que el negocio esté abierto. Los resultados públicos cambian y requieren revisión humana según el uso.

Las exportaciones mantienen el esquema de contactos para `integrations/browser-use/export_leads.py`. Esto no hace interoperables los checkpoints de distintos recolectores.

## Imagen Docker

La imagen `bunxdev/lupa:0.0.4` incluye los scripts y la capa de datos. Dentro de una instancia **dedicada**, por ejemplo:

```sh
docker exec --user abc -e LUPA_URL=http://127.0.0.1:3036 lupa-pruebas \
  python3 /opt/lupa/qwen/qwen_leads.py \
  --query 'veterinarias en Zapopan' --municipality Zapopan \
  --category veterin --limit 3 --output /config/Downloads/maps-ui
```

La UI toma el token del entorno del contenedor. Desde el host también puedes usar estos clientes con Lupa 0.0.3: no requieren una API nueva.

## Pruebas

```sh
python3 -m unittest discover -s qwen -v
python3 -m unittest discover -s integrations/browser-use -v
```

La comprobación DOM es optativa: navega la instancia indicada y necesita que esta alcance el servidor de fixtures en el mismo host/contenedor.

```sh
LUPA_MAPS_DOM_TESTS=1 python3 -m unittest discover -s qwen -p test_dom.py -v
```

[Informe de validación 0.0.4](../docs/MAPS-0.0.4.md). No se incorporan los datasets de la rama `qwen` ni los scripts antiguos de captura CDP ligados a una sesión concreta.
