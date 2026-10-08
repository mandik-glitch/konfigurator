#!/usr/bin/env python3
"""Test pravnich stranek hlavniho webu (api/legal_pages.py; bot16 2026-10-05): /ochrana-osobnich-udaju a /obchodni-podminky z miniweb_documents (cs) nad DOCASNOU kopii tabulky (ostra se jen cte
a na konci se porovna checksum). Overuje: schvaleny dokument = 200 s nadpisy a odstavci, draft = 404, HEAD, jen hosty se znackou (hlavni web, www, IP), anonymni host = 404 i u schvaleneho,
escapovani HTML, hlavicky (cache, jazyk), neexistujici dokument = 404, SK/EN dokumenty se na hlavnim webu nezobrazuji.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator \\
  api/venv/bin/python3 scripts/2026-10-05_pravni_stranky_testy/test_pravni_stranky.py"""
import os, sys, threading
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(REPO)
if not os.environ.get("DB_HOST"):
    print("CHYBA: chybi DB_* v prostredi"); sys.exit(2)
_orig = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _orig(self, *a, **k)
sys.path.insert(0, os.path.join(REPO, "api"))
try:
    import pymysql
    import app as appmod
    import legal_pages as LP
    import site_brand
finally:
    threading.Thread.start = _orig
bad = total = 0


def ok(cond, text):
    global bad, total
    total += 1
    bad += 0 if cond else 1
    print("[%s] %s" % ("OK   " if cond else "CHYBA", text))


def ostre():
    c = pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"], charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)
    try:
        with c.cursor() as cur:
            cur.execute("CHECKSUM TABLE miniweb_documents"); return list(cur.fetchone().values())[1]
    finally:
        c.close()


PRED = ostre()
wrap = appmod.get_conn(); real = object.__getattribute__(wrap, "_real")


def sql(q, params=None):
    with real.cursor() as cur:
        cur.execute(q, params or ())
        return cur.fetchall()


sql("CREATE TEMPORARY TABLE `_tpl_miniweb_documents` LIKE `miniweb_documents`"); sql("CREATE TEMPORARY TABLE `miniweb_documents` LIKE `_tpl_miniweb_documents`")
assert list(sql("SHOW CREATE TABLE miniweb_documents")[0].values())[1].startswith("CREATE TEMPORARY TABLE"), "miniweb_documents neni docasna - STOP"
real.commit()
HLAVNI = next(iter(sorted(h for h in site_brand._LOGO_HOSTS if "." in h and not h[0].isdigit() and not h.startswith("www."))))
BODY = "Kdo zpracovává vaše údaje\nSprávcem je LOGIMAN s.r.o., IČO 28337638.\n\nJaké údaje\nJméno, e-mail a telefon <script>alert(1)</script> & \"uvozovky\".\nDruhý řádek odstavce.\n\nPoslední věta bez nadpisu."


def vloz(kind, lang, status, title, body=BODY, family="packstations"):
    sql("REPLACE INTO miniweb_documents (family, kind, lang, title, body, status, approved_at) VALUES (%s,%s,%s,%s,%s,%s,%s)", (family, kind, lang, title, body, status, "2026-10-05 12:00:00" if status == "approved" else None)); real.commit()


def get(cesta, host=HLAVNI, method="GET"):
    c = appmod.app.test_client()
    return getattr(c, method.lower())(cesta, base_url="https://" + host, follow_redirects=False)


vloz("privacy", "cs", "approved", "Ochrana osobních údajů"); vloz("terms", "cs", "draft", "Obchodní podmínky")
r = get("/ochrana-osobnich-udaju"); t = r.get_data(as_text=True)
ok(r.status_code == 200 and r.mimetype == "text/html" and "<h1>Ochrana osobních údajů</h1>" in t, "L1 schválený dokument na hlavním webu (%s): 200 a nadpis stránky" % HLAVNI)
ok("<h2>Kdo zpracovává vaše údaje</h2><p>Správcem je LOGIMAN s.r.o., IČO 28337638.</p>" in t and "<h2>Jaké údaje</h2>" in t, "L2 první řádek bloku je nadpis, zbytek odstavec")
ok("<p>Poslední věta bez nadpisu.</p>" in t, "L3 blok bez nadpisu je jen odstavec")
ok("<script>" not in t and "&lt;script&gt;alert(1)&lt;/script&gt; &amp; &quot;uvozovky&quot;" in t, "L4 HTML z databáze je escapované (žádný <script>)")
ok(r.headers.get("Cache-Control") == "public, max-age=300" and r.headers.get("Content-Language") == "cs", "L5 hlavičky: cache 5 min, jazyk cs")
ok('<link rel="canonical" href="' in t and t.count("/ochrana-osobnich-udaju") >= 1 and 'name="robots" content="index,follow"' in t and "Platné od 5. 10. 2026" in t, "L6 canonical, robots index a datum platnosti (5. 10. 2026)")
h = get("/ochrana-osobnich-udaju", method="HEAD")
ok(h.status_code == 200 and not h.get_data(), "L7 HEAD = 200 bez těla (embed podle toho ukáže odkaz)")
ok(get("/obchodni-podminky").status_code == 404, "L8 draft dokumentu (podmínky) = 404 (objednávka hosta zůstává u dočasného znění souhlasu)")
vloz("terms", "cs", "approved", "Obchodní podmínky")
ok(get("/obchodni-podminky").status_code == 200, "L9 po schválení jsou podmínky 200")
ok(get("/ochrana-osobnich-udaju", host="www." + HLAVNI).status_code == 200 and get("/ochrana-osobnich-udaju", host="75.119.132.164").status_code == 200, "L10 stránka jde i na www a na IP vhostu hlavního webu")
for anon in ("baliace-stoly.top", "packing-tables.top", "neco.example.test"):
    ok(get("/ochrana-osobnich-udaju", host=anon).status_code == 404, "L11 anonymní doména %s: 404 i u schváleného dokumentu (žádný únik značky)" % anon)
vloz("privacy", "cs", "draft", "Ochrana osobních údajů")
ok(get("/ochrana-osobnich-udaju").status_code == 404, "L12 po vrácení do draftu (revize) stránka zmizí = 404")
vloz("privacy", "cs", "approved", "Ochrana osobních údajů", body="   ")
ok(get("/ochrana-osobnich-udaju").status_code == 404, "L13 schválený dokument s prázdným textem = 404")
sql("DELETE FROM miniweb_documents")
vloz("privacy", "sk", "approved", "Ochrana osobných údajov"); vloz("privacy", "en", "approved", "Privacy"); vloz("privacy", "cs", "approved", "Jiná rodina", family="jina")
ok(get("/ochrana-osobnich-udaju").status_code == 404, "L14 dokumenty v jiném jazyce nebo jiné rodině se na hlavním webu nezobrazují")
ok(get("/obchodni-podminky/").status_code in (404, 308, 301), "L15 varianta s lomítkem nespadne (%s)" % get("/obchodni-podminky/").status_code)
PO = ostre()
ok(PO == PRED, "K ostrá tabulka miniweb_documents se testem nezměnila (CHECKSUM stejný)")
print("\n==> %d/%d kontrol OK" % (total - bad, total))
sys.exit(1 if bad else 0)
