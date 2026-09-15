#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
version="${BROWSEROS_VERSION:?}"
if [ ! -x /usr/bin/browseros ]; then
  apt-get update -qq
  apt-get install -y --no-install-recommends curl ca-certificates socat
  deb="/config/BrowserOS-$version.deb"
  if [ ! -f "$deb" ]; then
    curl -fL --retry 3 "https://github.com/browseros-ai/BrowserOS/releases/download/v$version/BrowserOS_v${version}_amd64.deb" -o "$deb.tmp"
    mv "$deb.tmp" "$deb"
  fi
  apt-get install -y --no-install-recommends "$deb"
fi
mkdir -p /config/browseros-profile
chown abc:abc /config/browseros-profile
