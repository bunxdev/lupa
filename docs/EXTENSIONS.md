# Extensiones y complementos de Lupa

Cada componente tiene su propio repositorio. La imagen de Lupa no los incorpora automáticamente.

| Componente | Tipo | Versión importada | Repositorio |
|---|---|---|---|
| Dedo | Servicio HTTP → X11 | 0.1.0 | [lupa_extension_dedo](https://github.com/bunxdev/lupa_extension_dedo) |
| Cinder | Chromium MV3: pestañas ↔ Markdown | 0.3.2 | [lupa_extension_cinder](https://github.com/bunxdev/lupa_extension_cinder) |
| Lumbre | Chromium MV3: lector Markdown | 0.1.0 | [lupa_extension_lumbre](https://github.com/bunxdev/lupa_extension_lumbre) |
| Mutus | Chromium MV3: silenciar anuncios detectados en YouTube | 0.2.0 | [lupa_extension_mutus](https://github.com/bunxdev/lupa_extension_mutus) |
| Tinta | Chromium MV3: contenido legible → Markdown | 0.2.0 | [lupa_extension_tinta](https://github.com/bunxdev/lupa_extension_tinta) |
| Vimium | Chromium MV3: navegación de teclado | 2.4.2 | [lupa_extension_vimium](https://github.com/bunxdev/lupa_extension_vimium) |

## Instalación

En Compose slim, clona cada extensión Chromium dentro de `deploy/slim/.runtime/extensions/<nombre>/`. En el Compose tradicional, usa `extensions/<nombre>/`. El manifiesto debe quedar en `/extensions/<nombre>/manifest.json` dentro del contenedor. Los repositorios publicados tienen el manifiesto en la raíz, incluido Mutus.

Lupa descubre los manifiestos al abrir el contexto. Guardar los archivos no instala la extensión en un contexto que ya está abierto; planifica la reapertura para no interrumpir la sesión. No se modificaron las pestañas del usuario durante esta publicación.

Dedo se instala por separado siguiendo su README. No tiene manifiesto Chromium: envía eventos al foco X11 real mediante el socket Docker. Configura su destino y mantén el acceso HTTP local o autenticado mediante túnel/proxy.

## Procedencia y comprobaciones

Se comparó el código de los proyectos locales con las copias instaladas. Los repositorios contienen código, instrucciones y licencias correspondientes, sin perfiles, credenciales, capturas privadas ni notas del workspace. Vimium conserva la autoría upstream y su licencia MIT; Tinta incluye los avisos de Readability y Turndown también en su ZIP.

Se validaron los cinco manifiestos y sus archivos referenciados, la sintaxis de 58 archivos JavaScript, el endpoint de salud y Compose de Dedo, y el empaquetado de Tinta. Esto no equivale a una prueba completa contra todos los sitios externos. Los resultados de teclado de Vimium están en [INPUT.md](INPUT.md) y en [skillslupa](https://github.com/bunxdev/skillslupa).
