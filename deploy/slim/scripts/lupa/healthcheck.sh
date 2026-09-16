#!/usr/bin/env bash
set -euo pipefail
curl -fsS --max-time 3 "http://127.0.0.1:${PORT:-3036}/health" >/dev/null
xset q >/dev/null 2>&1
pactl info >/dev/null 2>&1
# Selkies listener and Nginx, including configurations with HTTP Basic auth.
(timeout 2 bash -c 'exec 3<>/dev/tcp/127.0.0.1/8082') >/dev/null 2>&1
(timeout 2 bash -c 'exec 3<>/dev/tcp/127.0.0.1/3000') >/dev/null 2>&1
