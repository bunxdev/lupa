# Prueba de los navegadores uno por uno

Ejecución del 7 de septiembre de 2026, iniciada a las 23:31 UTC. **Los cinco proyectos completaron las tres navegaciones y las pruebas funcionales. Browser Use no presentó el timeout de la comparación anterior.**

## Aislamiento aplicado

1. Se detuvieron los cuatro contenedores de comparación y se probó Lupa.
2. Se pausó Lupa, conservando su sesión, y se inició únicamente Browser Use.
3. Se detuvo Browser Use antes de iniciar Scrapling; después se hizo lo mismo con Obscura y Lightpanda.
4. Al terminar se reanudó Lupa. Los otros cuatro contenedores quedaron detenidos.

El servidor de fixture y el cliente CDP permanecieron disponibles en el contenedor auxiliar. Los archivos `*-containers.txt` registran el estado de los contenedores antes de cada prueba. Pausar Lupa suspende su CPU, pero conserva su memoria: este aislamiento no equivale a un host dedicado ni libera toda la RAM.

## Resultados

| Proyecto | JS, fetch, cookies | Formulario | PNG / PDF | Navegaciones |
|---|---|---|---|---|
| Lupa | Correcto | Correcto, JS en `/eval` | Correcto | 3/3 |
| Browser Use | Correcto | Correcto, Actor API | Correcto, PDF por CDP | 3/3 |
| Scrapling | Correcto | Correcto, Playwright | Correcto | 3/3 |
| Obscura | Correcto | Correcto, Puppeteer | Correcto | 3/3 |
| Lightpanda | Correcto | Correcto, Puppeteer | Correcto | 3/3 |

Generar PNG/PDF no certifica fidelidad visual. Se mantienen los enfoques distintos de renderizado descritos en el [informe anterior](REPORT.md): Lightpanda ofrece una representación textual y Obscura presenta diferencias frente a Chromium. Browser Use sigue probado sin LLM, conectado a Chromium preiniciado; no se repitió su lanzamiento automático original.

## Tiempos de esta ejecución

Milisegundos. Se incluyen las tres muestras, sin descartar el calentamiento.

| Proyecto | Muestra 1 | Muestra 2 | Muestra 3 | Mediana |
|---|---:|---:|---:|---:|
| Lupa | 664 | 611 | 633 | 633 |
| Browser Use | 525 | 317 | 254 | 317 |
| Scrapling | 935 | 168 | 134 | 168 |
| Obscura | 83 | 37 | 35 | 37 |
| Lightpanda | 66 | 18 | 17 | 18 |

Las cifras siguen sin ser un ranking de motores: Lupa incluye su petición HTTP, creación de contexto y espera `networkidle`; los otros adaptadores tienen políticas diferentes. Los valores de Browser Use y los motores CDP excluyen creación de página y arranque del proceso. Los de Scrapling incluyen la creación de página dentro de `fetch`, pero no el arranque de la sesión. Todos esperan los datos de la fixture por sus respectivas rutas.

La desaparición del timeout de Browser Use al reducir actividad es **compatible con interferencias de carga en las pruebas previas**, pero una pasada no demuestra la causa ni garantiza estabilidad sostenida. No se modificaron los proyectos ni se ampliaron sus límites para esta ejecución; se reutilizaron los adaptadores de la última pasada y se añadió un directorio de salida independiente.

## Evidencias y repetición

- [Resumen JSON](isolated-results/20260907-233101/summary.json)
- [Directorio de capturas, PDFs, logs y resultados](isolated-results/20260907-233101/)
- [Comprobación de firmas de archivos y dimensiones PNG](isolated-results/20260907-233101/artifact-validation.json)
- [Estado final de contenedores](isolated-results/20260907-233101/final-containers.txt)

```sh
python3 comparison/run-isolated.py
```

El comando necesita el contenedor auxiliar con la fixture disponible y Lupa funcionando. Detiene los contenedores del laboratorio, pausa temporalmente Lupa durante las pruebas ajenas y lo reanuda mediante `finally`. Cada ejecución escribe en un subdirectorio nuevo de `comparison/isolated-results/`. Al terminar deja los cuatro proyectos de comparación detenidos.
