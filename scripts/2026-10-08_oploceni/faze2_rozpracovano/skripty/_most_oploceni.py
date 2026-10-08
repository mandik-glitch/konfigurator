#!/usr/bin/env python3
"""Integracni most pro test STRANKY GENERATORU OCHRANNY KRYT A OPLOCENI (bot8, 2026-10-08; vzor scripts/2026-10-02_stul_testy/_most_stul.py).
SKUTECNY front-end (webapp/oploceni-konfigurator.html + js/oploceni-host.js + js/product-configurator.js + js/pdc-layout.js + viewer3d.js) nad SKUTECNYM kodem shop vrstvy (api/oploceni_shop.py, rozcestnik, routy
stul_shop.py): /api/shop/* vyrizuje Flask test_client (cte DB pro ceny, nic nezapisuje), zbytek jsou staticke soubory webapp/. Dva servery na 127.0.0.1:
  BASE      = zamestnanec (session admin, /api/auth/me vraci zamestnance, resolve s `staff: true` vrati blok staff),
  BASE_PUB  = verejny navstevnik (bez session, /api/auth/me vraci user null).
Mapovani produktu (app_settings.configurator_products) se podstrci jen v pameti: fiktivni karta PID (vychozi 9990) s receptem oploceni_kryt. Slouzi VYHRADNE na 127.0.0.1 pro testy.
Spusteni (DB pres systemd-run; koren repa = zivy /opt/konfigurator nebo <kandidat>/repo):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=<koren> \\
    /opt/konfigurator/api/venv/bin/python3 <koren>/scripts/2026-10-08_oploceni/_most_oploceni.py <test.js> [PID]"""
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
os.chdir(REPO)
if not os.environ.get("DB_HOST"):
    print("CHYBA: chybi DB_* v prostredi (viz hlavicka)")
    sys.exit(2)
_orig = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _orig(self, *a, **k)
sys.path.insert(0, os.path.join(REPO, "api"))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.dont_write_bytecode = True
try:
    import app as appmod
    import stul_shop as SH
finally:
    threading.Thread.start = _orig
SH.LIMIT_SCHEMA = (10 ** 6, 60)
SH.LIMIT_RESOLVE = (10 ** 6, 60)
SH.LIMIT_GLB = (10 ** 6, 60)
SH.HODINOVY_STROP.update({k: 10 ** 6 for k in SH.HODINOVY_STROP})
PID = sys.argv[2] if len(sys.argv) > 2 else "9990"
SH._PRODUKTY.update(t=time.time() + 100_000, map={PID: "oploceni_kryt"})
client = appmod.app.test_client()                       # zamestnanec
client_pub = appmod.app.test_client()                   # verejnost (bez session)
_c = appmod.get_conn()
_cu = _c.cursor()
_cu.execute("SELECT id FROM app_users WHERE role='admin' AND COALESCE(active, 1)=1 ORDER BY id LIMIT 1")
ADMIN_ID = _cu.fetchone()["id"]
_c.rollback()
with client.session_transaction() as _s:
    _s["user_id"] = ADMIN_ID
WEB = os.path.join(REPO, "webapp")
TYPY = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".hdr": "application/octet-stream"}
USER = {"user": {"id": 1, "email": "staff@example.test", "role": "admin", "name": "Staff"}}


def handler(api_client, user):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype, extra=()):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in extra:
                self.send_header(k, v)
            try:
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):          # prohlizec zavrel spojeni (zrusene nacitani modelu) - neni chyba mostu
                pass

        def _handle(self):
            u = urlparse(self.path)
            p = u.path
            if p == "/api/auth/me":
                return self._send(200, json.dumps(user).encode(), "application/json")
            if p.startswith("/api/shop/") or p.startswith("/api/stul/"):
                n = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(n) if n else None
                r = api_client.open(self.path, method=self.command, data=body, headers={"Content-Type": self.headers.get("Content-Type", "application/json"), "Accept-Encoding": self.headers.get("Accept-Encoding", "")})
                extra = [("Content-Encoding", r.headers["Content-Encoding"])] if r.headers.get("Content-Encoding") else []
                return self._send(r.status_code, r.get_data(), r.headers.get("Content-Type", "application/json"), extra)
            if p.startswith("/api/"):
                return self._send(404, b"{}", "application/json")
            f = os.path.normpath(os.path.join(WEB, p.lstrip("/")))
            if f.startswith(WEB) and os.path.isfile(f):
                return self._send(200, open(f, "rb").read(), TYPY.get(os.path.splitext(f)[1], "application/octet-stream"))
            self._send(404, b"nf", "text/plain")
        do_GET = do_POST = _handle
    return H


srv = ThreadingHTTPServer(("127.0.0.1", 0), handler(client, USER))
srv_pub = ThreadingHTTPServer(("127.0.0.1", 0), handler(client_pub, {"user": None}))
threading.Thread(target=srv.serve_forever, daemon=True).start()
threading.Thread(target=srv_pub.serve_forever, daemon=True).start()
base = "http://127.0.0.1:%d" % srv.server_address[1]
base_pub = "http://127.0.0.1:%d" % srv_pub.server_address[1]
env = dict(os.environ, BASE=base, BASE_PUB=base_pub, PID=PID)
sys.exit(subprocess.call(["node", sys.argv[1]], env=env))
