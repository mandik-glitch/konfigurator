#!/opt/konfigurator/api/venv/bin/python
"""Panel Prehledy > John: backend GET /api/admin/john/stav (api/john_stav.py) + shoda 3 vrstev RBAC (bot16, 2026-10-06).
Skutecna routa pres Flask test client; kandidat app.py (se sekci `prehledy_john` v PERMISSION_SECTIONS a importem john_stav) se bere z APP_PY, jinak se pouzije zivy, pokud uz sekci obsahuje.
Prihlaseni = podepsana session cookie existujiciho uzivatele (DB se jen CTE, nic se nezapisuje). Kandidatni JS/HTML pro kontrolu vrstev: ADMIN_HTML, ROLE_JS.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \
  /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-06_john_panel_testy/test_john_stav.py"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
API = os.path.join(REPO, "api")
APP_PY = os.environ.get("APP_PY") or os.path.join(API, "app.py")
JOHN_PY = os.environ.get("JOHN_STAV_PY") or os.path.join(API, "john_stav.py")
ADMIN_HTML = os.environ.get("ADMIN_HTML") or os.path.join(REPO, "webapp", "admin.html")
ROLE_JS = os.environ.get("ROLE_JS") or os.path.join(REPO, "webapp", "admin", "js", "uzivatele-role.js")
if "prehledy_john" not in open(APP_PY, encoding="utf-8").read():
    print("CHYBA: app.py nema sekci prehledy_john (zadej kandidata v APP_PY)")
    sys.exit(2)

tmp = tempfile.mkdtemp(prefix="kand_john_")
TAPI = os.path.join(tmp, "api")
os.makedirs(TAPI)
for f in os.listdir(API):
    if f not in ("app.py", "john_stav.py", "__pycache__", "venv"):
        os.symlink(os.path.join(API, f), os.path.join(TAPI, f))
for d in ("webapp", "private-files", "katalog", "scripts", "sql", "docs", "backups"):
    if os.path.exists(os.path.join(REPO, d)):
        os.symlink(os.path.join(REPO, d), os.path.join(tmp, d))
if os.path.exists(os.path.join(REPO, "DEPLOY_LOCK.json")):
    os.symlink(os.path.join(REPO, "DEPLOY_LOCK.json"), os.path.join(tmp, "DEPLOY_LOCK.json"))
shutil.copy(APP_PY, os.path.join(TAPI, "app.py"))
shutil.copy(JOHN_PY, os.path.join(TAPI, "john_stav.py"))
sys.path.insert(0, TAPI)

_orig = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _orig(self, *a, **k)
try:
    import pymysql  # noqa: E402
    import app as appmod  # noqa: E402
    import john_stav as js  # noqa: E402
finally:
    threading.Thread.start = _orig

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:500]))




def klient(uid):
    """test client s prihlasenym uzivatelem (session_transaction = spravny nazev cookie i podpis podle konfigurace appky); uid None = nepřihlášený."""
    c = appmod.app.test_client()
    if uid:
        with c.session_transaction() as sess:
            sess["user_id"] = uid
    return c


def db():
    return pymysql.connect(host=os.environ["DB_HOST"], port=int(os.environ.get("DB_PORT", "3306")), user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
                           database=os.environ["DB_NAME"], charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


def uzivatel(role):
    c = db()
    try:
        with c.cursor() as cur:
            cur.execute("SELECT id FROM app_users WHERE role=%s AND active=1 ORDER BY id LIMIT 1", (role,))
            r = cur.fetchone()
            return r["id"] if r else None
    finally:
        c.close()


def ma_grant(role):
    c = db()
    try:
        with c.cursor() as cur:
            cur.execute("SELECT COUNT(*) n FROM role_permissions WHERE role=%s AND section='prehledy_john' AND allowed=1", (role,))
            return cur.fetchone()["n"] > 0
    finally:
        c.close()


URL = "/api/admin/john/stav"
print("== A) sekce a opravneni")
over("A1 prehledy_john je v PERMISSION_SECTIONS", "prehledy_john" in appmod.PERMISSION_SECTIONS)
r = klient(None).get(URL)
over("A2 bez prihlaseni 401", r.status_code == 401, r.status_code)
admin = uzivatel("admin")
over("A3 existuje aktivni admin (pro test)", bool(admin))
js._cache.update(t=0.0, data=None)
r = klient(admin).get(URL)
j = r.get_json(silent=True) or {}
over("A4 admin: 200 a tvar odpovedi {zkontrolovano, bezi[], selhaly[], chyba}", r.status_code == 200 and set(j) >= {"zkontrolovano", "bezi", "selhaly", "chyba"} and isinstance(j["bezi"], list) and isinstance(j["selhaly"], list), (r.status_code, j))
over("A5 Cache-Control: no-store", "no-store" in (r.headers.get("Cache-Control") or ""), dict(r.headers))
over("A6 zkontrolovano je ISO cas s casovou zonou", bool(re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$", str(j.get("zkontrolovano")))), j.get("zkontrolovano"))
over("A7 jmena jednotek jsou jen john-*.service|scope", all(re.match(r"^john-[A-Za-z0-9_.@:-]+\.(service|scope)$", x["jednotka"]) for x in j.get("bezi", []) + j.get("selhaly", [])), j)
over("A8 odpoved neobsahuje popis ani prikazovou radku jednotky (jen jednotka/od/bezi_s)", all(set(x) <= {"jednotka", "od", "bezi_s"} for x in j.get("bezi", [])) and "codex" not in r.get_data(as_text=True) and "/home/" not in r.get_data(as_text=True))
for role in ("ucetni", "skladnik"):
    uid = uzivatel(role)
    if uid and not ma_grant(role):
        r2 = klient(uid).get(URL)
        over(f"A9 role {role} BEZ granta prehledy_john: 403 (fail-closed)", r2.status_code == 403, r2.status_code)
        break
else:
    print("PRESKOCENO A9: zadna ne-admin role bez granta (nebo zadny aktivni uzivatel)")
user_id = uzivatel("user")
if user_id:
    r3 = klient(user_id).get(URL)
    over("A10 bezny zakaznik (role user): 403", r3.status_code == 403, r3.status_code)

print("== B) zive jednotky")
aktivni = subprocess.run(["systemctl", "is-active", "john-prace-json.service"], capture_output=True, text=True).stdout.strip() == "active"
if aktivni:
    js._cache.update(t=0.0, data=None)
    j2 = klient(admin).get(URL).get_json()
    nasel = [x for x in j2["bezi"] if x["jednotka"] == "john-prace-json.service"]
    over("B1 beziaci john-prace-json.service je v odpovedi s casem startu", len(nasel) == 1 and nasel[0]["od"] and nasel[0]["bezi_s"] is not None and nasel[0]["bezi_s"] >= 0, j2)
else:
    print("PRESKOCENO B1: john-prace-json.service prave neni aktivni (zive porovnani jen kdyz bezi)")
VZOREK = "\n".join([
    "john-prace-json.service loaded active running /home/openai1/.npm-global/bin/codex exec --skip-git-repo-check -m x",
    "john-spoj-40.service loaded failed failed John spoj",
    "john-hotovo.service loaded inactive dead John hotovo",
    "john-start.service loaded activating start Johnstart",
    "john-x; rm -rf.service loaded active running evil",
    "../john-x.service loaded active running evil",
    "john-$(id).service loaded active running evil",
    "john-" + "a" * 200 + ".service loaded active running dlouhe",
    "other-unit.service loaded active running x",
    "john-scope-1.scope loaded active running scope",
    "", "   ", "john-kratky.service loaded",
])
bezi, selhaly = js._parsuj(VZOREK)
over("B2 parser: bezi = jen platna jmena john-* ve stavu active/activating", bezi == ["john-prace-json.service", "john-scope-1.scope", "john-start.service"], bezi)
over("B3 parser: selhala jednotka je v selhaly, neaktivni (dead) ne", selhaly == ["john-spoj-40.service"], selhaly)
over("B4 parser: vstup s mezerou/shell znaky/../ a prilis dlouha jmena se zahodi (nic z toho nejde do podprocesu)", not any(re.search(r"[;$ /]", x) for x in bezi + selhaly) and len(bezi + selhaly) == 4)

print("== C) selhani systemctl a mezipamet")
puvodni = js._run
js._run = lambda *a, **k: None
js._cache.update(t=0.0, data=None)
r4 = klient(admin).get(URL)
j4 = r4.get_json()
over("C1 systemctl nejde spustit: 200, chyba vyplnena, bezi prazdne (panel nespadne)", r4.status_code == 200 and j4["chyba"] and j4["bezi"] == [], (r4.status_code, j4))
js._run = puvodni
volani = {"n": 0}
puv_sestav = js._sestav_stav
js._sestav_stav = lambda: (volani.__setitem__("n", volani["n"] + 1), puv_sestav())[1]
js._cache.update(t=0.0, data=None)
for _ in range(3):
    klient(admin).get(URL)
over("C2 tri rychle dotazy = jedno zjisteni (mezipamet 5 s)", volani["n"] == 1, volani)
js._sestav_stav = puv_sestav

print("== D) tri vrstvy RBAC odkazuji na STEJNOU sekci")
html = open(ADMIN_HTML, encoding="utf-8").read()
over("D1 vrstva admin.html: TAB_SECTION john -> prehledy_john", re.search(r'\bjohn:\s*"prehledy_john"', html) is not None)
over("D2 vrstva admin.html: zalozka john existuje (tlacitko + panel)", 'data-tab="john"' in html and 'id="tab-john"' in html)
role_js = open(ROLE_JS, encoding="utf-8").read()
over("D3 Role a opravneni: popisek i napoveda sekce prehledy_john", len(re.findall(r"\bprehledy_john:\s*\"", role_js)) == 2, len(re.findall(r"\bprehledy_john:\s*\"", role_js)))
over("D4 endpoint chrani prave tuhle sekci (require_permission)", re.search(r'@require_permission\("prehledy_john",\s*"zobrazit"\)', open(JOHN_PY, encoding="utf-8").read()) is not None)

shutil.rmtree(tmp, ignore_errors=True)
print(f"\n==> {sum(vysl)}/{len(vysl)} kontrol OK")
sys.exit(0 if all(vysl) else 1)
