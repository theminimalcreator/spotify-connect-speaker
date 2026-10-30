#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Guilherme Zaia
"""Bridge MPRIS2 <-> pagina do Spotify Connect.

Exporta org.mpris.MediaPlayer2.linucao no barramento de sessao, para que
teclas de midia, o widget de midia do Plasma, playerctl etc. consigam
pausar / avancar / voltar / buscar a faixa que esta tocando na aba.

Le o estado da pagina em GET  /state  (porta 8099)
Envia comandos      em POST /queue
"""
import json
import os
import sys
import time
import urllib.request

import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

BUS_NAME = "org.mpris.MediaPlayer2.linucao"
MPRIS_PATH = "/org/mpris/MediaPlayer2"
ROOT_IFACE = "org.mpris.MediaPlayer2"
PLAYER_IFACE = "org.mpris.MediaPlayer2.Player"
PROPS_IFACE = "org.freedesktop.DBus.Properties"
API = os.environ.get(
    "SPOTIFY_CONNECT_API",
    f"http://127.0.0.1:{os.environ.get('SPOTIFY_CONNECT_PORT', '8099')}",
)

POLL_MS = 400
track_seq = 0


def http_get_state():
    try:
        with urllib.request.urlopen(f"{API}/state", timeout=1.5) as r:
            return json.load(r)
    except Exception:
        return None


def http_queue(cmd):
    try:
        req = urllib.request.Request(f"{API}/queue", data=cmd.encode(), method="POST")
        urllib.request.urlopen(req, timeout=1.5).read()
        print(f"[mpris] -> {cmd}", flush=True)
    except Exception as exc:
        print(f"[mpris] falha ao enviar {cmd}: {exc}", flush=True)


class SpotifyConnectPlayer(dbus.service.Object):
    def __init__(self, bus):
        self.state = {"connected": False, "playing": False, "title": "", "artist": "",
                      "album": "", "art": "", "position": 0, "duration": 0, "volume": 0.8}
        self.base_pos = 0
        self.base_at = time.monotonic()
        self.track_path = f"{MPRIS_PATH}/track/0"
        self.sig = {
            "PlaybackStatus": "Stopped", "Metadata": dbus.Dictionary({}, signature="sv"),
            "Volume": 0.8, "Position": dbus.Int64(0),
        }
        super().__init__(dbus.service.BusName(BUS_NAME, bus), MPRIS_PATH)
        self.player_iface = dbus.Interface(self, PLAYER_IFACE)

    # ---------- utilidades ----------
    def live_position_us(self):
        pos = self.base_pos
        if self.state.get("playing"):
            pos += int((time.monotonic() - self.base_at) * 1_000_000)
        dur = int(self.state.get("duration") or 0) * 1000
        return max(0, min(pos, dur) if dur else pos)

    def playback_status(self):
        if not self.state.get("title"):
            return "Stopped"
        return "Playing" if self.state.get("playing") else "Paused"

    def metadata(self):
        s = self.state
        global track_seq
        md = {
            "mpris:trackid": dbus.ObjectPath(self.track_path),
            "mpris:length": dbus.Int64(int(s.get("duration") or 0) * 1000),
            "xesam:title": s.get("title") or "",
            "xesam:artist": dbus.Array([s.get("artist") or ""], signature="s"),
            "xesam:album": s.get("album") or "",
        }
        if s.get("art"):
            md["mpris:artUrl"] = s["art"]
        return dbus.Dictionary(md, signature="sv")

    def props(self, iface):
        if iface == ROOT_IFACE:
            return dbus.Dictionary({
                "Identity": "Spotify Connect (linucao)",
                "DesktopEntry": "",
                "CanQuit": False, "CanRaise": False, "HasTrackList": False,
                "SupportedUriSchemes": dbus.Array([], signature="s"),
                "SupportedMimeTypes": dbus.Array([], signature="s"),
            }, signature="sv")
        if iface == PLAYER_IFACE:
            return dbus.Dictionary({
                "PlaybackStatus": self.playback_status(),
                "LoopStatus": "None",
                "Rate": 1.0,
                "Shuffle": False,
                "Metadata": self.metadata(),
                "Volume": dbus.Double(float(self.state.get("volume") or 0.8)),
                "Position": dbus.Int64(self.live_position_us()),
                "MinimumRate": 1.0, "MaximumRate": 1.0,
                "CanGoNext": True, "CanGoPrevious": True,
                "CanPlay": True, "CanPause": True,
                "CanSeek": True, "CanControl": True,
            }, signature="sv")
        return dbus.Dictionary({}, signature="sv")

    def changed(self, changed):
        self.PropertiesChanged(PLAYER_IFACE, dbus.Dictionary(changed, signature="sv"), [])

    # ---------- polling ----------
    def poll(self):
        s = http_get_state()
        if not s:
            return True
        old_status = self.playback_status()
        old_title = self.state.get("title")
        self.state = s
        self.base_pos = int(s.get("position") or 0) * 1000
        self.base_at = time.monotonic()
        if s.get("title") != old_title:
            global track_seq
            track_seq += 1
            self.track_path = f"{MPRIS_PATH}/track/{track_seq}"
            self.changed({"Metadata": self.metadata(), "PlaybackStatus": self.playback_status()})
            print(f"[mpris] faixa: {s.get('title')} — {s.get('artist')}", flush=True)
        elif self.playback_status() != old_status:
            self.changed({"PlaybackStatus": self.playback_status()})
        return True

    # ---------- org.mpris.MediaPlayer2 ----------
    @dbus.service.method(ROOT_IFACE, in_signature="", out_signature="")
    def Raise(self):
        pass

    @dbus.service.method(ROOT_IFACE, in_signature="", out_signature="")
    def Quit(self):
        pass

    # ---------- org.mpris.MediaPlayer2.Player ----------
    @dbus.service.method(PLAYER_IFACE, in_signature="", out_signature="")
    def Next(self):
        http_queue("next")

    @dbus.service.method(PLAYER_IFACE, in_signature="", out_signature="")
    def Previous(self):
        http_queue("previous")

    @dbus.service.method(PLAYER_IFACE, in_signature="", out_signature="")
    def Pause(self):
        http_queue("pause")

    @dbus.service.method(PLAYER_IFACE, in_signature="", out_signature="")
    def PlayPause(self):
        http_queue("playpause")

    @dbus.service.method(PLAYER_IFACE, in_signature="", out_signature="")
    def Stop(self):
        http_queue("pause")

    @dbus.service.method(PLAYER_IFACE, in_signature="", out_signature="")
    def Play(self):
        http_queue("play")

    @dbus.service.method(PLAYER_IFACE, in_signature="x", out_signature="")
    def Seek(self, offset_us):
        http_queue(f"seek_rel:{int(int(offset_us) / 1000)}")

    @dbus.service.method(PLAYER_IFACE, in_signature="ox", out_signature="")
    def SetPosition(self, track_id, position_us):
        http_queue(f"seek_abs:{int(int(position_us) / 1000)}")

    @dbus.service.method(PLAYER_IFACE, in_signature="s", out_signature="")
    def OpenUri(self, uri):
        pass

    # ---------- properties ----------
    @dbus.service.method(PROPS_IFACE, in_signature="ss", out_signature="v")
    def Get(self, interface, prop):
        value = self.props(interface).get(prop)
        if value is None:
            raise dbus.exceptions.DBusException(f"No such property {prop}",
                                                name="org.freedesktop.DBus.Error.InvalidArgs")
        return value

    @dbus.service.method(PROPS_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        return self.props(interface)

    @dbus.service.method(PROPS_IFACE, in_signature="ssv", out_signature="")
    def Set(self, interface, prop, value):
        if interface == PLAYER_IFACE and prop == "Volume":
            pct = max(0, min(100, round(float(value) * 100)))
            http_queue(f"volume:{pct}")
            self.state["volume"] = pct / 100
            self.changed({"Volume": dbus.Double(pct / 100)})

    @dbus.service.signal(PROPS_IFACE, signature="sa{sv}as")
    def PropertiesChanged(self, interface, changed, invalidated):
        pass


def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    player = SpotifyConnectPlayer(bus)
    print(f"[mpris] {BUS_NAME} disponível em {MPRIS_PATH}", flush=True)
    GLib.timeout_add(POLL_MS, player.poll)
    GLib.MainLoop().run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
