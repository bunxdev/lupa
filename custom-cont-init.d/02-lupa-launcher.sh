#!/bin/bash
# Idempotente: deja en /config un launcher que reabre el chromium headed de lupa
# con un click — sobre el escritorio (Desktop/) y como entrada del menú openbox
# (botón derecho sobre el escritorio).
#
# Por qué a este nivel: el sidebar "Manage Applications" del wish-dashboard de
# selkies es un cliente de proot-apps (lista cerrada del repo LSIO). Chromium
# vía lupa no entra ahí, así que la integración que el usuario espera ("un
# botón para reabrir") va por las dos vías estándar de un escritorio Linux.
set -e

CONFIG=/config
OWNER="abc:abc"

mkdir -p "$CONFIG/bin" "$CONFIG/Desktop" "$CONFIG/.config/openbox" "$CONFIG/.local/share/applications"
chown -R abc:abc "$CONFIG/bin" "$CONFIG/Desktop" "$CONFIG/.config" "$CONFIG/.local"

# --- launcher script ---
# Usa el endpoint /live de lupa que ya gestiona launchPersistentContext con las
# extensiones, las descargas y el resto del setup. about:blank evita arrastrar
# la última URL visitada.
cat > "$CONFIG/bin/lupa" <<'SH'
#!/bin/bash
# `lupa` — reabre la sesión headed de chromium en lupa.
# Uso: lupa [url]                         (default: about:blank)
#      lupa close                         (cierra la sesión actual)
# Llamado desde:
#   - icon Desktop/Chromium · Lupa.desktop
#   - openbox menu → "Chromium · Lupa"
#   - manualmente desde xterm dentro del escritorio Selkies
set -e
API_URL="http://127.0.0.1:${PORT:-3036}"
if [ -n "${LUPA_API_TOKEN_FILE:-}" ]; then
  LUPA_API_TOKEN="$(tr -d '\r\n' < "$LUPA_API_TOKEN_FILE")"
fi
: "${LUPA_API_TOKEN:?LUPA_API_TOKEN is required}"

api_curl() {
  curl --header @<(printf 'Authorization: Bearer %s\n' "$LUPA_API_TOKEN") "$@"
}

case "${1:-}" in
  close)
    api_curl -sS -m 10 -X POST "$API_URL/live/close" >/dev/null
    echo "[lupa] sesión cerrada"
    ;;
  status|"")
    if [ -z "${1:-}" ]; then url="about:blank"; else url=""; fi
    if [ -n "$url" ]; then
      api_curl -sS -m 30 -X POST "$API_URL/live" \
        -H 'content-type: application/json' --data "{\"url\":\"$url\"}" >/dev/null
      echo "[lupa] navegador reabierto"
    else
      api_curl -sS -m 5 "$API_URL/live"
      echo
    fi
    ;;
  -h|--help)
    cat <<HELP
Uso:
  lupa                # reabre headed chromium en about:blank
  lupa <url>          # reabre headed chromium en la URL dada
  lupa close          # cierra la sesión headed
  lupa status         # imprime { open, url } actual
HELP
    ;;
  *)
    api_curl -sS -m 30 -X POST "$API_URL/live" \
      -H 'content-type: application/json' --data "{\"url\":\"$1\"}" >/dev/null
    echo "[lupa] navegador reabierto"
    ;;
esac
SH
chmod +x "$CONFIG/bin/lupa"
chown abc:abc "$CONFIG/bin/lupa"
# Compat con la versión previa del launcher (.desktop / openbox aún apuntan a lupa-live.sh).
ln -sf lupa "$CONFIG/bin/lupa-live.sh"
chown -h abc:abc "$CONFIG/bin/lupa-live.sh"

# /config/bin en el PATH para login shells (.profile) y para shells interactivos
# no-login (.bashrc). Esto cubre tanto un xterm spawneado desde el desktop como
# `bash -lc` desde fuera. Bloque idempotente delimitado por marker.
PATH_BLOCK='
# lupa-launcher PATH
case ":$PATH:" in *":$HOME/bin:"*) ;; *) export PATH="$HOME/bin:$PATH" ;; esac
'
for rc in "$CONFIG/.bashrc" "$CONFIG/.profile"; do
  [ -f "$rc" ] || { touch "$rc"; chown abc:abc "$rc"; }
  if ! grep -q '# lupa-launcher PATH' "$rc"; then
    printf '%s\n' "$PATH_BLOCK" >> "$rc"
  fi
done

# --- icono en el escritorio ---
DESKTOP_FILE="$CONFIG/Desktop/Chromium · Lupa.desktop"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Chromium · Lupa
Comment=Reabre la sesión headed con las extensiones montadas
Icon=chromium
Exec=/config/bin/lupa
Terminal=false
Categories=Network;WebBrowser;
StartupNotify=false
EOF
chmod +x "$DESKTOP_FILE"
chown abc:abc "$DESKTOP_FILE"
# El "trust" del archivo .desktop hace que el WM no muestre el icono crudo.
gio set "$DESKTOP_FILE" metadata::trusted true 2>/dev/null || true

# --- versión .local/share/applications (xdg) ---
APP_FILE="$CONFIG/.local/share/applications/chromium-lupa.desktop"
cp "$DESKTOP_FILE" "$APP_FILE"
chown abc:abc "$APP_FILE"

# --- openbox menu (click derecho en el escritorio) ---
MENU="$CONFIG/.config/openbox/menu.xml"
if ! grep -q 'Chromium · Lupa' "$MENU" 2>/dev/null; then
  cat > "$MENU" <<'XML'
<?xml version="1.0" encoding="utf-8"?>
<openbox_menu xmlns="http://openbox.org/3.4/menu">
<menu id="root-menu" label="MENU">
  <item label="Chromium · Lupa" icon="/usr/share/pixmaps/chromium.xpm">
    <action name="Execute"><command>/config/bin/lupa</command></action>
  </item>
  <separator/>
  <item label="xterm" icon="/usr/share/pixmaps/xterm-color_48x48.xpm">
    <action name="Execute"><command>/usr/bin/xterm</command></action>
  </item>
</menu>
</openbox_menu>
XML
  chown abc:abc "$MENU"
fi

# Reload openbox si ya está corriendo (idempotente — no falla si no está).
s6-setuidgid abc openbox --reconfigure 2>/dev/null || true

echo "[lupa-launcher] OK — Desktop/Chromium · Lupa.desktop + openbox menu listo"
