#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Guilherme Zaia
#
# Verificacao rapida do repositorio. Nao ha suite de testes: este script cobre
# sintaxe, cabecalhos de licenca e, se os servicos estiverem no ar, a saude da
# aplicacao. Roda em qualquer maquina, com ou sem os servicos instalados.
set -uo pipefail

APPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APPDIR"

PORT="${SPOTIFY_CONNECT_PORT:-8099}"
FAIL=0
TMPJS="$(mktemp -t spotify-connect-check.XXXXXX.js)"
trap 'rm -f "$TMPJS"' EXIT

ok()   { printf '  \033[1;32mok\033[0m   %s\n' "$*"; }
bad()  { printf '  \033[1;31mFALHOU\033[0m %s\n' "$*"; FAIL=1; }
skip() { printf '  \033[1;33mskip\033[0m %s\n' "$*"; }
head_() { printf '\n\033[1m%s\033[0m\n' "$*"; }

# ---------- sintaxe python ----------
head_ "sintaxe python"
for f in server.py mpris.py scripts/gen-config.py; do
  if python3 -m py_compile "$f" 2>/dev/null; then ok "$f"; else bad "$f"; fi
done

# ---------- sintaxe bash ----------
head_ "sintaxe bash"
for f in install.sh uninstall.sh scripts/check.sh; do
  if bash -n "$f" 2>/dev/null; then ok "$f"; else bad "$f"; fi
done

# ---------- sintaxe js (inline no index.html) ----------
head_ "sintaxe javascript"
if ! command -v node >/dev/null; then
  skip "node ausente (pulei o check do <script> inline)"
elif python3 -c "
import re, sys
html = open('web/index.html', encoding='utf-8').read()
blocks = re.findall(r'<script>(.*?)</script>', html, re.S)
if not blocks:
    sys.exit('nenhum <script> inline encontrado')
open(sys.argv[1], 'w', encoding='utf-8').write(blocks[-1])
" "$TMPJS"; then
  if node --check "$TMPJS" 2>/dev/null; then ok "web/index.html (<script> inline)"; else bad "web/index.html (<script> inline)"; fi
else
  bad "web/index.html: nao consegui extrair o <script> inline"
fi

# ---------- cabecalhos de licenca ----------
head_ "cabecalhos SPDX"
for f in server.py mpris.py scripts/gen-config.py scripts/check.sh \
         install.sh uninstall.sh web/index.html config.example.js; do
  if grep -q 'SPDX-License-Identifier: GPL-3.0-only' "$f" 2>/dev/null; then
    ok "$f"
  else
    bad "$f (sem SPDX-License-Identifier)"
  fi
done
if grep -qF 'GNU GENERAL PUBLIC LICENSE' LICENSE 2>/dev/null; then
  ok "LICENSE"
else
  bad "LICENSE (texto da GPL ausente)"
fi

# ---------- segredo fora do git ----------
head_ "segredo nao versionado"
if ! git rev-parse --git-dir >/dev/null 2>&1; then
  skip "nao e um repositorio git"
elif git ls-files --error-unmatch web/config.js >/dev/null 2>&1; then
  bad "web/config.js esta versionado! (git rm --cached web/config.js)"
else
  ok "web/config.js fora do indice"
fi

# ---------- servico no ar (opcional) ----------
head_ "servico"
if ! curl -fsS --max-time 2 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  skip "servidor nao esta respondendo em :${PORT} (rode ./install.sh)"
else
  ok "GET /health"
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 "http://127.0.0.1:${PORT}/" || true)
  [ "$code" = "200" ] && ok "GET / (HTTP 200)" || bad "GET / retornou HTTP $code"

  if systemctl --user is-active --quiet spotify-connect-browser.service 2>/dev/null; then
    ok "spotify-connect-browser (Firefox headless) ativo"
  else
    skip "spotify-connect-browser inativo (rode ./install.sh)"
  fi

  if systemctl --user is-active --quiet spotify-connect-mpris.service 2>/dev/null; then
    ok "spotify-connect-mpris ativo"
    if command -v gdbus >/dev/null; then
      if gdbus call --session --dest org.mpris.MediaPlayer2.linucao \
           --object-path /org/mpris/MediaPlayer2 \
           --method org.freedesktop.DBus.Properties.Get \
           org.mpris.MediaPlayer2.Player PlaybackStatus >/dev/null 2>&1; then
        ok "D-Bus org.mpris.MediaPlayer2.linucao responde"
      else
        bad "D-Bus org.mpris.MediaPlayer2.linucao nao responde"
      fi
    else
      skip "gdbus ausente"
    fi
  else
    skip "spotify-connect-mpris inativo"
  fi
fi

echo
if [ "$FAIL" = "0" ]; then
  printf '\033[1;32mTudo certo.\033[0m Lembre: depois de mudar web/index.html, F5 na aba e\n'
  printf 're-selecionar o dispositivo no celular (o device_id muda).\n'
  exit 0
else
  printf '\033[1;31mHa falhas acima.\033[0m\n'
  exit 1
fi
