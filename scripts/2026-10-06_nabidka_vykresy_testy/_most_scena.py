#!/usr/bin/env python3
"""Most pro test SKUTECNE sceny (webapp/scene.html) - bot8, 2026-10-06. GET /api/* vyrizuje Flask test_client (prihlaseny admin v session; DB se jen cte), staticke soubory z webapp/.
Zapisujici pozadavky (POST / PUT / DELETE) na /api/ se NEPREDAVAJI aplikaci (vraci se 200 {}) - vyjimka jen cteci POST /api/stul/ a /api/shop/ (resolve, ceny); do ostrych dat se nezapisuje.
Chraneny Vandr GLB (/api/vandr-glb-file/, X-Accel-Redirect) vydava most primo ze souboru webapp/katalog/vandr/.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-06_nabidka_vykresy_testy/_most_scena.py <test.js>   (env BASE = adresa mostu)"""
import json, os, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

REPO = os.environ.get("REPO") or os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
os.chdir(REPO)
_orig = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _orig(self, *a, **k)
sys.path.insert(0, os.path.join(REPO, "api")); sys.path.insert(0, os.path.join(REPO, "scripts"))
try:
    import app as appmod
finally:
    threading.Thread.start = _orig
client = appmod.app.test_client()
_c = appmod.get_conn(); _cu = _c.cursor()
_cu.execute("SELECT id FROM app_users WHERE role='admin' AND COALESCE(active, 1)=1 ORDER BY id LIMIT 1")
ADMIN_ID = _cu.fetchone()["id"]; _c.rollback()
with client.session_transaction() as _s:
    _s["user_id"] = ADMIN_ID
WEB = os.environ.get("WEB_DIR") or os.path.join(REPO, "webapp")        # WEB_DIR = kandidat statiky (mutacni beh), API zustava zive
TYPY = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg",
        ".hdr": "application/octet-stream", ".glb": "model/gltf-binary", ".woff2": "font/woff2", ".ttf": "font/ttf"}
ZAPIS = []          # zapisujici pozadavky na /api/ (POST / PUT / DELETE) - test je ma videt; ostra data se NEZAPISUJI (vraci se 200 {}), kromě explicitne povolenych (cteci POST)
POVOLENE_POST = ("/api/stul/", "/api/shop/")


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, body, ctype, extra=()):
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store")
        for k, v in extra: self.send_header(k, v)
        try:
            self.end_headers(); self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _handle(self):
        u = urlparse(self.path); p = u.path
        if p.startswith("/api/"):
            n = int(self.headers.get("Content-Length") or 0); body = self.rfile.read(n) if n else None
            if self.command != "GET" and not p.startswith(POVOLENE_POST):
                ZAPIS.append((self.command, self.path, len(body or b"")))
                return self._send(200, b"{}", "application/json")
            r = client.open(self.path, method=self.command, data=body, headers={"Content-Type": self.headers.get("Content-Type", "application/json")})
            xa = r.headers.get("X-Accel-Redirect", "")
            if xa.startswith("/_vandr_glb_internal/"):          # chraneny Vandr GLB: nginx by ho vydal z webapp/katalog/vandr (X-Accel), most to nahrazuje primym ctenim
                from urllib.parse import unquote
                cesta = os.path.normpath(os.path.join(REPO, "webapp", "katalog", "vandr", unquote(xa[len("/_vandr_glb_internal/"):])))
                if cesta.startswith(os.path.join(REPO, "webapp", "katalog", "vandr")) and os.path.isfile(cesta):
                    return self._send(200, open(cesta, "rb").read(), "model/gltf-binary")
                return self._send(404, b"nf", "text/plain")
            return self._send(r.status_code, r.get_data(), r.headers.get("Content-Type", "application/json"))
        f = os.path.normpath(os.path.join(WEB, p.lstrip("/")))
        if f.startswith(WEB) and os.path.isfile(f):
            return self._send(200, open(f, "rb").read(), TYPY.get(os.path.splitext(f)[1], "application/octet-stream"))
        if p.startswith("/content-files/") or p.startswith("/katalog/"):
            return self._send(404, b"nf", "text/plain")
        self._send(404, b"nf", "text/plain")
    do_GET = do_POST = do_PUT = do_DELETE = _handle


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = "http://127.0.0.1:%d" % srv.server_address[1]
print("MOST", base, flush=True)
env = dict(os.environ, BASE=base)
sys.exit(subprocess.call(["node", sys.argv[1]], env=env))
