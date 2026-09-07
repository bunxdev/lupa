#!/bin/sh
set -eu
apt-get update -qq
apt-get install -y --no-install-recommends chromium ca-certificates fonts-liberation nodejs npm
pip install --no-cache-dir playwright
npm install --prefix /opt/client puppeteer-core
