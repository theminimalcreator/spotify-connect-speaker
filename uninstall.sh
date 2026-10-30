#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Guilherme Zaia
# Remove o que o install.sh criou. O repositorio em si nunca e apagado.
set -euo pipefail

PURGE=0
[ "${1:-}" = "--purge" ] && PURGE=1

UNITDIR="$HOME/.config/systemd/user"
APPDIR_DESKTOP="$HOME/.local/share/applications"
APPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> parando e desabilitando servicos"
systemctl --user disable --now spotify-connect-mpris.service 2>/dev/null || true
systemctl --user disable --now spotify-connect-web.service 2>/dev/null || true

rm -fv "$UNITDIR/spotify-connect-mpris.service" "$UNITDIR/spotify-connect-web.service"
rm -fv "$APPDIR_DESKTOP/spotify-connect.desktop"
rm -fv "$HOME/.config/autostart/spotify-connect.desktop"
rm -fv "$APPDIR/browser.log"

systemctl --user daemon-reload
update-desktop-database "$APPDIR_DESKTOP" 2>/dev/null || true

if [ "$PURGE" = "1" ]; then
  echo "==> removendo web/config.js (contem o refresh_token)"
  rm -fv "$APPDIR/web/config.js"
else
  echo "==> web/config.js mantido (use --purge para remover)"
fi

echo "==> pronto"
