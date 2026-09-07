# Lupa frente a Browser Use, Obscura, Scrapling y Lightpanda

> **Actualización: probados uno por uno.** Los cinco completaron la batería con los otros proyectos detenidos y Lupa pausado durante las pruebas ajenas. Browser Use también pasó sin timeout. Ver la [nueva prueba aislada](ISOLATED.md). El resto de este documento conserva los resultados anteriores bajo carga.

Comparación local realizada el 7 de septiembre de 2026. Contenedores nuevos e independientes, página de prueba común y artefactos en [results](results/). [Galería de capturas](results/gallery.html). [Instalación y metodología](README.md).

## Resultado práctico

**Mantendría Lupa para navegación visual y capturas.** Scrapling encaja como complemento de extracción. Obscura y Lightpanda completaron el flujo de datos con tiempos cortos en esta fixture, pero sus capturas muestran diferencias materiales frente a Chromium. Browser Use logró una pasada completa, aunque su conexión CDP no fue estable al repetirla en este entorno.

| Proyecto probado | JS, fetch y cookies | Formulario | PNG / PDF | Repetición final |
|---|---|---|---|---|
| Lupa: Bun 1.4.2, Playwright 1.59.1 | Sí | Sí, mediante JS en `/eval` | Sí, Chromium | 3/3 navegaciones |
| Browser Use 0.13.10 | Sí, pasada previa | Sí, Actor API | Sí, pasada previa; PDF mediante CDP | Timeout de conexión; 0 navegaciones |
| Scrapling 0.4.15, DynamicSession | Sí | Sí, callback Playwright | Sí, Chromium | 3/3 navegaciones |
| Obscura 0.2.2 | Sí | Sí, Puppeteer | Sí, diferencias visuales | 3/3 navegaciones |
| Lightpanda 1.0.0-nightly.9231+b21ec6085 | Sí | Sí, Puppeteer | Sí, representación de texto | 3/3 navegaciones |

Browser Use y Scrapling usan Chromium del sistema; la versión exacta se guarda en `results/*-chromium.txt`. Para Browser Use se conservan por separado el [resultado exitoso previo](results/browser-use-success.json) y el [fallo de repetición](results/browser-use.json). Su PNG/PDF pertenecen a la pasada exitosa. El resto de artefactos pertenece a la última pasada secuencial.

## Tiempos observados

Milisegundos, tres muestras. Se incluye la primera para mostrar el calentamiento y la variación; no se descartan muestras lentas.

| Proyecto | Muestra 1 | Muestra 2 | Muestra 3 | Mediana | Alcance |
|---|---:|---:|---:|---:|---|
| Lupa | 7643 | 1128 | 1116 | 1128 | Petición `/eval`, contexto y espera `networkidle` incluidos |
| Browser Use, pasada previa | 2439 | 5207 | 572 | 2439 | Navegación + sondeo de disponibilidad; repetición final fallida |
| Scrapling | 15797 | 328 | 223 | 328 | `fetch` hasta callback con fixture disponible; sesión previamente iniciada |
| Obscura | 306 | 38 | 38 | 38 | Navegación CDP hasta fixture disponible |
| Lightpanda | 216 | 43 | 45 | 45 | Navegación CDP hasta fixture disponible |

**No se deben convertir estas cifras en afirmaciones como «X es N veces más rápido».** Las rutas de ejecución y esperas son distintas, el host es compartido y hay variación muy grande. Browser Use falló en la repetición final. Un benchmark de motores requeriría misma política de espera, mismo cliente donde sea posible, más páginas/muestras y recursos dedicados.

Scrapling también extrajo las tres tarjetas por CSS con HTTP puro en unos 60 ms, pero el texto de disponibilidad siguió siendo «Cargando JavaScript…»: esa petición no ejecuta el JavaScript. Es una vía distinta y útil cuando el HTML inicial ya contiene los datos.

El [inventario](results/inventory.json) y la [instantánea de recursos](results/idle-stats.jsonl) están disponibles para auditoría. No se usan como ranking de memoria: los contenedores Python se habían reiniciado, mientras Lupa conservaba su escritorio y sesión activa. El tamaño de imagen tampoco incluye todas las instalaciones en capas escribibles y volúmenes.

## Qué aporta cada proyecto

| Proyecto | Enfoque | Relación con Lupa |
|---|---|---|
| Lupa | API HTTP sobre Chromium, sesión visual persistente y escritorio Selkies | Conserva la ventaja de observar y controlar una sesión con el navegador completo |
| Browser Use | Biblioteca de automatización y agentes que manejan el navegador | Complemento para tareas descritas en lenguaje natural; aquí se prueba sólo BrowserSession, sin LLM |
| Scrapling | Extracción, selectores y crawlers; puede usar HTTP o un navegador | Complemento para devolver datos estructurados y organizar extracción a escala |
| Obscura | Motor independiente con JavaScript, CDP y renderizado | Candidato experimental para trabajos que toleren diferencias visuales |
| Lightpanda | Motor independiente orientado a DOM, JavaScript y automatización | Candidato para extracción; su salida visual de texto no reemplaza las capturas de Chromium |

Browser Use se presenta como biblioteca/agente y requiere un proveedor de modelo para el flujo de agente mostrado en su [documentación oficial](https://github.com/browser-use/browser-use). Scrapling distingue peticiones HTTP y navegación con Chromium, y permite ejecutar acciones Playwright mediante `page_action`: [documentación de DynamicFetcher](https://scrapling.readthedocs.io/en/latest/fetching/dynamic.html). Obscura documenta su renderizador propio y sus diferencias respecto a Chromium: [rendering](https://github.com/h4ckf0r0day/obscura#rendering). Lightpanda documenta la exportación PNG/PDF como renderizado de texto: [dump a URL](https://github.com/lightpanda-io/browser#dump-a-url).

## Lectura visual

En la inspección de los PNG de la fixture, Obscura conserva el fondo, colores y distribución de tarjetas, pero presenta diferencias en los controles y el texto pintado en canvas. Lightpanda devuelve texto sobre fondo blanco: no conserva las tarjetas, colores ni canvas de la página. Por ello, que una operación `screenshot` devuelva un PNG no implica fidelidad visual.

Lupa, Browser Use y Scrapling muestran los mismos elementos básicos con el aspecto de Chromium. Se solicitó un viewport de 800×600, pero la salida nativa no es idéntica: Lupa/Obscura/Lightpanda producen 800×600, Browser Use produjo 800×513 y Scrapling 1600×1200 por escala de dispositivo. La galería conserva los archivos originales; no es una comparación píxel a píxel. [Validación de dimensiones y PDFs](results/artifact-validation.json).

La detección de canvas, `AudioContext` o un codec no equivale a comprobar que el navegador los implementa completamente. Esta prueba no reproduce audio/vídeo ni valida transmisión remota.

## Incidencias y límites

- El equipo tiene aproximadamente 8 GiB de RAM y ejecutaba además la sesión visual activa de Lupa. No se cerró ni navegó esa sesión durante la comparación.
- Browser Use tuvo timeouts con su lanzamiento automático de Chromium. La receta final inicia Chromium en `about:blank`, descubre un puerto CDP libre a través de `DevToolsActivePort` y conecta BrowserSession. Las extensiones predeterminadas se desactivan. Esto prueba Browser Use con CDP, no certifica su arranque automático en este entorno.
- Hubo procesos residuales y una repetición de Scrapling excedió el plazo del controlador. El ejecutor reinicia los contenedores Python antes y después de cada prueba para separar ejecuciones. Una ejecución exitosa no demuestra estabilidad sostenida.
- Se corrigieron adaptadores del laboratorio durante la preparación: Browser Use devuelve booleanos escalares como texto Python y Lupa espera un cuerpo JavaScript con `return` en `/eval`. Esos problemas del adaptador no se contabilizan como fallos de los productos.
- Sólo se usan tres navegaciones de una fixture pequeña y local. No se probaron sitios complejos, concurrencia, tareas con LLM, protección antibot, reinicios de perfiles, extensiones ni reproducción multimedia real.
- No hay ranking válido de motores por velocidad: cambian las APIs, esperas, procesos reutilizados, versiones de Chromium y límites de contenedor. Los tiempos sirven como observaciones de estas recetas.

## Qué incorporaría a Lupa

1. **Conservar Chromium y la sesión visual como backend principal.** En trabajos de captura o revisión humana, el diseño y los controles visibles forman parte del resultado.
2. **Añadir extracción estructurada.** Un endpoint que devuelva texto, enlaces y datos por selectores ahorraría scripts repetidos; Scrapling ofrece un modelo útil para esa capa.
3. **Facilitar la integración con agentes.** Un adaptador MCP o una conexión CDP opcional, restringida a la red interna, permitiría integrar herramientas como Browser Use. La API HTTP actual de Lupa no es por sí sola un endpoint CDP.
4. **Evaluar motores alternativos por tipo de trabajo.** Lightpanda puede resultar útil para DOM/datos; Obscura necesita una batería visual más amplia antes de considerarlo sustituto para PNG/PDF.
5. **Automatizar salud, instalación y pruebas de integración.** El laboratorio confirma el valor de `up.sh`, `doctor.sh`, comprobación de navegador disponible y pruebas de captura/PDF, además de manejar fallos de arranque y limpieza de procesos.

Estas son propuestas; esta tarea no cambia los endpoints ni el backend de Lupa.
