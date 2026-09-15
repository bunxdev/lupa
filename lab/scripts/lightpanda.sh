#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
if ! command -v curl >/dev/null; then
  apt-get update -qq
  apt-get install -y --no-install-recommends ca-certificates curl
fi
expected="${LIGHTPANDA_SHA256:?}"
binary="/data/lightpanda-$expected"
if [ ! -x "$binary" ]; then
  curl -fL --retry 3 https://github.com/lightpanda-io/browser/releases/download/nightly/lightpanda-x86_64-linux -o "$binary.tmp"
  printf '%s  %s\n' "$expected" "$binary.tmp" | sha256sum -c -
  chmod +x "$binary.tmp"
  mv "$binary.tmp" "$binary"
fi
exec "$binary" serve --host 127.0.0.1 --port "${LIGHTPANDA_PORT:-9232}"
