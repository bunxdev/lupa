# Revisión de Lupa — 2026-10-16

## Procedencia y alcance

- La copia local original estaba en `8bae0e7`; no comparte historia con el `main` público revisado (`357dc8b`). Su etiqueta local `v0.0.1` no se sobrescribió.
- La secuencia pública revisada es `main` → CDP/Browser Use (`9356694`) → laboratorio (`7d13b0f`) → MCP/slim (`53e7210`) → colectores experimentales (`f6410e5`).
- 0.0.2 parte de `testing`; 0.0.3 parte de `lupax` e integra 0.0.2 conservando el historial. `qwen` y sus conjuntos de contactos quedan fuera.
- Al comenzar, Docker Hub ofrecía `slim-20260915` para Linux AMD64. 0.0.3 reutiliza ese runtime por digest y sustituye la aplicación por `app/` de esta release.
- 0.0.2 distribuye código y Compose tradicional. No se creó una imagen Docker con ese número.
- La integración MCP mantiene su versión de paquete propia; la versión global se registra en `VERSION` y las etiquetas OCI.

## Correcciones realizadas

- Una fuente canónica de aplicación para la imagen; la copia vendorizada queda como referencia histórica.
- Puerto HTTP del escritorio, imagen de `.env.example` y proyecto de validación coherentes con las instrucciones.
- Límite de texto MCP alineado con HTTP; prueba de regresión.
- Validación compatible con autenticación del escritorio y token por archivo.
- Regresión de eventos de teclado en CDP y documentación de los destinos API, CDP y X11.

## Evidencia y límites

En la candidata 0.0.3 pasaron ocho pruebas de API/CDP, quince comprobaciones funcionales, el escritorio real por Selkies, persistencia/recreación, arranque sin red y el smoke MCP de 21 herramientas. El código 0.0.2 pasó sus ocho pruebas de API/CDP con el Chromium del runtime slim; su instalación tradicional desde cero no se validó de extremo a extremo.

Las pruebas usan cuentas, perfiles y páginas ficticias. Los informes previos del repositorio se consideran históricos. Se adjuntan por separado los resultados nuevos y sus límites.

La primera prueba CDP en el VPS superó su límite de 60 segundos, en un entorno con 65–83 % de CPU steal. Se conserva ese resultado; no se cuenta como prueba aprobada. La imagen candidata se trasladó a un Docker temporal aislado para contrastarla, sin usar el perfil ni las pestañas del usuario.

Los atajos de Vimium aportados por el usuario se contrastaron con el keymap instalado de 2.4.2. La atribución de intermitencias a MV3 sigue siendo una hipótesis. No se incluyen Vimium ni el helper X11 como dependencias de la imagen.

## Trabajo complementario

`skillslupa` recibió documentación de Vimium, X11 y colectores de Maps en `fc734c83e8c82d3010723842c8f3a5616236cf16`. Queda pendiente integrar y validar los colectores experimentales en una futura release de Lupa; no se promete extracción exhaustiva ni reanudación cruzada entre métodos.
