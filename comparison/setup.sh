#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
bench_dir="$PWD"
# In this workspace only the default bridge had working egress. DNS is
# explicit for that reason; port publications remain on host loopback.
if ! docker image inspect lupa-compare-python:20260907 >/dev/null 2>&1; then
  docker build --network host -f Dockerfile.base -t lupa-compare-python:20260907 .
fi
start_if_missing() {
  local name="$1"
  shift
  if docker container inspect "$name" >/dev/null 2>&1; then
    docker start "$name" >/dev/null
  else
    docker run -d --name "$name" --network bridge --dns 1.1.1.1 --memory 1g --cpus 1 "$@"
  fi
}
start_if_missing lupa-compare-base -v "$bench_dir:/bench" -w /bench lupa-compare-python:20260907 sleep infinity
if ! docker exec lupa-compare-base python -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8090/fixture.html",timeout=2)' >/dev/null 2>&1; then
  docker exec -d lupa-compare-base python -m http.server 8090 --bind 0.0.0.0 --directory /bench
fi
start_if_missing lupa-compare-obscura -p 127.0.0.1:9231:9222 h4ckf0r0day/obscura@sha256:4f915617741d2e7cd5fac6dd03592c10ca2653d37d9ac53c8224a621af874197 serve --host 0.0.0.0 --port 9222 --allow-private-network
start_if_missing lupa-compare-lightpanda -e LIGHTPANDA_DISABLE_TELEMETRY=true -p 127.0.0.1:9232:9222 lightpanda/browser@sha256:2621461f9e56208055c79f4e2aadb49a9c337ef385c7ee23216563b14a5f4b04
start_if_missing lupa-compare-browser-use --shm-size 256m -e ANONYMIZED_TELEMETRY=false -e BROWSER_USE_LOGGING_LEVEL=error -e BROWSER_USE_CLOUD_SYNC=false -v "$bench_dir:/bench" -w /bench lupa-compare-python:20260907 sleep infinity
docker exec lupa-compare-browser-use pip install --no-cache-dir browser-use==0.13.10
start_if_missing lupa-compare-scrapling --shm-size 256m -v "$bench_dir:/bench" -w /bench lupa-compare-python:20260907 sleep infinity
docker exec lupa-compare-scrapling pip install --no-cache-dir 'scrapling[fetchers]==0.4.15'
