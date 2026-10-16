# syntax=docker/dockerfile:1
# Reuse the verified AMD64 desktop/runtime; update application code from this release.
# The complete runtime recipe remains in deploy/slim/Dockerfiles/lupa/Dockerfile.
FROM bunxdev/lupa:slim-20260915@sha256:d7c94e9360e2b9d258b4cf659e586517a7b635a132e0e7b4694fb85d138cf6f6
ARG LUPA_VERSION=0.0.3
ARG LUPA_REVISION=unknown
LABEL org.opencontainers.image.title="Lupa" \
      org.opencontainers.image.description="Chromium HTTP/CDP automation with a persistent Selkies desktop" \
      org.opencontainers.image.source="https://github.com/bunxdev/lupa" \
      org.opencontainers.image.version="${LUPA_VERSION}" \
      org.opencontainers.image.revision="${LUPA_REVISION}" \
      io.lupa.upstream.revision="${LUPA_REVISION}"
COPY app/package.json app/bun.lock /app/
RUN bun install --production --frozen-lockfile
COPY app/src /app/src
COPY VERSION /app/VERSION
COPY --chmod=755 deploy/slim/scripts/lupa/entrypoint.sh deploy/slim/scripts/lupa/session.sh deploy/slim/scripts/lupa/healthcheck.sh deploy/slim/scripts/lupa/lupa /usr/local/bin/
