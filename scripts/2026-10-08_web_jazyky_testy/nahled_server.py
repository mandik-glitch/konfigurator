#!/usr/bin/env python3
"""Lokalni NAHLED jazykovych verzi webu z kandidatniho stromu (bot16): app z <koren>/api s modulem web_i18n, port 127.0.0.1:<port>, kazdy pozadavek se tvari jako zamestnanec (jen pro nahled, nikdy ven).
Render dozorce (vlakno render-dozorce) se NEspousti, zadne jine pozadavky nez GET zakaznickych stranek se nedelaji. Pouziti: nahled_server.py <koren> [port]"""
import sys
import threading

ROOT = sys.argv[1]
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8191
_orig = threading.Thread.start


def _start(self, *a, **k):
    if getattr(self, "name", "") == "render-dozorce":
        return None
    return _orig(self, *a, **k)


threading.Thread.start = _start
sys.path.insert(0, ROOT + "/api")
sys.dont_write_bytecode = True
import app as appmod  # noqa: E402
import web_i18n as W  # noqa: E402

W._je_zamestnanec = lambda: True

# staticke soubory jako nginx (Flask je jinak neposila): js, css, obrazky, fonty, content-files, katalog ...
import os  # noqa: E402
from flask import request, send_from_directory  # noqa: E402
_WEBAPP = os.path.join(ROOT, "webapp")
_PRIPONY = (".js", ".css", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico", ".woff", ".woff2", ".ttf", ".gif", ".json", ".glb", ".mp4", ".webmanifest")


@appmod.app.before_request
def _staticke():
    cesta = request.path.lstrip("/")
    if request.method == "GET" and not cesta.startswith("api/") and (cesta.lower().endswith(_PRIPONY) or cesta.startswith(("content-files/", "katalog/"))):
        if os.path.isfile(os.path.join(_WEBAPP, cesta)):
            return send_from_directory(_WEBAPP, cesta)
    return None
appmod.app.run(host="127.0.0.1", port=PORT, threaded=True, use_reloader=False)
