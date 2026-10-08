#!/usr/bin/env python3
"""Most MINI-SHOP (bot16, 2026-10-04): SKUTECNY front-end mini-shopu (webapp/miniweb/*.html) nad SKUTECNYM verejnym API (/api/miniweb/*, /api/shop/*) a skutecnymi daty
(jen cteni), s DOCASNYMI kopiemi tabulek miniweb_* na jednom spojeni. Kdyz je APPROVE=1 (vychozi), texty ve stavu draft se v KOPII oznaci jako approved = obchod tak, jak bude
po schvaleni Robertem, bez zasahu do provozu (ostre tabulky se jen ctou druhym spojenim a na konci se porovna jejich CHECKSUM).
Server je JEDNOVLAKNOVY a bezi v hlavnim vlakne: docasne tabulky patri spojeni vlakna (get_conn() je per-thread), dalsi vlakno by otevrelo ostre spojeni; pred kazdym API dotazem se
kontroluje, ze miniweb_* jsou stale docasne (kdyby ne, most se zastavi). Host pro API je MINIWEB_HOST (vychozi baliace-stoly.top = SK shop).
Staticke soubory jdou z webapp/ (nebo WEB_OVERRIDE). Spusteni:
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator \\
    api/venv/bin/python3 scripts/2026-10-02_miniweb_frontend_testy/bridge_miniweb.py <test.js>
Skript dostane BASE (adresa mostu); stranky se otviraji bez ?demo (konfigurace shopu jde z /api/miniweb/config podle hostu)."""
import json, os, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(REPO)
if not os.environ.get("DB_HOST"):
    print("CHYBA: chybi DB_* v prostredi (viz hlavicka)"); sys.exit(2)
if len(sys.argv) < 2:
    print("pouziti: bridge_miniweb.py <test.js>"); sys.exit(2)
_orig = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _orig(self, *a, **k)
sys.path.insert(0, os.path.join(REPO, "api"))
try:
    import pymysql
    import app as appmod
    import miniweb  # noqa: F401
    try:
        import stul_ulozeni as ULOZ        # ulozena konfigurace (bot16 2026-10-05)
        import ulozeni_testovaci as UT
    except ImportError:
        ULOZ = UT = None
finally:
    threading.Thread.start = _orig

import miniweb_cena
import miniweb_seo as _MS                      # cache server-side HTML (vymazat po zmene schvaleni v testu)
miniweb_cena._cache["EUR"] = (time.time() + 10_000_000, float(os.environ.get("EUR_RATE", "25.0")))       # pevny kurz Kc/EUR (shop ma eur_rate NULL = zivy kurz Fio; test nesmi zaviset na siti)
HOST = os.environ.get("MINIWEB_HOST", "baliace-stoly.top")
TABULKY = ("miniweb_categories", "miniweb_category_texts", "miniweb_products", "miniweb_product_texts", "miniweb_inquiries", "miniweb_inquiry_items", "crm_leads", "crm_lead_messages")
WEB = os.path.abspath(os.environ.get("WEB_OVERRIDE") or os.path.join(REPO, "webapp"))
TYPY = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg",
        ".glb": "model/gltf-binary", ".hdr": "application/octet-stream", ".webp": "image/webp"}


def ostre():                                     # druhe spojeni = skutecne tabulky
    c = pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"], charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)
    try:
        with c.cursor() as cur:
            out = {}
            for t in TABULKY:
                cur.execute(f"CHECKSUM TABLE `{t}`"); out[t] = list(cur.fetchone().values())[1]
            return out
    finally:
        c.close()


PRED = ostre()
wrap = appmod.get_conn(); real = object.__getattribute__(wrap, "_real")


def sql(q):
    with real.cursor() as cur:
        cur.execute(q)
        return cur.fetchall()


def docasne():
    return all(list(sql(f"SHOW CREATE TABLE `{t}`")[0].values())[1].startswith("CREATE TEMPORARY TABLE") for t in TABULKY)


for t in TABULKY:                                # docasne kopie na TOMTO spojeni (stejny nazev stinuje ostrou tabulku)
    sql(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`"); sql(f"INSERT INTO `_tpl_{t}` SELECT * FROM `{t}`")
    sql(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`"); sql(f"INSERT INTO `{t}` SELECT * FROM `_tpl_{t}`")
if ULOZ:                                          # ulozena konfigurace: docasna tabulka podle DDL modulu + podstrcene registry; crm_leads a crm_lead_messages jsou uz v TABULKY
    sql(ULOZ.DDL.replace("CREATE TABLE IF NOT EXISTS", "CREATE TEMPORARY TABLE", 1)); UT.instal(ULOZ)
assert docasne(), "miniweb_* nejsou docasne - STOP"
if os.environ.get("APPROVE", "1") == "1":
    sql("UPDATE miniweb_category_texts SET status='approved' WHERE status='draft'")
    sql("UPDATE miniweb_product_texts SET status='approved' WHERE status='draft'")
real.commit()
client = appmod.app.test_client()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, body, ctype, extra=()):
        extra = list(extra); keys = [k.lower() for k, _ in extra]
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
        if "cache-control" not in keys: self.send_header("Cache-Control", "no-store")
        for k, v in extra: self.send_header(k, v)
        try:
            self.end_headers(); self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):       # prohlizec prerusil pozadavek (zavreni stranky / zruseny preload) - bez vypisu
            pass

    def _handle(self):
        p = urlparse(self.path).path
        if ULOZ and p in ("/__bridge/registry", "/__bridge/ulozeni"):
            code, obj = UT.rizeni(p, parse_qs(urlparse(self.path).query), lambda q: sql(q))
            return self._send(code, json.dumps(obj, default=str, ensure_ascii=False).encode(), "application/json")
        if p == "/__bridge/approve":                                      # ?products=1,2 : v DOCASNE kopii jsou verejne jen texty techto produktu (a jejich kategorie + korenova 1); ostatni zpet na draft
            q = parse_qs(urlparse(self.path).query)
            ids = [int(x) for x in ((q.get("products") or [""])[0]).split(",") if x.strip().isdigit()] or [0]
            seznam = ",".join(str(i) for i in ids)
            sql(f"UPDATE miniweb_product_texts SET status = IF(miniweb_product_id IN ({seznam}), 'approved', 'draft')")
            sql(f"UPDATE miniweb_category_texts SET status = IF(miniweb_category_id = 1 OR miniweb_category_id IN (SELECT category_id FROM miniweb_products WHERE id IN ({seznam})), 'approved', 'draft')")
            real.commit(); _MS._CACHE.clear()
            return self._send(200, json.dumps({"products": ids}).encode(), "application/json")
        if p == "/api/auth/me": return self._send(401, b'{"error":"unauthorized"}', "application/json")
        if p.startswith("/api/"):
            if not docasne():
                print("STOP: miniweb_* uz nejsou docasne"); os._exit(3)
            n = int(self.headers.get("Content-Length") or 0); body = self.rfile.read(n) if n else None
            r = client.open(self.path, method=self.command, data=body, base_url="https://" + HOST,
                            headers={"Content-Type": self.headers.get("Content-Type", "application/json"), "Accept-Encoding": self.headers.get("Accept-Encoding", "")})
            ex = [(k, r.headers[k]) for k in ("Cache-Control", "Content-Encoding", "Vary") if r.headers.get(k)]
            return self._send(r.status_code, r.get_data(), r.headers.get("Content-Type", "application/json"), ex)
        f = os.path.normpath(os.path.join(WEB, p.lstrip("/")))
        if f.startswith(WEB) and os.path.isfile(f):
            return self._send(200, open(f, "rb").read(), TYPY.get(os.path.splitext(f)[1], "application/octet-stream"))
        self._send(404, b"nf", "text/plain")
    do_GET = do_POST = _handle


srv = HTTPServer(("127.0.0.1", 0), H)           # jednovlaknovy, v hlavnim vlakne (vlakno s docasnymi tabulkami)
base = "http://127.0.0.1:%d" % srv.server_address[1]
proc = subprocess.Popen(["node", sys.argv[1]], env=dict(os.environ, BASE=base, HOST=HOST))
threading.Thread(target=lambda: (proc.wait(), srv.shutdown()), daemon=True).start()
srv.serve_forever()
code = proc.returncode
PO = ostre()
zmena = [t for t in TABULKY if PO[t] != PRED[t]]
print("KONTROLA OSTRYCH TABULEK mini-shopu:", "ZMENA! %s" % zmena if zmena else "beze zmeny (nic se nezapsalo)")
sys.exit(code or (5 if zmena else 0))
