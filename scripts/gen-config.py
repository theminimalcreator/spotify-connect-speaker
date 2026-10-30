#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Guilherme Zaia
"""Gera web/config.js com client_id + refresh_token para o Web Playback SDK.

O SDK exige um access token de usuario com o scope `streaming`. A forma mais
simples de obter isso sem registrar um app proprio e reaproveitar o token que
o ncspot ja gravou (`~/.cache/ncspot/rspotify_token.json`), porque o app do
ncspot declara `streaming` nos scopes.

O token gerado e validado na hora contra accounts.spotify.com, e o script
avisa se `streaming` nao estiver entre os scopes concedidos.
"""
import argparse
import json
import os
import stat
import sys
import urllib.parse
import urllib.request

DEFAULT_CLIENT_ID = "d420a117a32841c2b3474932e49fb54b"  # app publico do ncspot
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(REPO, "web", "config.js")
DEFAULT_NCSPOT = os.path.expanduser("~/.cache/ncspot/rspotify_token.json")


def validar(client_id, refresh_token):
    """Troca o refresh_token por um access_token e devolve os scopes concedidos."""
    body = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        }
    ).encode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "spotify-connect-speaker/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        tok = json.load(r)
    return (tok.get("scope") or "").split(), tok


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--client-id", default=os.environ.get("SPOTIFY_CLIENT_ID", DEFAULT_CLIENT_ID))
    ap.add_argument("--refresh-token", default=os.environ.get("SPOTIFY_REFRESH_TOKEN"),
                    help="se omitido, le de --ncspot-token")
    ap.add_argument("--ncspot-token", default=DEFAULT_NCSPOT)
    ap.add_argument("--name", default=os.environ.get("SPOTIFY_DEVICE_NAME", "linucao"),
                    help="nome que aparece na lista de dispositivos")
    ap.add_argument("--volume", type=float, default=0.8, help="volume inicial 0.0-1.0")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--no-validate", action="store_true")
    args = ap.parse_args()

    token = args.refresh_token
    origem = "--refresh-token/env"
    if not token:
        if not os.path.exists(args.ncspot_token):
            sys.exit(f"erro: nenhum refresh_token informado e {args.ncspot_token} nao existe.\n"
                     "      rode o ncspot uma vez, ou passe --refresh-token.")
        try:
            token = json.load(open(args.ncspot_token)).get("refresh_token")
        except (OSError, ValueError) as exc:
            sys.exit(f"erro ao ler {args.ncspot_token}: {exc}")
        origem = args.ncspot_token

    if not token:
        sys.exit("erro: refresh_token vazio")

    if not args.no_validate:
        try:
            scopes, _ = validar(args.client_id, token)
        except Exception as exc:  # noqa: BLE001
            sys.exit(f"erro: o refresh_token foi recusado pelo Spotify: {exc}")
        if "streaming" not in scopes:
            sys.exit("erro: o token nao tem o scope 'streaming' (obrigatorio para o SDK).\n"
                     f"      scopes concedidos: {' '.join(scopes) or '(nenhum)'}")
        print(f"token validado — {len(scopes)} scopes, 'streaming' presente")
    else:
        print("token NAO validado (--no-validate)")

    cfg = {
        "client_id": args.client_id,
        "refresh_token": token,
        "device_name": args.name,
        "volume": args.volume,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write("window.CFG = " + json.dumps(cfg, indent=2, ensure_ascii=False) + ";\n")
    os.chmod(args.out, stat.S_IRUSR | stat.S_IWUSR)  # 0600: e um segredo

    print(f"escrito: {args.out} (0600)")
    print(f"token de origem: {origem}")
    print(f"device_name: {args.name}")


if __name__ == "__main__":
    main()
