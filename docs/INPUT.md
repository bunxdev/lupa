# Teclado, pestañas y Vimium

## Tres destinos distintos

- `/live/key`, `/live/type` y `/live/eval` operan sobre la pestaña `livePage`
  gestionada por la API. No prometen seguir la pestaña seleccionada manualmente
  en el escritorio. `/live` navega esa pestaña y la trae al frente.
- Un cliente CDP puede enumerar y elegir sus propias páginas dentro del contexto
  compartido. Debe identificar el destino por URL/ID y confirmar el resultado.
- X11 (`xdotool`) controla la ventana y el campo que tienen el foco real, incluida
  la barra de direcciones. Otro usuario o el visor pueden cambiar ese foco.

No se deben equiparar estos destinos. Antes y después de una secuencia verifica
la ventana, la URL y el resultado. No enumeres pestañas cerrándolas o navegando
sobre ellas. Un título repetido no identifica una pestaña de forma única.

## Vimium 2.4.2

Se instala por separado en `extensions/vimium/manifest.json`; Lupa descubre los
manifiestos al abrir el contexto del navegador. Esta release no empaqueta la
extensión ni reinicia perfiles existentes para instalarla.

El código de Vimium 2.4.2 instalado durante la revisión define:

| Teclas | Acción |
|---|---|
| `j`, `k` | Bajar/subir |
| `gg`, `G` | Inicio/final de página |
| `J`, `K` | Pestaña anterior/siguiente |
| `g0`, `g$` | Primera/última pestaña |
| `yy`, `yf` | Copiar URL actual/enlace elegido |
| `i`, `Escape` | Entrar/salir del modo inserción |

La sesión de pruebas aportada por el usuario reporta funcionamiento intermitente
para `p`, `P`, `t` y `x`. La causa MV3/service worker es una hipótesis, no un
diagnóstico confirmado. Los atajos nativos de Chromium (`Control+t`, `Control+w`,
`Alt+d`) enviados por X11 son una alternativa que también debe verificarse.

Las páginas internas de Chromium y la tienda de extensiones restringen los
content scripts. Para probar Vimium usa una página HTTP local sin otros atajos.
La ausencia de un `keydown` en un listener de la página no demuestra por sí sola
que CDP no envió la tecla: una extensión puede interceptarla. Las pruebas deben
medir además el foco, `isTrusted`, cambios de input y el efecto del atajo.

## X11 sin abrir otro visor

Ejecutar `xdotool` dentro del contenedor elegido evita enlazar sockets globales
de `/tmp/.X11-unix` que podrían pertenecer a otra instancia. Ejemplo para una
instancia de pruebas:

```sh
docker exec --user abc -e DISPLAY=:1 lupa-test xdotool getactivewindow
# Sustituye WINDOW_ID por una ventana previamente inspeccionada.
docker exec --user abc -e DISPLAY=:1 lupa-test xdotool windowactivate --sync WINDOW_ID
docker exec --user abc -e DISPLAY=:1 lupa-test xdotool key --clearmodifiers j
```

`xdotool` usa nombres como `Return`, `grave` y `ctrl+t`; Playwright usa `Enter`,
`Backquote` y `Control+t`. No intercambies ambos vocabularios sin traducirlos.
El helper externo `lupa-x` es una herramienta local revisada, no una dependencia
incluida en la imagen. Su selección por tamaño de ventana y su recorrido por
títulos no garantizan elegir el destino correcto con varias ventanas o títulos
repetidos. No se ejecutó sobre las pestañas del usuario durante esta revisión.

Abrir un segundo visor Selkies puede interferir con la sesión que el usuario
está mirando. Para automatización textual usa API/CDP o X11 en el contenedor;
para las pruebas del visor utiliza otra instancia y otro perfil.

## Comprobación de la candidata 0.0.3

En la imagen `0.0.3-rc.1`, commit `b11531a`, se ejecutó una página HTTP local
con Vimium 2.4.2 y un perfil aislado:

- `/live/key` con `a` y `/live/type` con `bc` produjeron `abc` y eventos
  `keydown` con `isTrusted: true`.
- `j` por API y por X11 desplazó la página 60 píxeles en ambos casos. El
  listener de la página no registró esos eventos, aunque el atajo funcionó.
- Con una segunda pestaña seleccionada, `/live/key` escribió en la pestaña
  gestionada por la API y dejó vacío el campo de la segunda pestaña.

Esto contradice la generalización de que CDP nunca genera `keydown`; no invalida
las observaciones de otras builds o páginas. Los informes y el script de esta
comprobación se adjuntan a la release. No se validó aquí la fiabilidad de todos
los atajos de Vimium ni se confirmó la causa de las intermitencias anteriores.
