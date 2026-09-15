#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
if ! command -v chromium >/dev/null; then
  apt-get update -qq
  apt-get install -y --no-install-recommends chromium ca-certificates fonts-liberation curl
fi
export PATH="/data/npm/bin:$PATH"
if [ ! -x /data/npm/bin/agent-browser ] || ! agent-browser --version | grep -Fq "${AGENT_BROWSER_VERSION:?}"; then
  npm install --prefix /data/npm --global "agent-browser@$AGENT_BROWSER_VERSION"
fi
ln -sf /data/npm/bin/agent-browser /usr/local/bin/agent-browser
agent-browser open about:blank
agent-browser dashboard start --port "${AGENT_BROWSER_DASHBOARD_PORT:-4848}"
cleanup() {
  agent-browser close || true
  agent-browser dashboard stop || true
  exit 0
}
trap cleanup TERM INT
while true; do
  sleep 20 & wait $!
  agent-browser get url >/dev/null
  curl -fsS "http://127.0.0.1:${AGENT_BROWSER_DASHBOARD_PORT:-4848}/" >/dev/null
done
