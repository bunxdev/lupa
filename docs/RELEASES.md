# Releases de Lupa

## Versiones

| Versión | Funciones | Distribución |
|---|---|---|
| 0.0.1 | HTTP autenticado y sesión visual | Código y Compose original |
| 0.0.2 | CDP compartido, Browser Use y laboratorio | Código y Compose original |
| 0.0.3 | MCP de 21 herramientas y runtime slim | Código y `bunxdev/lupa:0.0.3` (linux/amd64) |

La rama `qwen` agrega recolectores y resultados de Maps. No forma parte de estas
releases; su integración requiere una revisión independiente de sus scripts y datos.

## Imagen 0.0.3

```sh
git clone --branch v0.0.3 https://github.com/bunxdev/lupa.git
cd lupa/deploy/slim
cp .env.example .env
openssl rand -hex 32
# Configura LUPA_API_TOKEN en .env con el valor generado.
mkdir -p .runtime/extensions .runtime/downloads
docker compose -p lupa -f lupa.yml pull
docker compose -p lupa -f lupa.yml up -d --no-build --wait
```

API: `http://127.0.0.1:3136`. Escritorio: `http://127.0.0.1:6180`.
La API y CDP requieren Bearer. El escritorio admite usuario y contraseña.
Los puertos se publican en loopback. Para acceso remoto usa un túnel SSH o un
proxy autenticado. El MCP se ejecuta en el cliente siguiendo
[integrations/mcp](../integrations/mcp/README.md); no requiere un puerto adicional.

`0.0.3` usa el runtime AMD64 de `slim-20260915`, fijado por digest
`sha256:d7c94e9360e2b9d258b4cf659e586517a7b635a132e0e7b4694fb85d138cf6f6`,
y copia el código canónico `app/` de esta release. Las etiquetas OCI identifican
la versión y el commit exactos. La receta completa está en
`deploy/slim/Dockerfiles/lupa/Dockerfile` y usa el mismo código de aplicación.
No se afirma compatibilidad ARM64. No se reemplaza la etiqueta histórica.

## Actualizar una instalación

Conserva la instancia y volumen originales. Detén la instancia propietaria antes
de copiar su perfil a un volumen nuevo; no compartas un perfil activo entre dos
Chromium. Mantén las extensiones y descargas en sus mounts. El rollback consiste
en volver a la versión anterior con su volumen original.

La imagen slim incluye Bun, Playwright y Chromium y arranca sin descargar
paquetes. `docker-compose.yml` en la raíz conserva la instalación tradicional,
que descarga dependencias durante el primer arranque.

Consulta también [teclado, pestañas y Vimium](INPUT.md) para distinguir el
destino de API/CDP del foco del escritorio.

## Validación

Las notas de cada release registran las pruebas ejecutadas en Linux AMD64.
Los informes antiguos de `comparison/` y `deploy/slim/reports/` son evidencia
histórica, no mediciones nuevas. Las comprobaciones actuales cubren API y CDP,
PNG/JPEG/PDF, aislamiento, perfil/cookies, teclado/ratón, extensiones, descargas,
audio/vídeo y el protocolo MCP. Los resultados de esta publicación se adjuntan
a la release correspondiente.

Para ejecutar las pruebas que controlan el navegador, usa una instancia dedicada:

```sh
cd deploy/slim
set -a; . ./.env; set +a
export LUPA_COMPOSE_PROJECT=lupa-validation
./scripts/lupa/test.sh
bun run scripts/lupa/lifecycle.ts
```

Estas pruebas navegan y cierran la sesión, recrean el contenedor de pruebas y
escriben informes en `reports/`. No deben apuntar a un perfil de trabajo activo.
