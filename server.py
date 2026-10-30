#!/usr/bin/env python3
"""Servidor local do Spotify Connect Speaker (bridge HTTP + arquivos estaticos).

Responsabilidades
-----------------
  GET  /            -> web/index.html
  GET  /config.js   -> web/config.js (client_id + refresh_token, nunca versionado)
  GET  /state       -> ultimo estado conhecido (lido pelo bridge MPRIS)
  POST /state       -> a pagina envia seu estado e recebe comandos pendentes
  POST /queue       -> enfileira um comando (usado pelo bridge MPRIS)
  POST /log         -> log do navegador -> browser.log

O EME/Widevine exige *secure context*, por isso servimos em 127.0.0.1 em vez
de abrir o arquivo direto (file://).
"""
import json
import os
import socketserver
import threading
import time
from http.server import SimpleHTTPRequestHandler

BASE = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE, "web")
LOGFILE = os.path.join(BASE, "browser.log")
PORT = int(os.environ.get("SPOTIFY_CONNECT_PORT", "8099"))

STATE = {
    "connected": False, "playing": False,
    "title": "", "artist": "", "album": "", "art": "",
    "position": 0, "duration": 0, "volume": 0.8, "updated": 0,
}
QUEUE = []
LOCK = threading.Lock()


def log_line(msg):
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOGFILE, "a", encoding="utf-8") as fh:
            for line in str(msg).splitlines() or [""]:
                fh.write(f"{stamp} {line}\n")
    except OSError:
        pass


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def end_headers(self):
        # durante o desenvolvimento um F5 nunca deve servir HTML velho
        self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
        except ValueError:
            return b""
        return self.rfile.read(n) if n else b""

    def _json(self, obj, code=200):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _no_content(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        if self.path == "/state":
            with LOCK:
                return self._json(STATE)
        if self.path == "/health":
            return self._json({"ok": True, "port": PORT})
        return super().do_GET()

    def do_POST(self):
        raw = self._body()

        if self.path == "/log":
            log_line(raw.decode("utf-8", "replace"))
            return self._no_content()

        if self.path == "/state":
            try:
                incoming = json.loads(raw or b"{}")
            except ValueError:
                incoming = {}
            if isinstance(incoming, dict):
                with LOCK:
                    STATE.update(incoming)
                    STATE["updated"] = time.time()
                    cmds = QUEUE[:]
                    QUEUE.clear()
            else:
                cmds = []
            return self._json({"commands": cmds})

        if self.path == "/queue":
            cmd = raw.decode("utf-8", "replace").strip()
            if cmd:
                with LOCK:
                    if len(QUEUE) < 20:
                        QUEUE.append(cmd)
            return self._no_content()

        self.send_error(404)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    log_line(f"--- servidor iniciado em 127.0.0.1:{PORT} (web: {WEB_DIR}) ---")
    with Server(("127.0.0.1", PORT), Handler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    main()
