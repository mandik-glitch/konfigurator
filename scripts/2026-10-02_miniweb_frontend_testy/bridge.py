#!/usr/bin/env python3
"""Integracni most pro test mini-shopu: SKUTECNY front-end (webapp/miniweb + js/product-configurator.js + viewer3d.js) nad SKUTECNYM kodem
konfiguratoru stolu (api/stul_shop.py, bot8) - /api/shop/* vyrizuje Flask test_client (cte DB pro ceny, nic nezapisuje), zbytek jsou staticke soubory
webapp/. /api/auth/me vraci falesneho zamestnance. Mapovani produktu (app_settings.configurator_products) se podstrci jen v pameti.
Slouzi VYHRADNE na 127.0.0.1 pro testy. Spusteni (DB pres systemd-run):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator \\
    api/venv/bin/python3 scripts/2026-10-02_miniweb_frontend_testy/bridge.py <testovaci_skript.js> [PID]"""
import json, os, re, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(REPO)
if not os.environ.get("DB_HOST"):
    print("CHYBA: chybi DB_* v prostredi (viz hlavicka)"); sys.exit(2)
_orig = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _orig(self, *a, **k)
sys.path.insert(0, os.path.join(REPO, "api")); sys.path.insert(0, os.path.join(REPO, "scripts"))
try:
    import app as appmod
    import stul_shop as SH
finally:
    threading.Thread.start = _orig

PID = sys.argv[2] if len(sys.argv) > 2 else "9001"
PID40 = str(int(PID) + 1)                                   # druhy testovaci produkt = system 40 (titulek, prepinac systemu); skript ho dostane v env PID40
PID35 = str(int(PID) + 2)                                   # treti testovaci produkt = system 35 (karta #4955, zive API ma od 2026-10-05 schema.systems 30/35/40); env PID35
REAL = os.environ.get("BRIDGE_CARDS") == "real"                      # BRIDGE_CARDS=real: schema.systems ukazuje na SKUTECNE karty 4934 / 4954 (test karty produktu s generatorem)
SH._PRODUKTY.update(t=time.time() + 100_000, map={PID: SH.RECEPT, PID40: SH.RECEPT_40, PID35: SH.RECEPT_35, "4934": SH.RECEPT, "4954": SH.RECEPT_40, "4955": SH.RECEPT_35})
SH._SYSTEMY_CACHE.update(t=time.time() + 100_000, list=[{"system": 30, "card_id": 4934 if REAL else int(PID), "active": True}, {"system": 35, "card_id": 4955 if REAL else int(PID35), "active": True}, {"system": 40, "card_id": 4954 if REAL else int(PID40), "active": True}])      # obe testovaci karty aktivni = verejny prepinac systemu je videt
client = appmod.app.test_client()
WEB = os.path.abspath(os.environ.get("WEB_OVERRIDE") or os.path.join(REPO, "webapp"))     # WEB_OVERRIDE: jine webapp (napr. git worktree pro porovnani PRED/PO)
TYPY = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".hdr": "application/octet-stream"}
USER = {"user": {"id": 1, "email": "staff@example.test", "role": "admin", "name": "Staff"}}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, body, ctype, extra=()):
        extra = list(extra); keys = [k.lower() for k, _ in extra]
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
        if "cache-control" not in keys: self.send_header("Cache-Control", "no-store")
        for k, v in extra: self.send_header(k, v)
        try:
            self.end_headers(); self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):       # prohlizec prerusil pozadavek (zavreni stranky, zruseny preload) - bez vypisu
            pass

    def _handle(self):
        u = urlparse(self.path); p = u.path
        if p == "/api/auth/me": return self._send(200, json.dumps(USER).encode(), "application/json")
        if p.startswith("/api/shop/") or (self.command == "GET" and (p == "/api/categories" or re.match(r"^/api/categories/\d+/content\Z", p))):
            n = int(self.headers.get("Content-Length") or 0); body = self.rfile.read(n) if n else None
            r = client.open(self.path, method=self.command, data=body, headers={"Content-Type": self.headers.get("Content-Type", "application/json"), "Accept-Encoding": self.headers.get("Accept-Encoding", "")})
            ex = [(k, r.headers[k]) for k in ("Cache-Control", "Content-Encoding", "Vary") if r.headers.get(k)]       # jako ostry server: komprese GLB a mezipamet prohlizece
            return self._send(r.status_code, r.get_data(), r.headers.get("Content-Type", "application/json"), ex)
        if p == "/api/admin/konfigurace/nabidka" and self.command == "GET": return self._send(200, b'{"ok": true, "verze": 1}', "application/json")     # sonda tlacitka "Do online nabidky" (js/stul-nabidka.js, bot16 2026-10-06): skutecne API ji da prihlasenemu adminovi (200); jinak by kazdy test s kontrolou konzole hlasil 404
        if p == "/api/admin/konfigurace/karta" and self.command == "GET": return self._send(200, b'{"ok": true, "verze": 1, "muze_aktivovat": true, "kategorie": [], "vychozi_kategorie": {}}', "application/json")     # sonda tlacitka "Vytvorit kartu" (js/stul-karta.js, bot10 2026-10-07): skutecne API ji da prihlasenemu s pravem sklad_karty/vytvorit
        if p.startswith("/api/"): return self._send(404, b"{}", "application/json")
        SLUGY = {"pracovni-stul-system-30-konfigurovatelny": 4934, "pracovni-stul-system-40-konfigurovatelny": 4954, "pracovni-stul-system-35-konfigurovatelny": 4955}
        if p.startswith("/produkt/") and p[len("/produkt/"):] in SLUGY:      # cista adresa karty: server vklada window.__PRODUCT_ID__ (jako api/storefront_pages.py)
            h = open(os.path.join(WEB, "product.html"), "rb").read().replace(b"<head>", b"<head><script>window.__PRODUCT_ID__=%d;</script>" % SLUGY[p[len("/produkt/"):]], 1)
            return self._send(200, h, "text/html; charset=utf-8")
        f = os.path.normpath(os.path.join(WEB, p.lstrip("/")))
        if f.startswith(WEB) and os.path.isfile(f):
            data = open(f, "rb").read()
            if re.search(r"/miniweb/config\.[a-z]+\.json\Z", p):      # demo konfigurace mini-shopu: konfigurator ukazuje na testovaci produkt (testy to dosud delaly page.route, ktery vypina HTTP cache stranky)
                j = json.loads(data); j["configurator_product_id"] = int(PID); data = json.dumps(j).encode()
            return self._send(200, data, TYPY.get(os.path.splitext(f)[1], "application/octet-stream"))
        self._send(404, b"nf", "text/plain")
    do_GET = do_POST = _handle


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = "http://127.0.0.1:%d" % srv.server_address[1]
if len(sys.argv) > 1 and sys.argv[1] == "--schema":
    import urllib.request
    print(urllib.request.urlopen(base + "/api/shop/products/%s/configurator?lang=cs" % PID).read().decode()[:6000]); sys.exit(0)
env = dict(os.environ, BASE=base, PID=PID, PID40=PID40, PID35=PID35)
sys.exit(subprocess.call(["node", sys.argv[1]], env=env))
