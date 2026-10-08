#!/opt/konfigurator/api/venv/bin/python
"""Test backendu "zakreslene zmeny v online nabidce" (api/offer_markup_requests.py; bot16, 2026-10-07; Robert: "zakreslovani zmen komplet je na webu hotove, jen to prenest
do online nabidky a to i pro stoly z generatoru").

Flask test client nad kandidatem; do OSTRE DB se NEZAPISUJE ani nic neodesila:
  * VSECHNY dotcene tabulky jsou ZASTINENE docasnymi (DDL ze SHOW CREATE TABLE bez cizich klicu) v jednom vyhrazenem spojeni; `get_conn` je ve vsech modulech nahrazen
    funkci, ktera vraci prave tohle spojeni (bez automatickeho znovupripojeni - kdyby spadlo, test skonci, misto aby psal do ostre DB),
  * kazdy SQL dotaz se pred spustenim kontroluje: sahne-li na tabulku, ktera NENI zastinena, test spadne driv, nez se dotaz provede (viz memory "Testy: zastinit VSECHNY tabulky"),
  * soubory (Drive priloha, galerie) jdou do docasneho adresare; na konci se porovna stav zivych radku i zivych adresaru pred/po,
  * e-maily jen jako radky fronty v docasne tabulce (send_email se v testu nesmi zavolat).
Overuje: priznak `markup_requests` ve verejne odpovedi (vlastnost nabidky, i u admin tokenu), uspech (CRM poptavka + zprava + prilohy na disku + galerie + poznamka u nabidky +
2 e-maily do fronty), honeypot, validace (e-mail/telefon/popis/pohledy/znacky/composite), admin token 403, nepodporovana nabidka 400, 404 (neexistuje/expirovana/neaktivni),
rate limit 429, rollback + uklid souboru pri chybe, stranku Vandr vykresu (page_key drawings_vandr) v Dotazu / statistikach / znackach a INTEGRACI S PROHLIZECEM: skutecny surovy
multipart POST odeslany online nabidkou z prohlizece (fixture_post_z_prohlizece.bin + .ct: stejny boundary, poradi poli i bajty obrazku) se posle test klientem na endpoint pro nabidku
z Vandr karty a musi projit stejne jako ostatni uspesne pripady (viz sekce J; kdyz ji backend odmitne, v hlaseni je presna odpoved vcetne pole `field`).

Spusteni (z korene repa nebo z izolovane kopie HEAD):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=<REPO> \
    /opt/konfigurator/api/venv/bin/python3 <REPO>/scripts/2026-10-07_nabidka_zakresleni_testy/test_offer_markup_requests.py
Kandidat modulu / mutace: OMR_PY=/cesta/offer_markup_requests.py, SO_PY=/cesta/scene_offers.py (viz mutace.py)."""
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
API = os.path.join(REPO, "api")
TMP = tempfile.mkdtemp(prefix="omr_test_")
os.environ["PRIVATE_FILES_DIR"] = os.path.join(TMP, "private")
os.environ["CONTENT_UPLOAD_DIR"] = os.path.join(TMP, "content")
for d in (os.environ["PRIVATE_FILES_DIR"], os.environ["CONTENT_UPLOAD_DIR"]):
    os.makedirs(d, exist_ok=True)

# kandidat modulu DRIV nez se importuje app (app.py importuje uz nasazeny modul, z cache sys.modules by pak vyhral on)
KANDIDAT = os.environ.get("OMR_PY")
sys.path.insert(0, API)
KANDIDAT_SO = os.environ.get("SO_PY")
if KANDIDAT or KANDIDAT_SO:
    kdir = os.path.join(TMP, "kandidat")
    os.makedirs(kdir)
    if KANDIDAT:
        shutil.copy(KANDIDAT, os.path.join(kdir, "offer_markup_requests.py"))
    if KANDIDAT_SO:
        shutil.copy(KANDIDAT_SO, os.path.join(kdir, "scene_offers.py"))
    sys.path.insert(0, kdir)

vysl = []
CERVENE = []          # nazvy selhanych kontrol


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    if not podminka:
        CERVENE.append(nazev)
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:600]))


import pymysql  # noqa: E402
from PIL import Image  # noqa: E402

import app as A  # noqa: E402
import crm  # noqa: E402,F401
import drive  # noqa: E402
import gallery_items  # noqa: E402
import offer_markup_requests as OMR  # noqa: E402
import product_markups as PM  # noqa: E402
import scene_offers as SO  # noqa: E402

# ---------------------------------------------------------------- spojeni: ostre (jen cteni) a vyhrazene s docasnymi tabulkami
SPOJENI = dict(host=A.DB_HOST, port=A.DB_PORT, user=A.DB_USER, password=A.DB_PASSWORD, database=A.DB_NAME, charset="utf8mb4", connect_timeout=10, read_timeout=60, write_timeout=60)
R = pymysql.connect(cursorclass=pymysql.cursors.DictCursor, **SPOJENI)          # OSTRE, jen SELECT/SHOW
rc = R.cursor()
SHADOW = set()
_TAB_RE = re.compile(r"(?<!FOR )(?<!KEY )\b(?:FROM|JOIN|INTO|UPDATE|TABLE)\s+`?([A-Za-z_][A-Za-z0-9_]*)`?", re.I)


class GuardCursor(pymysql.cursors.DictCursor):
    """Kazdy dotaz se pred spustenim zkontroluje: jen zastinene (docasne) tabulky, nic jineho (ani cteni) - jinak AssertionError PRED provedenim."""
    LOG = []

    def execute(self, query, args=None):
        q = query.decode("utf-8", "replace") if isinstance(query, (bytes, bytearray)) else query
        cizi = [t for t in _TAB_RE.findall(q) if t.lower() not in SHADOW]
        if cizi:
            raise AssertionError(f"dotaz sahl na NEZASTINENOU tabulku {cizi}: {q[:200]}")
        GuardCursor.LOG.append(q)
        return super().execute(query, args)


T = pymysql.connect(cursorclass=GuardCursor, **SPOJENI)                           # vyhrazene spojeni s docasnymi tabulkami (testovaci "get_conn")
tc = T.cursor()


def ddl_docasna(tabulka):
    rc.execute("SHOW CREATE TABLE `" + tabulka + "`")
    ddl = rc.fetchone()["Create Table"]
    ddl = ddl.decode("utf-8") if isinstance(ddl, (bytes, bytearray)) else ddl
    radky = [l for l in ddl.split("\n") if not l.strip().startswith(("CONSTRAINT", "FULLTEXT"))]
    text = re.sub(r",\s*\n\)", "\n)", "\n".join(radky))
    return text.replace("CREATE TABLE", "CREATE TEMPORARY TABLE", 1)


TABULKY = ("scene_offers", "scene_offer_notes", "scene_offer_acceptances", "scene_offer_declines", "scene_offer_order_prefs", "scene_offer_markups", "scene_offer_renders",
           "crm_leads", "crm_lead_messages", "crm_lead_folder_sequence", "crm_quotes", "shared_drive_folders", "shared_drive_files",
           "content_gallery_items", "system_emails", "shop_customers", "app_settings", "scene_offer_views", "scene_offer_page_events")
DDL = {t: ddl_docasna(t) for t in TABULKY}
R.rollback()
_ddl_c = T.cursor(pymysql.cursors.DictCursor)           # jen DDL docasnych tabulek (bez strazce; vsechno dalsi jde pres hlidany `tc`)
for t in TABULKY:
    _ddl_c.execute("DROP TEMPORARY TABLE IF EXISTS `" + t + "`")
    _ddl_c.execute(DDL[t])
    SHADOW.add(t)
T.commit()

# pojistka: docasna tabulka opravdu zastinuje ostrou (znackovy radek vlozeny do T nesmi byt videt v ostre DB)
tc.execute("INSERT INTO crm_leads (contact_email, subject, source) VALUES ('__omr_znacka__@example.invalid', 'znacka', 'offer_markup')")
T.commit()
rc.execute("SELECT COUNT(*) c FROM crm_leads WHERE contact_email='__omr_znacka__@example.invalid'")
if rc.fetchone()["c"] != 0:
    print("STOP: docasna tabulka crm_leads nezastinuje ostrou - nic se nespousti")
    sys.exit(3)
tc.execute("DELETE FROM crm_leads WHERE contact_email='__omr_znacka__@example.invalid'")
T.commit()
R.rollback()


class _Konn:
    """Nahrada _PooledConn: close() = rollback, jinak primo vyhrazene spojeni T (zadne znovupripojeni na ostrou DB)."""
    __slots__ = ()

    def close(self):
        T.rollback()

    def __getattr__(self, n):
        return getattr(T, n)


def _testovaci_get_conn():
    return _Konn()


_puvodni = A.get_conn
for _n, _m in list(sys.modules.items()):
    if _m is not None and getattr(_m, "get_conn", None) is _puvodni:
        _m.get_conn = _testovaci_get_conn
A._pooled_conn_local.conn = T

# soubory do docasnych adresaru
DRIVE_DIR = os.path.join(TMP, "drive")
GAL_DIR = os.path.join(TMP, "galerie")
os.makedirs(DRIVE_DIR)
os.makedirs(GAL_DIR)
drive.DRIVE_FILES_DIR = DRIVE_DIR
gallery_items.GALLERY_ITEMS_DIR = GAL_DIR

# e-mail se v testu NIKDY nesmi odeslat primo (pravidlo 16) - jen radek fronty
ODESLANO = []


def _zakazane_odeslani(*a, **k):
    ODESLANO.append((a, k))
    raise AssertionError("send_email se nesmi volat")


for _m in list(sys.modules.values()):
    if _m is not None and getattr(_m, "send_email", None) is not None and getattr(_m, "__name__", "").split(".")[0] in ("app", "scene_offers", "offer_markup_requests", "quotes", "crm"):
        _m.send_email = _zakazane_odeslani

# DNS (dig) se v testu nepouziva: domena "nemamailserver.invalid" nema MX, vse ostatni ano
PM._domena_ma_mailserver = lambda domena, timeout=2.0: domena != "nemamailserver.invalid"

# ---------------------------------------------------------------- data
SIRKA, VYSKA = 640, 360


def jpeg(barva=(250, 250, 250), w=SIRKA, h=VYSKA):
    b = io.BytesIO()
    Image.new("RGB", (w, h), barva).save(b, "JPEG", quality=80)
    return b.getvalue()


def png(w=SIRKA, h=VYSKA):
    b = io.BytesIO()
    Image.new("RGB", (w, h), (240, 240, 255)).save(b, "PNG")
    return b.getvalue()


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


TOK = {  # token -> (id nabidky)
    "conf-klient": 1, "conf-admin": 1, "vandr-klient": 2, "scena-klient": 3, "expir-klient": 4, "neaktivni-klient": 5, "test-klient": 6,
}
CONF = {"source": "configurator", "configuration": {"kod": "STL-TEST", "summary": [{"label": "Šířka desky", "value": "1280 mm"}], "bom": [{"nazev": "profil 30×30", "mnozstvi": 4, "rozmer": "800 mm"}]}}


def vloz_nabidku(id_, cislo, opts, jmeno, email, klient_token, admin_token=None, expires="2099-01-01 00:00:00", aktivni=1):
    tc.execute(
        "INSERT INTO scene_offers (id, offer_number, items, total_price, view_narys, view_3d_a, view_3d_b, editable_text_popis, editable_text_patka, customer_name, customer_email, "
        "view_token_hash, admin_view_token_hash, expires_at, is_active, offer_options) VALUES (%s,%s,'[]',1000,'a.png','b.jpg','c.jpg','popis','patka',%s,%s,%s,%s,%s,%s,%s)",
        (id_, cislo, jmeno, email, sha(klient_token), sha(admin_token) if admin_token else None, expires, aktivni, json.dumps(opts)))


vloz_nabidku(1, "Logiman9001", CONF, "Jan Zákazník", "jan@example.com", "conf-klient", "conf-admin")
vloz_nabidku(2, "Logiman9002", {"vandr_single_drawing": True, "vandr_drawings": [{"slot": "narys", "label": "Levá strana"}]}, None, None, "vandr-klient")
vloz_nabidku(3, "Logiman9003", {"is_vehicle_assembly": False}, "Scéna Zákazník", None, "scena-klient")
vloz_nabidku(4, "Logiman9004", CONF, "Expirovaný", None, "expir-klient", expires="2020-01-01 00:00:00")
vloz_nabidku(5, "Logiman9005", CONF, "Neaktivní", None, "neaktivni-klient", aktivni=0)
vloz_nabidku(6, "TEST", CONF, "Testovací", None, "test-klient")
tc.execute("INSERT INTO shared_drive_folders (id, parent_folder_id, name, created_by) VALUES (1, NULL, %s, NULL)", (crm.LEAD_DRIVE_ROOT_FOLDER_NAME,))
tc.execute("INSERT INTO crm_lead_folder_sequence (id, next_number) VALUES (1, 1000)")
T.commit()

klient = A.app.test_client()
_ip_citac = [0]

# Zaznam SUROVEHO tela pozadavku tak, jak ho dostane aplikace (WSGI): sekce J takhle dokazuje, ze se fixture z prohlizece poslala bajt po bajtu (stejny Content-Type i delka).
# Zapnuto jen behem sekce J (jinak se nic nemeni); telo se precte a vrati aplikaci beze zmeny.
VIDENE = {"aktivni": False}
_puvodni_wsgi = A.app.wsgi_app


def _wsgi_zaznam(environ, start_response):
    if VIDENE["aktivni"] and environ.get("PATH_INFO", "").endswith("/markup-requests"):
        telo = environ["wsgi.input"].read(int(environ.get("CONTENT_LENGTH") or 0))
        VIDENE.update(sha=hashlib.sha256(telo).hexdigest(), delka=len(telo), ct=environ.get("CONTENT_TYPE"), cl=environ.get("CONTENT_LENGTH"), metoda=environ.get("REQUEST_METHOD"))
        environ["wsgi.input"] = io.BytesIO(telo)
    return _puvodni_wsgi(environ, start_response)


A.app.wsgi_app = _wsgi_zaznam


def post(token, form=None, soubory=None, ip=None, limit=False):
    """POST na endpoint; bez limit=True se pred volanim vycisti pamet rate limitu (jinak by zaplnil limit 3/h na token a 8/h na IP)."""
    if not limit:
        A._rate_limit_buckets.clear()
    if ip is None:
        _ip_citac[0] += 1
        ip = f"10.7.{_ip_citac[0] // 250}.{_ip_citac[0] % 250 + 1}"
    data = dict(form or {})
    for nazev, (obsah, jmeno, mime) in (soubory or {}).items():
        data[nazev] = (io.BytesIO(obsah), jmeno, mime)
    return klient.post(f"/api/public/offers/{token}/markup-requests", data=data, content_type="multipart/form-data", headers={"X-Real-IP": ip})


MARKA = {"kind": "ellipse", "color": "#ff3a3a", "width": 0.006, "points": [{"x": 0.2, "y": 0.3}, {"x": 0.4, "y": 0.5}]}


def pohled(**zmeny):
    p = {"label": "Nárys", "page": "drawings_vandr", "view": {"kind": "drawing", "key": "narys"}, "marks": [MARKA], "image_w": SIRKA, "image_h": VYSKA}
    p.update(zmeny)
    return p


def form(pohledy=None, **zmeny):
    f = {"email": "Zakaznik@Example.com", "phone": "+420 603 111 222", "note": "Prosím posunout spodní polici o 5 cm výš a přidat druhý šuplík.", "website": "",
         "views": json.dumps(pohledy if pohledy is not None else [pohled()])}
    f.update(zmeny)
    return f


def soub(n=1, obsah=None, jmeno="pripominka-{}.jpg", mime="image/jpeg"):
    return {f"composite_{i}": (obsah if obsah is not None else jpeg((250 - i * 20, 250, 250)), jmeno.format(i + 1), mime) for i in range(n)}


def pocty():
    out = {}
    for t in ("crm_leads", "crm_lead_messages", "scene_offer_notes", "system_emails", "shared_drive_files", "shared_drive_folders", "content_gallery_items"):
        tc.execute("SELECT COUNT(*) c FROM `" + t + "`")
        out[t] = tc.fetchone()["c"]
    out["soubory_drive"] = sum(len(f) for _, _, f in os.walk(DRIVE_DIR))
    out["soubory_galerie"] = sum(len(f) for _, _, f in os.walk(GAL_DIR))
    T.rollback()
    return out


def radky(sql, args=None):
    tc.execute(sql, args)
    out = tc.fetchall()
    T.rollback()
    return out


ZIVE_TAB = ("crm_leads", "crm_lead_messages", "scene_offer_notes", "system_emails", "content_gallery_items", "shared_drive_files", "shared_drive_folders", "scene_offers",
            "scene_offer_views", "scene_offer_page_events", "scene_offer_markups")


def zive_stav():
    out = {}
    for t in ZIVE_TAB:
        R.rollback()
        rc.execute("SELECT COUNT(*) c, COALESCE(MAX(" + ("offer_id" if t == "scene_offer_markups" else "id") + "),0) m FROM `" + t + "`")
        r = rc.fetchone()
        out[t] = (r["c"], r["m"])
    R.rollback()
    rc.execute("SELECT next_number FROM crm_lead_folder_sequence WHERE id=1")
    s = rc.fetchone()
    out["crm_lead_folder_sequence"] = s["next_number"] if s else None
    R.rollback()
    LIVE_PRIV = "/opt/konfigurator/private-files/shared-drive"
    LIVE_GAL = "/opt/konfigurator/webapp/content-files/gallery-items"
    out["zive_soubory_drive"] = len(os.listdir(LIVE_PRIV)) if os.path.isdir(LIVE_PRIV) else None
    out["zive_soubory_galerie"] = len(os.listdir(LIVE_GAL)) if os.path.isdir(LIVE_GAL) else None
    return out


ZIVE_PRED = zive_stav()

# ================================================================ A) pojistky testu
print("== A) pojistky testu")
over("A0 kandidat modulu je nacteny odtud, odkud ma byt (OMR_PY / api)", (OMR.__file__.startswith(os.path.join(TMP, "kandidat")) if KANDIDAT else OMR.__file__.startswith(API)), OMR.__file__)
over("A0b kandidat scene_offers je nacteny odtud, odkud ma byt (SO_PY / api)", (SO.__file__.startswith(os.path.join(TMP, "kandidat")) if KANDIDAT_SO else SO.__file__.startswith(API)), SO.__file__)
over("A1 soubory Drive a galerie jdou do docasneho adresare (ne do ostrych)", drive.DRIVE_FILES_DIR == DRIVE_DIR and gallery_items.GALLERY_ITEMS_DIR == GAL_DIR)
try:
    tc.execute("SELECT * FROM shop_products LIMIT 1")
    straz = False
except AssertionError:
    straz = True
T.rollback()
over("A2 straz zachyti dotaz na nezastinenou (ostrou) tabulku jeste pred spustenim", straz)
over("A3 get_conn je ve vsech modulech nahrazen (scene_offers, offer_markup_requests, quotes, crm)", all(getattr(m, "get_conn", None) is _testovaci_get_conn for m in (SO, OMR, A)))
import system_emails as SE  # noqa: E402
over("A4 druh e-mailu scene_offer_markup ma cesky stitek v adminu (Systemove e-maily)", bool(SE.SYSTEM_EMAIL_KIND_LABELS.get("scene_offer_markup")), SE.SYSTEM_EMAIL_KIND_LABELS.get("scene_offer_markup"))

# ================================================================ B) priznak ve verejne odpovedi
print("== B) priznak markup_requests ve verejne odpovedi nabidky")
for token, ocek, popis in (("conf-klient", True, "nabidka z konfigurace stolu, klientsky token"), ("conf-admin", True, "nabidka z konfigurace stolu, ADMIN token (vlastnost nabidky, ne role)"),
                           ("vandr-klient", True, "nabidka z Vandr karty"), ("scena-klient", False, "nabidka ze sceny (1. vetev)")):
    r = klient.get(f"/api/public/offers/{token}")
    d = r.get_json(silent=True) or {}
    over(f"B {popis}: markup_requests == {ocek} (HTTP {r.status_code})", r.status_code == 200 and d.get("markup_requests") is ocek, (r.status_code, d.get("markup_requests"), d.get("error")))
d_admin = (klient.get("/api/public/offers/conf-admin").get_json(silent=True) or {})
d_klient = (klient.get("/api/public/offers/conf-klient").get_json(silent=True) or {})
over("B viewer_role se u priznaku nemeni: admin token = 'admin', klient = 'client'", d_admin.get("viewer_role") == "admin" and d_klient.get("viewer_role") == "client", (d_admin.get("viewer_role"), d_klient.get("viewer_role")))

# ================================================================ C) uspech
print("== C) uspech: CRM poptavka + prilohy + galerie + poznamka + 2 e-maily do fronty")
pred = pocty()
f = form([pohled(label="Nárys"), pohled(label="3D pohled", view={"kind": "3d", "key": "v3d", "camera": {"position": [1, 2, 3], "target": [0, 0, 0], "fov": 40}}, page="view_3d")])
r = post("conf-klient", f, soub(2), ip="10.9.9.9")
d = r.get_json(silent=True) or {}
over("C1 201 {status: ok, views: 2}", r.status_code == 201 and d == {"status": "ok", "views": 2}, (r.status_code, d))
po = pocty()
over("C2 pribyl presne 1 lead, 1 zprava, 2 prilohy, 2 polozky galerie, 1 poznamka, 2 e-maily", {k: po[k] - pred[k] for k in ("crm_leads", "crm_lead_messages", "shared_drive_files", "content_gallery_items", "scene_offer_notes", "system_emails")}
     == {"crm_leads": 1, "crm_lead_messages": 1, "shared_drive_files": 2, "content_gallery_items": 2, "scene_offer_notes": 1, "system_emails": 2}, {k: po[k] - pred[k] for k in po})
lead = (radky("SELECT * FROM crm_leads ORDER BY id DESC LIMIT 1") or [{}])[0]
over("C3 lead: zdroj offer_markup, predmet s cislem nabidky, e-mail malymi pismeny, telefon, jmeno z nabidky, nepřečteno adminem",
     lead.get("source") == "offer_markup" and lead.get("subject") == "Zakreslená změna k nabídce Logiman9001" and lead.get("contact_email") == "zakaznik@example.com"
     and lead.get("contact_phone") == "+420 603 111 222" and lead.get("contact_name") == "Jan Zákazník" and lead.get("unread_by_admin") == 1, lead)
over("C3b lead ma Drive slozku poptavky (vanRM-1000-...) a cislo slozky z sekvence", bool(lead.get("drive_folder_id")) and lead.get("drive_folder_number") == 1000, (lead.get("drive_folder_id"), lead.get("drive_folder_number")))
zpr = (radky("SELECT * FROM crm_lead_messages WHERE lead_id=%s", (lead.get("id"),)) or [{}])[0]
over("C4 zprava poptavky: poznamka, cislo nabidky, odkaz na administraci, seznam pohledu s popisky",
     zpr.get("sender_type") == "contact" and "posunout spodní polici" in (zpr.get("body") or "") and "Logiman9001" in zpr["body"] and "/admin.html#onlineoffers" in zpr["body"]
     and "Přiložené pohledy (2)" in zpr["body"] and "Pohled 1: Nárys (výkres)" in zpr["body"] and "Pohled 2: 3D pohled (3D pohled)" in zpr["body"], zpr.get("body"))
soubory = radky("SELECT f.*, d.name AS slozka FROM shared_drive_files f LEFT JOIN shared_drive_folders d ON d.id=f.folder_id WHERE f.folder_id=%s ORDER BY f.id", (lead.get("drive_folder_id"),))
over("C5 prilohy ve slozce poptavky: 2 souboru image/jpeg, nazvy zakreslena-zmena-N.jpg, slozka vanRM-1000-Jan Zákazník", len(soubory) == 2 and all(s["content_type"] == "image/jpeg" for s in soubory)
     and [s["filename"] for s in soubory] == ["zakreslena-zmena-1.jpg", "zakreslena-zmena-2.jpg"] and soubory[0]["slozka"] == "vanRM-1000-Jan Zákazník", soubory)
ok_soubory = True
for s in soubory:
    cesta = os.path.join(DRIVE_DIR, s["stored_filename"])
    try:
        im = Image.open(cesta)
        im.load()
        ok_soubory = ok_soubory and im.format == "JPEG" and im.size == (SIRKA, VYSKA) and os.path.getsize(cesta) == s["size_bytes"]
    except Exception as e:  # noqa: BLE001
        ok_soubory = False
over("C6 soubory prilohy jsou na disku, platne JPEG 640x360 a velikost sedi s radkem", ok_soubory)
gal = radky("SELECT * FROM content_gallery_items WHERE owner_type='lead' AND owner_id=%s ORDER BY sort_order", (lead.get("id"),))
over("C7 galerie poptavky: 2 polozky, neverejne, poradi 0,1, soubory na disku a stejne jako odeslane", len(gal) == 2 and [g["sort_order"] for g in gal] == [0, 1] and all(g["is_public"] == 0 for g in gal)
     and all(os.path.exists(os.path.join(GAL_DIR, g["filename"])) for g in gal) and open(os.path.join(GAL_DIR, gal[0]["filename"]), "rb").read() == soub(2)["composite_0"][0], gal)
nota = (radky("SELECT * FROM scene_offer_notes ORDER BY id DESC LIMIT 1") or [{}])[0]
over("C8 poznamka u nabidky: offer_id 1, polozka 'Zakreslená změna', bez stranky, kontakt a CRM poptavka v textu, IP a guest_id",
     nota.get("offer_id") == 1 and nota.get("item_name") == "Zakreslená změna" and nota.get("page_key") is None and "zakaznik@example.com" in nota["body"] and f"CRM poptávka #{lead['id']}" in nota["body"]
     and "posunout spodní polici" in nota["body"] and nota.get("ip_address") == "10.9.9.9" and len(nota.get("guest_id") or "") >= 16, nota)
em = radky("SELECT * FROM system_emails ORDER BY id")
adm = [e for e in em if e["recipient_email"] == SO.SUPPLIER["email"]]
zak = [e for e in em if e["recipient_email"] == "zakaznik@example.com"]
over("C9 e-maily jen do FRONTY (kind scene_offer_markup, status pending, trigger auto): upozorneni dodavateli + potvrzeni zakaznikovi, nic se neodeslalo primo",
     len(em) == 2 and len(adm) == 1 and len(zak) == 1 and all(e["kind"] == "scene_offer_markup" and e["status"] == "pending" and e["trigger_type"] == "auto" for e in em) and not ODESLANO, em)
over("C9b e-mail dodavateli: predmet s cislem nabidky, kontakt, popis, pohledy, cislo CRM poptavky a odkaz do administrace; e-mail zakaznikovi: potvrzeni s cislem nabidky",
     adm[0]["subject"] == "Zakreslená změna k nabídce Logiman9001" and "zakaznik@example.com" in adm[0]["body_text"] and "posunout spodní polici" in adm[0]["body_text"]
     and f"CRM poptávce č. {lead['id']}" in adm[0]["body_text"] and "/admin.html#onlineoffers" in adm[0]["body_text"] and "Pohled 2: 3D pohled" in adm[0]["body_text"]
     and zak[0]["subject"] == "Zakreslenou změnu jsme přijali" and "Logiman9001" in zak[0]["body_text"] and "LOGIMAN" in zak[0]["body_text"], (adm[0]["subject"], zak[0]["subject"]))

# Vandr nabidka (bez jmena zakaznika), PNG composite, znamy zakaznik v shop_customers
tc.execute("INSERT INTO shop_customers (user_id, email) VALUES (990001, 'vandr.zakaznik@example.com')")
T.commit()
zid = radky("SELECT id FROM shop_customers WHERE email='vandr.zakaznik@example.com'")[0]["id"]
r = post("vandr-klient", form([pohled(label="", view={"kind": "render", "key": "render_7"})], email="vandr.zakaznik@example.com"), soub(1, png(), "p.png", "image/png"))
lead2 = (radky("SELECT * FROM crm_leads ORDER BY id DESC LIMIT 1") or [{}])[0]
f2 = radky("SELECT filename, content_type FROM shared_drive_files WHERE folder_id=%s", (lead2.get("drive_folder_id"),))
over("C10 Vandr nabidka: 201, lead bez jmena (NULL), navazany na existujiciho zakaznika, priloha PNG (image/png, .png), popisek pohledu podle druhu (vizualizace)",
     r.status_code == 201 and lead2.get("contact_name") is None and lead2.get("customer_id") == zid and f2 == [{"filename": "zakreslena-zmena-1.png", "content_type": "image/png"}]
     and lead2.get("subject") == "Zakreslená změna k nabídce Logiman9002", (r.status_code, lead2, f2))
zpr2 = (radky("SELECT body FROM crm_lead_messages WHERE lead_id=%s", (lead2.get("id"),)) or [{}])[0]
over("C10b popisek pohledu bez labelu: 'Pohled 1: vizualizace'", "Pohled 1: vizualizace" in (zpr2.get("body") or ""), zpr2)
# popisek pohledu s novym radkem se slozi na jeden radek (nesmi podvrhnout dalsi radek seznamu pohledu)
r = post("conf-klient", form([pohled(label="Nárys\n- Pohled 9: podvrh")]), soub(1))
lead3 = (radky("SELECT id FROM crm_leads ORDER BY id DESC LIMIT 1") or [{}])[0]
zpr3 = (radky("SELECT body FROM crm_lead_messages WHERE lead_id=%s", (lead3.get("id"),)) or [{}])[0].get("body") or ""
over("C13 popisek pohledu s novym radkem: v CRM zprave zustane na jednom radku, zadny podvrzeny radek seznamu", r.status_code == 201 and "- Pohled 1: Nárys - Pohled 9: podvrh (výkres)" in zpr3
     and not any(l.startswith("- Pohled 9") for l in zpr3.splitlines()), zpr3)
# 6 pohledu najednou
r = post("conf-klient", form([pohled(label=f"P{i}") for i in range(6)]), soub(6))
over("C11 sest pohledu (maximum) projde: 201, views 6", r.status_code == 201 and (r.get_json() or {}).get("views") == 6, (r.status_code, r.get_data(as_text=True)[:200]))
# testovaci nabidka: predpona
pred_t = radky("SELECT id FROM system_emails")
r = post("test-klient", form(), soub(1))
em_t = radky("SELECT subject FROM system_emails WHERE id > %s", (max([e["id"] for e in pred_t]),))
lead_t = (radky("SELECT subject FROM crm_leads ORDER BY id DESC LIMIT 1") or [{}])[0]
over("C12 testovaci nabidka (cislo TEST): predpona [TESTOVACÍ NABÍDKA] v predmetu poptavky i obou e-mailu", r.status_code == 201 and len(em_t) == 2 and all(e["subject"].startswith("[TESTOVACÍ NABÍDKA] ") for e in em_t)
     and lead_t["subject"].startswith("[TESTOVACÍ NABÍDKA] "), (em_t, lead_t))

# ================================================================ D) validace
print("== D) validace: kazda chyba = 400 s polem a ZADNY zapis")
pred = pocty()
PRAZDNE = []


def chyba(nazev, token="conf-klient", pole=None, status=400, f=None, s=None, fragment=None):
    r = post(token, f if f is not None else form(), s if s is not None else soub(1))
    d = r.get_json(silent=True) or {}
    dobre = r.status_code == status and (pole is None or d.get("field") == pole) and (fragment is None or fragment in (d.get("error") or ""))
    over(f"D {nazev}: HTTP {status}" + (f", pole {pole}" if pole else ""), dobre, (r.status_code, d))


chyba("e-mail bez zavinace", pole="email", f=form(email="neni-email"))
chyba("e-mail bez tecky v domene", pole="email", f=form(email="a@domena"))
chyba("e-mail s domenou bez mailserveru (MX)", pole="email", f=form(email="a@nemamailserver.invalid"))
chyba("prazdny e-mail", pole="email", f=form(email=""))
chyba("e-mail s novym radkem (vlozeni hlavicky)", pole="email", f=form(email="a@b.cz\nBcc: x@y.cz"))
chyba("e-mail s mezerou", pole="email", f=form(email="a b@c.cz"))
chyba("e-mail se dvema zavinaci", pole="email", f=form(email="a@b@c.cz"))
chyba("kratky telefon", pole="phone", f=form(phone="12345"))
chyba("telefon samá stejná čísla (vymyšlený)", pole="phone", f=form(phone="999999999"))
chyba("telefon rostouci rada (vymyšlený)", pole="phone", f=form(phone="123456789"))
chyba("popis kratsi nez 3 znaky", pole="note", f=form(note="ab"))
chyba("popis prazdny (jen mezery)", pole="note", f=form(note="    "))
chyba("popis delsi nez 2000 znaku", pole="note", f=form(note="x" * 2001))
chyba("views neni JSON", pole="views", f=form(views="{nesmysl"))
chyba("views prazdne pole", pole="views", f=form(views="[]"))
chyba("views neni pole", pole="views", f=form(views='{"a":1}'))
chyba("7 pohledu (limit 6)", pole="views", f=form([pohled() for _ in range(7)]), s=soub(7))
chyba("pohled neni objekt", pole="views", f=form(views='["x"]'), fragment="Pohled 1")
chyba("pohled bez view", pole="views", f=form([{"label": "x", "marks": [], "image_w": 1, "image_h": 1}]), fragment="Pohled 1")
chyba("neplatny druh pohledu (kind)", pole="views", f=form([pohled(view={"kind": "foto"})]))
chyba("klic pohledu delsi nez 80", pole="views", f=form([pohled(view={"kind": "drawing", "key": "k" * 81})]))
chyba("kamera neni objekt", pole="views", f=form([pohled(view={"kind": "3d", "camera": [1, 2, 3]})]))
chyba("view JSON vetsi nez 4 kB", pole="views", f=form([pohled(view={"kind": "3d", "camera": {"x": "y" * 5000}})]), fragment="příliš velké")
chyba("popisek pohledu delsi nez 120", pole="views", f=form([pohled(label="L" * 121)]))
chyba("stranka pohledu delsi nez 30", pole="views", f=form([pohled(page="p" * 31)]))
chyba("znacka neplatneho druhu", pole="views", f=form([pohled(marks=[{"kind": "kometa", "points": [{"x": 0.1, "y": 0.1}]}])]), fragment="Neplatný typ značky")
chyba("znacka bez bodu", pole="views", f=form([pohled(marks=[{"kind": "pen", "points": []}])]))
chyba("bod znacky mimo rozsah 0..1", pole="views", f=form([pohled(marks=[{"kind": "pen", "points": [{"x": 1.5, "y": 0.2}]}])]), fragment="mimo rozsah")
chyba("zaporny rozmer obrazku", pole="views", f=form([pohled(image_w=-5)]))
chyba("rozmer obrazku jako pravdivostni hodnota", pole="views", f=form([pohled(image_h=True)]))
chyba("chybi composite", pole="views", s={})
chyba("composite neni obrazek (text)", pole="views", s=soub(1, b"to neni obrazek, jen text", "x.jpg"), fragment="není platný obrázek")
chyba("composite je GIF (jen JPEG/PNG)", pole="views", s=soub(1, (lambda b: (Image.new("RGB", (8, 8)).save(b, "GIF"), b.getvalue())[1])(io.BytesIO()), "x.gif", "image/gif"), fragment="JPEG nebo PNG")
chyba("composite nad 3 MB", pole="views", s=soub(1, b"\xff\xd8\xff" + os.urandom(3 * 1024 * 1024 + 10), "x.jpg"), fragment="příliš velký")
chyba("composite jen pro prvni z dvou pohledu", pole="views", f=form([pohled(), pohled()]), s=soub(1))
po = pocty()
over("D** po vsech chybach se NIC nezapsalo (zadny radek, zadny soubor na disku)", po == pred, {k: (pred[k], po[k]) for k in po if po[k] != pred[k]})

# ================================================================ E) nabidka a token
print("== E) token a gating")
pred = pocty()
r = post("conf-admin", form(), soub(1))
over("E1 ADMIN token (Zobrazit online): 403 'Administrátorský náhled neodesílá změny.'", r.status_code == 403 and (r.get_json() or {}).get("error") == "Administrátorský náhled neodesílá změny.", (r.status_code, r.get_data(as_text=True)[:200]))
r = post("scena-klient", form(), soub(1))
over("E2 nabidka ze sceny (1. vetev): 400 'Tato nabídka zakreslení změn nepodporuje.'", r.status_code == 400 and (r.get_json() or {}).get("error") == "Tato nabídka zakreslení změn nepodporuje.", (r.status_code, r.get_data(as_text=True)[:200]))
for token, popis in (("neexistuje-token", "neexistujici token"), ("expir-klient", "expirovana nabidka"), ("neaktivni-klient", "neaktivni (zrusena) nabidka")):
    r = post(token, form(), soub(1))
    over(f"E3 {popis}: 404 'Nabídka nebyla nalezena.'", r.status_code == 404 and (r.get_json() or {}).get("error") == "Nabídka nebyla nalezena.", (r.status_code, r.get_data(as_text=True)[:200]))
over("E4 zadny z odmitnutych pozadavku nic nezapsal", pocty() == pred)
for opts, ocek, popis in (({"source": "configurator"}, True, "configurator"), ({"vandr_single_drawing": True}, True, "vandr_single_drawing"), ({"vandr_single_drawing": False}, False, "vandr_single_drawing=false"),
                          ({"source": "scene"}, False, "jiny zdroj"), ({}, False, "prazdne volby"), ({"vandr_single_drawing": "true"}, False, "vandr_single_drawing jako text")):
    over(f"E5 markup_requests_enabled({popis}) == {ocek}", OMR.markup_requests_enabled({"offer_options": json.dumps(opts)}) is ocek)
over("E5b markup_requests_enabled: nabidka bez offer_options / rozbite JSON / JSON jako pole -> False", all(OMR.markup_requests_enabled(o) is False for o in ({"offer_options": None}, {"offer_options": "{rozbite"}, {"offer_options": "[1,2]"}, {})))

# ================================================================ F) honeypot a rate limit
print("== F) honeypot a rate limit")
pred = pocty()
r = post("conf-klient", form(website="http://spam.example", email="spatny", note=""), {})
over("F1 honeypot: vyplnene skryte pole = 200 {status: ok} a NIC se neulozi (ani pri jinak neplatnem formulari)", r.status_code == 200 and (r.get_json() or {}) == {"status": "ok"} and pocty() == pred, (r.status_code, r.get_data(as_text=True)[:100]))
A._rate_limit_buckets.clear()
kody = [post("conf-klient", form(website="spam"), {}, ip=f"10.50.0.{i}", limit=True).status_code for i in range(4)]
over("F2 rate limit na token: 3 pozadavky projdou, 4. = 429", kody == [200, 200, 200, 429], kody)
A._rate_limit_buckets.clear()
kody = [post(t, form(website="spam"), {}, ip="10.60.0.1", limit=True).status_code for t in ("conf-klient", "vandr-klient", "scena-klient", "expir-klient", "neaktivni-klient", "test-klient", "x1", "x2", "x3")]
over("F3 rate limit na IP: 8 pozadavku (ruzne tokeny) projde, 9. = 429", kody == [200] * 8 + [429], kody)
A._rate_limit_buckets.clear()
r = post("conf-klient", form(), soub(1), limit=True)
over("F4 po vycisteni limitu zase funguje (201)", r.status_code == 201, (r.status_code, r.get_data(as_text=True)[:100]))

# ================================================================ G) rollback a uklid souboru
print("== G) chyba uprostred zapisu: rollback vseho + uklid souboru")
pred = pocty()
_puv_emaily = OMR._zaradit_emaily


def _spadne(*a, **k):
    raise RuntimeError("umysleny pad pri zarazovani e-mailu")


OMR._zaradit_emaily = _spadne
r = post("conf-klient", form([pohled(), pohled(label="druhy")]), soub(2))
OMR._zaradit_emaily = _puv_emaily
po = pocty()
over("G1 pad pri e-mailech (po zapsanych prilohach): JSON 500 se srozumitelnou hlaskou, ZADNY radek a ZADNY soubor (Drive ani galerie) nezustal", r.status_code == 500 and "error" in (r.get_json(silent=True) or {}) and po == pred,
     (r.status_code, r.get_data(as_text=True)[:150], {k: (pred[k], po[k]) for k in po if po[k] != pred[k]}))
_puv_galerie = OMR._kopie_do_galerie
_cit = [0]


def _spadne_na_druhem(*a, **k):
    _cit[0] += 1
    if _cit[0] == 2:
        raise OSError("disk plny (umysl)")
    return _puv_galerie(*a, **k)


OMR._kopie_do_galerie = _spadne_na_druhem
r = post("conf-klient", form([pohled(), pohled(label="druhy")]), soub(2))
OMR._kopie_do_galerie = _puv_galerie
po = pocty()
over("G2 pad pri kopii do galerie u 2. pohledu (1. pohled uz ma soubory na disku): vse vraceno, zadny osirely soubor", r.status_code == 500 and po == pred,
     (r.status_code, {k: (pred[k], po[k]) for k in po if po[k] != pred[k]}))
r = post("conf-klient", form(), soub(1))
over("G3 po chybach endpoint dal funguje (201)", r.status_code == 201, (r.status_code, r.get_data(as_text=True)[:100]))

# ================================================================ I) stranka Vandr vykresu (page_key drawings_vandr) v backendu
print("== I) page_key drawings_vandr: Dotaz, statistiky, znacky, by_page; cile kliku zakreslovani")
idx2 = SO.OFFER_PAGE_KEYS.index("drawings_2")
over("I0 OFFER_PAGE_KEYS: drawings_vandr je hned za drawings_2 a verejna odpoved ho nabizi v `pages`", SO.OFFER_PAGE_KEYS[idx2 + 1] == "drawings_vandr"
     and "drawings_vandr" in ((klient.get("/api/public/offers/vandr-klient").get_json(silent=True) or {}).get("pages") or []), SO.OFFER_PAGE_KEYS)
over("I0b CLICK_TARGETS obsahuje markup_request_draw i markup_request_sent", all(t in SO.CLICK_TARGETS for t in ("markup_request_draw", "markup_request_sent")), SO.CLICK_TARGETS)

# a) "Dotaz" (public_offer_note) ze stranky Vandr vykresu
A._rate_limit_buckets.clear()
r = klient.post("/api/public/offers/vandr-klient/note", json={"body": "Prosím upravit pravou stranu regálu.", "page_key": "drawings_vandr"}, headers={"X-Real-IP": "10.8.0.1"})
nota_v = radky("SELECT * FROM scene_offer_notes WHERE page_key='drawings_vandr'")
over("I1 Dotaz (public_offer_note) s page_key drawings_vandr: 201 a poznamka ulozena u nabidky Vandr", r.status_code == 201 and len(nota_v) == 1 and nota_v[0]["offer_id"] == 2, (r.status_code, r.get_data(as_text=True)[:150], nota_v))
A._rate_limit_buckets.clear()
r = klient.post("/api/public/offers/vandr-klient/note", json={"body": "x", "page_key": "stranka_ktera_neexistuje"}, headers={"X-Real-IP": "10.8.0.2"})
over("I1b neznamy page_key zustava odmitnuty (400 'Neplatná stránka.')", r.status_code == 400 and (r.get_json() or {}).get("error") == "Neplatná stránka.", (r.status_code, r.get_data(as_text=True)[:100]))

# b) statistiky /event: zobrazeni stranky + kliky zakreslovani
tc.execute("INSERT INTO scene_offer_views (id, offer_id, ip_address, started_at, last_seen_at) VALUES (1, 2, '10.8.0.9', NOW(), NOW())")
T.commit()


def udalost(**kw):
    A._rate_limit_buckets.clear()
    return klient.post("/api/public/offers/vandr-klient/event", json=kw)


r_pv = udalost(view_id=1, page_index=1, page_key="drawings_vandr", dwell_ms=4200, scroll_pct=40)
r_draw = udalost(view_id=1, page_index=1, page_key="drawings_vandr", event_type="click", target="markup_request_draw")
r_sent = udalost(view_id=1, page_index=1, page_key="drawings_vandr", event_type="click", target="markup_request_sent")
r_zly = udalost(view_id=1, page_index=1, page_key="drawings_vandr", event_type="click", target="neznamy_cil")
over("I2 /event: page_view se strankou drawings_vandr = 201", r_pv.status_code == 201, (r_pv.status_code, r_pv.get_data(as_text=True)[:120]))
over("I3 /event: kliky markup_request_draw a markup_request_sent (na drawings_vandr) = 201, neznamy cil zustava 400", r_draw.status_code == 201 and r_sent.status_code == 201 and r_zly.status_code == 400,
     (r_draw.status_code, r_sent.status_code, r_zly.status_code))
udal = radky("SELECT page_key, event_type, target FROM scene_offer_page_events WHERE view_id=1 ORDER BY id")
over("I3b v databazi jsou 3 udalosti (page_view + 2 kliky), vsechny se strankou drawings_vandr", udal == [{"page_key": "drawings_vandr", "event_type": "page_view", "target": None},
     {"page_key": "drawings_vandr", "event_type": "click", "target": "markup_request_draw"}, {"page_key": "drawings_vandr", "event_type": "click", "target": "markup_request_sent"}], udal)

# c) ukladani znacek (PUT .../markups) na strance drawings_vandr
znacky = [{"kind": "number", "page": "drawings_vandr", "view": "narys", "number": 1, "label": "kontrola", "points": [{"x": 0.5, "y": 0.5}]},
          {"kind": "pen", "page": "drawings_vandr", "view": "narys", "points": [{"x": 0.1, "y": 0.1}, {"x": 0.2, "y": 0.3}]}]
A._rate_limit_buckets.clear()
r = klient.put("/api/public/offers/vandr-klient/markups", json={"marks": znacky}, headers={"X-Real-IP": "10.8.0.3"})
ulozene = radky("SELECT data FROM scene_offer_markups WHERE offer_id=2")
uloz = json.loads(ulozene[0]["data"]) if ulozene else []
over("I4 PUT markups se strankou drawings_vandr: 200 (2 znacky) a ulozeno jako znacky klienta", r.status_code == 200 and (r.get_json() or {}).get("count") == 2 and len(uloz) == 2
     and all(m["page"] == "drawings_vandr" and m["author"] == "client" for m in uloz), (r.status_code, r.get_data(as_text=True)[:120], uloz))
A._rate_limit_buckets.clear()
r = klient.put("/api/public/offers/vandr-klient/markups", json={"marks": [dict(znacky[0], page="stranka_ktera_neexistuje")]}, headers={"X-Real-IP": "10.8.0.4"})
over("I4b znacka s neznamou strankou zustava odmitnuta (400)", r.status_code == 400, (r.status_code, r.get_data(as_text=True)[:100]))

# d) admin statistiky: by_page ma vzdy vsechny stranky vcetne drawings_vandr
with A.app.test_request_context("/api/admin/scene-offers/2/stats"):
    odp = SO.admin_scene_offer_stats.__wrapped__(2)          # bez prihlaseni/opravneni (dekorator nevolame), tabulky jsou zastinene
stat = odp.get_json(silent=True) or {}
klice = [b["page_key"] for b in stat.get("by_page", [])]
vandr_b = next((b for b in stat.get("by_page", []) if b["page_key"] == "drawings_vandr"), {})
kliky = {c["target"]: c["clicks"] for c in stat.get("by_click", [])}
over("I5 admin statistiky: by_page obsahuje drawings_vandr hned za drawings_2, eviduje 1 zobrazeni; by_click eviduje oba cile zakreslovani; Dotaz je v poznamkach",
     bool(klice) and klice[klice.index("drawings_2") + 1] == "drawings_vandr" and vandr_b.get("views") == 1 and vandr_b.get("unique_views") == 1 and kliky.get("markup_request_draw") == 1
     and kliky.get("markup_request_sent") == 1 and any(n["page_key"] == "drawings_vandr" for n in stat.get("notes", [])), (klice, vandr_b, kliky))

# ================================================================ J) integrace: SKUTECNY surovy POST z prohlizece (bajt po bajtu)
print("== J) surovy multipart POST z prohlizece (fixture_post_z_prohlizece.bin/.ct), nabidka z Vandr karty (vandr_single_drawing)")
FIX_DIR = os.path.dirname(os.path.abspath(__file__))
FIX_BIN = open(os.path.join(FIX_DIR, "fixture_post_z_prohlizece.bin"), "rb").read()
FIX_CT = open(os.path.join(FIX_DIR, "fixture_post_z_prohlizece.ct"), encoding="utf-8").read().strip()


def rozbal_multipart(raw, ct):
    """NEZAVISLY (bez werkzeugu) rozbor surove multipart zpravy: [(name, filename, content_type, bytes)] v poradi, jak prisla; None = neni korektne ohranicena."""
    m = re.search(r"boundary=([^;\s]+)", ct)
    if not m:
        return None
    hranice = m.group(1).encode()
    uvod, konec = b"--" + hranice + b"\r\n", b"\r\n--" + hranice + b"--\r\n"
    if not (raw.startswith(uvod) and raw.endswith(konec)):
        return None
    out = []
    for cast in raw[len(uvod):-len(konec)].split(b"\r\n--" + hranice + b"\r\n"):
        hlavicky, oddelovac, obsah = cast.partition(b"\r\n\r\n")
        if not oddelovac:
            return None
        h = hlavicky.decode("utf-8")
        jmeno = re.search(r'(?<![A-Za-z])name="([^"]*)"', h)
        soubor = re.search(r'filename="([^"]*)"', h)
        typ = re.search(r"(?im)^content-type:\s*(\S+)", h)
        out.append((jmeno.group(1) if jmeno else None, soubor.group(1) if soubor else None, typ.group(1) if typ else None, obsah))
    return out


CASTI = rozbal_multipart(FIX_BIN, FIX_CT)
POLE = {n: o.decode("utf-8") for n, f, t, o in (CASTI or []) if f is None}
OBRAZKY = [(n, o) for n, f, t, o in (CASTI or []) if f is not None]
try:
    VIEWS_FIX = json.loads(POLE.get("views", "null"))
except ValueError:
    VIEWS_FIX = None
print("     (poradi poli ve fixture z prohlizece: " + ", ".join(n for n, f, t, o in (CASTI or [])) + ")")
over("J0 fixture je cela, korektne ukoncena multipart zprava z prohlizece (boundary ----WebKitFormBoundary, CRLF), ma email/phone/note/views a JPEG casti composite_N; views = pole se stejnym poctem pohledu",
     CASTI is not None and FIX_CT.startswith("multipart/form-data; boundary=----WebKitFormBoundary") and all(k in POLE for k in ("email", "phone", "note", "views")) and len(OBRAZKY) >= 1
     and [n for n, o in OBRAZKY] == [f"composite_{i}" for i in range(len(OBRAZKY))] and all(o[:3] == b"\xff\xd8\xff" and t == "image/jpeg" for (n, f, t, o) in (CASTI or []) if f is not None)
     and isinstance(VIEWS_FIX, list) and len(VIEWS_FIX) == len(OBRAZKY), (FIX_CT, sorted(POLE), len(OBRAZKY), type(VIEWS_FIX).__name__))


def post_raw(token, raw, ct, ip):
    """Surove telo + Content-Type PRESNE jak je poslal prohlizec (zadna prestavba formulare); pamet rate limitu se pred volanim vycisti."""
    A._rate_limit_buckets.clear()
    VIDENE.update(aktivni=True, sha=None, delka=None, ct=None, cl=None, metoda=None)
    try:
        return klient.post(f"/api/public/offers/{token}/markup-requests", data=raw, content_type=ct, headers={"X-Real-IP": ip})
    finally:
        VIDENE["aktivni"] = False


pred = pocty()
max_email = radky("SELECT COALESCE(MAX(id),0) m FROM system_emails")[0]["m"]
r = post_raw("vandr-klient", FIX_BIN, FIX_CT, "10.77.0.1")
d = r.get_json(silent=True) or {}
POCET = len(OBRAZKY)
over(f"J1 surovy POST z prohlizece na nabidku z Vandr karty: 201 {{status: ok, views: {POCET}}}, odpoved je JSON (jinak se vypise PRESNA odpoved backendu vcetne pole `field`)",
     r.status_code == 201 and d == {"status": "ok", "views": POCET} and r.mimetype == "application/json", (r.status_code, r.get_data(as_text=True)[:600]))
over("J1b aplikace dostala presne ty same bajty: SHA-256 tela, delka (= Content-Length) i Content-Type (vc. boundary) shodne s fixture, metoda POST", VIDENE.get("sha") == hashlib.sha256(FIX_BIN).hexdigest()
     and VIDENE.get("delka") == len(FIX_BIN) and VIDENE.get("cl") == str(len(FIX_BIN)) and VIDENE.get("ct") == FIX_CT and VIDENE.get("metoda") == "POST", VIDENE)
po = pocty()
over(f"J2 pribyl presne 1 lead, 1 zprava, {POCET} priloh v Drive, {POCET} polozek galerie, 1 poznamka u nabidky a 2 e-maily do fronty (jako u ostatnich uspesnych pripadu)",
     {k: po[k] - pred[k] for k in ("crm_leads", "crm_lead_messages", "shared_drive_files", "content_gallery_items", "scene_offer_notes", "system_emails")}
     == {"crm_leads": 1, "crm_lead_messages": 1, "shared_drive_files": POCET, "content_gallery_items": POCET, "scene_offer_notes": 1, "system_emails": 2}
     and po["soubory_drive"] - pred["soubory_drive"] == POCET and po["soubory_galerie"] - pred["soubory_galerie"] == POCET, {k: po[k] - pred[k] for k in po})
lead = (radky("SELECT * FROM crm_leads ORDER BY id DESC LIMIT 1") or [{}])[0]
over("J3 lead: zdroj offer_markup, predmet s cislem nabidky, e-mail a telefon z formulare (e-mail malymi pismeny), nabidka bez jmena zakaznika = kontakt bez jmena, nepřečteno adminem",
     lead.get("source") == "offer_markup" and lead.get("subject") == "Zakreslená změna k nabídce Logiman9002" and lead.get("contact_email") == POLE.get("email", "").lower()
     and lead.get("contact_phone") == POLE.get("phone") and lead.get("contact_name") is None and lead.get("unread_by_admin") == 1, lead)
zpr = (radky("SELECT * FROM crm_lead_messages WHERE lead_id=%s", (lead.get("id"),)) or [{}])[0].get("body") or ""
popisky = [f"Pohled {i + 1}: {v.get('label')} (výkres)" for i, v in enumerate(VIEWS_FIX or [])]
over("J4 zprava poptavky: popis zmeny presne jako ve formulari (cestina), cislo nabidky, odkaz do administrace, seznam pohledu s popisky z prohlizece (Levá strana / Pravá strana)",
     POLE.get("note", "\0") in zpr and "Logiman9002" in zpr and "/admin.html#onlineoffers" in zpr and f"Přiložené pohledy ({POCET})" in zpr and bool(popisky) and all(p in zpr for p in popisky), (zpr, popisky))
soubory = radky("SELECT * FROM shared_drive_files WHERE folder_id=%s ORDER BY id", (lead.get("drive_folder_id"),))
na_disku = []
for sf in soubory:
    try:
        na_disku.append(open(os.path.join(DRIVE_DIR, sf["stored_filename"]), "rb").read())
    except OSError:
        na_disku.append(None)
over("J5 prilohy ve slozce poptavky: " + str(POCET) + " souboru image/jpeg zakreslena-zmena-N.jpg, na disku BAJT PO BAJTU stejne jako JPEG z prohlizece (zadne poskozeni multipartu), velikost sedi s radkem",
     len(soubory) == POCET and [sf["filename"] for sf in soubory] == [f"zakreslena-zmena-{i + 1}.jpg" for i in range(POCET)] and all(sf["content_type"] == "image/jpeg" for sf in soubory)
     and na_disku == [o for n, o in OBRAZKY] and all(sf["size_bytes"] == len(o) for sf, (n, o) in zip(soubory, OBRAZKY)), [(sf["filename"], sf["content_type"], sf["size_bytes"]) for sf in soubory])
rozmery = []
for data_jpg, v in zip(na_disku, VIEWS_FIX or []):
    try:
        im = Image.open(io.BytesIO(data_jpg))
        im.load()
        rozmery.append((im.format, im.size, (v.get("image_w"), v.get("image_h"))))
    except Exception as e:  # noqa: BLE001
        rozmery.append(("chyba", str(e)[:80], None))
over("J5b ulozene JPEG jsou platne a jejich rozmer sedi s deklarovanym image_w x image_h z views (hygiena kontraktu frontendu)", len(rozmery) == POCET and all(f == "JPEG" and sz == dekl for f, sz, dekl in rozmery), rozmery)
gal = radky("SELECT * FROM content_gallery_items WHERE owner_type='lead' AND owner_id=%s ORDER BY sort_order", (lead.get("id"),))
gal_data = []
for g in gal:
    try:
        gal_data.append(open(os.path.join(GAL_DIR, g["filename"]), "rb").read())
    except OSError:
        gal_data.append(None)
over("J6 galerie poptavky: polozky v poradi pohledu, neverejne, soubory bajt po bajtu stejne jako z prohlizece", len(gal) == POCET and [g["sort_order"] for g in gal] == list(range(POCET))
     and all(g["is_public"] == 0 for g in gal) and gal_data == [o for n, o in OBRAZKY], [(g["filename"], g["sort_order"], g["is_public"]) for g in gal])
nota = (radky("SELECT * FROM scene_offer_notes ORDER BY id DESC LIMIT 1") or [{}])[0]
over("J7 poznamka u nabidky: offer_id 2 (Vandr), polozka 'Zakreslená změna', popis zmeny, kontakt a CRM poptavka v textu",
     nota.get("offer_id") == 2 and nota.get("item_name") == "Zakreslená změna" and nota.get("page_key") is None and POLE.get("note", "\0") in (nota.get("body") or "")
     and POLE.get("email", "\0").lower() in nota["body"] and POLE.get("phone", "\0") in nota["body"] and f"CRM poptávka #{lead.get('id')}" in nota["body"], nota)
em = radky("SELECT * FROM system_emails WHERE id > %s ORDER BY id", (max_email,))
adm = [e for e in em if e["recipient_email"] == SO.SUPPLIER["email"]]
zak = [e for e in em if e["recipient_email"] == POLE.get("email", "").lower()]
over("J8 e-maily jen do FRONTY (kind scene_offer_markup, pending, auto): upozorneni dodavateli (popis, kontakt, oba pohledy, CRM poptavka) + potvrzeni zakaznikovi na jeho e-mail; nic neodeslano primo",
     len(em) == 2 and len(adm) == 1 and len(zak) == 1 and all(e["kind"] == "scene_offer_markup" and e["status"] == "pending" and e["trigger_type"] == "auto" for e in em) and not ODESLANO
     and POLE.get("note", "\0") in adm[0]["body_text"] and all(p in adm[0]["body_text"] for p in popisky) and f"CRM poptávce č. {lead.get('id')}" in adm[0]["body_text"]
     and POLE.get("email", "\0").lower() in adm[0]["body_text"] and "Logiman9002" in zak[0]["body_text"] and zak[0]["subject"] == "Zakreslenou změnu jsme přijali", [(e["recipient_email"], e["subject"]) for e in em])
# odvozena varianta TOHOTO SKUTECNEHO pozadavku: chybi posledni obrazek (prohlizec ho nepriložil) -> 400 s presnou hlaskou a nic se nezapise
B = re.search(r"boundary=([^;\s]+)", FIX_CT).group(1).encode()
posledni = f"composite_{POCET - 1}".encode()
pozice = FIX_BIN.find(b"--" + B + b'\r\nContent-Disposition: form-data; name="' + posledni + b'"')
raw_bez = FIX_BIN[:pozice] + b"--" + B + b"--\r\n" if pozice > 0 else b""
pred = pocty()
r = post_raw("vandr-klient", raw_bez, FIX_CT, "10.77.0.2")
d = r.get_json(silent=True) or {}
over(f"J9 stejny skutecny pozadavek, ale bez posledniho obrazku ({posledni.decode()}): 400, pole views, hlaska 'Pohled {POCET}: Chybí obrázek (composite).' a NIC se nezapise", pozice > 0 and r.status_code == 400
     and d.get("field") == "views" and d.get("error") == f"Pohled {POCET}: Chybí obrázek (composite)." and pocty() == pred, (pozice, r.status_code, r.get_data(as_text=True)[:300]))

# ================================================================ H) ostra DB a ostre adresare beze zmeny
print("== H) ostra DB a ostre adresare po celem testu")
ZIVE_PO = zive_stav()
over("H1 zadny zivy radek (crm_leads, zpravy, poznamky, e-maily, galerie, Drive, nabidky) ani sekvence se nezmenily", ZIVE_PO == ZIVE_PRED, {k: (ZIVE_PRED[k], ZIVE_PO[k]) for k in ZIVE_PO if ZIVE_PO[k] != ZIVE_PRED[k]})
over("H2 send_email se nikdy nezavolal", not ODESLANO, ODESLANO)

print(f"\nVYSLEDEK zakreslene zmeny v online nabidce (backend): {sum(vysl)}/{len(vysl)} OK" + (f"   SELHALO: {CERVENE}" if CERVENE else ""))
try:
    shutil.rmtree(TMP, ignore_errors=True)
except Exception:  # noqa: BLE001
    pass
sys.exit(0 if all(vysl) else 1)
