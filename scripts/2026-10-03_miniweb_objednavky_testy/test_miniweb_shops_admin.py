#!/opt/konfigurator/api/venv/bin/python
"""Admin API Mini-shopy (bot5, 2026-10-03): api/miniweb_shops_admin.py + RBAC sekce `miniweb` a `miniweb_schvalovani` (patche adm_app.py.patch, adm_miniweb_admin.py.patch).
Skutecne routy pres Flask test client nad DOCASNYMI tabulkami; kandidati app.py a miniweb_admin.py (kopie zivych souboru s patchem ze sady, nebo uz patchnute zive); role manager se vytvori jen v docasne kopii app_users.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-03_miniweb_objednavky_testy/test_miniweb_shops_admin.py"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
API = os.path.join(REPO, "api")
KIT = os.path.join(HERE, "nasazeni")
tmp = tempfile.mkdtemp(prefix="kand_mw_admin_")
TAPI = os.path.join(tmp, "api")
os.makedirs(TAPI)
KAND = {"app.py", "miniweb_admin.py", "miniweb_shops_admin.py"}
for f in os.listdir(API):
    if f not in KAND and f not in ("__pycache__", "venv"):
        os.symlink(os.path.join(API, f), os.path.join(TAPI, f))
for d in ("webapp", "private-files", "katalog", "scripts", "sql", "docs", "backups"):
    if os.path.exists(os.path.join(REPO, d)):
        os.symlink(os.path.join(REPO, d), os.path.join(tmp, d))
os.symlink(os.path.join(REPO, "DEPLOY_LOCK.json"), os.path.join(tmp, "DEPLOY_LOCK.json"))
for f, patch, marker in (("app.py", "adm_app.py.patch", "miniweb_schvalovani"), ("miniweb_admin.py", "adm_miniweb_admin.py.patch", "miniweb_schvalovani")):
    shutil.copy(os.path.join(API, f), os.path.join(TAPI, f))
    if marker not in open(os.path.join(API, f), encoding="utf-8").read():
        subprocess.run(["patch", "-p1", "-s", "-d", tmp, "-i", os.path.join(KIT, patch)], check=True)
shutil.copy(os.environ.get("MINIWEB_SHOPS_ADMIN_PY") or os.path.join(API, "miniweb_shops_admin.py"), os.path.join(TAPI, "miniweb_shops_admin.py"))
sys.path.insert(0, TAPI)

import pymysql  # noqa: E402
import app as appmod  # noqa: E402
import miniweb_shops_admin as msa  # noqa: E402
from flask.sessions import SecureCookieSessionInterface  # noqa: E402

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:500]))


AUDIT = []
msa.log_audit = lambda *a, **k: AUDIT.append((a, k))
import miniweb_admin as ma  # noqa: E402
ma.log_audit = lambda *a, **k: AUDIT.append((a, k))


def ostre():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                           port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


TABS = ("miniweb_shops", "car_storefronts", "miniweb_inquiries", "miniweb_inquiry_items", "crm_leads", "shop_orders", "role_permissions", "app_users",
        "miniweb_categories", "miniweb_category_texts", "miniweb_products", "miniweb_product_texts", "miniweb_documents")      # approve/unapprove sahaji na texty: MUSI byt docasne (zivy text 2026-10-03 11:43 vracen do draftu)


def stav():
    c = ostre()
    try:
        with c.cursor() as cur:
            out = {}
            for t in TABS:
                cur.execute(f"SELECT COUNT(*) AS n FROM `{t}`")
                out[t] = cur.fetchone()["n"]
            cur.execute("SELECT COALESCE(SUM(role='manager'),0) AS m FROM app_users")
            out["managers"] = int(cur.fetchone()["m"])
            for t, idc in (("miniweb_category_texts", "miniweb_category_id"), ("miniweb_product_texts", "miniweb_product_id"), ("miniweb_documents", "id")):
                cur.execute(f"SELECT {idc} AS i, lang, status, approved_by, updated_at FROM {t} ORDER BY 1, 2")
                out["stav_" + t] = [tuple(str(v) for v in r.values()) for r in cur.fetchall()]      # stav schvaleni zivych textu se testem NIKDY nesmi zmenit
            return out
    finally:
        c.close()


PRED = stav()
wrap = appmod.get_conn()
real = object.__getattribute__(wrap, "_real")


def sql(q, params=None):
    with real.cursor() as cur:
        cur.execute(q, params or ())
        out = cur.fetchall() if q.lstrip().upper().startswith(("SELECT", "SHOW")) else cur.rowcount
    real.commit()
    return out


def jedno(q, params=None):
    r = sql(q, params)
    return r[0] if r else None


try:
    with real.cursor() as cur:
        for t in TABS:
            cur.execute(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`")
            cur.execute(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")
            cur.execute(f"SHOW CREATE TABLE `{t}`")
            assert list(cur.fetchone().values())[1].startswith("CREATE TEMPORARY TABLE"), f"ABORT: {t} neni docasna"
    real.commit()
    # app_users: docasna kopie s jednim adminem a jednou rolí manager (z bezneho uzivatele); skutecna tabulka se nemeni
    c0 = ostre()
    try:
        with c0.cursor() as cur0:
            cur0.execute("SELECT * FROM app_users WHERE active=1 AND role IN ('admin','user') ORDER BY role, id")
            radky = cur0.fetchall()
    finally:
        c0.close()
    adm_r = next(r for r in radky if r["role"] == "admin")
    usr_r = [r for r in radky if r["role"] == "user"][:2]
    for r in [adm_r] + usr_r:
        sql(f"INSERT INTO app_users ({', '.join(r)}) VALUES ({', '.join(['%s'] * len(r))})", list(r.values()))
    ADMIN, MGR, USR = adm_r["id"], usr_r[0]["id"], usr_r[1]["id"]
    sql("UPDATE app_users SET role='manager' WHERE id=%s", (MGR,))

    sql("INSERT INTO car_storefronts (name, slug, primary_domain, status, lang) VALUES ('Baliace stoly (SK)','packstations-sk','sk.example.top','live','sk'),('Packstations (EN)','packstations-en','en.example.top','draft','en')")
    S1 = jedno("SELECT id FROM car_storefronts WHERE slug='packstations-sk'")["id"]
    S2 = jedno("SELECT id FROM car_storefronts WHERE slug='packstations-en'")["id"]
    sql("INSERT INTO miniweb_shops (storefront_id, family, price_mode, currency, countries, inquiry_enabled, orders_enabled, margin_pct, eur_rate, contact_json) VALUES "
        "(%s,'packstations','shown','EUR','SK',1,0,0,NULL,'{\"use_company\": true, \"hours\": \"Po-Pi 9-17\"}'),(%s,'packstations','hidden','EUR','IE,GB',1,0,NULL,NULL,NULL)", (S1, S2))
    sql("INSERT INTO crm_leads (contact_name, contact_email, contact_phone, company_name, subject, source, unread_by_admin) VALUES ('Ján','jan@firma.test','+421900','Firma s.r.o.','Poptávka','miniweb',1)")
    lead = jedno("SELECT id FROM crm_leads")["id"]
    sql("INSERT INTO miniweb_inquiries (storefront_id, shop_host, lang, crm_lead_id, country, consent_at) VALUES (%s,'sk.example.top','sk',%s,'SK',NOW())", (S1, lead))
    sql("INSERT INTO shop_orders (order_number, status, delivery_state, billing_state, customer_name, customer_email, total_czk, storefront_id, order_host, order_lang, shipping_review, vat_mode, vat_check, billing_name, billing_ico) "
        "VALUES ('OBJ-1','nova','nova','nevyfakturovano','Ján','jan@firma.test',53400,%s,'sk.example.top','sk',1,'standard','none','Firma s.r.o.','12345678'),"
        "('OBJ-2','nova','nova','nevyfakturovano','Ján','jan@firma.test',100,%s,NULL,NULL,0,NULL,NULL,'X','1')", (S1, S1))
    sql("INSERT INTO role_permissions (role, section, action, allowed) VALUES ('manager','miniweb','zobrazit',1)")

    _si = SecureCookieSessionInterface()
    cl = appmod.app.test_client(use_cookies=False)

    def vol(metoda, cesta, uid, body=None):
        appmod._rate_limit_buckets.clear()
        h = {"Cookie": "session=" + _si.get_signing_serializer(appmod.app).dumps({"user_id": uid})} if uid else {}
        return cl.open(cesta, method=metoda, headers=h, json=body) if body is not None else cl.open(cesta, method=metoda, headers=h)

    # ---- RBAC
    over("R1 sekce miniweb a miniweb_schvalovani jsou v PERMISSION_SECTIONS (jinak by se modul nenacetl)", "miniweb" in appmod.PERMISSION_SECTIONS and "miniweb_schvalovani" in appmod.PERMISSION_SECTIONS, None)
    r_admin, r_mgr, r_mgr_put, r_usr, r_anon = (vol("GET", "/api/admin/miniweb/shops", ADMIN), vol("GET", "/api/admin/miniweb/shops", MGR), vol("PUT", f"/api/admin/miniweb/shops/{S1}", MGR, {"margin_pct": 5}),
                                                vol("GET", "/api/admin/miniweb/shops", USR), vol("GET", "/api/admin/miniweb/shops", None))
    over("R2 admin vidi vzdy; manager s pravem miniweb/zobrazit vidi, ale PUT (upravit) nema pravo 403; zakaznik 403, anonym 401", r_admin.status_code == 200 and r_mgr.status_code == 200 and r_mgr_put.status_code == 403
         and r_usr.status_code == 403 and r_anon.status_code == 401, [x.status_code for x in (r_admin, r_mgr, r_mgr_put, r_usr, r_anon)])
    sql("DELETE FROM role_permissions")
    r_nogrant = vol("GET", "/api/admin/miniweb/shops", MGR)
    ov0 = vol("GET", "/api/admin/miniweb/overview", MGR)
    over("R3 manager bez grantu: shopy 403, schvalovani (overview) 403 - fail closed, sekce se nededuji", r_nogrant.status_code == 403 and ov0.status_code == 403, (r_nogrant.status_code, ov0.status_code))
    sql("INSERT INTO role_permissions (role, section, action, allowed) VALUES ('manager','miniweb_schvalovani','zobrazit',1)")
    ov1 = vol("GET", "/api/admin/miniweb/overview", MGR)
    ap1 = vol("POST", "/api/admin/miniweb/approve", MGR, {"items": [{"kind": "product", "id": 1, "lang": "sk", "rev": "0" * 16}]})
    sql("INSERT INTO role_permissions (role, section, action, allowed) VALUES ('manager','miniweb_schvalovani','upravit',1)")
    ap2 = vol("POST", "/api/admin/miniweb/approve", MGR, {"items": [{"kind": "product", "id": 1, "lang": "sk", "rev": "0" * 16}]})
    ap_admin = vol("POST", "/api/admin/miniweb/unapprove", ADMIN, {"items": [{"kind": "product", "id": 1, "lang": "sk"}]})
    over("R4 schvalovani: overview jen s miniweb_schvalovani/zobrazit, approve vyzaduje upravit (bez nej 403, s nim projde na vlastni validaci), admin vzdy", ov1.status_code == 200 and ap1.status_code == 403 and ap2.status_code in (200,)
         and ap_admin.status_code == 200, (ov1.status_code, ap1.status_code, ap2.status_code, ap_admin.status_code))
    sql("DELETE FROM role_permissions")
    sql("INSERT INTO role_permissions (role, section, action, allowed) VALUES ('manager','miniweb','zobrazit',1),('manager','miniweb','upravit',1)")

    # ---- GET shops
    d = vol("GET", "/api/admin/miniweb/shops", ADMIN).get_json()["shops"]
    by = {x["slug"]: x for x in d}
    sk = by["packstations-sk"]
    over("S1 seznam shopu: domena, jazyk, stav, cena (mode, mena, marze, ruzny kurz = Fio), zeme jako pole, poptavky a objednavky zapnute, kontakt, pocty (poptavky 1, objednavky z mini-shopu 1, ke schvaleni 1)",
         sk["domain"] == "sk.example.top" and sk["lang"] == "sk" and sk["status"] == "live" and sk["price_mode"] == "shown" and sk["currency"] == "EUR" and sk["margin_pct"] == 0.0 and sk["eur_rate"] is None
         and sk["rate_source"] == "fio" and sk["countries"] == ["SK"] and sk["inquiry_enabled"] is True and sk["orders_enabled"] is False and sk["contact"] == {"phone": "", "hours": "Po-Pi 9-17", "use_company": True}
         and sk["inquiries"] == 1 and sk["orders"] == 1 and sk["orders_to_review"] == 1 and by["packstations-en"]["margin_pct"] is None and by["packstations-en"]["countries"] == ["IE", "GB"], sk)

    # ---- PUT shops
    def put(sid, body, uid=ADMIN):
        return vol("PUT", f"/api/admin/miniweb/shops/{sid}", uid, body)

    r = put(S1, {"margin_pct": 7.5, "eur_rate": 24.5})
    sk2 = r.get_json()["shop"]
    row = jedno("SELECT * FROM miniweb_shops WHERE storefront_id=%s", (S1,))
    over("P1 uprava marze a rucniho kurzu: ulozeno (7,50 %, 24,5000), v odpovedi rate_source manual, auditovano", r.status_code == 200 and float(row["margin_pct"]) == 7.5 and float(row["eur_rate"]) == 24.5 and sk2["rate_source"] == "manual"
         and sk2["margin_pct"] == 7.5 and any(a[0][2] == "miniweb_shop" for a in AUDIT), (r.status_code, r.get_json()))
    r = put(S1, {"eur_rate": None})
    over("P2 eur_rate null = zpet na zivy kurz Fio", r.status_code == 200 and jedno("SELECT eur_rate FROM miniweb_shops WHERE storefront_id=%s", (S1,))["eur_rate"] is None and r.get_json()["shop"]["rate_source"] == "fio", r.get_json())
    r_s = put(S1, {"contact": {"phone": "+421 900", "use_company": False}})
    c_ = jedno("SELECT contact_json FROM miniweb_shops WHERE storefront_id=%s", (S1,))["contact_json"]
    over("P3 kontakt se sloucuje (telefon, doba zustava, use_company vypnuto)", r_s.status_code == 200 and r_s.get_json()["shop"]["contact"] == {"phone": "+421 900", "hours": "Po-Pi 9-17", "use_company": False} and "use_company" not in c_, (r_s.get_json(), c_))
    zlo = {"unknown_field": {"status": "live"}, "price_mode_invalid": {"price_mode": "free"}, "margin_pct_invalid": {"margin_pct": -1}, "margin_pct_invalid2": {"margin_pct": "abc"}, "eur_rate_invalid": {"eur_rate": 0},
           "countries_invalid": {"countries": ["SKX"]}, "inquiry_enabled_invalid": {"inquiry_enabled": "ano"}, "accent_invalid": {"accent": "red"}, "contact_invalid": {"contact": {"email": "a@b.c"}},
           "contact_invalid2": {"contact": {"phone": "<b>"}}, "currency_invalid": {"currency": "eur"}}
    odp = {k: put(S1, b) for k, b in zlo.items()}
    over("P4 validace: neznamy klic (vc. status), mod ceny, marze mimo rozsah, kurz 0, zeme, bool, barva, e-mail v kontaktu, znacky, mena = 400 se svym kodem a pole, nic se nezmeni",
         all(r_.status_code == 400 and r_.get_json()["error"] == k.rstrip("2") for k, r_ in odp.items()) and jedno("SELECT margin_pct FROM miniweb_shops WHERE storefront_id=%s", (S1,))["margin_pct"] == 7.5
         and jedno("SELECT status FROM car_storefronts WHERE id=%s", (S1,))["status"] == "live", {k: (r_.status_code, r_.get_json()) for k, r_ in odp.items() if r_.status_code != 400 or r_.get_json()["error"] != k.rstrip("2")})
    r_g = put(S2, {"orders_enabled": True})
    r_g2 = put(S1, {"orders_enabled": True})
    r_g3 = put(S1, {"price_mode": "hidden", "orders_enabled": True})
    over("P5 objednavky jdou zapnout jen s kompletni cenou (shown + EUR + marze): koncept bez ceny 422 price_not_configured, shop s cenou projde, hidden + zapnuti zaroven 422",
         r_g.status_code == 422 and r_g.get_json()["error"] == "price_not_configured" and r_g2.status_code == 200 and r_g2.get_json()["shop"]["orders_enabled"] is True and r_g3.status_code == 422
         and jedno("SELECT price_mode, orders_enabled FROM miniweb_shops WHERE storefront_id=%s", (S1,)) == {"price_mode": "shown", "orders_enabled": 1}, (r_g.get_json(), r_g3.get_json()))
    # S1 ma ted zapnute objednavky: zmena ceny po zapnuti nesmi rozbit objednavky (externi revize #8) a ceny se nikdy neskryvaji (#3)
    r_h1, r_h2, r_h3 = put(S1, {"price_mode": "hidden"}), put(S1, {"margin_pct": None}), put(S1, {"currency": "CZK"})
    r_ok = put(S1, {"margin_pct": 2})
    over("P5b u SHOPU SE ZAPNUTYMI OBJEDNAVKAMI nejde skryt cenu, smazat marzi ani zmenit menu (422 price_not_configured, nic se nezmeni); zmena marze na platnou hodnotu projde",
         all(r_.status_code == 422 and r_.get_json()["error"] == "price_not_configured" for r_ in (r_h1, r_h2, r_h3)) and r_ok.status_code == 200
         and jedno("SELECT price_mode, currency, margin_pct FROM miniweb_shops WHERE storefront_id=%s", (S1,))["price_mode"] == "shown", [x.get_json() for x in (r_h1, r_h2, r_h3)])
    put(S1, {"orders_enabled": False})
    r_pol = put(S1, {"price_mode": "hidden"})
    over("P5c shop ve stavu LIVE nesmi mit skryte ceny ani bez objednavek (Robert 2026-10-03: ceny se nikdy neskryvaji): 422 price_policy; koncept (draft) skryte ceny smi", r_pol.status_code == 422 and r_pol.get_json()["error"] == "price_policy"
         and put(S2, {"price_mode": "indicative"}).status_code == 200, r_pol.get_json())
    put(S1, {"orders_enabled": True})
    r404, r_empty, r_form = put(99999, {"margin_pct": 1}), put(S1, {}), cl.put(f"/api/admin/miniweb/shops/{S1}", data="x=1", headers={"Cookie": "session=" + _si.get_signing_serializer(appmod.app).dumps({"user_id": ADMIN})})
    over("P6 neexistujici shop 404, prazdne telo a formular 400", r404.status_code == 404 and r_empty.status_code == 400 and r_form.status_code == 400, (r404.status_code, r_empty.status_code, r_form.status_code))
    r_m = put(S1, {"margin_pct": 3}, MGR)
    over("P7 manager s pravem upravit smi menit (200)", r_m.status_code == 200, r_m.get_json())

    # ---- inquiries / orders
    qi = vol("GET", f"/api/admin/miniweb/inquiries?shop={S1}", MGR).get_json()
    qo = vol("GET", f"/api/admin/miniweb/orders?shop={S1}", MGR).get_json()
    over("L1 poptavky: celkem 1, kontakt firmy a pocet polozek, nepřečtená; bez textu zpravy", qi["total"] == 1 and qi["inquiries"][0]["company"] == "Firma s.r.o." and qi["inquiries"][0]["unread"] is True and "message" not in qi["inquiries"][0], qi)
    over("L2 objednavky shopu jen z mini-shopu (order_host), kompaktne s puvodem, kontrolou DPH a priznakem ke schvaleni (hlavni e-shop objednavka OBJ-2 tu neni)",
         qo["total"] == 1 and qo["orders"][0]["order_number"] == "OBJ-1" and qo["orders"][0]["origin_label"] == "sk.example.top · sk" and qo["orders"][0]["shipping_review"] == 1 and qo["orders"][0]["company_id"] == "12345678", qo)
    bad = [vol("GET", u, ADMIN).status_code for u in ("/api/admin/miniweb/inquiries", "/api/admin/miniweb/orders?shop=abc", f"/api/admin/miniweb/orders?shop={S1}&limit=x")]
    over("L3 chybny nebo chybejici parametr shop/limit = 400", bad == [400, 400, 400], bad)
    over("L4 anonym a zakaznik nevidi poptavky ani objednavky", vol("GET", f"/api/admin/miniweb/orders?shop={S1}", None).status_code == 401 and vol("GET", f"/api/admin/miniweb/inquiries?shop={S1}", USR).status_code == 403, None)
finally:
    with real.cursor() as cur:
        for t in TABS:
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `{t}`")
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `_tpl_{t}`")
    real.commit()
over("ostre tabulky (shopy, storefronty, poptavky, CRM, objednavky, role_permissions, uzivatele) beze zmeny", stav() == PRED, (PRED, stav()))
ok = sum(vysl)
print(f"\nVYSLEDEK admin API Mini-shopy: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
