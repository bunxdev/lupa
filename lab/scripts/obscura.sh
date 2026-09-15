#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
if ! command -v curl >/dev/null; then
  apt-get update -qq
  apt-get install -y --no-install-recommends ca-certificates curl libfontconfig1 libfreetype6
fi
version="${OBSCURA_VERSION:?}"
if [ ! -x "/data/$version/obscura" ]; then
  mkdir -p "/data/$version"
  curl -fL --retry 3 "https://github.com/h4ckf0r0day/obscura/releases/download/$version/obscura-x86_64-linux.tar.gz" -o /data/obscura.tar.gz
  tar -xzf /data/obscura.tar.gz -C "/data/$version"
  rm /data/obscura.tar.gz
fi
exec "/data/$version/obscura" serve --host 127.0.0.1 --port "${OBSCURA_PORT:-9231}" --allow-private-network
