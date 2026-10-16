# Changelog

## 0.0.2

Comparación: `v0.0.1...v0.0.2`. Integra la evolución publicada en `testing`.

- CDP autenticado por HTTP y WebSocket sobre la misma sesión visible de Lupa.
- Descubrimiento CDP, conexiones simultáneas y reconexión tras cerrar la sesión.
- Integración Browser Use y recolección/exportación de contactos con filtros,
  deduplicación, reanudación y escape de HTML y fórmulas de hojas de cálculo.
- Laboratorio Docker y resultados históricos de comparación de navegadores.
- Conserva la API HTTP, cookies, descargas, extensiones y escritorio Selkies.

Esta versión se ejecuta desde el código fuente con `docker compose up -d`.
Requiere `LUPA_API_TOKEN`, como 0.0.1. API y escritorio se publican en loopback.
El primer arranque instala dependencias y Chromium; necesita acceso a Internet.
No corresponde a una nueva imagen `bunxdev/lupa:0.0.2`: la imagen publicada
`slim-20260915` se incorpora al proceso de distribución en 0.0.3.

## 0.0.1

Publicación inicial: API HTTP con Bearer, validación y límites de peticiones,
sesión persistente Chromium y escritorio Selkies. La etiqueta pública apunta
al historial publicado en GitHub, no al historial local anterior a la publicación.
