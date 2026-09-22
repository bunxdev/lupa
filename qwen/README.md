# qwen/ — Recolectores optimizados de contactos de Google Maps

Scripts propios para recolectar contactos públicos de negocios en Google Maps,
creados **sin modificar** los scripts originales de `integrations/browser-use/`
(esos se conservan tal cual y siguen siendo la vía «UI visible» de la skill
`lupa-local-leads`). Solo Python 3 de biblioteca estándar: sin pip, uv, venv ni
dependencias de terceros.

## Archivos

| Archivo | Propósito |
|---|---|
| `qwen_leads_fast.py` | **Colector rápido (recomendado).** HTTP directo al endpoint interno de búsqueda de Maps. Sin navegador, sin Lupa, sin token. ~9–10 s por 100 contactos. |
| `qwen_leads.py` | **Colector v1 (UI).** Maneja la sesión visible de Lupa por su API HTTP (`/live`, `/live/eval`). Útil cuando quieres *ver* el trabajo en Selkies. |
| `lead_data.py` | Copia de la capa de datos probada del repo (`integrations/browser-use/lead_data.py`): normalización, filtros, deduplicación y export CSV/JSON/HTML. Ambos colectores la reutilizan sin modificarla. |
| `maps_pb.txt` | Plantilla `pb` capturada de la petición real que la SPA de Maps hace a su endpoint de búsqueda. |
| `cdp_net.js`, `cdp_net_scroll.js` | Capturas por CDP (WebSocket crudo, Bun) para re-capturar la plantilla si Google cambia el formato. |

Ambos colectores usan el mismo `state.json` que `integrations/browser-use/leads.py`,
así que las carpetas de salida son interoperables (`--resume`, `export_leads.py`,
skill `lupa-local-leads`).

## Cómo se crearon (proceso)

1. **Reuso, no reescritura.** `lead_data.py` ya estaba probado
   (`test_lead_data.py`), así que los colectores nuevos solo producen
   «fichas de detalle» con su esquema y delegan validación, filtros y
   exportación en esa capa.

2. **v1 (`qwen_leads.py`):** navegador gestionado por Lupa, controlado desde el
   host con `urllib` contra `/live` (navegar) y `/live/eval` (evaluar JS en la
   pestaña visible). Cero CDP, cero librerías.

3. **El bug que motivó la v2:** el discovery por scroll del feed de Maps se
   quedaba en ~18 fichas por consulta (la condición «un scroll sin progreso»
   cortaba antes de que cargara el siguiente lote; el feed en realidad da ~40
   y termina en «Iniciar sesión»). Se corrigió en `integrations/browser-use/leads.py`
   (scroll a fondo + tolerancia de 3 cargas sin progreso) y **luego se revirtió**
   a petición del usuario: los scripts originales quedaron intactos.

4. **v2 (`qwen_leads_fast.py`) — descubrimiento del endpoint:**
   - La SPA de Maps trae los resultados de `/search?tbm=map&pb=...`.
   - Hooks de `fetch`/XHR en la página **no funcionaban** (la SPA conserva la
     referencia nativa a `fetch` desde el bundle), así que se capturó con CDP
     crudo: `cdp_net.js` abre un WebSocket al `webSocketDebuggerUrl` del
     navegador y registra `Network.responseReceived` + `Network.getResponseBody`.
   - De la respuesta real se aisló la carga útil: la primera línea es el
     envelope `)]}'` y el resto es JSON; los resultados están en `data[64]`
     (lista de ítems; `item[1]` es la ficha).
   - El `pb` se guardó como plantilla (`maps_pb.txt`) paramétrizándose solo el
     segmento `!1s<consulta>` y el tamaño de página `!7i<N>` (20–100; con 100
     una sola petición por consulta).

5. **Mapa de campos de la ficha** (índices estables + respaldo):
   `11`=nombre, `13[0]`=categoría, `10`=cid, `39` (o `2,2`)=dirección,
   `7[0]`=sitio web, `178`=bloque de teléfono (`178,0,1,1,0` internacional,
   `178,0,0,0` local, y por último escaneo del bloque con patrón de teléfono).
   El `cid` (`...:0x<hex>`) se convierte a decimal para la URL
   `https://www.google.com/maps?cid=<decimal>`. Si falta nombre o cid, la ficha
   se descarta; si la estructura cambió, el colector **falla explícito** en
   vez de exportar basura.

6. **Validación del método:** contra los 100 contactos de veterinarias
   recolectados por UI (Lupa/CDP) hubo **71 coincidencias por teléfono** y 29
   únicas de la vía rápida → misma información pública, distinto recorrido.

## Uso

```sh
# Rápido (sin navegador): ~10 s por 100 contactos
python3 qwen/qwen_leads_fast.py \
  --query 'veterinarias en Zapopan' --query 'clínicas veterinarias en Zapopan' \
  --municipality Zapopan --limit 100 --category veterin \
  --output /root/lupa/downloads/leads-fast-zapopan-AAAAMMDD

# Reanudar (mismo municipio/categorías; el límite no puede bajar del guardado)
python3 qwen/qwen_leads_fast.py ... --resume

# v1, sesión visible de Lupa (requiere Lupa corriendo; token por LUPA_API_TOKEN(_FILE))
python3 qwen/qwen_leads.py --query 'escuelas en Zapopan' --municipality Zapopan \
  --limit 50 --category escuela --output /root/lupa/downloads/leads-escuelas-zapopan-AAAAMMDD
```

`--category` acepta fragmentos de categoría repetibles (ej. `veterin`,
`escuela`, `colegio`). Se descartan: sin teléfono público, dirección fuera del
municipio (cuando no confirma), categoría no coincide y duplicados por
teléfono/Maps/nombre+dirección.

## Limitaciones conocidas

- **Máx. 100 fichas por consulta** (`!7i100`); el token de continuación del feed
  es de un solo uso / ligado a la sesión, por lo que no hay paginación. Para
  más de 100, añadir consultas o usar la variante UI con scroll.
- **`permanently_closed` no lo expone el feed de búsqueda**; solo la variante
  UI lo verifica por ficha. La vía rápida puede incluir algún negocio cerrado
  (revisable cruzando con una corrida UI).
- Si Google cambia la respuesta, el colector rápido falla explícito:
  re-capturar `maps_pb.txt` con `cdp_net.js` (Maps debe estar abierto en la
  sesión de Lupa) y, si cambió el mapa de campos, actualizar los índices.
  Ese punto es el indicado para reparación asistida por LLM.

## Resultados incluidos en `downloads/`

| Carpeta | Giro | Cantidad | Método |
|---|---|---|---|
| `leads-veterinarias-zapopan-20260921/` | Veterinarias, Zapopan | 100 | UI (Lupa/CDP, repo) |
| `leads-fast-zapopan-20260922/` | Veterinarias, Zapopan (prueba) | 100 | HTTP rápido |
| `leads-fast100-zapopan-20260922/` | Veterinarias, Zapopan | 100 | HTTP rápido (validado vs UI) |
| `qwen-fasttest-20260922/` | Prueba del endpoint | — | HTTP rápido |
| `qwen-fasttest-http-20260922/` | Prueba del endpoint | — | HTTP rápido |
| `leads-taquerias-zapopan-20260922/` | Taquerías, Zapopan | 100 | UI (Lupa/CDP, repo) |
| `leads-escuelas-zapopan-20260922/` | Escuelas, Zapopan | 50 | HTTP rápido |
| `computadoras-guadalajara-20260915/` (+`-revisado`) | Computadoras, Guadalajara | — | UI (corridas previas) |
