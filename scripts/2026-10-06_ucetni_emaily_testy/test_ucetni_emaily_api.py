#!/opt/konfigurator/api/venv/bin/python
"""Admin > Prodej > E-maily ucetni: backend api/ucetni_emaily.py (bot16, 2026-10-06; Robert: "schvalene doklady automaticky posilat na emaily ucetni ... postav nato tabulku v adminu").
Skutecne routy pres Flask test client a SKUTECNE opravneni (cte se jen DB s uzivateli/pravy), ale ULOZENI nastaveni jde do pametove atrapy (patch `ucetni_emaily.get_conn`, ktera
zna jen 3 ocekavane SQL prikazy - jakykoli jiny test shodi) a audit do zaznamniku (patch `ucetni_emaily.log_audit`): do ostre DB se NIC nezapisuje, nic se neodesila.
Kandidat: APP_PY (app.py se sekci ucetni_emaily + importem modulu), MOD_PY (api/ucetni_emaily.py); bez nich se pouzije zivy strom. Staticke kontroly 3 vrstev RBAC: ADMIN_HTML, ROLE_JS.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \
  /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-06_ucetni_emaily_testy/test_ucetni_emaily_api.py"""
import json
import os
import re
import shutil
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
API = os.path.join(REPO, "api")
APP_PY = os.environ.get("APP_PY") or os.path.join(API, "app.py")
MOD_PY = os.environ.get("MOD_PY") or os.path.join(API, "ucetni_emaily.py")
ADMIN_HTML = os.environ.get("ADMIN_HTML") or os.path.join(REPO, "webapp", "admin.html")
ROLE_JS = os.environ.get("ROLE_JS") or os.path.join(REPO, "webapp", "admin", "js", "uzivatele-role.js")
if "ucetni_emaily" not in open(APP_PY, encoding="utf-8").read():
    print("CHYBA: app.py nema sekci ucetni_emaily (zadej kandidata v APP_PY)")
    sys.exit(2)

tmp = tempfile.mkdtemp(prefix="kand_ucemail_")
TAPI = os.path.join(tmp, "api")
os.makedirs(TAPI)
for f in os.listdir(API):
    if f not in ("app.py", "ucetni_emaily.py", "__pycache__", "venv"):
        os.symlink(os.path.join(API, f), os.path.join(TAPI, f))
for d in ("webapp", "private-files", "katalog", "scripts", "sql", "docs", "backups"):
    if os.path.exists(os.path.join(REPO, d)):
        os.symlink(os.path.join(REPO, d), os.path.join(tmp, d))
if os.path.exists(os.path.join(REPO, "DEPLOY_LOCK.json")):
    os.symlink(os.path.join(REPO, "DEPLOY_LOCK.json"), os.path.join(tmp, "DEPLOY_LOCK.json"))
shutil.copy(APP_PY, os.path.join(TAPI, "app.py"))
shutil.copy(MOD_PY, os.path.join(TAPI, "ucetni_emaily.py"))
sys.path.insert(0, TAPI)

_orig = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _orig(self, *a, **k)
try:
    import app as appmod  # noqa: E402
    import ucetni_emaily as ue  # noqa: E402
    import documents  # noqa: E402
finally:
    threading.Thread.start = _orig

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:600]))


# ---- atrapa uloziste: zna JEN 3 prikazy, ktere modul smi pouzit
class Store:
    def __init__(self):
        self.data = {}
        self.commits = 0


class Cur:
    def __init__(self, st):
        self.st, self.row = st, None

    def execute(self, q, args=()):
        qn = " ".join(q.split())
        if qn == "SELECT setting_value FROM app_settings WHERE setting_key=%s" or qn == "SELECT setting_value FROM app_settings WHERE setting_key=%s FOR UPDATE":
            self.row = {"setting_value": self.st.data[args[0]]} if args[0] in self.st.data else None
        elif qn == "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s, %s) ON DUPLICATE KEY UPDATE setting_key=setting_key":
            self.st.data.setdefault(args[0], args[1])
        elif qn == "UPDATE app_settings SET setting_value=%s WHERE setting_key=%s":
            self.st.data[args[1]] = args[0]
        else:
            raise AssertionError("neocekavany SQL: " + qn)

    def fetchone(self):
        return self.row

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Conn:
    def __init__(self, st):
        self.st = st

    def cursor(self):
        return Cur(self.st)

    def commit(self):
        self.st.commits += 1

    def rollback(self):
        pass

    def close(self):
        pass


STORE = Store()
AUDIT = []
ue.get_conn = lambda: Conn(STORE)
ue.log_audit = lambda *a, **k: AUDIT.append(a)


def klient(uid):
    c = appmod.app.test_client()
    if uid:
        with c.session_transaction() as sess:
            sess["user_id"] = uid
    return c


def sql_real(q, args=()):
    c = appmod.get_conn()
    try:
        with c.cursor() as cur:
            cur.execute(q, args)
            return cur.fetchall()
    finally:
        c.rollback()
        c.close()


def uzivatel(role):
    r = sql_real("SELECT id FROM app_users WHERE role=%s AND COALESCE(active,1)=1 ORDER BY id LIMIT 1", (role,))
    return r[0]["id"] if r else None


GET = "/api/admin/ucetni-emaily"
PUT = "/api/admin/ucetni-emaily/%s"
admin, zakaznik = uzivatel("admin"), uzivatel("user")
A = klient(admin)
audit_pred = sql_real("SELECT COUNT(*) n FROM audit_log WHERE entity_type='ucetni_emaily'")[0]["n"]
KLICE = ["invoice", "proforma_invoice", "payment_tax_document", "credit_note", "delivery_note", "prijaty_doklad"]


def put(kod, body, c=None):
    return (c or A).put(PUT % kod, json=body)


def ulozeno():
    raw = STORE.data.get(ue.KLIC)
    return json.loads(raw) if raw else None


print("== A) opravneni a tvar odpovedi")
over("A1 sekce ucetni_emaily je v PERMISSION_SECTIONS", "ucetni_emaily" in appmod.PERMISSION_SECTIONS)
over("A2 bez prihlaseni: GET 401 i PUT 401", klient(None).get(GET).status_code == 401 and klient(None).put(PUT % "invoice", json={}).status_code == 401)
if zakaznik:
    over("A3 zakaznik (role user): GET 403 i PUT 403", klient(zakaznik).get(GET).status_code == 403 and klient(zakaznik).put(PUT % "invoice", json={"adresy": [], "aktivni": False}).status_code == 403)
for role in ("ucetni", "skladnik", "manager", "remeslnik"):
    uid = uzivatel(role)
    if uid:
        r = klient(uid).get(GET)
        over(f"A4 role {role} bez granta ucetni_emaily: 403 (fail-closed, sekce je nova)", r.status_code == 403, r.status_code)
r = A.get(GET)
j = r.get_json() or {}
over("A5 admin: GET 200, Cache-Control no-store", r.status_code == 200 and "no-store" in (r.headers.get("Cache-Control") or ""), (r.status_code, dict(r.headers)))
over("A6 typy v poradi pro ucetni (faktura prvni), stabilni klice, posledni prijaty_doklad", [t["kod"] for t in j.get("typy", [])] == KLICE, [t["kod"] for t in j.get("typy", [])])
over("A7 vychozi stav: zadne adresy, neaktivni, bez poznamky a casu; odesilani_zapojeno true (od 2026-10-06 hak ucetni_hak zarazuje do fronty ke schvaleni); max_adres 5",
     all(t["adresy"] == [] and t["aktivni"] is False and t["poznamka"] == "" and t["upraveno"] is None and t["upravil"] is None for t in j["typy"]) and j["odesilani_zapojeno"] is True and j["max_adres"] == 5, j)
over("A8 smer: 5 vydanych a 1 prijaty; kazdy typ ma citelny nazev", [t["smer"] for t in j["typy"]] == ["vydany"] * 5 + ["prijaty"] and all(len(t["nazev"]) > 3 for t in j["typy"]), j["typy"][:2])
over("A9 vsechny typy z documents.DOCUMENT_TYPES jsou v tabulce (nic se neztrati)", set(documents.DOCUMENT_TYPES) <= {t["kod"] for t in j["typy"]})
over("A10 GET nic neulozil (atrapa prazdna)", STORE.data == {} and STORE.commits == 0)

print("== B) neplatne PUT: 4xx a NIC se neulozi")
PRIPADY = [
    ("neznamy typ", "neexistuje", {"adresy": [], "aktivni": False}, 404, "typ_neznamy"),
    ("aktivni jako text", "invoice", {"adresy": ["a@b.cz"], "aktivni": "ano"}, 400, "aktivni_neplatne"),
    ("aktivni jako cislo", "invoice", {"adresy": ["a@b.cz"], "aktivni": 1}, 400, "aktivni_neplatne"),
    ("adresa bez zavinace", "invoice", {"adresy": ["abc"], "aktivni": False}, 400, "adresy_neplatne"),
    ("adresa bez tecky v domene", "invoice", {"adresy": ["a@b"], "aktivni": False}, 400, "adresy_neplatne"),
    ("adresa s koncovkou 1 znak", "invoice", {"adresy": ["a@b.c"], "aktivni": False}, 400, "adresy_neplatne"),
    ("adresa ve spicatych zavorkach", "invoice", {"adresy": ["<a@b.cz>"], "aktivni": False}, 400, "adresy_neplatne"),
    ("adresa s uvozovkami", "invoice", {"adresy": ['"x"@b.cz'], "aktivni": False}, 400, "adresy_neplatne"),
    ("injekce hlavicky (novy radek + Bcc)", "invoice", {"adresy": "a@b.cz\r\nBcc: x@y.cz", "aktivni": False}, 400, "adresy_neplatne"),
    ("diakritika v domene", "invoice", {"adresy": ["a@bř.cz"], "aktivni": False}, 400, "adresy_neplatne"),
    ("sest adres (max 5)", "invoice", {"adresy": ["a%d@b.cz" % i for i in range(6)], "aktivni": False}, 400, "adresy_neplatne"),
    ("adresy jako cislo", "invoice", {"adresy": 5, "aktivni": False}, 400, "adresy_neplatne"),
    ("adresy jako seznam s cislem", "invoice", {"adresy": ["a@b.cz", 3], "aktivni": False}, 400, "adresy_neplatne"),
    ("aktivni bez adres", "invoice", {"adresy": [], "aktivni": True}, 400, "aktivni_bez_adres"),
    ("poznamka jako cislo", "invoice", {"adresy": [], "aktivni": False, "poznamka": 5}, 400, "poznamka_neplatna"),
    ("telo neni objekt", "invoice", [1, 2], 400, "telo_neplatne"),
]
for nazev, kod, body, st, err in PRIPADY:
    r = put(kod, body)
    j = r.get_json() or {}
    over(f"B {nazev}: {st} {err} se zpravou", r.status_code == st and j.get("error") == err and bool(j.get("message")), (r.status_code, j))
r = A.put(PUT % "invoice", data="neni json", content_type="application/json")
over("B telo neni JSON: 400 telo_neplatne", r.status_code == 400 and (r.get_json() or {}).get("error") == "telo_neplatne", (r.status_code, r.get_json()))
over("B po vsech chybach se nic neulozilo a nic se neauditovalo", STORE.data == {} and STORE.commits == 0 and AUDIT == [], (STORE.data, AUDIT))

print("== C) uspesne ulozeni: normalizace, izolace typu, prepis")
r = put("invoice", {"adresy": ["Ucetni@Firma.CZ", " b@c.cz ; ucetni@firma.cz\n x@y.cz"], "aktivni": True, "poznamka": "  faktury\tvydané \x07  "})
j = r.get_json() or {}
radek = j.get("radek") or {}
over("C1 200 ok; adresy normalizovane (strip, mala pismena, bez duplicit, oddelovace carka/strednik/mezera/novy radek)", r.status_code == 200 and j.get("ok") is True and radek.get("adresy") == ["ucetni@firma.cz", "b@c.cz", "x@y.cz"], (r.status_code, j))
over("C2 radek: kod, nazev, aktivni, poznamka bez ridicich znaku, cas a jmeno upravujiciho", radek.get("kod") == "invoice" and radek.get("aktivni") is True and radek.get("poznamka") == "faktury vydané" and re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$", radek.get("upraveno") or "") and bool(radek.get("upravil")), radek)
d = ulozeno()
over("C3 v uloziste je JSON v=1 s radkem invoice (a upravil_id = prihlaseny admin)", d and d["v"] == 1 and set(d["radky"]) == {"invoice"} and d["radky"]["invoice"]["upravil_id"] == admin and d["radky"]["invoice"]["adresy"] == ["ucetni@firma.cz", "b@c.cz", "x@y.cz"], d)
over("C4 ulozeno v jedne transakci (commit 1x) a zapsan audit: update / ucetni_emaily, detail s typem, z a na (bez metadat)", STORE.commits == 1 and len(AUDIT) == 1 and AUDIT[0][1:3] == ("update", "ucetni_emaily") and AUDIT[0][4]["typ"] == "invoice" and AUDIT[0][4]["z"] == {} and AUDIT[0][4]["na"]["aktivni"] is True and "upravil" not in AUDIT[0][4]["na"], AUDIT)
r = put("credit_note", {"adresy": ["dobropisy@ucetni.cz"], "aktivni": False, "poznamka": ""})
over("C5 jiny typ: ulozeno i NEaktivni s adresou; prvni typ zustal beze zmeny", r.status_code == 200 and set(ulozeno()["radky"]) == {"invoice", "credit_note"} and ulozeno()["radky"]["invoice"]["adresy"][0] == "ucetni@firma.cz", ulozeno())
r = put("invoice", {"adresy": "jina@ucetni.cz", "aktivni": True, "poznamka": "x" * 500})
over("C6 prepis: adresy nahrazeny (ne pripojeny), poznamka oriznuta na 200 znaku, audit nese puvodni stav", r.get_json()["radek"]["adresy"] == ["jina@ucetni.cz"] and len(r.get_json()["radek"]["poznamka"]) == 200 and AUDIT[-1][4]["z"]["adresy"] == ["ucetni@firma.cz", "b@c.cz", "x@y.cz"], AUDIT[-1])
r = put("prijaty_doklad", {"adresy": ["prijate@ucetni.cz", "druhy@ucetni.cz"], "aktivni": True})
over("C7 prijaty_doklad lze nastavit stejne jako vydane typy", r.status_code == 200 and r.get_json()["radek"]["smer"] == "prijaty", r.get_json())
r = put("delivery_note", {"adresy": [], "aktivni": False})
over("C8 vyprazdneni radku (zadne adresy, neaktivni) je platne = typ se neposila", r.status_code == 200 and r.get_json()["radek"]["adresy"] == [] and r.get_json()["radek"]["aktivni"] is False)
r = put("invoice", {"adresy": ["a@b.cz"]})
over("C9 bez klice aktivni = neaktivni (vychozi je bezpecne vypnuto)", r.status_code == 200 and r.get_json()["radek"]["aktivni"] is False, r.get_json())
put("invoice", {"adresy": ["jina@ucetni.cz"], "aktivni": True})
r = A.get(GET)
t = {x["kod"]: x for x in r.get_json()["typy"]}
over("C10 GET po ulozeni ukazuje ulozene radky a ostatni prazdne", t["invoice"]["adresy"] == ["jina@ucetni.cz"] and t["invoice"]["aktivni"] is True and t["credit_note"]["adresy"] == ["dobropisy@ucetni.cz"] and t["credit_note"]["aktivni"] is False and t["payment_tax_document"]["adresy"] == [], t)
n_audit = len(AUDIT)
put("invoice", {"adresy": ["a@b.cz"], "aktivni": True})
over("C11 kazde uspesne ulozeni = presne 1 audit zaznam", len(AUDIT) == n_audit + 1)

print("== D) prijemci(): jen cteni, fail closed")
cur = Cur(STORE)                  # kurzor nad atrapou (jako v routach)
commits0 = STORE.commits
over("D1 aktivni radek s adresami -> seznam adres", ue.prijemci(cur, "prijaty_doklad") == ["prijate@ucetni.cz", "druhy@ucetni.cz"], ue.prijemci(cur, "prijaty_doklad"))
over("D2 neaktivni radek (i s adresou) -> []", ue.prijemci(cur, "credit_note") == [])
over("D3 prazdny radek -> []", ue.prijemci(cur, "delivery_note") == [])
over("D4 neznamy typ / chybejici radek -> []", ue.prijemci(cur, "neexistuje") == [] and ue.prijemci(cur, "payment_tax_document") == [])
over("D5 prijemci() nic nezapsal (jen cteni: zadny commit)", STORE.commits == commits0)
puvodni = STORE.data[ue.KLIC]
base = json.loads(puvodni)
for nazev, uprav in (("rozbity JSON", lambda: "{neni json"), ("prazdny retezec", lambda: ""), ("radky nejsou objekt", lambda: json.dumps({"v": 1, "radky": []})),
                     ("neplatna adresa rucne zapsana", lambda: json.dumps({"v": 1, "radky": {"invoice": {"adresy": ["spatna adresa"], "aktivni": True}}})),
                     ("sest adres rucne zapsano", lambda: json.dumps({"v": 1, "radky": {"invoice": {"adresy": ["a%d@b.cz" % i for i in range(6)], "aktivni": True}}})),
                     ("aktivni jako text 'true'", lambda: json.dumps({"v": 1, "radky": {"invoice": {"adresy": ["a@b.cz"], "aktivni": "true"}}})),
                     ("adresy jako text misto seznamu s injekci", lambda: json.dumps({"v": 1, "radky": {"invoice": {"adresy": "a@b.cz\nBcc: x@y.cz", "aktivni": True}}}))):
    STORE.data[ue.KLIC] = uprav()
    over(f"D6 poskozene uloziste ({nazev}): prijemci() = [] (nic se neposle) a GET nespadne", ue.prijemci(cur, "invoice") == [] and A.get(GET).status_code == 200)
STORE.data[ue.KLIC] = puvodni
STORE.data[ue.KLIC] = "{rozbity"
r = put("invoice", {"adresy": ["ok@ucetni.cz"], "aktivni": True})
over("D8 PUT nad rozbitym JSON: 200 a uloziste je znovu platne s jednim radkem", r.status_code == 200 and set(ulozeno()["radky"]) == {"invoice"}, (r.status_code, STORE.data[ue.KLIC][:80]))

print("== E) stabilni klice typu")
puvodni_typy = ue.DOCUMENT_TYPES
ue.DOCUMENT_TYPES = tuple(puvodni_typy) + ("novy_typ_dokladu",)
j = A.get(GET).get_json()
over("E1 novy typ pridany do documents.DOCUMENT_TYPES se v tabulce objevi sam (na konci vydanych, pred prijatymi), prazdny", [t["kod"] for t in j["typy"]] == KLICE[:5] + ["novy_typ_dokladu", "prijaty_doklad"] and j["typy"][5]["adresy"] == [], [t["kod"] for t in j["typy"]])
r = put("novy_typ_dokladu", {"adresy": ["novy@ucetni.cz"], "aktivni": True})
over("E2 a lze ho hned nastavit", r.status_code == 200 and ue.prijemci(Cur(STORE), "novy_typ_dokladu") == ["novy@ucetni.cz"], r.get_json())
ue.DOCUMENT_TYPES = puvodni_typy

print("== F) staticke kontroly 3 vrstev opravneni a bezpecnosti")
html = open(ADMIN_HTML, encoding="utf-8").read()
role_js = open(ROLE_JS, encoding="utf-8").read()
zdroj = open(MOD_PY, encoding="utf-8").read()
over("F1 vrstva admin.html: TAB_SECTION accountantemails -> ucetni_emaily", re.search(r'\baccountantemails:\s*"ucetni_emaily"', html) is not None)
over("F2 vrstva admin.html: tlacitko zalozky v menu Prodej a panel", 'data-tab="accountantemails"' in html and 'id="tab-accountantemails"' in html)
over("F3 Role a opravneni: stitek i popis sekce ucetni_emaily", len(re.findall(r"\bucetni_emaily:\s*\"", role_js)) == 2, len(re.findall(r"\bucetni_emaily:\s*\"", role_js)))
over("F4 obe routy chrani sekci ucetni_emaily (GET zobrazit, PUT upravit)", 'require_permission("ucetni_emaily", "zobrazit")' in zdroj and 'require_permission("ucetni_emaily", "upravit")' in zdroj)
over("F5 modul NIC neodesila: zadny SMTP, send_email, send_and_log ani import emails", not re.search(r"smtplib|send_email|send_and_log|system_emails|^\s*import emails|^\s*from emails", zdroj, re.M))
over("F6 ODESILANI_ZAPOJENO je True (zapojil ho ucetni_hak 2026-10-06 21:29, Robertova volba: schvalene doklady do FRONTY ke schvaleni, odeslani az po schvaleni e-mailu - pravidlo 16 beze zmeny)", ue.ODESILANI_ZAPOJENO is True)

audit_po = sql_real("SELECT COUNT(*) n FROM audit_log WHERE entity_type='ucetni_emaily'")[0]["n"]
over("Z do ostre DB se NIC nezapsalo (audit_log ucetni_emaily stejny, app_settings klic neexistuje)", audit_po == audit_pred and not sql_real("SELECT 1 FROM app_settings WHERE setting_key=%s", (ue.KLIC,)), (audit_pred, audit_po))
shutil.rmtree(tmp, ignore_errors=True)
print(f"\n==> {sum(vysl)}/{len(vysl)} kontrol OK")
sys.exit(0 if all(vysl) else 1)
