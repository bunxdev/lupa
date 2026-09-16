#!/usr/bin/env bash
set -euo pipefail
children=()
app_pid=""
cleanup() {
  trap - TERM INT EXIT
  # Let Chromium flush cookies/downloads before stopping X and PulseAudio.
  if [ -n "$app_pid" ]; then
    kill -TERM "$app_pid" 2>/dev/null || true
    for attempt in {1..100}; do
      kill -0 "$app_pid" 2>/dev/null || break
      sleep .1
    done
  fi
  for pid in "${children[@]}"; do kill -TERM "$pid" 2>/dev/null || true; done
  wait || true
}
trap cleanup EXIT
trap 'exit 0' TERM INT
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/lupa/session-bus
rm -f /run/lupa/session-bus
dbus-daemon --session --nofork --address="$DBUS_SESSION_BUS_ADDRESS" &
children+=("$!")
Xvfb "$DISPLAY" -screen 0 "${MAX_RES:-15360x8640}x24" -dpi 96 \
  +extension COMPOSITE +extension DAMAGE +extension GLX +extension RANDR \
  +extension RENDER +extension MIT-SHM +extension XFIXES +extension XTEST \
  +iglx +render -nolisten tcp -ac -noreset -shmem &
children+=("$!")
for attempt in {1..100}; do
  xset q >/dev/null 2>&1 && break
  kill -0 "${children[1]}" 2>/dev/null || exit 1
  sleep .1
done
xset q >/dev/null
# Start at a usable size, while retaining the large virtual screen for live resize.
selkies-resize 1280x720
pulseaudio --daemonize=no --exit-idle-time=-1 --log-target=stderr --log-level=error \
  --use-pid-file=no -nF /etc/lupa/pulse.pa &
children+=("$!")
for attempt in {1..100}; do pactl info >/dev/null 2>&1 && break; sleep .1; done
pactl info >/dev/null
openbox --config-file /config/.config/openbox/rc.xml & children+=("$!")
selkies --addr=127.0.0.1 --mode=websockets & children+=("$!")
nginx -c /run/lupa/nginx.conf -g 'daemon off;' & children+=("$!")
bun run /app/src/server.ts & app_pid=$!; children+=("$app_pid")
# Exit on any supervised service failure so Docker restarts the complete session.
set +e
wait -n "${children[@]}"
status=$?
set -e
[ "$status" -ne 0 ] || status=1
exit "$status"
