#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")/../.."
compose=(docker compose -p debina-lupa -f lupa.yml)
mkdir -p .runtime/extensions/lupa-test .runtime/downloads reports
cp tests/lupa/extension/* .runtime/extensions/lupa-test/
"${compose[@]}" up -d --no-build --wait --wait-timeout 120
container="$("${compose[@]}" ps -q lupa)"
docker cp tests/lupa "$container:/tmp/lupa-tests"
# Reopen after loading the test extension; this affects only this test instance.
docker exec --user abc "$container" lupa close >/dev/null
docker exec --user abc -e RUN_BROWSER_TESTS=1 "$container" bun test /app/src
docker exec --user abc "$container" bun run /tmp/lupa-tests/verify.ts
docker exec --user abc "$container" bun run /tmp/lupa-tests/desktop.ts
docker cp "$container:/tmp/lupa-verify/results.json" reports/functions.json
docker cp "$container:/tmp/lupa-verify/desktop.json" reports/desktop.json
docker cp "$container:/tmp/lupa-verify/desktop.png" reports/desktop.png
docker cp "$container:/tmp/lupa-verify/page.pdf" reports/page.pdf
docker inspect "$container" --format '{{.Image}}' > reports/tested-image.txt
printf 'Functional and desktop reports saved under reports/.\n'
