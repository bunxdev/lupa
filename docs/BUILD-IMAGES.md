# Construcción de imágenes Lupa

Desde 0.0.5 se distinguen dos recetas para Linux AMD64:

| Etiqueta | Receta | Base del runtime |
|---|---|---|
| `bunxdev/lupa:0.0.5` | `Dockerfile` | Runtime slim histórico fijado por digest; actualiza aplicación y colectores |
| `bunxdev/lupa:0.0.5-multistage` | `deploy/slim/Dockerfiles/lupa/Dockerfile` | Debian slim con artefactos copiados desde etapas independientes |

La organización sigue el uso de Debian slim y `Dockerfiles/` de
[debina](https://github.com/bunxdev/debina). La receta de Lupa tiene tres etapas:

1. `selkies`: extrae el entorno Python, Xvfb y los componentes de escritorio.
2. `browser-build`: instala dependencias de producción con el lockfile de Bun y descarga Chromium.
3. `runtime`: instala las bibliotecas de Debian necesarias y copia únicamente los artefactos de ejecución de las otras etapas.

El runtime final no hereda las capas de la imagen Selkies ni la etapa de
construcción. Incluye Bun porque ejecuta la API; Python ejecuta los colectores.
Las bases Debian, Selkies y Bun están fijadas por digest. Los repositorios APT y las
URLs de descargas siguen siendo externos: no se promete reconstrucción idéntica
bit por bit. Las pruebas y los datasets de Maps no se copian desde `qwen/` a la
imagen.

## Construir y publicar

Desde un checkout limpio de la versión deseada:

```sh
version="$(cat VERSION)"
revision="$(git rev-parse HEAD)"
docker build --platform linux/amd64 \
  --build-arg LUPA_VERSION="$version" --build-arg LUPA_REVISION="$revision" \
  -t "bunxdev/lupa:$version" .
docker build --platform linux/amd64 \
  -f deploy/slim/Dockerfiles/lupa/Dockerfile \
  --build-arg LUPA_VERSION="$version" --build-arg LUPA_REVISION="$revision" \
  -t "bunxdev/lupa:$version-multistage" .
# Ejecutar las pruebas con cada imagen antes de publicar.
docker push "bunxdev/lupa:$version"
docker push "bunxdev/lupa:$version-multistage"
```

`org.opencontainers.image.version`, `org.opencontainers.image.revision` e
`io.lupa.build.variant` permiten identificar la versión, el commit y la receta.
Los `COPY` del contexto normalizan los permisos con `u=rwX,go=rX`, para que
`abc` pueda leer la aplicación aunque el checkout se haya creado con `umask 077`.
Esto usa la sintaxis de Dockerfile 1.14 o posterior, resuelta por el frontend
`docker/dockerfile:1` ([referencia oficial](https://docs.docker.com/reference/dockerfile/#copy---chmod)).
Los digests publicados y el alcance de las comprobaciones van en los adjuntos de
cada release. Multistage describe la construcción; no implica soporte multiarch.

## Validar en una instancia dedicada

Configura `.env` siguiendo `docs/RELEASES.md`, con puertos, token y perfil propios.
Para seleccionar la variante multistage, establece
`LUPA_IMAGE=bunxdev/lupa:0.0.5-multistage`. Los siguientes comandos navegan el
perfil de pruebas y recrean su contenedor:

```sh
cd deploy/slim
set -a; . ./.env; set +a
export LUPA_COMPOSE_PROJECT=lupa-validation
./scripts/lupa/test.sh
bun run scripts/lupa/lifecycle.ts
```

El laboratorio guarda `checks.tsv` y un log por etapa (`app`, `functions`,
`desktop`). Un fallo no oculta las demás comprobaciones, y la salida global
sigue siendo distinta de cero si alguna etapa o informe falla.

El margen habitual de las solicitudes de pruebas es de 20–30 segundos. En un
host lento se puede usar `LUPA_TEST_TIMEOUT_MS=90000` (rango 1000–120000). Esa
opción solo cambia el cliente de pruebas y sus esperas CDP; no aumenta los
límites del servicio. El informe registra el margen empleado. Conserva también
los fallos de la ejecución original para no presentar como rendimiento normal
lo que necesitó un margen mayor.
