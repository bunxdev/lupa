#!/bin/bash
# Instala bun + deps de chromium para playwright. Idempotente — los binarios
# viven en /config (volumen) así que sólo el primer arranque hace trabajo real.
set -e

export DEBIAN_FRONTEND=noninteractive

if ! command -v curl >/dev/null 2>&1 || ! command -v unzip >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y --no-install-recommends curl ca-certificates unzip
fi

# Deps que playwright/chromium necesita más allá de las que ya trae la base de selkies.
# Idempotente — apt salta lo ya instalado.
apt-get update -qq
apt-get install -y --no-install-recommends \
  libnss3 libnspr4 libasound2t64 libatk-bridge2.0-0t64 libatk1.0-0t64 \
  libcups2t64 libdrm2 libxcomposite1 libxdamage1 libxfixes3 libxkbcommon0 \
  libxrandr2 libgbm1 libpango-1.0-0 libcairo2 fonts-liberation \
  libavif16 libwoff1 >/dev/null 2>&1 || true

# Bun para el usuario abc (uid 911). HOME=/config para que persista.
if [ ! -x /config/.bun/bin/bun ]; then
  echo "[lupa-init] instalando bun en /config/.bun"
  s6-setuidgid abc bash -lc '
    export HOME=/config
    curl -fsSL https://bun.sh/install | bash >/dev/null
  '
fi

# Dependencias de la app (bun install) e instalar chromium-headless-shell + chromium.
if [ ! -d /app/node_modules ]; then
  echo "[lupa-init] bun install"
  cd /app && s6-setuidgid abc bash -lc '
    export HOME=/config
    export PATH=/config/.bun/bin:$PATH
    bun install
  '
fi

# Cache de playwright en /config para persistencia.
if [ ! -d /config/.cache/ms-playwright ]; then
  echo "[lupa-init] descargando chromium para playwright"
  cd /app && s6-setuidgid abc bash -lc '
    export HOME=/config
    export PATH=/config/.bun/bin:$PATH
    export PLAYWRIGHT_BROWSERS_PATH=/config/.cache/ms-playwright
    bunx playwright install chromium
  '
fi

echo "[lupa-init] OK"
