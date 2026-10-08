#!/opt/konfigurator/api/venv/bin/python
"""Mini-shop (Packstations), FAZE 2: POST /api/miniweb/inquiry - poptavka a kontaktni formular (bot5, 2026-10-02; navrh schvalil bot3).

SKUTECNY kod (nebo kandidat MINIWEB_PY) pres Flask test client nad DOCASNYMI tabulkami (storefronty, aliasy, miniweb_*, crm_leads, crm_lead_messages, system_emails, shop_customers). Ostre tabulky se jen ctou
(app_users pro session staffu a zakaznika) a po testu se porovnavaji pocty. Odesilani e-mailu je pri testu ZAKAZANE (send_email i smtplib spadnou, kdyby se na ne sahlo).

Cast A  uspesna poptavka: kontaktni formular, poptavka s polozkami a konfiguraci (snimek z databaze, ne od klienta), CRM zprava, potvrzeni zakaznikovi ZATIM VYPNUTE (rozhodnuti Roberta), po zapnuti jen ve fronte (pending), nic se neodesila
Cast B  validace: jmeno, e-mail (vcetne vlozeni hlavicky), zeme, souhlas, polozky (neviditelny/neexistujici produkt, pocet, konfigurace), JSON, velikost
Cast C  ochrany: honeypot, nahled (shop, ktery neni live) nic neuklada, vypnuta poptavka, neznamy host, limit na IP a na e-mail, atomicita
Cast D  texty: ciste a bez HTML, SQL znaky ulozene doslova, zadne ceny od klienta, potvrzeni bez znacky a jen pro jazyky se sablonou
Cast M  mutace klicovych ochran
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
  /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-02_miniweb_testy/test_miniweb_poptavka.py      (kandidat: --setenv=MINIWEB_PY=/cesta/miniweb.py)
"""
import ast
import contextlib
import json
import os
import re
import shutil
import smtplib
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
API = os.path.join(REPO, "api")
MINIWEB_PY = os.environ.get("MINIWEB_PY") or (os.path.join(API, "miniweb.py") if os.path.exists(os.path.join(API, "miniweb.py")) else os.path.join(HERE, "nasazeni", "miniweb.py"))
tmp = tempfile.mkdtemp(prefix="kand_miniweb_pt_")
shutil.copy(MINIWEB_PY, os.path.join(tmp, "miniweb.py"))
sys.path.insert(0, API)
sys.path.insert(0, tmp)                    # kandidat PRED importem app (app.py importuje nasazeny miniweb, jinak by kandidat vyhrala kopie z cache modulu)

import pymysql  # noqa: E402
import app as appmod  # noqa: E402
from flask.sessions import SecureCookieSessionInterface  # noqa: E402

import miniweb as mw  # noqa: E402

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:600]))


ODESLANO = []


def _zakazano(*a, **k):
    ODESLANO.append((a, k))
    raise AssertionError("TEST: odesilani e-mailu je zakazane")


appmod.send_email = _zakazano
smtplib.SMTP = _zakazano
smtplib.SMTP_SSL = _zakazano


def ostre():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                           port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


OSTRE_TABULKY = ("car_storefronts", "storefront_hosts", "miniweb_shops", "miniweb_categories", "miniweb_category_texts", "miniweb_products", "miniweb_product_texts", "miniweb_inquiries",
                 "miniweb_inquiry_items", "crm_leads", "crm_lead_messages", "system_emails", "shop_customers", "app_users", "audit_log")


def stav_ostrych():
    c = ostre()
    try:
        with c.cursor() as cur:
            out = {}
            for t in OSTRE_TABULKY:
                cur.execute(f"SELECT COUNT(*) AS n FROM `{t}`")
                out[t] = cur.fetchone()["n"]
            return out
    finally:
        c.close()


PRED_OSTRE = stav_ostrych()
wrap = appmod.get_conn()
real = object.__getattribute__(wrap, "_real")
TEMP_LIKE = ("car_storefronts", "storefront_hosts", "miniweb_shops", "miniweb_categories", "miniweb_category_texts", "miniweb_products", "miniweb_product_texts", "miniweb_inquiries",
             "miniweb_inquiry_items", "crm_leads", "crm_lead_messages", "system_emails", "shop_customers")
ZAPISOVANE = ("crm_leads", "crm_lead_messages", "miniweb_inquiries", "miniweb_inquiry_items", "system_emails")


def sql(q, params=None):
    with real.cursor() as cur:
        cur.execute(q, params or ())
        out = cur.fetchall() if q.lstrip().upper().startswith("SELECT") else cur.rowcount
    real.commit()
    return out


def jedno(q, params=None):
    r = sql(q, params)
    return r[0] if r else None


def pocty():
    return {t: jedno(f"SELECT COUNT(*) AS n FROM `{t}`")["n"] for t in ZAPISOVANE}


BRAND = re.compile(r"logiman|konfigur[aá]tor|vandrawee|vandr|dogus", re.I)

try:
    with real.cursor() as cur:
        for t in TEMP_LIKE:
            cur.execute(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`")
            cur.execute(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")
            cur.execute(f"SHOW CREATE TABLE `{t}`")
            assert list(cur.fetchone().values())[1].startswith("CREATE TEMPORARY TABLE"), f"ABORT: {t} neni docasna"
    real.commit()

    def sf(slug, host, status="live", lang="en"):
        sql("INSERT INTO car_storefronts (name, slug, primary_domain, status, lang) VALUES (%s,%s,%s,%s,%s)", (slug, slug, host, status, lang))
        return jedno("SELECT * FROM car_storefronts WHERE slug=%s", (slug,))

    def shop(storefront, inquiry_enabled=1):
        sql("INSERT INTO miniweb_shops (storefront_id, family, price_mode, currency, inquiry_enabled) VALUES (%s,'packstations','hidden','EUR',%s)", (storefront["id"], inquiry_enabled))

    S_EN = sf("packstations-en", "packstations.example.top")
    S_IE = sf("packstations-ie", "ie.packstations.example.top", lang="en-ie")
    S_DE = sf("packstationen-de", "packstationen.example.top", lang="de")
    S_DRAFT = sf("packstations-draft", "draft.packstations.example.top", status="draft")
    S_OFF = sf("packstations-off", "off.packstations.example.top")
    S_SK = sf("packstations-sk", "baliace-stoly.example.top", lang="sk")
    S_BR = sf("brandshop", "logiman-shop.example.top")
    sf("cars", "cars.example.top")                                      # storefront bez mini-shopu (v miniweb_shops nema radek)
    ALIAS = "shop.alias-packstations.com"
    sql("INSERT INTO storefront_hosts (storefront_id, host) VALUES (%s,%s)", (S_EN["id"], ALIAS))
    for s_ in (S_EN, S_IE, S_DE, S_DRAFT, S_BR, S_SK):
        shop(s_)
    shop(S_OFF, inquiry_enabled=0)

    sql("INSERT INTO miniweb_categories (family, slug, sort_order) VALUES ('packstations', 'tables', 1)")
    C1 = jedno("SELECT id FROM miniweb_categories WHERE slug='tables'")["id"]
    for lang, name in (("en", "Tables"), ("de", "Tische")):
        sql("INSERT INTO miniweb_category_texts (miniweb_category_id, lang, name, status) VALUES (%s,%s,%s,'approved')", (C1, lang, name))

    def prod(slug, sku, active=1, shop_product_id=None, configurator=0):
        sql("INSERT INTO miniweb_products (category_id, slug, public_sku, shop_product_id, configurator_available, is_active) VALUES (%s,%s,%s,%s,%s,%s)", (C1, slug, sku, shop_product_id, configurator, active))
        return jedno("SELECT id FROM miniweb_products WHERE slug=%s", (slug,))["id"]

    def prod_text(pid, lang, name, status="approved"):
        sql("INSERT INTO miniweb_product_texts (miniweb_product_id, lang, name, summary, description, delivery, status) VALUES (%s,%s,%s,'S','D','3 weeks',%s)", (pid, lang, name, status))

    P1 = prod("packing-station-ps120", "PS-120", shop_product_id=777, configurator=1)
    prod_text(P1, "en", "Packing station PS-120")
    prod_text(P1, "de", "Packstation PS-120")
    P2 = prod("draft-only", "DR-1")
    prod_text(P2, "en", "Draft only product", status="draft")
    P3 = prod("inactive", "IN-1", active=0)
    prod_text(P3, "en", "Inactive product")
    P4 = prod("work-table-wt100", "WT-100")
    prod_text(P4, "en", "Work table WT-100")
    P5 = prod("only-german", "DE-1")
    prod_text(P5, "de", "Nur Deutsch")

    uzivatele = [r["id"] for r in sql("SELECT id FROM app_users WHERE role='user' AND active=1 ORDER BY id LIMIT 1")]
    admin_id = sql("SELECT id FROM app_users WHERE role='admin' AND active=1 LIMIT 1")[0]["id"]
    _si = SecureCookieSessionInterface()
    cl = appmod.app.test_client(use_cookies=False)

    def cookie(uid):
        return {"Cookie": "session=" + _si.get_signing_serializer(appmod.app).dumps({"user_id": uid})} if uid else {}

    H = "packstations.example.top"
    DH = "draft.packstations.example.top"
    URL = "/api/miniweb/inquiry"

    def post(host, body, uid=None, keep=False, raw=None, ctype="application/json", headers=None, **params):
        if not keep:
            appmod._rate_limit_buckets.clear()
        h = {**cookie(uid), **(headers or {})}
        if raw is not None:
            return cl.post(URL, base_url=f"http://{host}", query_string=params or None, headers=h, data=raw, content_type=ctype)
        return cl.post(URL, base_url=f"http://{host}", query_string=params or None, headers=h, json=body)

    @contextlib.contextmanager
    def potvrzeni(zapnuto=True):
        """Potvrzeni zakaznikovi je ve vychozim stavu VYPNUTE (CONFIRMATION_ENABLED = False), testy jeho logiky ho zapinaji jen na dobu jednoho pozadavku."""
        stare = mw.CONFIRMATION_ENABLED
        mw.CONFIRMATION_ENABLED = zapnuto
        try:
            yield
        finally:
            mw.CONFIRMATION_ENABLED = stare

    _n = [0]

    def valid(**kw):
        _n[0] += 1
        b = {"name": "Jane Doe", "email": f"Jane.Doe{_n[0]}@Example.com", "phone": "+353 1 555 0100", "company": "Acme Ltd", "company_id": "6388047", "vat_id": "IE6388047V", "country": "ie", "message": "We need 3 packing stations.", "consent": True, "b2b_confirm": True}
        b.update(kw)
        return {k: v for k, v in b.items() if v is not Ellipsis}

    def beze_zmeny(nazev, fn):
        pred = pocty()
        r = fn()
        return r, pocty() == pred

    # ============================================================================================================ A) uspesna poptavka
    print("== A uspesna poptavka")
    pred = pocty()
    b1 = valid()
    r = post(H, b1)
    j = r.get_json()
    over("A1 kontaktni formular (jen zprava): 201 {status ok, inquiry_id}, hlavicky no-store a noindex", r.status_code == 201 and set(j) == {"status", "inquiry_id"} and j["status"] == "ok" and j["inquiry_id"] > 0
         and r.headers["Cache-Control"] == "no-store" and r.headers["X-Robots-Tag"] == "noindex, nofollow", (r.status_code, j))
    lead = jedno("SELECT * FROM crm_leads ORDER BY id DESC LIMIT 1")
    msg = jedno("SELECT * FROM crm_lead_messages WHERE lead_id=%s", (lead["id"],))
    inq = jedno("SELECT * FROM miniweb_inquiries WHERE id=%s", (j["inquiry_id"],))
    over("A2 CRM poptavka: zdroj miniweb, jmeno, e-mail malymi pismeny, telefon, firma, predmet s domenou, nova a necitena; zprava od kontaktu s textem a firmou a zemi",
         lead["source"] == "miniweb" and lead["contact_name"] == "Jane Doe" and lead["contact_email"] == b1["email"].lower() and lead["contact_phone"] == "+353 1 555 0100" and lead["company_name"] == "Acme Ltd"
         and lead["subject"] == "Poptávka z mini-shopu packstations.example.top" and lead["status"] == "nova" and lead["unread_by_admin"] == 1 and lead["customer_id"] is None
         and msg["sender_type"] == "contact" and msg["sender_name"] == "Jane Doe" and msg["body"] == "We need 3 packing stations.\n\nFirma: Acme Ltd | IČO: 6388047 | DIČ/IČ DPH: IE6388047V | Země: IE", (lead, msg))
    over("A3 snimek: shop, nemenny host a jazyk, odkaz na CRM poptavku, zeme velkymi pismeny, souhlas s casem, odkaz na potvrzeni; zadne polozky; zadne osobni udaje v tabulce",
         inq["storefront_id"] == S_EN["id"] and inq["shop_host"] == H and inq["lang"] == "en" and inq["crm_lead_id"] == lead["id"] and inq["country"] == "IE" and inq["consent_at"] is not None
         and sql("SELECT COUNT(*) AS n FROM miniweb_inquiry_items")[0]["n"] == 0 and not (set(inq) & {"contact_name", "contact_email", "contact_phone", "message", "company"}), inq)
    over("A4 potvrzeni zakaznikovi je ve vychozim stavu VYPNUTE (rozhodnuti Roberta pres bot3: mini-shop nepotvrzuje, odpovi zamestnanec osobne): prepinac je False, system_email_id je NULL, ve fronte system_emails nic neni a nic se neodeslalo",
         mw.CONFIRMATION_ENABLED is False and inq["system_email_id"] is None and pocty()["system_emails"] == pred["system_emails"] and not ODESLANO, (mw.CONFIRMATION_ENABLED, inq["system_email_id"]))
    po = pocty()
    over("A5 presne jeden zaznam v CRM poptavce, zprave a snimku, zadne polozky a zadne potvrzeni ve fronte", {k: po[k] - pred[k] for k in ZAPISOVANE} == {"crm_leads": 1, "crm_lead_messages": 1, "miniweb_inquiries": 1, "miniweb_inquiry_items": 0, "system_emails": 0}, po)
    b_on = valid()
    with potvrzeni():
        r_on = post(H, b_on)
    inq_on = jedno("SELECT * FROM miniweb_inquiries WHERE id=%s", (r_on.get_json()["inquiry_id"],))
    em = jedno("SELECT * FROM system_emails WHERE id=%s", (inq_on["system_email_id"],))
    over("A5b po ZAPNUTI prepinace jde potvrzeni JEN do fronty ke schvaleni: kind storefront_lead, status pending, trigger auto, bez uzivatele, anglicky, s jmenem a domenou, BEZ znacky; nic se neodeslalo",
         r_on.status_code == 201 and em["kind"] == "storefront_lead" and em["status"] == "pending" and em["trigger_type"] == "auto" and em["user_id"] is None and em["recipient_email"] == b_on["email"].lower()
         and em["subject"] == "Inquiry received" and em["body_text"] == "Dear Jane Doe,\n\nthank you for your inquiry via packstations.example.top.\n\nWe will get back to you shortly with further information.\n\nKind regards"
         and not BRAND.search(em["subject"] + em["body_text"]) and not ODESLANO and em["sent_by"] is None, (em, ODESLANO))

    sql("INSERT INTO shop_customers (user_id, full_name, email) VALUES (%s,'Known Customer','known.customer@example.com')", (uzivatele[0],))
    zname = jedno("SELECT id FROM shop_customers WHERE email='known.customer@example.com'")
    pred = pocty()
    SUMMARY = [{"label": "Width", "value": "1200 mm"}, {"label": "<b>Colour</b>", "value": "RAL &amp; 9005"}, {"label": "", "value": "nolabel"}, "junk", {"label": "NoValue", "value": ""}]
    CONF = {"hash": "cfg_ABC-123.x", "parts": [{"id": 1, "n": "Frame"}]}                 # neprusvitna konfigurace z konfiguratoru, server ji nevaliduje (nikdy z ni nebrat cenu)
    b2 = valid(email="Known.Customer@Example.com", message=..., items=[
        {"product_id": P1, "qty": 2, "kod": "CFG-1", "configuration": CONF, "summary": SUMMARY, "name": "Hacked name", "sku": "HACK-1", "unit_net": 9999, "price": 1, "total": 5},
        {"product_id": str(P4), "qty": "1"}])
    r = post(H, b2)
    j = r.get_json()
    ok_status = r.status_code == 201
    inq = jedno("SELECT * FROM miniweb_inquiries WHERE id=%s", (j.get("inquiry_id") or 0,)) if ok_status else None
    items = sql("SELECT * FROM miniweb_inquiry_items WHERE inquiry_id=%s ORDER BY id", (inq["id"],)) if inq else []
    lead = jedno("SELECT * FROM crm_leads WHERE id=%s", (inq["crm_lead_id"],)) if inq else None
    msg = jedno("SELECT * FROM crm_lead_messages WHERE lead_id=%s", (lead["id"],)) if lead else None
    over("A6 poptavka s polozkami: 201, dve radky polozek, SNIMEK z databaze (verejny kod a nazev v jazyce shopu), klient o nazvu, kodu ani cene nerozhoduje (Hacked/HACK-1/9999 se nikde neobjevi)",
         ok_status and len(items) == 2 and (items[0]["miniweb_product_id"], items[0]["public_sku"], items[0]["product_name"], items[0]["qty"]) == (P1, "PS-120", "Packing station PS-120", 2)
         and (items[1]["miniweb_product_id"], items[1]["public_sku"], items[1]["product_name"], items[1]["qty"]) == (P4, "WT-100", "Work table WT-100", 1)
         and not re.search(r"Hacked|HACK-1|9999", json.dumps(items, default=str) + (msg["body"] if msg else "")), (r.status_code, j, items))
    over("A7 konfigurace: kod, platny otisk, neoverena konfigurace ulozena beze zmeny, parametry vycistene (HTML pryc, prazdne a nesmyslne vypadnou); druha polozka bez konfigurace ma vse NULL",
         items and items[0]["config_code"] == "CFG-1" and items[0]["config_hash"] == "cfg_ABC-123.x" and json.loads(items[0]["config_json"]) == CONF
         and json.loads(items[0]["summary_json"]) == [{"label": "Width", "value": "1200 mm"}, {"label": "Colour", "value": "RAL & 9005"}]
         and items[1]["config_code"] is None and items[1]["config_hash"] is None and items[1]["config_json"] is None and items[1]["summary_json"] is None, items)
    over("A8 zprava v CRM pro zamestnance obsahuje vycet polozek s kodem konfigurace a parametry; zname e-mailove adrese se priradi zakaznik, nova zprava bez textu se sklada jen z polozek",
         msg is not None and msg["body"] == "Firma: Acme Ltd | IČO: 6388047 | DIČ/IČ DPH: IE6388047V | Země: IE\n\n--- Položky poptávky (mini-shop packstations.example.top, jazyk en) ---\n1. 2× Packing station PS-120 (PS-120), kód konfigurace CFG-1\n    - Width: 1200 mm\n    - Colour: RAL & 9005\n2. 1× Work table WT-100 (WT-100)"
         and (lead["customer_id"] == zname["id"] if zname else lead["customer_id"] is None), msg)
    pred = pocty()
    r = post(H, valid(items=[{"product_id": P1, "qty": 1, "configuration": {"hash": "!!"}}], message=...))
    it = jedno("SELECT * FROM miniweb_inquiry_items ORDER BY id DESC LIMIT 1")
    over("A9 neplatny otisk konfigurace se ulozi jako NULL (konfigurace samotna zustane), poptavka projde", r.status_code == 201 and it["config_hash"] is None and json.loads(it["config_json"]) == {"hash": "!!"}, (r.status_code, it))
    over("A10 poptavka pres ALIAS hostu dopadne do stejneho shopu a snimek drzi host, kterym zakaznik prisel", post(ALIAS, valid()).status_code == 201 and jedno("SELECT shop_host FROM miniweb_inquiries ORDER BY id DESC LIMIT 1")["shop_host"] == ALIAS, None)
    over("A11 staff na spolecne domene s ?shop=<slug> zivy shop: poptavka se ulozi a snimek drzi DOMENU shopu (ne spolecny host)",
         post("spolecna.example.org", valid(), uid=admin_id, shop="packstations-en").status_code == 201 and jedno("SELECT shop_host FROM miniweb_inquiries ORDER BY id DESC LIMIT 1")["shop_host"] == H, None)
    r_sk = post("baliace-stoly.example.top", valid(country="sk", message="Potrebujeme 3 baliace stoly. Ďakujeme, pekný deň!", name="Ján Kováč", company="Firma s.r.o.", company_id="36 396 567", vat_id="SK 2020202020"))
    lead_sk = jedno("SELECT * FROM crm_leads ORDER BY id DESC LIMIT 1")
    msg_sk = jedno("SELECT * FROM crm_lead_messages WHERE lead_id=%s", (lead_sk["id"],))
    inq_sk = jedno("SELECT * FROM miniweb_inquiries ORDER BY id DESC LIMIT 1")
    over("A12 poptavka ze SLOVENSKEHO shopu (dalsi jazyk bez zasahu do kodu): 201, slovenska diakritika prezije do CRM, snimek drzi jazyk sk, host slovenskeho shopu a zemi SK",
         r_sk.status_code == 201 and lead_sk["source"] == "miniweb" and lead_sk["contact_name"] == "Ján Kováč" and lead_sk["subject"] == "Poptávka z mini-shopu baliace-stoly.example.top"
         and msg_sk["body"] == "Potrebujeme 3 baliace stoly. Ďakujeme, pekný deň!\n\nFirma: Firma s.r.o. | IČO: 36396567 | DIČ/IČ DPH: SK2020202020 | Země: SK" and inq_sk["lang"] == "sk" and inq_sk["shop_host"] == "baliace-stoly.example.top" and inq_sk["country"] == "SK"
         and inq_sk["storefront_id"] == S_SK["id"], (r_sk.status_code, r_sk.get_json(), lead_sk, msg_sk, inq_sk))

    # ============================================================================================================ B) validace
    print("== B validace")

    def odmitnuto(body, code, field=None, host=H, **kw):
        pred_ = pocty()
        rr = post(host, body, **kw)
        jj = rr.get_json() or {}
        return rr.status_code == 400 and jj.get("error") == code and (field is None or jj.get("field") == field) and pocty() == pred_, (rr.status_code, jj)

    ok_, det = odmitnuto(valid(name=...), "name_required", "name")
    ok2, det2 = odmitnuto(valid(name="   <b></b> "), "name_required", "name")
    over("B1 jmeno je povinne (i prazdne po vycisteni), chyba nese kod a pole, nic se neulozi", ok_ and ok2, (det, det2))
    zle_emaily = ["", "nope", "a@b", "a b@example.com", "a@@example.com", "a@example..com", "a..b@example.com", "jméno@example.com", "a@example.com\r\nBcc: x@y.cz", "a@example.com,b@example.com", "<a@example.com>",
                  "a@exam ple.com", "x" * 250 + "@example.com", "a@example.c", "a@-.com"]
    res = [odmitnuto(valid(email=e), "email_invalid", "email") for e in zle_emaily]
    over("B2 neplatny e-mail (prazdny, bez domeny, mezery, dvojita @ nebo tecka, diakritika, vlozeni hlavicky pres CRLF, vic adres, prilis dlouhy) -> 400 email_invalid a nic se neulozi", all(x[0] for x in res), [(e, x[1]) for e, x in zip(zle_emaily, res) if not x[0]])
    over("B3 e-mail s trailing newline po orezani projde jen jako cisty (CR/LF uvnitr adresy vzdy 400)", post(H, valid(email="  clean.addr@example.com\n")).status_code == 201 and odmitnuto(valid(email="clean\n.addr@example.com"), "email_invalid", "email")[0], None)
    over("B4 zeme: dve pismena (i malymi) projdou, nesmysl (tri pismena, cislo, objekt) -> 400 country_invalid; chybejici zeme u shopu bez jedine zeme dodani -> 400 country_required (B2B potrebuje zemi pro DIC)",
         all(odmitnuto(valid(country=c), "country_invalid", "country")[0] for c in ("IRL", "1", "I", {"a": 1}, "I E")) and odmitnuto(valid(country=...), "country_required", "country")[0], None)
    sql("UPDATE miniweb_shops SET countries='CZ,SK,DE' WHERE storefront_id=%s", (S_EN["id"],))
    b4_us = odmitnuto(valid(country="US"), "country_invalid", "country")
    b4_de = post(H, valid(country="de", email="b4.de@example.com", vat_id=...))
    b4b = b4_us[0] and b4_de.status_code == 201
    sql("UPDATE miniweb_shops SET countries=NULL WHERE storefront_id=%s", (S_EN["id"],))
    over("B4b shop se seznamem zemi: zeme MIMO seznam (US) = 400 country_invalid, zeme ze seznamu (de) projde; shop bez seznamu zemi nic nevynucuje (externi revize 2026-10-03, #14)", b4b, (b4_us, b4_de.status_code, b4_de.get_json()))
    over("B5 souhlas se zpracovanim: chybi, false, retezec 'true', cislo 1 -> 400 consent_required, nic se neulozi", all(odmitnuto(valid(consent=c), "consent_required", "consent")[0] for c in (False, "true", 1, None, "yes"))
         and odmitnuto(valid(consent=...), "consent_required", "consent")[0], None)
    over("B6 bez zpravy a bez polozek -> 400 message_or_items_required (i zprava jen z mezer a HTML), s polozkou bez zpravy projde",
         odmitnuto(valid(message=...), "message_or_items_required", "message")[0] and odmitnuto(valid(message="  <p> </p> "), "message_or_items_required", "message")[0]
         and odmitnuto(valid(message=..., items=[]), "message_or_items_required", "message")[0] and post(H, valid(message=..., items=[{"product_id": P1, "qty": 1}])).status_code == 201, None)
    base_item = {"product_id": P1, "qty": 1}
    spatne = {"nejsou seznam": "x", "objekt misto seznamu": {"product_id": P1}, "21 polozek": [base_item] * 21, "polozka neni objekt": [5], "chybi product_id": [{"qty": 1}], "product_id retezec s pismeny": [{"product_id": "abc", "qty": 1}],
              "product_id true": [{"product_id": True, "qty": 1}], "product_id desetinne": [{"product_id": 1.9, "qty": 1}], "neexistujici produkt": [{"product_id": 99999, "qty": 1}],
              "koncept textu": [{"product_id": P2, "qty": 1}], "neaktivni": [{"product_id": P3, "qty": 1}], "jen nemecky v anglickem shopu": [{"product_id": P5, "qty": 1}],
              "qty 0": [{"product_id": P1, "qty": 0}], "qty 100": [{"product_id": P1, "qty": 100}], "qty zaporne": [{"product_id": P1, "qty": -1}], "qty retezec": [{"product_id": P1, "qty": "x"}], "qty true": [{"product_id": P1, "qty": True}],
              "qty desetinne": [{"product_id": P1, "qty": 1.5}], "konfigurace seznam": [{"product_id": P1, "qty": 1, "configuration": [1]}], "konfigurace retezec": [{"product_id": P1, "qty": 1, "configuration": "x"}],
              "konfigurace prilis velka": [{"product_id": P1, "qty": 1, "configuration": {"hash": "abcdef12", "pad": "x" * 7000}}]}
    res = {k: odmitnuto(valid(items=v), "items_invalid") for k, v in spatne.items()}
    over("B7 polozky: nejsou seznam, vic nez 20, ne objekt, chybejici nebo nezname id, neviditelny produkt (koncept textu, neaktivni, jen jiny jazyk), nesmyslne mnozstvi, nesmyslna nebo prilis velka konfigurace -> 400 items_invalid",
         all(x[0] for x in res.values()), [(k, x[1]) for k, x in res.items() if not x[0]])
    fld = odmitnuto(valid(items=[base_item, {"product_id": P2, "qty": 1}]), "items_invalid", "items[1]")
    over("B8 chyba polozky nese pole s indexem (items[1]), aby formular ukazal radek", fld[0], fld[1])
    json_pripady = (("not json", "application/json"), (json.dumps(valid()), "text/plain"), (json.dumps(valid()), "application/x-www-form-urlencoded"), ("[1,2]", "application/json"), ("", "application/json"),
                    ("null", "application/json"), (b'{"name":"\xff\xfe"}', "application/json"))
    res = [odmitnuto(None, "invalid_json", raw=raw, ctype=ct) for raw, ct in json_pripady]
    over("B9 JSON: neplatny JSON, jiny content-type (text/plain a formular - bariera proti cross-site), pole misto objektu, prazdne telo, null, neplatne UTF-8 -> 400 invalid_json a nic se neulozi",
         all(x[0] for x in res), [(str(c[0])[:20], c[1], x[1]) for c, x in zip(json_pripady, res) if not x[0]])
    pred9 = pocty()
    nahore = [post(H, None, raw='{"a":' * h_ + "1" + "}" * h_) for h_ in (5000, 10800)]
    over("B9b hluboce vnoreny JSON v tele (5000 a 10800 urovni, pod 64 kB) nikdy neskonci chybou 500: vzdy 400 a nic se neulozi", all(x.status_code == 400 for x in nahore) and pocty() == pred9, [(x.status_code, x.get_json()) for x in nahore])
    pred9 = pocty()
    hl_pole = "[" * 2900 + "]" * 2900                                     # 5800 znaku, pod limitem velikosti konfigurace, ale MySQL JSON vic nez 100 urovni odmita
    v_konf = post(H, None, raw='{"name":"A","email":"deep@example.com","consent":true,"company":"Deep Ltd","company_id":"123456","vat_id":"IE1234567","country":"IE","b2b_confirm":true,"items":[{"product_id":%d,"qty":1,"configuration":{"x":%s}}]}' % (P1, hl_pole))
    over("B9c hluboka konfigurace v polozce (2900 urovni) -> 400 items_invalid, nikdy 500 (MySQL by ji pri ulozeni odmitl) a nic se neulozi", v_konf.status_code == 400 and v_konf.get_json() == {"error": "items_invalid", "field": "items[0].configuration"} and pocty() == pred9, (v_konf.status_code, v_konf.get_json()))
    ok_konf = post(H, valid(items=[{"product_id": P1, "qty": 1, "configuration": {"hash": "abcdef12", "a": {"b": {"c": [1, 2, {"d": "e"}]}}}}], message=...))
    over("B9d rozumne vnorena konfigurace (hloubka 7) se ulozi", ok_konf.status_code == 201, ok_konf.get_json())
    sur = post(H, None, raw='{"name":"A\\ud800B","email":"sur@example.com","consent":true,"message":"hi \\udc00 there","company":"Ac\\ud83dme","company_id":"6388047","vat_id":"IE6388047V","country":"IE","b2b_confirm":true,"items":[{"product_id":%d,"qty":1,"kod":"K\\ud800","configuration":{"hash":"abcdef12","k":"\\ud800x"},"summary":[{"label":"L\\ud800","value":"V\\ud800"}]}]}' % P1)
    lead_s = jedno("SELECT * FROM crm_leads ORDER BY id DESC LIMIT 1")
    it_s = jedno("SELECT * FROM miniweb_inquiry_items ORDER BY id DESC LIMIT 1")
    over("B12 osamocene surrogaty (JSON \\ud800 ve jmene, zprave, firme, kodu, konfiguraci i parametrech) se odstrani, neskonci to chybou 500 pri ukladani do databaze",
         sur.status_code == 201 and lead_s["contact_name"] == "AB" and lead_s["company_name"] == "Acme" and it_s["config_code"] == "K" and json.loads(it_s["config_json"]) == {"hash": "abcdef12", "k": "x"}
         and json.loads(it_s["summary_json"]) == [{"label": "L", "value": "V"}], (sur.status_code, sur.get_json(), lead_s, it_s))
    emoji = post(H, valid(name="Zoë 😀 Müller-Łukasiewicz", message="Příliš žluťoučký kůň 🐴 — 你好"))
    lead_e = jedno("SELECT * FROM crm_leads ORDER BY id DESC LIMIT 1")
    msg_e = jedno("SELECT * FROM crm_lead_messages ORDER BY id DESC LIMIT 1")
    over("B13 ctyrbajtove znaky, diakritika a CJK se ulozi beze zmeny (utf8mb4)", emoji.status_code == 201 and lead_e["contact_name"] == "Zoë 😀 Müller-Łukasiewicz" and msg_e["body"].startswith("Příliš žluťoučký kůň 🐴 — 你好"), (emoji.status_code, lead_e["contact_name"]))
    velka = post(H, valid(message="Z" * 4000, items=[{"product_id": P1, "qty": 1, "summary": [{"label": "L" * 120, "value": "V" * 300} for _ in range(40)]} for _ in range(3)]))
    msg_v = jedno("SELECT * FROM crm_lead_messages ORDER BY id DESC LIMIT 1")
    n_pol = jedno("SELECT COUNT(*) AS n FROM miniweb_inquiry_items WHERE inquiry_id=(SELECT MAX(id) FROM miniweb_inquiries)")["n"]
    over("B14 velky vycet polozek: zprava v CRM se zkrati na strop (sloupec TEXT by pretekl) a konci poznamkou, polozky jsou ulozeny cele (3), poptavka projde (ne 500)",
         velka.status_code == 201 and len(msg_v["body"]) <= mw.INQUIRY_MAX_MESSAGE + 100 and msg_v["body"].endswith("miniweb_inquiry_items]") and n_pol == 3, (velka.status_code, len(msg_v["body"]), n_pol))
    pred_ = pocty()
    rr = post(H, None, raw=json.dumps(valid(message="x" * 70000)))
    over("B10 telo nad 64 kB -> 413 payload_too_large, nic se neulozi", rr.status_code == 413 and rr.get_json() == {"error": "payload_too_large"} and pocty() == pred_, rr.status_code)
    over("B11 dlouhe hodnoty se orezou: jmeno na 120, firma na 160, zprava na 4000 znaku; telefon se vycisti od pismen",
         post(H, valid(name="N" * 500, company="C" * 500, message="M" * 6000, phone="call me: +353 (1) 555-0100 ext. 5")).status_code == 201
         and (lambda l, m: len(l["contact_name"]) == 120 and len(l["company_name"]) == 160 and l["contact_phone"] == "+353 (1) 555-0100 . 5" and len(m["body"].split("\n")[0]) == 4000)(
             jedno("SELECT * FROM crm_leads ORDER BY id DESC LIMIT 1"), jedno("SELECT * FROM crm_lead_messages ORDER BY id DESC LIMIT 1")), jedno("SELECT contact_phone FROM crm_leads ORDER BY id DESC LIMIT 1"))

    # ============================================================================================================ C) ochrany
    print("== G jen firmam (B2B)")
    pred_g = pocty()
    over("G1 firma je povinna (Robert: 'vzdy jen firmam'): chybi, prazdna, jen HTML nebo mezery -> 400 company_required, nic se neulozi", all(odmitnuto(valid(company=c), "company_required", "company")[0] for c in (..., "", "  ", "<b></b>", None)), None)
    over("G1b potvrzeni, ze poptavku posila podnikatel (b2b_confirm true) je povinne: chybi, false, retezec 'true', cislo 1 -> 400 b2b_confirm_required, nic se neulozi", all(odmitnuto(valid(b2b_confirm=c), "b2b_confirm_required", "b2b_confirm")[0] for c in (..., False, "true", 1, None))
         and odmitnuto(valid(consent=False, b2b_confirm=False), "consent_required", "consent")[0], None)
    over("G2 ICO je povinne: chybi/prazdne -> 400 company_id_required; SK a CZ jen 6 az 8 cislic (pismena, 5 cislic, 9 cislic, mezery uvnitr bez cislic) -> company_id_invalid; jinde 4 az 20 znaku",
         all(odmitnuto(valid(country="SK", vat_id="SK2020202020", company_id=c), "company_id_required", "company_id")[0] for c in (..., "", "  ", "- . -"))
         and all(odmitnuto(valid(country="SK", vat_id="SK2020202020", company_id=c), "company_id_invalid", "company_id")[0] for c in ("ABC12345", "12345", "123456789", "12 34x"))
         and all(odmitnuto(valid(country="CZ", vat_id=..., company_id=c), "company_id_invalid", "company_id")[0] for c in ("1234567A", "999"))
         and all(odmitnuto(valid(country="IE", company_id=c), "company_id_invalid", "company_id")[0] for c in ("123", "x" * 21, "ab#cd")), None)
    over("G3 DIC / IC DPH je NEPOVINNE (Robert pres bot3: 'DIC volitelne'): bez nej projde SK, IE, DE i CZ; prazdny retezec a mezery se berou jako nezadane, do CRM se pak DIC nepise",
         all(post(H, valid(country=c, company_id="12345678", vat_id=v)).status_code == 201 for c in ("SK", "IE", "DE", "CZ") for v in (..., "", "  ", None)), None)
    over("G4 syntaxe DIC / IC DPH: SK jen 10 cislic nebo SK a 10 cislic; CZ 8 az 10 cislic s prefixem CZ nebo bez; jinde prefix zeme (GR = EL) a 2 az 12 znaku, cizi prefix, kratke nebo s nepovolenymi znaky -> 400 vat_id_invalid",
         all(odmitnuto(valid(country="SK", company_id="36396567", vat_id=v), "vat_id_invalid", "vat_id")[0] for v in ("SK123", "CZ2020202020", "20202020201", "SK20202020AB", "2020202"))
         and all(odmitnuto(valid(country="CZ", company_id="12345678", vat_id=v), "vat_id_invalid", "vat_id")[0] for v in ("SK12345678", "CZ1234567", "CZ12345678901"))
         and all(odmitnuto(valid(country="IE", vat_id=v), "vat_id_invalid", "vat_id")[0] for v in ("DE6388047V", "IE", "IE#6388", "6388047V"))
         and all(odmitnuto(valid(country="GR", company_id="123456789", vat_id=v), "vat_id_invalid", "vat_id")[0] for v in ("GR123456789", "123456789")), None)
    ok_sk = [post(H, valid(country="sk", company_id=ico, vat_id=vat)).status_code for ico, vat in (("36396567", "2020202020"), ("36396567", "sk 2020 202 020"), ("00123456", "SK2020202020"), ("123456", "SK-2020202020"))]
    ok_cz = [post(H, valid(country="cz", company_id=ico, vat_id=vat)).status_code for ico, vat in (("12345678", "CZ12345678"), ("12 34 56 78", "12345678"), ("12345678", "cz1234567890"), ("1234567", ...))]
    ok_gr = post(H, valid(country="GR", company_id="123456789", vat_id="EL123456789")).status_code
    over("G5 platne udaje projdou: SK (DIC i IC DPH, mezery a pomlcky se odstrani, ICO se doplni nulami na 8), CZ (ICO s mezerami, DIC s prefixem i bez, bez DIC), GR s prefixem EL", ok_sk == [201] * 4 and ok_cz == [201] * 4 and ok_gr == 201, (ok_sk, ok_cz, ok_gr))
    r_pad = post(H, valid(country="SK", company_id="123456", vat_id="2020202020", message="Padding"))
    msg_pad = jedno("SELECT body FROM crm_lead_messages ORDER BY id DESC LIMIT 1")["body"]
    over("G6 CRM dostane firmu, ICO (doplnene nulami na 8, ve tvaru 'IČO: 00123456', ktery CRM umi vycist pri prevodu na zakaznika) a DIC / IC DPH normalizovane (velka pismena, bez mezer); zadne z nich neni v nepersonalnim snimku miniweb_inquiries",
         r_pad.status_code == 201 and msg_pad == "Padding\n\nFirma: Acme Ltd | IČO: 00123456 | DIČ/IČ DPH: 2020202020 | Země: SK" and "company_id" not in jedno("SELECT * FROM miniweb_inquiries ORDER BY id DESC LIMIT 1")
         and not any(k in jedno("SELECT * FROM miniweb_inquiries ORDER BY id DESC LIMIT 1") for k in ("vat_id", "company_name", "ico", "dic")), msg_pad)
    SK_H = "baliace-stoly.example.top"
    sql("UPDATE miniweb_shops SET countries='SK' WHERE storefront_id=%s", (S_SK["id"],))
    r_def = post(SK_H, valid(country=..., company_id="36396567", vat_id="SK2020202020", message="Default country"))
    inq_def = jedno("SELECT country FROM miniweb_inquiries ORDER BY id DESC LIMIT 1")
    sql("UPDATE miniweb_shops SET countries='SK,CZ' WHERE storefront_id=%s", (S_SK["id"],))
    ok_dva, det_dva = odmitnuto(valid(country=..., company_id="36396567", vat_id="SK2020202020"), "country_required", "country", host=SK_H)
    sql("UPDATE miniweb_shops SET countries=NULL WHERE storefront_id=%s", (S_SK["id"],))
    ok_zadna, det_zadna = odmitnuto(valid(country=..., company_id="36396567", vat_id="SK2020202020"), "country_required", "country", host=SK_H)
    over("G7 shop s JEDINOU zemi dodani (SK) doplni zemi sam (zakaznik ji nemusi zadavat); shop s vice zememi nebo bez zemi ji vyzaduje (400 country_required)", r_def.status_code == 201 and inq_def["country"] == "SK" and ok_dva and ok_zadna, (r_def.status_code, inq_def, det_dva, det_zadna))
    sql("UPDATE miniweb_shops SET countries=NULL WHERE storefront_id=%s", (S_SK["id"],))
    pred_staff = pocty()
    staff_nahled = post("spolecna.example.org", valid(company=...), uid=admin_id, shop="packstations-draft")
    over("G8 i nahled pro staff (koncept shopu, nic se neuklada) validuje firmu: bez firmy 400 company_required, s udaji 201 preview", staff_nahled.status_code == 400 and staff_nahled.get_json()["error"] == "company_required"
         and post("spolecna.example.org", valid(), uid=admin_id, shop="packstations-draft").get_json().get("preview") is True and pocty() == pred_staff, (staff_nahled.status_code, staff_nahled.get_json()))
    over("G9 poradi chyb a nic se nezapise: nevalidni inquiry (chybi firma i ICO) nevytvori CRM poptavku ani snimek; VIES a overeni v registrech je OTEVRENY BOD (jen syntaxe)", pocty() == pred_staff and "VIES" in open(mw.__file__, encoding="utf-8").read(), pocty())

    print("== C ochrany")
    pred_ = pocty()
    orig_get_conn = mw.get_conn

    def _bez_db():
        raise AssertionError("TEST: honeypot nesmi otevrit databazi")
    mw.get_conn = _bez_db
    try:
        rr = post(H, valid(website="http://spam.example"))
        rr2 = post("neznamy.example.top", valid(website="x"))
    finally:
        mw.get_conn = orig_get_conn
    over("C1 honeypot (pole website): tvari se jako uspech (201, inquiry_id 0), nic se neulozi a nesahne se ani do databaze (ani pro neznamy host)", rr.status_code == 201 and rr.get_json() == {"status": "ok", "inquiry_id": 0} and rr2.status_code == 201 and pocty() == pred_, (rr.status_code, rr2.status_code))
    pred_ = pocty()
    r_a = post("neznamy.example.top", valid())
    r_c = post("cars.example.top", valid())
    r_d = post(DH, valid())
    r_u = post(DH, valid(), uid=uzivatele[0])
    over("C2 neznamy host, host bez mini-shopu, koncept pro anonyma i bezneho zakaznika: 404 shop_not_found a nic se neulozi", all(x.status_code == 404 and x.get_json() == {"error": "shop_not_found"} for x in (r_a, r_c, r_d, r_u)) and pocty() == pred_, [x.status_code for x in (r_a, r_c, r_d, r_u)])
    r_p = post(DH, valid(items=[{"product_id": P1, "qty": 1}]), uid=admin_id)
    r_pb = post(DH, valid(email="nope"), uid=admin_id)
    over("C3 NAHLED (shop ve stavu koncept) pro staff: poptavka se plne zvaliduje (spatny e-mail 400), ale NEULOZI se (201, inquiry_id 0, preview true) - zadna testovaci data v produkci, zadne potvrzeni ve fronte",
         r_p.status_code == 201 and r_p.get_json() == {"status": "ok", "inquiry_id": 0, "preview": True} and r_pb.status_code == 400 and pocty() == pred_, (r_p.get_json(), r_pb.status_code))
    r_o = post("off.packstations.example.top", valid())
    over("C4 shop s vypnutou poptavkou: 403 inquiry_disabled, nic se neulozi", r_o.status_code == 403 and r_o.get_json() == {"error": "inquiry_disabled"} and pocty() == pred_, r_o.status_code)
    appmod._rate_limit_buckets.clear()
    kody = [post(H, valid(), keep=True, headers={"X-Real-IP": "203.0.113.7"}).status_code for _ in range(7)]
    r_x = post(H, valid(), keep=True, headers={"X-Real-IP": "203.0.113.7"})
    r_y = post(H, valid(), keep=True, headers={"X-Real-IP": "203.0.113.99"})
    over("C5 limit 5 poptavek za 10 minut na IP: prvnich 5 projde, dalsi 429 rate_limited (nic se neulozi), jina IP neni dotcena", kody == [201] * 5 + [429] * 2 and r_x.get_json() == {"error": "rate_limited"} and r_y.status_code == 201, (kody, r_y.status_code))
    appmod._rate_limit_buckets.clear()
    same = "Same.Person@Example.com"
    kody = [post(H, valid(email=e), headers={"X-Real-IP": f"198.51.100.{i}"}).status_code for i, e in enumerate((same, same.lower(), same.upper(), same))]
    over("C6 limit 3 poptavky za den na e-mail (bez ohledu na velikost pismen) i z ruznych IP: ctvrta 429 too_many_inquiries; jiny e-mail projde", kody == [201, 201, 201, 429] and post(H, valid()).status_code == 201, kody)
    pred_ = pocty()
    orig_conf = mw._confirmation

    def _selze(ctx, name):
        raise RuntimeError("simulovana chyba pri zapisu potvrzeni")
    mw._confirmation = _selze
    try:
        with potvrzeni():
            r_f = post(H, valid(items=[{"product_id": P1, "qty": 1}]))
    finally:
        mw._confirmation = orig_conf
    over("C7 ATOMICITA (potvrzeni zapnute): kdyz selze posledni krok (potvrzeni), neulozi se NIC (zadny lead, zprava, snimek ani polozka) a klient dostane 500 internal_error bez podrobnosti", r_f.status_code == 500 and r_f.get_json() == {"error": "internal_error"} and pocty() == pred_, (r_f.status_code, pocty(), pred_))

    # ============================================================================================================ D) texty
    print("== D texty")
    pred_ = pocty()
    nasty = valid(name="Robert'); DROP TABLE crm_leads;--", message="<script>alert(1)</script>Hello <b>there</b>\r\n\r\n\r\n\r\nLine &amp; two\x00\x07 <img src=x onerror=alert(1)>", company="<i>Acme</i>")
    with potvrzeni():
        rr = post(H, nasty)
    lead = jedno("SELECT * FROM crm_leads ORDER BY id DESC LIMIT 1")
    msg = jedno("SELECT * FROM crm_lead_messages ORDER BY id DESC LIMIT 1")
    over("D1 SQL znaky se ulozi doslova (parametrizovane dotazy, tabulka zustala), HTML a skripty a ridici znaky z jmena, zpravy i firmy pryc",
         rr.status_code == 201 and lead["contact_name"] == "Robert'); DROP TABLE crm_leads;--" and jedno("SELECT COUNT(*) AS n FROM crm_leads")["n"] > 0 and lead["company_name"] == "Acme"
         and msg["body"] == "Hello there\n\nLine & two\n\nFirma: Acme | IČO: 6388047 | DIČ/IČ DPH: IE6388047V | Země: IE" and "<" not in msg["body"] and "alert" not in msg["body"] and "\x00" not in msg["body"], (lead["contact_name"], msg["body"]))
    em = jedno("SELECT * FROM system_emails ORDER BY id DESC LIMIT 1")
    over("D2 potvrzeni nenese nic z textu zpravy, jen jmeno a domenu (zadne HTML ani cizi vstup mimo jmeno)", "alert" not in em["body_text"] and "DROP TABLE" in em["body_text"] and em["body_text"].count("\n") == 6 and "<" not in em["body_text"], em["body_text"])
    price_rows = json.dumps(sql("SELECT * FROM crm_leads") + sql("SELECT * FROM crm_lead_messages") + sql("SELECT * FROM miniweb_inquiries") + sql("SELECT * FROM miniweb_inquiry_items") + sql("SELECT * FROM system_emails"), default=str)
    over("D3 klient poslal ceny navic (price, unit_net, total) - v zadne zapisovane tabulce neni zadna z podvrzenych cen (9999)", "9999" not in price_rows, None)
    pred_ = pocty()
    with potvrzeni():
        r_de = post("packstationen.example.top", valid(items=[{"product_id": P1, "qty": 1}, {"product_id": P5, "qty": 1}]))
    inq = jedno("SELECT * FROM miniweb_inquiries ORDER BY id DESC LIMIT 1")
    it_de = sql("SELECT product_name FROM miniweb_inquiry_items WHERE inquiry_id=%s ORDER BY id", (inq["id"],))
    po = pocty()
    over("D4 nemecky shop: poptavka se ulozi (nazvy z nemeckych textu, jazyk de), ale potvrzeni se NEZAKLADA (pro jazyk neni schvalena sablona), system_email_id je NULL",
         r_de.status_code == 201 and inq["lang"] == "de" and inq["system_email_id"] is None and [x["product_name"] for x in it_de] == ["Packstation PS-120", "Nur Deutsch"] and po["system_emails"] == pred_["system_emails"], (r_de.status_code, inq, it_de))
    with potvrzeni():
        r_ie = post("ie.packstations.example.top", valid())
    em = jedno("SELECT * FROM system_emails ORDER BY id DESC LIMIT 1")
    over("D5 regionalni anglictina (en-ie) pouzije anglickou sablonu a snimek drzi jazyk en-ie", r_ie.status_code == 201 and em["subject"] == "Inquiry received" and jedno("SELECT lang FROM miniweb_inquiries ORDER BY id DESC LIMIT 1")["lang"] == "en-ie", None)
    with potvrzeni():
        r_br = post("logiman-shop.example.top", valid())
    em = jedno("SELECT * FROM system_emails ORDER BY id DESC LIMIT 1")
    over("D6 domena se znackou se v potvrzeni NEPISE (misto ni 'our website')", r_br.status_code == 201 and "via our website." in em["body_text"] and not BRAND.search(em["subject"] + em["body_text"]), em["body_text"])
    vse = sql("SELECT subject, body_text FROM system_emails")
    over("D7 zadne potvrzeni ve fronte nenese znacku a vsechna jsou pending (nic nebylo odeslano, send_email ani smtplib se nezavolaly)", all(not BRAND.search(x["subject"] + x["body_text"]) for x in vse) and not ODESLANO
         and all(x["status"] == "pending" for x in sql("SELECT status FROM system_emails")), ODESLANO)

    # ============================================================================================================ M) mutace
    print("== M mutace klicovych ochran")
    zdroj = open(mw.__file__, encoding="utf-8").read()

    def mutant(funkce, stare, nove, n=1):
        node = next(n_ for n_ in ast.parse(zdroj).body if isinstance(n_, ast.FunctionDef) and n_.name == funkce)
        src = ast.get_source_segment(zdroj, node)
        assert src.count(stare) == n, f"{funkce}: '{stare}' nalezeno {src.count(stare)}x, ocekavano {n}x"
        ns = dict(vars(mw))
        exec(src.replace(stare, nove), ns)
        return ns[funkce]

    def s_pohledem(funkce, stare, nove, akce):
        vf = appmod.app.view_functions["miniweb_inquiry"]
        appmod.app.view_functions["miniweb_inquiry"] = mw._guard(mutant(funkce, stare, nove))
        try:
            return akce()
        finally:
            appmod.app.view_functions["miniweb_inquiry"] = vf

    pred_ = pocty()
    r_m = s_pohledem("miniweb_inquiry", 'if body.get("consent") is not True:', "if False:", lambda: post(H, valid(consent=...)))
    over("M1 mutace: bez kontroly souhlasu by se poptavka ulozila (spravne 400) - testy B5 ji zachyti", r_m.status_code == 201 and pocty() != pred_, r_m.status_code)
    pred_ = pocty()
    r_m = s_pohledem("miniweb_inquiry", "if not ctx[\"live\"]:", "if False:", lambda: post(DH, valid(), uid=admin_id))
    over("M2 mutace: bez ochrany nahledu by staff ulozil testovaci poptavku do produkce (spravne nic) - test C3 ji zachyti", r_m.status_code == 201 and pocty() != pred_, r_m.status_code)
    pred_ = pocty()
    r_m = s_pohledem("miniweb_inquiry", 'if body.get("website"):', "if False:", lambda: post(H, valid(website="spam")))
    over("M3 mutace: bez honeypotu by robot vytvoril poptavku - test C1 ji zachyti", r_m.status_code == 201 and pocty() != pred_, r_m.status_code)
    appmod._rate_limit_buckets.clear()
    r_m = s_pohledem("miniweb_inquiry", "if cur.fetchone()[\"n\"] >= INQUIRY_LIMIT_PER_EMAIL_DAY:", "if False:",
                     lambda: [post(H, valid(email="mut.limit@example.com"), headers={"X-Real-IP": f"192.0.2.{i}"}).status_code for i in range(5)])
    over("M4 mutace: bez limitu na e-mail by prosel i 4. a 5. pokus (spravne 429) - test C6 ji zachyti", r_m == [201] * 5, r_m)
    mw_items = mw._inquiry_items
    mw._inquiry_items = mutant("_inquiry_items", '"product_name": p["name"]', '"product_name": it.get("name") or p["name"]')
    try:
        r_m = post(H, valid(items=[{"product_id": P1, "qty": 1, "name": "Falesny nazev"}]))
        pn = jedno("SELECT product_name FROM miniweb_inquiry_items ORDER BY id DESC LIMIT 1")["product_name"]
    finally:
        mw._inquiry_items = mw_items
    over("M5 mutace: kdyby se nazev bral od klienta, ulozil by se falesny (spravne z databaze) - test A6 ji zachyti", pn == "Falesny nazev", pn)
    mw._inquiry_items = mutant("_inquiry_items", "p = visible_by_id.get(pid)", 'p = visible_by_id.get(pid) or {"sku": "X", "name": "Y"}')
    try:
        r_m = post(H, valid(items=[{"product_id": P2, "qty": 1}]))
    finally:
        mw._inquiry_items = mw_items
    over("M6 mutace: bez kontroly viditelnosti by prosla poptavka na produkt s konceptem textu (spravne 400) - test B7 ji zachyti", r_m.status_code == 201, r_m.status_code)
    mw_plain = mw._plain
    mw._plain = lambda value, limit, multiline=False: ("" if value is None else str(value))[:limit]
    try:
        post(H, valid(message="<script>alert(1)</script>Hi"))
        body_m = jedno("SELECT body FROM crm_lead_messages ORDER BY id DESC LIMIT 1")["body"]
    finally:
        mw._plain = mw_plain
    over("M7 mutace: bez cisteni textu by se do CRM ulozilo HTML ze zpravy (spravne ne) - test D1 ji zachyti", "<script>" in body_m, body_m)
finally:
    with real.cursor() as cur:
        for t in TEMP_LIKE + tuple(f"_tpl_{x}" for x in TEMP_LIKE):
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `{t}`")
    real.commit()

po = stav_ostrych()
over("ostre tabulky (poptavky, CRM, fronta e-mailu, zakaznici, mini-shopy, storefronty, audit) jsou po testu beze zmeny", po == PRED_OSTRE, (PRED_OSTRE, po))
ok = sum(vysl)
print(f"\nVYSLEDEK mini-shop faze 2 - poptavka POST /api/miniweb/inquiry: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
