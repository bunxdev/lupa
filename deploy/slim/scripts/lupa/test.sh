#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")/../.."
compose=(docker compose -p "${LUPA_COMPOSE_PROJECT:-lupa-validation}" -f lupa.yml)
mkdir -p .runtime/extensions/lupa-test .runtime/downloads reports
cp tests/lupa/extension/* .runtime/extensions/lupa-test/
# Fixtures must be readable by abc even when the checkout uses umask 077.
chmod 755 .runtime/extensions .runtime/extensions/lupa-test
chmod 644 .runtime/extensions/lupa-test/*
"${compose[@]}" up -d --no-build --wait --wait-timeout 120
container="$("${compose[@]}" ps -q lupa)"
docker exec "$container" mkdir -p /tmp/lupa-tests
docker cp tests/lupa/. "$container:/tmp/lupa-tests/"
docker exec "$container" chmod -R a+rX /tmp/lupa-tests
# Clear only generated test artifacts so a failed run cannot reuse old reports.
docker exec "$container" rm -rf /tmp/lupa-verify
rm -f reports/functions.json reports/desktop.json reports/desktop.png reports/page.pdf
# Reopen after loading the test extension; this affects only this test instance.
docker exec --user abc "$container" lupa close >/dev/null
failed=0
printf 'stage\texit_code\n' > reports/checks.tsv
run_check() {
  local name="$1" code=0
  shift
  "$@" > "reports/$name.log" 2>&1 || code=$?
  printf '%s\t%s\n' "$name" "$code" >> reports/checks.tsv
  printf '%s: exit %s (reports/%s.log)\n' "$name" "$code" "$name"
  if [ "$code" -ne 0 ]; then failed=1; fi
}
# A failed stage remains a failure, but does not hide the other diagnostics.
run_check app docker exec --user abc -e LUPA_TEST_TIMEOUT_MS -e RUN_BROWSER_TESTS=1 "$container" bun test /app/src
run_check functions docker exec --user abc -e LUPA_TEST_TIMEOUT_MS "$container" bun run /tmp/lupa-tests/verify.ts
run_check desktop docker exec --user abc -e LUPA_TEST_TIMEOUT_MS "$container" bun run /tmp/lupa-tests/desktop.ts
for pair in results.json:functions.json desktop.json:desktop.json desktop.png:desktop.png page.pdf:page.pdf; do
  if ! docker cp "$container:/tmp/lupa-verify/${pair%%:*}" "reports/${pair#*:}"; then failed=1; fi
done
docker inspect "$container" --format '{{.Image}}' > reports/tested-image.txt
printf 'Functional and desktop reports saved under reports/. Overall exit: %s\n' "$failed"
exit "$failed"
