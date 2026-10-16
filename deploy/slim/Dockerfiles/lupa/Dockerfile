# syntax=docker/dockerfile:1
# Debian slim layout from debina; Debian 13 matches the pinned Selkies ABI.
ARG DEBIAN_IMAGE=debian:trixie-slim@sha256:d7e12182ce18b85b93007c1dedf31f2d29e01ccf3182cc4017c709b6259bc132
ARG SELKIES_IMAGE=ghcr.io/linuxserver/baseimage-selkies@sha256:a0b70771408d216d3f80f8cf06bc0380afb717a5c8fc68871792b8d49ffa4995
FROM ${SELKIES_IMAGE} AS selkies
# Export runtime artifacts only. This stage is not an ancestor of the final image.
RUN mkdir -p /export && cp -a /lsiopy /export/lsiopy && \
    find /export/lsiopy -type d -name __pycache__ -prune -exec rm -rf '{}' + && \
    rm -rf /export/lsiopy/lib/python3.13/site-packages/pip* && \
    rm -f /export/lsiopy/bin/pip*

FROM oven/bun:1.4.2-slim AS browser-build
WORKDIR /app
COPY app/package.json app/bun.lock ./
RUN bun install --production --frozen-lockfile
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/browsers
# Use one full Chromium for both headed and new-headless operation.
RUN bunx playwright install chromium --no-shell && rm -rf /opt/browsers/.links

FROM ${DEBIAN_IMAGE} AS runtime
ARG LUPA_REVISION=unknown
ARG LUPA_VERSION=0.0.3
LABEL org.opencontainers.image.title="Lupa slim" \
      org.opencontainers.image.description="Lupa API, authenticated CDP, persistent Chromium and Selkies desktop on Debian slim" \
      org.opencontainers.image.source="https://github.com/bunxdev/lupa" \
      org.opencontainers.image.version="${LUPA_VERSION}" \
      org.opencontainers.image.revision="${LUPA_REVISION}" \
      io.lupa.upstream.revision="${LUPA_REVISION}"
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl tini gosu python3 \
      nginx-light libnginx-mod-http-fancyindex apache2-utils openssl \
      dbus dbus-x11 openbox xterm x11-xserver-utils x11-xkb-utils x11-utils \
      xauth xclip xdotool xcvt xkb-data xfonts-base xdg-utils \
      pulseaudio pulseaudio-utils \
      fonts-liberation fonts-noto-core fonts-noto-cjk fonts-noto-color-emoji \
      libnss3 libnspr4 libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 \
      libdrm2 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
      libxkbcommon0 libxkbcommon-x11-0 libpango-1.0-0 libcairo2 libasound2t64 \
      libavif16 libwoff1 libgtk-3-0t64 libxfont2 libunwind8 libepoxy0 \
      libgl1 libglx0 libxtst6 libev4 libopus0 libwayland-client0 libwayland-server0 \
      procps && \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/* && \
    groupadd -g 911 abc && useradd -u 911 -g abc -d /config -s /bin/bash abc && \
    mkdir -p /config /extensions /run/lupa && chown abc:abc /config
COPY --from=selkies /export/lsiopy /lsiopy
COPY --from=selkies /usr/bin/Xvfb /usr/bin/Xvfb
COPY --from=selkies /usr/lib/selkies_joystick_interposer.so /usr/lib/selkies_joystick_interposer.so
COPY --from=selkies /opt/lib /opt/lib
COPY --from=selkies /usr/share/selkies/selkies-dashboard-wish /usr/share/selkies/web
COPY --from=selkies /usr/share/selkies/www /usr/share/selkies/www
COPY --from=selkies /usr/share/selkies/www/icon.png /usr/share/selkies/web/icon.png
COPY --from=selkies /proot-apps /proot-apps
COPY --from=browser-build /usr/local/bin/bun /usr/local/bin/bun
COPY --from=browser-build /opt/browsers /opt/browsers
COPY --from=browser-build /app/node_modules /app/node_modules
COPY app/src /app/src
COPY app/package.json VERSION /app/
COPY deploy/slim/Dockerfiles/lupa/rootfs/ /
COPY --chmod=755 deploy/slim/scripts/lupa/entrypoint.sh deploy/slim/scripts/lupa/session.sh deploy/slim/scripts/lupa/healthcheck.sh deploy/slim/scripts/lupa/lupa /usr/local/bin/
ENV HOME=/config DISPLAY=:1 XDG_RUNTIME_DIR=/run/lupa \
    PATH=/lsiopy/bin:/proot-apps:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    PLAYWRIGHT_BROWSERS_PATH=/opt/browsers LUPA_HEADLESS_CHANNEL=chromium LUPA_MANAGED_SHUTDOWN=1 \
    API_HOST=0.0.0.0 PORT=3036 PUID=911 PGID=911 \
    PULSE_SERVER=unix:/run/lupa/pulse/native \
    PULSE_RUNTIME_PATH=/run/lupa/pulse \
    SELKIES_INTERPOSER=/usr/lib/selkies_joystick_interposer.so \
    CUSTOM_WS_PORT=8082 SELKIES_UI_TITLE=lupa \
    SELKIES_AUDIO_ENABLED=true SELKIES_FRAMERATE=60 \
    SELKIES_ENCODER=x264enc PYTHONDONTWRITEBYTECODE=1 \
    TITLE=lupa FILE_MANAGER_PATH=/config/Downloads LC_ALL=C.UTF-8
WORKDIR /app
EXPOSE 3036 3000 3001
VOLUME ["/config"]
HEALTHCHECK --interval=20s --timeout=5s --start-period=40s --retries=3 CMD ["/usr/local/bin/healthcheck.sh"]
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
