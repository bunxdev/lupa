# Comparación local de Lupa

Fecha: 2026-09-07. El informe con resultados está en `REPORT.md`.

La [prueba posterior de uno en uno](ISOLATED.md) se repite con `python3 comparison/run-isolated.py`. Durante ella sólo se ejecuta el proyecto que toca y el servidor auxiliar; Lupa se pausa conservando su sesión y se reanuda al finalizar. Los cuatro contenedores del laboratorio quedan detenidos.

## Repetir las pruebas

Con Lupa ya iniciado desde el directorio raíz:

```sh
bash comparison/setup.sh
python3 comparison/run.py
```

`setup.sh` crea cuatro contenedores de los proyectos y un quinto contenedor auxiliar que sirve la página local y ejecuta el cliente CDP. Browser Use y Scrapling son bibliotecas: sus contenedores permanecen disponibles para `docker exec`, no exponen una API HTTP propia en esta instalación.

| Contenedor | Uso | Puerto del host |
|---|---|---|
| lupa-compare-browser-use | BrowserSession + Chromium | ninguno |
| lupa-compare-scrapling | DynamicSession + Chromium | ninguno |
| lupa-compare-obscura | servidor CDP | 127.0.0.1:9231 |
| lupa-compare-lightpanda | servidor CDP | 127.0.0.1:9232 |
| lupa-compare-base | fixture HTTP y cliente Puppeteer | ninguno |

Se emplea el bridge predeterminado y DNS explícito porque la red de Compose no tenía salida en este entorno. La excepción `--allow-private-network` de Obscura permite acceder a la fixture local. No se monta el socket de Docker en ningún contenedor.

## Qué mide

La página `fixture.html` contiene DOM estático, JavaScript inline, fetch de JSON, cookies, formulario, CSS grid y canvas. Se ejecutan tres navegaciones por proyecto. La primera también genera PNG y PDF e intenta rellenar el campo y pulsar el botón. Scrapling añade extracción CSS y una petición HTTP sin navegador.

Los resultados JSON conservan errores, comprobaciones y tiempos de cada muestra. El cliente usa Puppeteer para Obscura/Lightpanda, Actor API para Browser Use, `DynamicSession` para Scrapling y HTTP para Lupa. La interacción de Lupa se realiza con JavaScript en `/eval`; no es una prueba de sus endpoints de teclado y ratón.

No son tiempos equivalentes de motor: Lupa abre un contexto por petición y espera `networkidle`; Browser Use y los motores CDP reutilizan el proceso; Scrapling usa una sesión. La primera llamada puede incluir calentamiento. En Scrapling `total_ms` de la primera muestra incluye interacción y exportaciones; usar `navigation_to_ready_ms` para observar navegación.

El equipo es compartido, sin CPU dedicada, y el servicio Lupa conserva su escritorio. Los cuatro contenedores nuevos tienen un límite de 1 CPU y 1 GiB; Lupa conserva su configuración original. Tres muestras de una página pequeña no sirven para afirmar multiplicadores generales ni comparar concurrencia. `idle-stats.jsonl` es una instantánea posterior, no memoria máxima ni consumo del navegador bajo carga.

No se evalúan agentes con LLM, costes por tarea, CAPTCHAs, evasión antibot, sitios externos complejos, extensiones, persistencia después de reiniciar ni transmisión real de audio/vídeo. Detectar `AudioContext` o `canPlayType` no demuestra reproducción.

## Versiones y artefactos

`results/inventory.json` registra IDs/digests de imágenes y límites sin exportar variables de entorno. Las versiones Python principales están fijadas en `setup.sh`; las dependencias transitivas y paquetes Debian pueden cambiar al reconstruir. Se conservan los inventarios de paquetes de la ejecución. Las imágenes de Obscura, Lightpanda y Python están fijadas por digest. La base utilizada aquí se creó instalando `provision-base.sh` en un contenedor Python y guardándolo con `docker commit`; `Dockerfile.base` permite reconstruir la misma receta, pero no garantiza bytes idénticos.

Para detener únicamente el laboratorio y conservarlo:

```sh
docker stop lupa-compare-browser-use lupa-compare-scrapling lupa-compare-obscura lupa-compare-lightpanda lupa-compare-base
```

`setup.sh` vuelve a iniciarlos y restablece el servidor de fixture. El script de repetición presupone los nombres actuales, incluido `lupa-lupa-1` para el servicio original.
