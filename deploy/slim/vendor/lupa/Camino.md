# Camino técnico

Este documento resume la evolución genérica de Lupa y las fronteras que conviene conservar.

## Etapa 1: Automatización HTTP

La primera capa ofrece operaciones aisladas de Chromium para capturas, contenido, PDF, renderizado de HTML y evaluación. Cada trabajo headless obtiene un contexto nuevo, evitando que cookies y estado se mezclen accidentalmente entre peticiones.

## Etapa 2: Navegador observable

La sesión `/live` añade un contexto headed reutilizable sobre el display de Selkies. Esto permite observar y controlar la misma página por API, ratón y teclado remoto. PulseAudio se prepara antes del navegador para que la transmisión incluya audio de forma fiable.

## Etapa 3: Estado útil

El contexto live usa un perfil en `/config`, las extensiones automatizadas reciben perfiles separados y las descargas terminan en un bind mount explícito. La persistencia deja de depender del ciclo de vida del contenedor sin mezclar esos datos con el código público.

## Etapa 4: Extensibilidad

`/extensions` se mantiene como punto de overlay read-only. El núcleo sólo descubre manifiestos y gestiona contextos; las extensiones concretas, sus credenciales y sus datos permanecen fuera del repositorio. `/extension/run` conserva una interfaz genérica y nombres de directorio restringidos.

## Etapa 5: Publicación endurecida

La API queda publicada en loopback por defecto y todos los controles exigen un Bearer fuerte. Se incorporan comparación constante, rechazo de arranque sin secreto, límites de cuerpo y de campos de alto impacto, validación de viewport y errores sin datos de petición. Health y la página multimedia permanecen públicas por diseño.

Compose parametriza binds y puertos, evita nombres globales de contenedor y mantiene volúmenes por proyecto. Esto permite validación side-by-side sin tocar una instancia activa.

## Siguientes pasos

- Fijar la imagen base por digest y automatizar la revisión periódica de dependencias.
- Añadir pruebas de integración efímeras para screenshot, PDF, audio y persistencia de perfil.
- Evaluar políticas de egress o allowlists para despliegues multiusuario.
- Añadir métricas sin URLs, cabeceras, scripts, cookies ni nombres de archivos.
- Documentar TURN/TLS para despliegues WebRTC que dejen loopback.

La prioridad de evolución es preservar compatibilidad funcional y mounts estables, haciendo explícita cada ampliación de exposición o privilegios.
