#!/usr/bin/env bash
set -euo pipefail
# Validate before starting desktop services; never log the token.
bun -e '
const t = process.env.LUPA_API_TOKEN_FILE ? (await Bun.file(process.env.LUPA_API_TOKEN_FILE).text()).trim() : (process.env.LUPA_API_TOKEN || "");
if (t.length < 32 || t.length > 512 || new Set(t).size < 8 || /[\x00-\x1f\x7f]/.test(t)) throw new Error("Set a strong LUPA_API_TOKEN or LUPA_API_TOKEN_FILE");
'
if [ "$(id -u)" = 0 ]; then
  mkdir -p /config
  exec 9>/config/.lupa-runtime.lock
  flock -n 9 || { echo "This /config volume is already in use by another Lupa container." >&2; exit 73; }
  [[ "${PUID}" =~ ^[0-9]+$ && "${PGID}" =~ ^[0-9]+$ ]] || { echo 'PUID/PGID must be numeric' >&2; exit 1; }
  if [ "$(id -g abc)" != "$PGID" ]; then groupmod -o -g "$PGID" abc; fi
  if [ "$(id -u abc)" != "$PUID" ]; then usermod -o -u "$PUID" abc; fi
  mkdir -p /config/Downloads /config/Desktop /config/live-profile /config/ext-profiles /config/ssl \
    /config/.config/openbox /config/.local/share/applications /run/lupa/pulse /run/dbus
  # Only these managed directories, not an entire existing profile on every boot.
  chown abc:abc /config /config/Downloads /config/Desktop /config/live-profile /config/ext-profiles \
    /config/ssl /config/.config /config/.config/openbox /config/.local /config/.local/share \
    /config/.local/share/applications
  chown -R abc:abc /run/lupa
  chmod 700 /run/lupa /run/lupa/pulse
  mkdir -p /tmp/.X11-unix
  chown root:root /tmp/.X11-unix
  chmod 1777 /tmp/.X11-unix
  # The exclusive volume lock makes clearing previous-container Chromium locks safe.
  find /config/live-profile /config/ext-profiles -maxdepth 2 -type l \( -name SingletonLock -o -name SingletonCookie -o -name SingletonSocket \) -delete
  rm -f /tmp/.X1-lock /tmp/.X11-unix/X1 /run/lupa/nginx.pid /run/lupa/pulse/pid
  dbus-uuidgen --ensure
  dbus-daemon --system --fork --nopidfile
else
  echo 'Entrypoint needs root to initialize PUID/PGID; all application services run as abc.' >&2
  exit 1
fi
# Nginx config and auth stay in ephemeral runtime storage.
cp /etc/lupa/nginx.conf /run/lupa/nginx.conf
if [ -n "${SELKIES_PASSWORD:-${PASSWORD:-}}" ]; then
  printf '%s\n' "${SELKIES_PASSWORD:-${PASSWORD:-}}" | htpasswd -ci /run/lupa/htpasswd "${SELKIES_USER:-${CUSTOM_USER:-lupa}}" >/dev/null 2>&1
  sed -i 's/#AUTH#/auth_basic "Lupa"; auth_basic_user_file \/run\/lupa\/htpasswd;/' /run/lupa/nginx.conf
fi
if [ ! -s /config/ssl/cert.pem ] || [ ! -s /config/ssl/cert.key ]; then
  openssl req -x509 -newkey rsa:2048 -nodes -days 365 -subj /CN=lupa \
    -keyout /config/ssl/cert.key -out /config/ssl/cert.pem >/dev/null 2>&1
fi
chown abc:abc /run/lupa/nginx.conf /config/ssl/cert.*
if [ -f /run/lupa/htpasswd ]; then chown abc:abc /run/lupa/htpasswd; chmod 600 /run/lupa/htpasswd; fi
cp /etc/lupa/openbox.xml /config/.config/openbox/rc.xml
cp /etc/lupa/menu.xml /config/.config/openbox/menu.xml
cp /etc/lupa/lupa.desktop /config/Desktop/lupa.desktop
cp /etc/lupa/lupa.desktop /config/.local/share/applications/lupa.desktop
chmod +x /config/Desktop/lupa.desktop
chown abc:abc /config/.config/openbox/*.xml /config/Desktop/lupa.desktop /config/.local/share/applications/lupa.desktop
exec gosu abc /usr/local/bin/session.sh
