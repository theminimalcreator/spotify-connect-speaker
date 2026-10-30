#!/usr/bin/env bash
# Instala/atualiza o Spotify Connect Speaker na sessao do usuario.
# Idempotente: pode rodar quantas vezes quiser.
set -euo pipefail

APPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${SPOTIFY_CONNECT_PORT:-8099}"
URL="http://127.0.0.1:${PORT}/"
NAME="${SPOTIFY_DEVICE_NAME:-linucao}"
UNITDIR="$HOME/.config/systemd/user"
APPDIR_DESKTOP="$HOME/.local/share/applications"

say() { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

# ---------- pre-requisitos ----------
command -v python3 >/dev/null || die "python3 nao encontrado"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' \
  || die "python3 >= 3.8 necessario"

python3 -c 'import dbus' 2>/dev/null || warn "python3-dbus ausente: o bridge MPRIS (teclas de midia) nao vai subir"
python3 -c 'import gi' 2>/dev/null || warn "python3-gobject ausente: idem"

if [ ! -f /var/lib/widevine/gmp-widevinecdm/system-installed/manifest.json ]; then
  warn "Widevine nao encontrado em /var/lib/widevine."
  warn "Sem ele o navegador nao descriptografa o audio. Rode: sudo widevine-installer"
fi

# ---------- config.js (segredo, 0600, fora do git) ----------
if [ ! -f "$APPDIR/web/config.js" ] || ! grep -q refresh_token "$APPDIR/web/config.js"; then
  say "gerando web/config.js"
  python3 "$APPDIR/scripts/gen-config.py" --name "$NAME" --out "$APPDIR/web/config.js"
else
  say "web/config.js ja existe (mantido)"
fi

# ---------- units do systemd ----------
mkdir -p "$UNITDIR"
say "instalando units em $UNITDIR"
for unit in web mpris; do
  src="$APPDIR/systemd/spotify-connect-${unit}.service.in"
  dst="$UNITDIR/spotify-connect-${unit}.service"
  sed "s|@APPDIR@|$APPDIR|g" "$src" > "$dst"
  echo "    $dst"
done

systemctl --user daemon-reload
systemctl --user enable spotify-connect-web.service spotify-connect-mpris.service >/dev/null
systemctl --user restart spotify-connect-web.service
systemctl --user restart spotify-connect-mpris.service
sleep 2

# ---------- atalho ----------
mkdir -p "$APPDIR_DESKTOP"
sed -e "s|@URL@|$URL|g" -e "s|@NAME@|$NAME|g" \
  "$APPDIR/desktop/spotify-connect.desktop.in" > "$APPDIR_DESKTOP/spotify-connect.desktop"
update-desktop-database "$APPDIR_DESKTOP" 2>/dev/null || true
say "atalho instalado: $APPDIR_DESKTOP/spotify-connect.desktop"

# ---------- verificacao ----------
echo
say "verificando"
sleep 1
code=$(curl -s -o /dev/null -w '%{http_code}' "$URL" || true)
[ "$code" = "200" ] && echo "    servidor web ....... OK (HTTP 200 em $URL)" \
                    || die "servidor web nao respondeu (HTTP $code)"
systemctl --user is-active --quiet spotify-connect-mpris.service \
  && echo "    bridge MPRIS ....... OK" || warn "bridge MPRIS inativo"

cat <<EOF

$(say "pronto")

  1. Abra:  $URL     (ou o atalho "Spotify Connect ($NAME)" no menu)
  2. Clique em "Ativar audio nesta aba"  <- o Firefox exige um gesto
  3. No celular: lista de dispositivos -> $NAME -> play

Lembretes:
  * a aba precisa ficar aberta; se fechar, o dispositivo sai da lista
  * depois de um F5, re-selecione "$NAME" no celular (o device_id muda)
  * teclas de midia funcionam com a aba em segundo plano (via MPRIS)

Para abrir a aba sozinho no login:
  mkdir -p ~/.config/autostart
  cp "$APPDIR_DESKTOP/spotify-connect.desktop" ~/.config/autostart/
EOF
