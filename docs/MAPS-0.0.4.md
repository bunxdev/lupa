# Validación de los colectores Maps — 0.0.4

Pruebas realizadas el 17 de octubre de 2026 UTC (16 de octubre en México), en Linux AMD64. Código de partida: `qwen` en `f6410e512bfe58a0da98370695198bdb8a3ede33`. Se integran los dos colectores y la plantilla, sin datasets de contactos ni capturadores CDP ligados a una sesión.

## Resultado real

Consulta: `veterinarias en Zapopan`, municipio `Zapopan`, categoría `veterin`. Cada método reunió tres contactos y después reanudó la misma carpeta con objetivo de cinco. El método HTTP pidió 20 fichas por consulta.

| Comprobación | HTTP experimental | UI mediante Lupa |
|---|---:|---:|
| Contactos iniciales | 3 | 3 |
| Contactos después de `--resume --limit 5` | 5 | 5 |
| Teléfonos únicos finales | 5 | 5 |
| Identificadores de Maps comunes | 5 | 5 |
| Teléfonos coincidentes entre métodos | 5 | 5 |
| Direcciones coincidentes entre métodos | 5 | 5 |

La reanudación HTTP utilizó las candidatas guardadas sin repetir la búsqueda. La UI redescubrió el feed al ampliar el límite y abrió dos fichas nuevas. Es una muestra pequeña de una consulta y una localidad: no demuestra cobertura exhaustiva, rendimiento general ni vigencia de los teléfonos.

Se usaron un proceso API, display Xvfb y perfil nuevos, separados de los navegadores de trabajo. La API de prueba procedía de 0.0.3; los colectores no requieren cambios de API. Chromium: 147.0.7727.15; Python del runtime: 3.13. El contenedor de pruebas tenía un fallo de DNS (`ERR_NAME_NOT_RESOLVED`). Solo su Chromium de prueba utilizó un proxy CONNECT local limitado a dominios de Google, con TLS extremo a extremo. Esa configuración no forma parte de la imagen publicada. No se modificaron las pestañas ni los perfiles de trabajo.

## Fallos reproducidos y corregidos

- El parser HTTP original rechazaba respuestas válidas con menos de tres fichas. Ahora admite una, dos o ninguna; separa un resultado vacío de un cambio de formato.
- Un fallo en la segunda consulta podía perder el progreso de la primera. Ahora hay checkpoints antes de la primera petición, por consulta/lote y por ficha, incluidos errores e interrupciones.
- El feed declaraba `permanently_closed: false` sin comprobarlo. Ahora conserva el estado desconocido y lo exporta como `closure_status: unverified`, con nota visible.
- Los estados carecían de identidad de método. Ahora llevan versión y colector; se rechazan estados antiguos, cruzados o con filtros incompatibles sin sobrescribirlos.
- Se guardan los cinco errores consecutivos antes de detenerse y las fichas fallidas siguen pendientes. Los bloqueos/consentimientos detienen la ejecución sin intentar resolverlos.
- La API cliente no sigue redirecciones con el token Bearer. La extracción reconoce las dos formas españolas de cierre permanente y el aviso de tráfico inusual.

## Pruebas automatizadas

- **17 pruebas unitarias de regresión aprobadas**: parser, filtros de municipio/categoría/teléfono, duplicados, checkpoints, reanudación, errores, bloqueos y redirecciones. La fecha de una ficha guardada conserva la fecha de recuperación del feed.
- **5 pruebas existentes de la capa de datos aprobadas**: se reutiliza esa capa sin modificarla.
- **1 prueba DOM optativa aprobada** en Chromium real: feed, ficha, teléfono, cierre permanente y aviso de bloqueo mediante fixtures locales. Se omite por defecto para no navegar una sesión de trabajo.

```sh
python3 -m unittest discover -s qwen -v
python3 -m unittest discover -s integrations/browser-use -v
# Solo con una instancia dedicada en el mismo host/contenedor:
LUPA_MAPS_DOM_TESTS=1 python3 -m unittest discover -s qwen -p test_dom.py -v
```

El workflow `Maps collectors` ejecuta las pruebas sin consultar Google en Python 3.11 y 3.13. La ejecución real de Maps y la prueba DOM son comprobaciones separadas; CI no consulta Google. Las evidencias de empaquetado y publicación se adjuntan a la release.

## Límites de esta versión

El endpoint HTTP es interno y experimental; puede cambiar. No hay paginación HTTP, ni garantía de alcanzar el límite solicitado. La UI depende de los selectores y textos de Maps. Ninguno de los métodos realiza llamadas para verificar teléfonos. `not_marked_closed` solo indica que la UI no reconoció una marca de cierre.

Los checkpoints antiguos no se migran automáticamente: se conservan y se debe iniciar una carpeta nueva. Se admite un escritor por carpeta. Las exportaciones incompletas se conservan y el proceso devuelve un código distinto de cero.

La imagen incluye los clientes en `/opt/lupa/qwen/` y la capa de datos en `/opt/lupa/integrations/browser-use/`. El núcleo HTTP/CDP/MCP no cambia respecto a 0.0.3; esta validación se centra en los colectores y su empaquetado, no repite toda la matriz del escritorio de la release anterior. Los datasets reales y tokens de prueba no se publican.

Instrucciones y opciones: [qwen/README.md](../qwen/README.md).
