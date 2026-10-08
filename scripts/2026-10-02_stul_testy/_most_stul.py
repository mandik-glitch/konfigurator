#!/usr/bin/env python3
"""Integracni most pro test STRANKY STOLU PRO ZAMESTNANCE (bot8, 2026-10-04; kopie scripts/2026-10-02_miniweb_frontend_testy/bridge.py + prihlaseny admin v session, produkt 4934).
SKUTECNY front-end (webapp/miniweb + js/product-configurator.js + viewer3d.js) nad SKUTECNYM kodem
konfiguratoru stolu (api/stul_shop.py, bot8) - /api/shop/* vyrizuje Flask test_client (cte DB pro ceny, nic nezapisuje), zbytek jsou staticke soubory
webapp/. /api/auth/me vraci falesneho zamestnance. Mapovani produktu (app_settings.configurator_products) se podstrci jen v pameti.
Slouzi VYHRADNE na 127.0.0.1 pro testy. Spusteni (DB pres systemd-run):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator \\
    api/venv/bin/python3 scripts/2026-10-02_miniweb_frontend_testy/bridge.py <testovaci_skript.js> [PID]"""
import json, os, subprocess, sys, threading, time
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

PID = sys.argv[2] if len(sys.argv) > 2 else "4934"
PID40 = os.environ.get("PID40")                              # volitelne: fiktivni karta systemu 40 (recept stul_system40) pro test stranky Generator stolu 02 (bot10, 2026-10-04)
PID35 = os.environ.get("PID35")                              # volitelne: fiktivni karta systemu 35 (recept stul_system35) pro test stranky Generator stolu 03 (bot10, 2026-10-05)
PID41 = os.environ.get("PID41")                              # volitelne: fiktivni karta systemu 41 (recept stul_system41, stul SSE) pro test stranky Generator stolu 04 (bot8, 2026-10-05)
PID45 = os.environ.get("PID45")                              # volitelne: fiktivni karta systemu 45 (recept stul_system45, hluboky stul az 2500 mm) pro test stranky Generator stolu 05 (bot10, 2026-10-07)
SH._PRODUKTY.update(t=time.time() + 100_000, map={PID: SH.RECEPT, **({PID40: SH.RECEPT_40} if PID40 else {}), **({PID35: SH.RECEPT_35} if PID35 else {}), **({PID41: SH.RECEPT_SSE} if PID41 else {}),
                                                  **({PID45: SH.RECEPT_45} if PID45 else {})})
PRAVIDLA_TEST = os.environ.get("PRAVIDLA_TEST")              # volitelne: pravidla stolu pro test MISTO zivych z app_settings (JSON ve tvaru `stul_pravidla`; "{}" = vychozi hodnoty vsech systemu) - test pak nezavisi na tom,
if PRAVIDLA_TEST is not None:                                # co zrovna zadal Robert v Pravidlech stolu (cena noh SSE, prah stredni nohy; bot8 2026-10-05, test SSE stranky padal po zadani zivych pravidel)
    import stul_api as _SA
    import stul_konfigurator as _S
    _S.nastav_pravidla_po_systemech(_SA.pravidla_z_json(PRAVIDLA_TEST))
    _SA.obnov_pravidla = lambda force=False: None            # before_request ani GET /api/stul/pravidla uz zive nastaveni nenacte (nic se do DB nezapisuje ani tak)
VYCHOZI_TEST = json.loads(os.environ.get("VYCHOZI_TEST") or "{}")   # ulozene VYCHOZI KONFIGURACE generatoru pro test, JSON {"<id produktu>": {slot: hodnota}}; testy pocitaji s VESTAVENYMI vychozimi hodnotami, takze se zive
import stul_api as _SA3                                              # ulozene (app_settings configurator_default_<id>, tlacitko "Ulozit jako vychozi", bot8 2026-10-05) NIKDY nenacitaji (ani kdyz je admin ulozi)
_SA3.nacti_vychozi = lambda product_id, force=False: (dict(VYCHOZI_TEST[str(product_id)]) if str(product_id) in VYCHOZI_TEST else None)
client = appmod.app.test_client()
_c = appmod.get_conn(); _cu = _c.cursor()
_cu.execute("SELECT id FROM app_users WHERE role='admin' AND COALESCE(active, 1)=1 ORDER BY id LIMIT 1")
ADMIN_ID = _cu.fetchone()["id"]; _c.rollback()
with client.session_transaction() as _s:
    _s["user_id"] = ADMIN_ID                                  # zamestnanec: resolve s `staff: true` vrati blok staff
WEB = os.path.join(REPO, "webapp")
TYPY = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".hdr": "application/octet-stream"}
USER = {"user": {"id": 1, "email": "staff@example.test", "role": "admin", "name": "Staff"}}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, body, ctype, extra=()):
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store")
        for k, v in extra: self.send_header(k, v)
        try:
            self.end_headers(); self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):          # prohlizec zavrel spojeni (zrusene nacitani modelu) - neni chyba mostu
            pass

    def _handle(self):
        u = urlparse(self.path); p = u.path
        if p == "/api/auth/me": return self._send(200, json.dumps(USER).encode(), "application/json")
        if p == "/api/admin/konfigurace/nabidka" and self.command == "GET": return self._send(200, b'{"ok": true, "verze": 1}', "application/json")     # sonda tlacitka "Do online nabidky" (js/stul-nabidka.js, bot16 2026-10-06): skutecne API ji da prihlasenemu adminovi (200); jinak by kazdy test s kontrolou konzole hlasil 404
        if p == "/api/admin/konfigurace/karta" and self.command == "GET": return self._send(200, b'{"ok": true, "verze": 1, "muze_aktivovat": true, "kategorie": [], "vychozi_kategorie": {}}', "application/json")     # sonda tlacitka "Vytvorit kartu" (js/stul-karta.js, bot10 2026-10-07): skutecne API ji da prihlasenemu s pravem sklad_karty/vytvorit
        if p.startswith("/api/shop/") or p.startswith("/api/stul/"):
            n = int(self.headers.get("Content-Length") or 0); body = self.rfile.read(n) if n else None
            r = client.open(self.path, method=self.command, data=body, headers={"Content-Type": self.headers.get("Content-Type", "application/json")})
            return self._send(r.status_code, r.get_data(), r.headers.get("Content-Type", "application/json"))
        if p.startswith("/api/"): return self._send(404, b"{}", "application/json")
        f = os.path.normpath(os.path.join(WEB, p.lstrip("/")))
        if f.startswith(WEB) and os.path.isfile(f):
            return self._send(200, open(f, "rb").read(), TYPY.get(os.path.splitext(f)[1], "application/octet-stream"))
        self._send(404, b"nf", "text/plain")
    do_GET = do_POST = _handle


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = "http://127.0.0.1:%d" % srv.server_address[1]
if len(sys.argv) > 1 and sys.argv[1] == "--schema":
    import urllib.request
    print(urllib.request.urlopen(base + "/api/shop/products/%s/configurator?lang=cs" % PID).read().decode()[:6000]); sys.exit(0)
env = dict(os.environ, BASE=base, PID=PID)
sys.exit(subprocess.call(["node", sys.argv[1]], env=env))
