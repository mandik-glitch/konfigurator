#!/opt/konfigurator/api/venv/bin/python
"""Online nabidka z konfigurace stolu - backend (bot5, 2026-10-06): api/nabidka_z_konfigurace.py + patch scene_offers.py (zachovani snimku pri uprave, verejny JSON bez soukrome casti)
+ import v app.py. SKUTECNE routy pres Flask test client nad DOCASNYMI tabulkami (zadny zapis do zive DB, zadny soubor do zivych slozek, zadny e-mail).
Kandidati: KAND_DIR=/cesta (slozka s nabidka_z_konfigurace.py, scene_offers.py, app.py) nebo zive soubory v api/.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-06_nabidka_z_konfigurace_testy/test_nabidka_z_konfigurace.py
"""
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
API = os.path.join(REPO, "api")
KAND_DIR = os.environ.get("KAND_DIR")
tmp = tempfile.mkdtemp(prefix="kand_nabidka_konf_")
TAPI = os.path.join(tmp, "api")
os.makedirs(TAPI)
KAND = {"app.py", "scene_offers.py", "orders.py", "nabidka_z_konfigurace.py"}
for f in os.listdir(API):
    if f not in KAND and f not in ("__pycache__", "venv"):
        os.symlink(os.path.join(API, f), os.path.join(TAPI, f))
for d in ("webapp", "private-files", "katalog", "scripts", "sql", "docs", "backups"):
    if os.path.exists(os.path.join(REPO, d)):
        os.symlink(os.path.join(REPO, d), os.path.join(tmp, d))
os.symlink(os.path.join(REPO, "DEPLOY_LOCK.json"), os.path.join(tmp, "DEPLOY_LOCK.json"))
for f in KAND:
    src = os.path.join(KAND_DIR, f) if KAND_DIR and os.path.exists(os.path.join(KAND_DIR, f)) else os.path.join(API, f)
    if os.path.exists(src):
        shutil.copy(src, os.path.join(TAPI, f))
sys.path.insert(0, TAPI)

import pymysql  # noqa: E402
import app as appmod  # noqa: E402
from flask.sessions import SecureCookieSessionInterface  # noqa: E402

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:600]))


if not os.path.exists(os.path.join(TAPI, "nabidka_z_konfigurace.py")):
    over("0 existuje api/nabidka_z_konfigurace.py (kandidat nebo zivy)", False, "chybi")
    print(f"\nVYSLEDEK nabidka z konfigurace: 0/{len(vysl)} OK")
    sys.exit(1)
import nabidka_z_konfigurace as nz  # noqa: E402
import scene_offers as so  # noqa: E402
import konfigurace_kosik as kk  # noqa: E402
import orders as ordersmod  # noqa: E402
import stul_shop  # noqa: E402

AUDIT = []
nz.log_audit = lambda *a, **k: AUDIT.append((a, k))
so.log_audit = lambda *a, **k: AUDIT.append((a, k))
so.OFFER_MODELS_DIR = tempfile.mkdtemp(prefix="kand_nabidka_modely_")          # nic do zivych slozek private-files
so.OFFER_IMAGES_DIR = tempfile.mkdtemp(prefix="kand_nabidka_obrazky_")
so.DRIVE_FILES_DIR = tempfile.mkdtemp(prefix="kand_nabidka_drive_")
real = appmod.get_conn()
TABS = ("scene_offers", "scene_offer_revisions", "scene_offer_order_prefs", "shared_drive_folders", "shared_drive_files", "crm_quote_sequence", "app_settings",
        "role_permissions", "app_users", "shop_orders", "shop_order_items", "shop_order_status_history", "shop_order_number_sequence", "shop_order_number_released")


def ostre():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                           port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


def sql(q, params=None):
    with real.cursor() as cur:
        cur.execute(q, params or ())
        out = cur.fetchall() if q.lstrip().upper().startswith(("SELECT", "SHOW")) else cur.rowcount
    real.commit()
    return out


def jedno(q, params=None):
    r = sql(q, params)
    return r[0] if r else None


def kopie_z_ostre(tabulka, kde=""):
    c0 = ostre()
    try:
        with c0.cursor() as cur0:
            cur0.execute(f"SELECT * FROM `{tabulka}` {kde}")
            return cur0.fetchall()
    finally:
        c0.close()


try:
    with real.cursor() as cur:
        for t in TABS:
            cur.execute(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`")
            cur.execute(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")
            cur.execute(f"SHOW CREATE TABLE `{t}`")
            assert list(cur.fetchone().values())[1].startswith("CREATE TEMPORARY TABLE"), f"ABORT: {t} neni docasna"
    real.commit()
    for r in kopie_z_ostre("app_settings"):
        sql(f"INSERT INTO app_settings ({', '.join(r)}) VALUES ({', '.join(['%s'] * len(r))})", list(r.values()))
    sql("DELETE FROM app_settings WHERE setting_key='stul_montaz_pct'")            # vychozi sazba stolu = 12 (kod), at test nezavisi na zive hodnote
    sql("INSERT INTO crm_quote_sequence (id, next_number) VALUES (1, 5000)")
    for r in kopie_z_ostre("shop_order_number_sequence"):
        sql(f"INSERT INTO shop_order_number_sequence ({', '.join(r)}) VALUES ({', '.join(['%s'] * len(r))})", list(r.values()))
    radky = kopie_z_ostre("app_users", "WHERE active=1 AND role IN ('admin','user') ORDER BY role, id")
    adm_r = next(r for r in radky if r["role"] == "admin")
    usr_r = [r for r in radky if r["role"] == "user"][:2]
    for r in [adm_r] + usr_r:
        sql(f"INSERT INTO app_users ({', '.join(r)}) VALUES ({', '.join(['%s'] * len(r))})", list(r.values()))
    ADMIN, MGR, USR = adm_r["id"], usr_r[0]["id"], usr_r[1]["id"]
    sql("UPDATE app_users SET role='manager' WHERE id=%s", (MGR,))
    sql("INSERT INTO role_permissions (role, section, action, allowed) VALUES ('manager','nabidky','vytvorit',1)")

    _si = SecureCookieSessionInterface()
    cl = appmod.app.test_client(use_cookies=False)

    def cookie(uid):
        return {"Cookie": "session=" + _si.get_signing_serializer(appmod.app).dumps({"user_id": uid})} if uid else {}

    def vol(metoda, cesta, uid, body=None):
        appmod._rate_limit_buckets.clear()
        h = cookie(uid)
        return cl.open(cesta, method=metoda, headers=h, json=body) if body is not None else cl.open(cesta, method=metoda, headers=h)

    URL = "/api/admin/konfigurace/nabidka"
    over("A0 modul je registrovany v app.py (import) - jinak by endpoint neexistoval", any(r.rule == URL for r in appmod.app.url_map.iter_rules()), None)

    # ------------------------------------------------------------------------------------------------------------------------- RBAC a sonda
    r_adm, r_mgr, r_usr, r_anon = vol("GET", URL, ADMIN), vol("GET", URL, MGR), vol("GET", URL, USR), vol("GET", URL, None)
    over("R1 sonda: admin a manager s pravem nabidky/vytvorit 200 {ok, verze:1}; zakaznik 403; anonym 401", r_adm.status_code == 200 and r_adm.get_json() == {"ok": True, "verze": 1}
         and r_mgr.status_code == 200 and r_usr.status_code == 403 and r_anon.status_code == 401, [x.status_code for x in (r_adm, r_mgr, r_usr, r_anon)])
    sql("DELETE FROM role_permissions")
    sql("INSERT INTO role_permissions (role, section, action, allowed) VALUES ('manager','nabidky','zobrazit',1)")
    cfg0 = {"product_id": 4934, "configuration": {"selection": stul_shop.vychozi_vyber(30), "rules_version": None}}
    r_zobr = vol("GET", URL, MGR)
    r_zobr_post = vol("POST", URL, MGR, cfg0)
    over("R2 manager jen s pravem nabidky/zobrazit: sonda i POST 403 (vytvorit je samostatne pravo), zadna nabidka nevznikla", r_zobr.status_code == 403 and r_zobr_post.status_code == 403
         and jedno("SELECT COUNT(*) n FROM scene_offers")["n"] == 0, (r_zobr.status_code, r_zobr_post.status_code))
    r_anon_post, r_usr_post = vol("POST", URL, None, cfg0), vol("POST", URL, USR, cfg0)
    over("R3 anonym a zakaznik nemohou vytvorit nabidku (401/403)", r_anon_post.status_code == 401 and r_usr_post.status_code == 403, (r_anon_post.status_code, r_usr_post.status_code))
    sql("DELETE FROM role_permissions")
    sql("INSERT INTO role_permissions (role, section, action, allowed) VALUES ('manager','nabidky','vytvorit',1)")

    # ------------------------------------------------------------------------------------------------------------------------- vytvoreni nabidky (system 30)
    sel30 = stul_shop.vychozi_vyber(30)
    with real.cursor() as cur:
        res = kk.vyres(cur, 4934, sel30, "cs", None)
    UNIT = int(res["net_czk"])
    r1 = vol("POST", URL, MGR, {"product_id": 4934, "configuration": {"selection": sel30, "rules_version": res["rules_version"]}, "qty": 1})
    j1 = r1.get_json() or {}
    over("P1 vychozi stul system 30: 201, odpoved podle kontraktu (offer_id, offer_number, online_url, line, price, montaz, rules_version, v3d)",
         r1.status_code == 201 and all(k in j1 for k in ("offer_id", "offer_number", "online_url", "line", "price", "montaz", "rules_version", "v3d")) and j1["online_url"].startswith("/nabidka-online.html?t="), (r1.status_code, j1))
    over("P2 cena = vyres (bez DPH, cele Kc), DPH a s DPH podle VAT_RATE, zadne zaokrouhlovani navic",
         j1["line"] == {"kod": res["kod"], "hash": res["hash"], "qty": 1, "unit_net_czk": UNIT, "total_net_czk": UNIT}
         and j1["price"] == {"net_czk": UNIT, "vat_rate": nz.VAT_RATE, "vat_czk": round(UNIT * nz.VAT_RATE / 100, 2), "gross_czk": round(UNIT + round(UNIT * nz.VAT_RATE / 100, 2), 2)}, j1.get("price"))
    row = jedno("SELECT * FROM scene_offers WHERE id=%s", (j1["offer_id"],))
    opts = json.loads(row["offer_options"])
    items = json.loads(row["items"])
    over("P3 radek nabidky: total_price = cena 1 ks, jedna polozka s kodem konfigurace a hashem, product_id NULL, nazev z kodu, bez vlastnich dat od klienta",
         float(row["total_price"]) == float(UNIT) and len(items) == 1 and items[0]["configuration_code"] == res["kod"] and items[0]["config_hash"] == res["hash"] and items[0]["product_id"] is None
         and items[0]["unit_price"] == float(UNIT) and res["kod"] in items[0]["name"], (row["total_price"], items))
    over("P4 offer_options: source=configurator, verejna cast config (kod, hash, system 30, ks, souhrn voleb, neutralni kusovnik), soukroma config_private (vyber, cenovy souhrn); vychozi klice zustaly",
         opts.get("source") == "configurator" and opts["config"]["kod"] == res["kod"] and opts["config"]["system"] == 30 and opts["config"]["qty"] == 1 and opts["config"]["souhrn"] == res["summary"]
         and opts["config"]["bom"] == res["bom"] and opts["config_private"]["selection"] == res["selection"] and opts["config_private"]["price_summary"]["total_czk"] == UNIT
         and "show_qr" in opts and "hide_bom_prices" in opts, opts.keys())
    over("P5 verejna cast config neobsahuje ceny dilu, cenovy souhrn ani vyber (nic z config_private)", all(k not in json.dumps(opts["config"]) for k in ("price_summary", "list_net_czk", "material", "weight")), opts["config"].keys())
    over("P6 platba jen predem (hidden_payment_method=dobirka), montaz = vychozi sazba stolu 12 % ulozena JAKO SNIMEK v nabidce, zeme CZ",
         opts["hidden_payment_method"] == "dobirka" and opts["montaz_pct"] == 12.0 and opts["config"]["delivery_country"] == "CZ"
         and j1["montaz"] == {"pct": 12.0, "czk": round(UNIT * 12 / 100, 2)}, (opts.get("montaz_pct"), j1.get("montaz")))
    token = j1["online_url"].split("t=")[1]
    pub = vol("GET", f"/api/public/offers/{token}", None)
    pj = pub.get_json() or {}
    over("P7 verejny JSON nabidky: 200, source configurator, configuration {kod, summary, bom} pro stranku, offer_options.config JEN verejna cast (kod, ks, zeme, souhrn, kusovnik - ne hash, pravidla, id karty), "
         "config_private NENI (cena dilu a hmotnost nesmi ven), montaz_pct 12, total_price = cena 1 ks",
         pub.status_code == 200 and pj["source"] == "configurator" and pj["configuration"] == {"kod": res["kod"], "summary": res["summary"], "bom": res["bom"], "vykresy": False}
         and pj["offer_options"].get("source") == "configurator" and "config_private" not in pj["offer_options"]
         and set(pj["offer_options"]["config"]) <= {"kod", "qty", "delivery_country", "souhrn", "bom", "pocet_spoju", "vykresy"} and "hash" not in pj["offer_options"]["config"]
         and pj["montaz_pct"] == 12.0 and float(pj["total_price"]) == float(UNIT), (pub.status_code, pj.get("configuration"), list((pj.get("offer_options") or {}).keys())))
    over("P8 3D model: v3d true, soubor modelu ulozen (has_3d_model) a model_url je ve verejnem JSON",
         j1["v3d"] is True and pj["has_3d_model"] is True and pj["model_url"], (j1.get("v3d"), j1.get("v3d_duvod")))
    mod = vol("GET", pj["model_url"], None)
    over("P9 GET /model: 200, model/gltf-binary, zacina glTF a nese spec v3d (scenes[0].extras.v3d)", mod.status_code == 200 and mod.headers.get("Content-Type", "").startswith("model/gltf-binary")
         and mod.data[:4] == b"glTF" and b'"v3d"' in mod.data[:200000], (mod.status_code, mod.headers.get("Content-Type")))
    import v3d_glb  # noqa: E402
    spec_nab = v3d_glb.embedded_spec(mod.data)
    ms_nab = [d.get("m") for d in spec_nab.get("dims", [])]
    zaklad_bez_razitek = stul_shop.glb_bytes(sel30, 30, razitka=False)       # vychozi je od pravidla 61 S razitky, zaklad pro porovnani se vyslovne postavi bez nich
    zaklad_san = v3d_glb.sanitize(zaklad_bez_razitek, v3d_glb.embedded_spec(zaklad_bez_razitek))
    over("P9c model v nabidce nese RAZITKA loga (stul_shop.glb_bytes razitka=True; od pravidla 61 jsou vychozi vsude): je vyrazne vetsi nez stejny stul vyslovne BEZ razitek a prosel sanitizerem",
         len(mod.data) > len(zaklad_san) + 100000 and mod.data[:4] == b"glTF", (len(mod.data), len(zaklad_san)))
    over("P9b polohy popisku kot z generatoru (dims[].m) zustaly v modelu nabidky (sanitizer je zna), ne zahozene", any(m is not None for m in ms_nab) and 0.3 in ms_nab and 0.7 in ms_nab, ms_nab)
    over("P10 audit: create_from_configuration (kod, hash, system, ks, v3d) + create z create_scene_offer_row", any(a[0][1] == "create_from_configuration" and a[0][3] == j1["offer_id"] for a in AUDIT)
         and any(a[0][1] == "create" for a in AUDIT), [a[0][:3] for a in AUDIT])

    # ------------------------------------------------------------------------------------------------------------------------- klient nesmi urcit cenu ani obsah
    r_fake = vol("POST", URL, MGR, {"product_id": 4934, "configuration": {"selection": sel30, "rules_version": None}, "qty": 1, "price": 1, "unit_price": 1, "name": "ZDARMA", "bom": [{"nazev": "x"}],
                                    "items": [{"name": "x", "unit_price": 1}], "total_price": 1})
    jf = r_fake.get_json() or {}
    rowf = jedno("SELECT * FROM scene_offers WHERE id=%s", (jf.get("offer_id"),))
    over("S1 cena, nazev, kusovnik ani polozky od klienta se neberou: stejna cena a nazev jako P1", r_fake.status_code == 201 and float(rowf["total_price"]) == float(UNIT) and "ZDARMA" not in rowf["items"]
         and jf["price"]["net_czk"] == UNIT, (r_fake.status_code, rowf and rowf["total_price"]))
    r_h_ok = vol("POST", URL, MGR, {"product_id": 4934, "configuration": {"selection": sel30}, "hash": res["hash"]})
    r_h_bad = vol("POST", URL, MGR, {"product_id": 4934, "configuration": {"selection": sel30}, "hash": "0123456789abcdef"})
    over("S2 volitelny hash: shodny 201, jiny 409 configuration_changed (nabidka nevznikne)", r_h_ok.status_code == 201 and r_h_bad.status_code == 409 and r_h_bad.get_json()["error"] == "configuration_changed", (r_h_ok.status_code, r_h_bad.get_json()))

    # ------------------------------------------------------------------------------------------------------------------------- chyby (kody jako u kosiku)
    n0 = jedno("SELECT COUNT(*) n FROM scene_offers")["n"]
    r_rv = vol("POST", URL, MGR, {"product_id": 4934, "configuration": {"selection": sel30, "rules_version": "2000-01-01.0"}})
    inval = dict(sel30, drawers=True, drawercount=8, boxpos=-2500)
    r_422 = vol("POST", URL, MGR, {"product_id": 4934, "configuration": {"selection": inval}})
    r_nosel = vol("POST", URL, MGR, {"product_id": 4934, "configuration": {"selection": "x"}})
    r_nopid = vol("POST", URL, MGR, {"configuration": {"selection": sel30}})
    r_body = cl.open(URL, method="POST", data="x=1", headers=cookie(ADMIN))
    r_card = vol("POST", URL, MGR, {"product_id": 4962, "configuration": {"selection": sel30}})
    r_noprod = vol("POST", URL, MGR, {"product_id": 99999999, "configuration": {"selection": sel30}})
    over("E1 zmenena rules_version 409 rules_changed", r_rv.status_code == 409 and r_rv.get_json()["error"] == "rules_changed", r_rv.get_json())
    over("E2 nelze vyrobit: 422 invalid_configuration + errors [{slot,message}]", r_422.status_code == 422 and r_422.get_json()["error"] == "invalid_configuration" and r_422.get_json()["errors"]
         and "message" in r_422.get_json()["errors"][0], r_422.get_json())
    over("E3 neplatny tvar: selection ne-slovnik, chybi product_id, ne-JSON telo = 400 invalid_selection", r_nosel.status_code == 400 and r_nopid.status_code == 400 and r_body.status_code == 400
         and all((x.get_json() or {}).get("error") == "invalid_selection" for x in (r_nosel, r_nopid, r_body)), [x.status_code for x in (r_nosel, r_nopid, r_body)])
    over("E4 produkt, ktery neni konfigurovatelny stul (Vandr karta, neexistujici id): 404 not_configurable", r_card.status_code == 404 and r_noprod.status_code == 404
         and r_card.get_json()["error"] == "not_configurable" and r_noprod.get_json()["error"] == "not_configurable", (r_card.get_json(), r_noprod.get_json()))
    over("E5 po chybach nevznikla zadna dalsi nabidka", jedno("SELECT COUNT(*) n FROM scene_offers")["n"] == n0, (n0, jedno("SELECT COUNT(*) n FROM scene_offers")["n"]))

    # ------------------------------------------------------------------------------------------------------------------------- ks, montaz, zeme, zakaznik
    def post(**kw):
        return vol("POST", URL, MGR, {"product_id": 4934, "configuration": {"selection": sel30}, **kw})

    def opt(offer_id):
        return json.loads(jedno("SELECT offer_options FROM scene_offers WHERE id=%s", (offer_id,))["offer_options"])
    r_q3, r_q99, r_q0, r_q100, r_qx, r_q25 = post(qty=3), post(qty=99), post(qty=0), post(qty=100), post(qty="x"), post(qty=2.5)
    j3 = r_q3.get_json()
    over("Q1 ks 1-99: 3 ks -> celkem 3x cena, total_price radku zustava cena 1 ks (stranka ma vlastni volbu ks, vychozi z config.qty), ks 99 ok; 0, 100, 'x', 2.5 = 400 items_invalid",
         r_q3.status_code == 201 and j3["price"]["net_czk"] == 3 * UNIT and j3["line"]["qty"] == 3 and float(jedno("SELECT total_price FROM scene_offers WHERE id=%s", (j3["offer_id"],))["total_price"]) == float(UNIT)
         and opt(j3["offer_id"])["config"]["qty"] == 3 and r_q99.status_code == 201
         and all(x.status_code == 400 and x.get_json()["error"] == "items_invalid" for x in (r_q0, r_q100, r_qx, r_q25)), [x.status_code for x in (r_q3, r_q99, r_q0, r_q100, r_qx, r_q25)])
    r_m0, r_m20, r_mx, r_m150, r_msk = post(montaz_pct=0), post(montaz_pct=20), post(montaz_pct="abc"), post(montaz_pct=150), post(delivery_country="sk")
    over("M1 montaz: 0 = nenabizi (montaz null, offer_options.montaz_pct 0.0), 20 % = vlastni sazba nabidky s castkou; 'abc' a 150 = 400",
         r_m0.status_code == 201 and r_m0.get_json()["montaz"] is None and opt(r_m0.get_json()["offer_id"])["montaz_pct"] == 0.0
         and r_m20.get_json()["montaz"] == {"pct": 20.0, "czk": round(UNIT * 20 / 100, 2)} and r_mx.status_code == 400 and r_m150.status_code == 400, (r_m0.get_json(), r_m20.get_json()))
    ojsk = opt(r_msk.get_json()["offer_id"])
    over("M2 dodani mimo CR (SK): montaz se vynuti 0 (do zahranici jen rozlozeny stul), zeme ulozena velkymi pismeny", r_msk.status_code == 201 and r_msk.get_json()["montaz"] is None and ojsk["montaz_pct"] == 0.0
         and ojsk["config"]["delivery_country"] == "SK" and ojsk["hidden_delivery_state"] == "smontovano" and opts.get("hidden_delivery_state") is None,
         (ojsk, opts.get("hidden_delivery_state")))
    r_zx = post(delivery_country="CZE")
    over("M3 neplatna zeme (3 pismena) = 400", r_zx.status_code == 400, r_zx.get_json())
    sql("INSERT INTO app_settings (setting_key, setting_value) VALUES ('stul_montaz_pct','25') ON DUPLICATE KEY UPDATE setting_value='25'")
    r_m25 = post()
    oj_stara = opt(j1["offer_id"])
    pub_stara = vol("GET", f"/api/public/offers/{token}", None).get_json()
    over("M4 zmena vychozi sazby stolu na 25 %: nova nabidka 25, uz vytvorena (P1) ZUSTAVA 12 % (snimek), verejny JSON stare nabidky 12", r_m25.get_json()["montaz"]["pct"] == 25.0 and oj_stara["montaz_pct"] == 12.0
         and pub_stara["montaz_pct"] == 12.0, (r_m25.get_json()["montaz"], oj_stara["montaz_pct"]))
    sql("DELETE FROM app_settings WHERE setting_key='stul_montaz_pct'")
    r_c = post(customer={"name": "  Jan Novák ", "email": "jan@firma.cz"})
    rc = jedno("SELECT customer_name, customer_email FROM scene_offers WHERE id=%s", (r_c.get_json()["offer_id"],))
    r_cx = post(customer={"name": "Jan", "email": "neni-email"})
    r_cy = post(customer="x")
    over("C1 zakaznik: jmeno (orezane) a e-mail se ulozi; neplatny e-mail / ne-slovnik = 400", rc["customer_name"] == "Jan Novák" and rc["customer_email"] == "jan@firma.cz" and r_cx.status_code == 400 and r_cy.status_code == 400, (rc, r_cx.status_code, r_cy.status_code))

    # ------------------------------------------------------------------------------------------------------------------------- vsechny systemy
    systemy = {x["system"]: x["card_id"] for x in stul_shop.systemy_produktu()}
    over("Y0 existuji karty vsech 5 systemu (30, 35, 40, 41, 45)", set(systemy) == {30, 35, 40, 41, 45}, systemy)          # 45 = Robustni (bot10, karta #5353 od 2026-10-07)
    for sysm, karta in sorted(systemy.items()):
        sel = stul_shop.vychozi_vyber(sysm)
        r = vol("POST", URL, MGR, {"product_id": karta, "configuration": {"selection": sel}})
        jj = r.get_json() or {}
        with real.cursor() as cur:
            rs = kk.vyres(cur, karta, sel, "cs", None)
        o = opt(jj["offer_id"]) if r.status_code == 201 else {}
        over(f"Y{sysm} system {sysm} (karta {karta}, i neaktivni): 201, cena = vyres, kod, system v snimku, 3D model prosel sanitizerem",
             r.status_code == 201 and jj["line"]["unit_net_czk"] == int(rs["net_czk"]) and jj["line"]["kod"] == rs["kod"] and o["config"]["system"] == sysm and jj["v3d"] is True, (r.status_code, jj))

    # ------------------------------------------------------------------------------------------------------------------------- 3D selhani a znaceni
    orig_glb = nz._zakaznicky_glb

    def spadne(*a, **k):
        raise ValueError("test: model neprosel")

    nz._zakaznicky_glb = spadne
    r3 = post()
    j3d = r3.get_json() or {}
    nz._zakaznicky_glb = orig_glb
    rr3 = jedno("SELECT view_3d_model FROM scene_offers WHERE id=%s", (j3d.get("offer_id"),))
    over("D1 selhani 3D nezakaze nabidku: 201, v3d false + duvod, nabidka bez modelu (view_3d_model NULL), cena i souhrn jsou", r3.status_code == 201 and j3d["v3d"] is False and "neprošel" in (j3d["v3d_duvod"] or "")
         and rr3["view_3d_model"] is None and j3d["price"]["net_czk"] == UNIT, j3d)

    def vyjimka(*a, **k):
        raise RuntimeError("test: neocekavana chyba")

    nz._zakaznicky_glb = vyjimka
    r3b = post()
    nz._zakaznicky_glb = orig_glb
    over("D2 neocekavana chyba pri stavbe modelu = taky 201 bez 3D (nikdy 500)", r3b.status_code == 201 and r3b.get_json()["v3d"] is False, (r3b.status_code, r3b.get_json()))
    os.environ["V3D_MARK_SECRET"] = "t" * 64
    nz._znacka_vypnuto_zalogovano = False
    r_mark = post()
    del os.environ["V3D_MARK_SECRET"]
    zazn = [a for a in AUDIT if a[0][1] == "create_from_configuration" and a[0][3] == (r_mark.get_json() or {}).get("offer_id")]
    over("D3 zapnute neviditelne znaceni (klic v prostredi): model oznacen cislem nabidky, v audit logu znacka=zapnuto, 201", r_mark.status_code == 201 and r_mark.get_json()["v3d"] is True
         and zazn and json.loads(zazn[0][0][4])["znacka"] == "zapnuto", (r_mark.status_code, r_mark.get_json(), zazn[:1]))
    os.environ["V3D_MARK_SECRET"] = "kratky"
    r_kr = post()
    del os.environ["V3D_MARK_SECRET"]
    over("D4 neplatny (kratky) klic = znaceni vypnuto, nabidka vznikne s modelem bez znacky", r_kr.status_code == 201 and r_kr.get_json()["v3d"] is True, r_kr.get_json())

    # ------------------------------------------------------------------------------------------------------------------------- uprava nabidky v adminu nesmi smazat snimek
    body_put = {"items": items, "total_price": float(UNIT), "editable_text": {"popis": "p", "patka": "f"}, "offer_options": {"montaz_pct": 15, "show_qr": True,
                "source": "hacker", "config": {"kod": "PODVRH"}, "config_private": {"selection": {}}}, "change_note": "test"}
    r_put = vol("PUT", f"/api/admin/scene-offers/{j1['offer_id']}", ADMIN, body_put)
    oput = opt(j1["offer_id"])
    over("U1 uprava nabidky v adminu: snimek konfigurace (source, config, config_private) ZUSTAL, hodnoty z tela se nepropusti (zadny podvrh), sazba montaze z formulare 15 se ulozila",
         r_put.status_code == 200 and oput["source"] == "configurator" and oput["config"]["kod"] == res["kod"] and oput["config_private"]["selection"] == res["selection"] and oput["montaz_pct"] == 15.0,
         (r_put.status_code, oput.get("source"), oput.get("config", {}).get("kod")))
    body_put2 = {"items": items, "total_price": float(UNIT), "editable_text": {}, "offer_options": {"montaz_pct": 15}}
    r_put2 = vol("PUT", f"/api/admin/scene-offers/{j1['offer_id']}", ADMIN, body_put2)
    oput2 = opt(j1["offer_id"])
    over("U2 uprava bez klicu snimku v tele (starsi admin.html) snimek taky zachova", r_put2.status_code == 200 and oput2["config"]["kod"] == res["kod"] and "config_private" in oput2, oput2.keys())
    # stara (scenova) nabidka bez snimku: z tela se snimek vytvorit neda
    sql("INSERT INTO scene_offers (offer_number, items, total_price, customer_name, view_narys, view_3d_a, view_3d_b, editable_text_popis, editable_text_patka, view_token_hash, expires_at, created_by, offer_options) "
        "VALUES ('RM9999','[{\"name\":\"x\",\"qty\":1,\"unit_price\":1,\"total\":1}]',1,'X','a','a','a','p','f',SHA2('x',256),DATE_ADD(NOW(), INTERVAL 5 DAY),%s,'{\"show_qr\": true}')", (ADMIN,))
    sid = jedno("SELECT id FROM scene_offers WHERE offer_number='RM9999'")["id"]
    token_stara = "x"                                              # view_token_hash = SHA2('x', 256)
    r_put3 = vol("PUT", f"/api/admin/scene-offers/{sid}", ADMIN, {"items": [{"name": "x", "qty": 1, "unit_price": 1, "total": 1}], "total_price": 1, "editable_text": {},
                                                                 "offer_options": {"source": "configurator", "config": {"kod": "X"}}})
    oput3 = opt(sid)
    over("U3 stara (scenova) nabidka: upravou se NEda z tela vytvorit source/config (200, klice tam nejsou)", r_put3.status_code == 200 and not any(k in oput3 for k in ("source", "config", "config_private")), oput3.keys())

    # ------------------------------------------------------------------------------------------------------------------------- kotovane 2D vykresy ze sceny
    import base64 as _b64
    import struct as _st
    import zlib as _zl

    def png_uri(r, g, b, w=8, h=8):
        """Platny maly PNG (jednobarevny) jako data-URI - dalsi barva = dalsi obsah souboru."""
        raw = b"".join(b"\x00" + bytes([r, g, b]) * w for _ in range(h))
        def chunk(t, d):
            c = _st.pack(">I", len(d)) + t + d
            return c + _st.pack(">I", _zl.crc32(t + d) & 0xFFFFFFFF)
        data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", _st.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", _zl.compress(raw)) + chunk(b"IEND", b"")
        return "data:image/png;base64," + _b64.b64encode(data).decode(), data
    VYK = "/api/admin/konfigurace/nabidka/{}/vykresy"
    r_v0 = post()
    oid_v, tok_v = r_v0.get_json()["offer_id"], r_v0.get_json()["online_url"].split("t=")[1]
    pred = jedno("SELECT view_narys, view_bokorys, view_pudorys, view_3d_a, view_3d_b FROM scene_offers WHERE id=%s", (oid_v,))
    pub_pred = vol("GET", f"/api/public/offers/{tok_v}", None).get_json()
    n_uri, n_raw = png_uri(10, 20, 30)
    b_uri, b_raw = png_uri(40, 50, 60)
    p_uri, p_raw = png_uri(70, 80, 90)
    a_uri, a_raw = png_uri(100, 110, 120)
    c_uri, c_raw = png_uri(130, 140, 150)
    r_vy = vol("POST", VYK.format(oid_v), MGR, {"views": {"narys": n_uri, "bokorys": b_uri, "pudorys": p_uri, "view3d_a": a_uri, "view3d_b": c_uri}})
    po = jedno("SELECT view_narys, view_bokorys, view_pudorys, view_3d_a, view_3d_b FROM scene_offers WHERE id=%s", (oid_v,))
    pub_po = vol("GET", f"/api/public/offers/{tok_v}", None).get_json()
    img_n = vol("GET", f"/api/public/offers/{tok_v}/image/narys", None)
    over("V1 nahrani vykresu ze sceny (nárys, bokorys, pudorys + 2 x 3D): 200 {ok, offer_id, vykresy}, v DB nove soubory (jina nez zastupne), verejny JSON nabidky hlasi configuration.vykresy true i v offer_options.config, obrazek se servíruje pres token",
         r_vy.status_code == 200 and r_vy.get_json() == {"ok": True, "offer_id": oid_v, "vykresy": ["bokorys", "narys", "pudorys", "view3d_a", "view3d_b"]} and all(po[k] != pred[k] for k in po)
         and pub_pred["configuration"]["vykresy"] is False and pub_po["configuration"]["vykresy"] is True and pub_po["offer_options"]["config"]["vykresy"] is True
         and img_n.status_code == 200 and img_n.data == n_raw, (r_vy.status_code, r_vy.get_json(), pub_po.get("configuration"), img_n.status_code))
    over("V2 zastupne obrazky (1x1 PNG; bokorys a pudorys zastupne nemaji) po nahrani zmizely z disku a nove soubory na disku jsou (nic se neztratilo, nic nezustalo viset)",
         all(not os.path.exists(os.path.join(so.OFFER_IMAGES_DIR, pred[k])) for k in pred if pred[k]) and all(os.path.exists(os.path.join(so.OFFER_IMAGES_DIR, po[k])) for k in po), (pred, po))
    r_vy2 = vol("POST", VYK.format(oid_v), MGR, {"views": {"narys": b_uri, "bokorys": n_uri, "pudorys": p_uri}})
    po2 = jedno("SELECT view_narys, view_bokorys, view_pudorys, view_3d_a, view_3d_b FROM scene_offers WHERE id=%s", (oid_v,))
    over("V3 opakovane nahrani jen 3 povinnych vykresu je vymeni (stare soubory pryc), 3D pohledy zustavaji z minuleho nahrani", r_vy2.status_code == 200 and r_vy2.get_json()["vykresy"] == ["bokorys", "narys", "pudorys"]
         and po2["view_3d_a"] == po["view_3d_a"] and po2["view_3d_b"] == po["view_3d_b"] and po2["view_narys"] != po["view_narys"]
         and all(not os.path.exists(os.path.join(so.OFFER_IMAGES_DIR, po[k])) for k in ("view_narys", "view_bokorys", "view_pudorys")) and vol("GET", f"/api/public/offers/{tok_v}/image/narys", None).data == b_raw, (r_vy2.get_json(), po, po2))
    n_pred = len(os.listdir(so.OFFER_IMAGES_DIR))
    chybi = vol("POST", VYK.format(oid_v), MGR, {"views": {"narys": n_uri, "bokorys": b_uri}})
    spatny = vol("POST", VYK.format(oid_v), MGR, {"views": {"narys": n_uri, "bokorys": b_uri, "pudorys": "data:text/html;base64,PGI+eDwvYj4="}})
    nedek = vol("POST", VYK.format(oid_v), MGR, {"views": {"narys": n_uri, "bokorys": b_uri, "pudorys": "data:image/png;base64,@@@neplatne@@@"}})
    bez = vol("POST", VYK.format(oid_v), MGR, {"neco": 1})
    over("V4 neplatne vstupy (chybi povinny vykres, ne-obrazek, nedekodovatelny base64, bez views): 400 invalid_views a NIC se nezapise (zadny novy soubor, DB beze zmeny)",
         all(x.status_code == 400 and x.get_json()["error"] == "invalid_views" for x in (chybi, spatny, nedek, bez)) and len(os.listdir(so.OFFER_IMAGES_DIR)) == n_pred
         and jedno("SELECT view_narys FROM scene_offers WHERE id=%s", (oid_v,))["view_narys"] == po2["view_narys"], [x.status_code for x in (chybi, spatny, nedek, bez)])
    r_stara = vol("POST", VYK.format(sid), MGR, {"views": {"narys": n_uri, "bokorys": b_uri, "pudorys": p_uri}})
    r_nikdo = vol("POST", VYK.format(99999999), MGR, {"views": {"narys": n_uri, "bokorys": b_uri, "pudorys": p_uri}})
    sql("UPDATE scene_offers SET created_at = NOW() - INTERVAL 25 HOUR WHERE id=%s", (oid_v,))
    r_stara_cas = vol("POST", VYK.format(oid_v), MGR, {"views": {"narys": n_uri, "bokorys": b_uri, "pudorys": p_uri}})
    sql("UPDATE scene_offers SET created_at = NOW() - INTERVAL 23 HOUR WHERE id=%s", (oid_v,))
    r_cas_ok = vol("POST", VYK.format(oid_v), MGR, {"views": {"narys": n_uri, "bokorys": b_uri, "pudorys": p_uri}})
    over("V5 stara (scenova) nabidka 409 not_configurator_offer, neexistujici 404, starsi nez 24 h 409 vykresy_expired (po 23 h jeste projde)",
         r_stara.status_code == 409 and r_stara.get_json()["error"] == "not_configurator_offer" and r_nikdo.status_code == 404 and r_stara_cas.status_code == 409 and r_stara_cas.get_json()["error"] == "vykresy_expired"
         and r_cas_ok.status_code == 200, [x.status_code for x in (r_stara, r_nikdo, r_stara_cas, r_cas_ok)])
    sql("DELETE FROM role_permissions")
    sql("INSERT INTO role_permissions (role, section, action, allowed) VALUES ('manager','nabidky','zobrazit',1)")
    r_zob = vol("POST", VYK.format(oid_v), MGR, {"views": {"narys": n_uri, "bokorys": b_uri, "pudorys": p_uri}})
    r_usr_v, r_anon_v = vol("POST", VYK.format(oid_v), USR, {"views": {"narys": n_uri, "bokorys": b_uri, "pudorys": p_uri}}), vol("POST", VYK.format(oid_v), None, {"views": {"narys": n_uri, "bokorys": b_uri, "pudorys": p_uri}})
    sql("DELETE FROM role_permissions")
    sql("INSERT INTO role_permissions (role, section, action, allowed) VALUES ('manager','nabidky','vytvorit',1)")
    over("V6 pravo: jen nabidky/vytvorit (jen zobrazit 403, zakaznik 403, anonym 401)", r_zob.status_code == 403 and r_usr_v.status_code == 403 and r_anon_v.status_code == 401, [x.status_code for x in (r_zob, r_usr_v, r_anon_v)])
    r_put_v = vol("PUT", f"/api/admin/scene-offers/{oid_v}", ADMIN, {"items": json.loads(jedno("SELECT items FROM scene_offers WHERE id=%s", (oid_v,))["items"]), "total_price": float(UNIT), "editable_text": {}, "offer_options": {"montaz_pct": 5}})
    over("V7 uprava nabidky v adminu priznak vykresy zachova (snimek konfigurace se cely bere z ulozeneho radku)", r_put_v.status_code == 200 and opt(oid_v)["config"]["vykresy"] is True, (r_put_v.status_code, opt(oid_v).get("config")))

    # ------------------------------------------------------------------------------------------------------------------------- montaz Praha / Slavicin jen u sestav do aut, vylucuje dopravu (Robert 2026-10-06)
    print("== MA montaz Praha / Slavicin: jen sestavy do aut, vylucuje dopravu")
    with real.cursor() as cur:
        mista = so._montaz_mista_map(cur)
    misto = next(iter(mista), None)
    sql("INSERT INTO scene_offers (offer_number, items, total_price, customer_name, view_narys, view_3d_a, view_3d_b, editable_text_popis, editable_text_patka, view_token_hash, expires_at, created_by, offer_options) "
        "VALUES ('RM9998','[{\"name\":\"x\",\"qty\":1,\"unit_price\":1,\"total\":1}]',10000,'X','a','a','a','p','f',SHA2('vandr-token',256),DATE_ADD(NOW(), INTERVAL 5 DAY),%s,%s)",
        (ADMIN, json.dumps({"vandr_single_drawing": True, "montaz_pct": 15.0, "show_qr": True})))
    oid_auto = jedno("SELECT id FROM scene_offers WHERE offer_number='RM9998'")["id"]

    def prefs(token_, **body):
        appmod._rate_limit_buckets.clear()
        return cl.post(f"/api/public/offers/{token_}/order-prefs", json=body)

    def ulozene(offer_id):
        return jedno("SELECT shipping_method, montaz_zvolena, montaz_misto, delivery_zip, toptrans_price_czk FROM scene_offer_order_prefs WHERE offer_id=%s ORDER BY id DESC LIMIT 1", (offer_id,))             # test klient nema cookie: kazdy pozadavek = jiny host = novy radek, bere se posledni
    pub_auto = vol("GET", "/api/public/offers/vandr-token", None).get_json()
    pub_cfg = vol("GET", f"/api/public/offers/{token}", None).get_json()
    over("MA1 verejny JSON: nabidka z Vandr karty (vandr_single_drawing) je sestava do auta (offer_options.is_vehicle_assembly true, montaz_volba true) i bez rucniho priznaku; stul (konfigurace) montaz_volba false a bez priznaku auta",
         pub_auto["offer_options"].get("is_vehicle_assembly") is True and pub_auto["montaz_volba"] is True and pub_cfg["montaz_volba"] is False and not pub_cfg["offer_options"].get("is_vehicle_assembly"), (pub_auto["offer_options"], pub_auto["montaz_volba"], pub_cfg["montaz_volba"]))
    if misto:
        r_a = prefs("vandr-token", montaz_zvolena=True, montaz_misto=misto, shipping_method="vlastni", qty=1)
        u_a = ulozene(oid_auto)
        over("MA2 sestava do auta: zvolena montaz + misto se ulozi a doprava se VYNULUJE (vylucuje se: shipping_method NULL, PSC i cena Toptransu pryc)", r_a.status_code == 200 and u_a["montaz_zvolena"] == 1 and u_a["montaz_misto"] == misto
             and u_a["shipping_method"] is None and u_a["delivery_zip"] is None and u_a["toptrans_price_czk"] is None, (r_a.status_code, u_a))
        r_b = prefs("vandr-token", montaz_zvolena=True, montaz_misto=misto, shipping_method="toptrans", delivery_zip="11000", toptrans_price_czk=900, qty=1)
        over("MA3 sestava do auta: montaz + Toptrans zaroven = 400 montaz_doprava_vylouceno (UI to nedovoli, server ano hlida), ulozene volby se NEzmenily", r_b.status_code == 400 and r_b.get_json()["code"] == "montaz_doprava_vylouceno" and ulozene(oid_auto) == u_a, (r_b.status_code, r_b.get_json()))
        r_c = prefs("vandr-token", montaz_zvolena=False, shipping_method="toptrans", delivery_zip="11000", toptrans_price_czk=900, qty=1)
        u_c = ulozene(oid_auto)
        over("MA4 sestava do auta BEZ montaze: doprava Toptrans se ulozi jako dosud", r_c.status_code == 200 and u_c["shipping_method"] == "toptrans" and u_c["montaz_zvolena"] == 0 and u_c["toptrans_price_czk"] == 900, (r_c.status_code, u_c))
        r_d = prefs(token, montaz_zvolena=True, montaz_misto=misto, shipping_method="toptrans", delivery_zip="11000", toptrans_price_czk=900, qty=1)
        u_d = ulozene(j1["offer_id"])
        over("MA5 STUL (nabidka z konfigurace): montaz Praha / Slavicin se k objednavce NEulozi (montaz_zvolena 0, misto NULL) a doprava zustane - montaz stolu je jen informace, nic nevylucuje", r_d.status_code == 200 and u_d["montaz_zvolena"] == 0
             and u_d["montaz_misto"] is None and u_d["shipping_method"] == "toptrans", (r_d.status_code, u_d))
    else:
        over("MA2-5 (PRESKOCENO: v databazi neni zadne misto montaze)", True)
    sql("UPDATE scene_offers SET offer_options=%s WHERE id=%s", (json.dumps({"vandr_single_drawing": True, "montaz_pct": 0.0, "show_qr": True}), oid_auto))
    if misto:
        r_e = prefs("vandr-token", montaz_zvolena=True, montaz_misto=misto, shipping_method="toptrans", delivery_zip="11000", toptrans_price_czk=900, qty=1)
        over("MA6 sestava do auta se sazbou montaze 0 (montaz se nenabizi): doprava se montazi NEvylucuje (Toptrans se ulozi, 200)", r_e.status_code == 200 and ulozene(oid_auto)["shipping_method"] == "toptrans", (r_e.status_code, ulozene(oid_auto)))

    # ------------------------------------------------------------------------------------------------------------------------- doprava Toptrans (hmotnost z katalogu je dnes neuplna)
    def toptrans(token_, **body):
        appmod._rate_limit_buckets.clear()
        return cl.post(f"/api/public/offers/{token_}/toptrans-price", json=body)

    def nastav_priv(offer_id, **zmeny):
        o = opt(offer_id)
        o["config_private"].update(zmeny)
        sql("UPDATE scene_offers SET offer_options=%s WHERE id=%s", (json.dumps(o), offer_id))
    r_tt = post()
    tok_tt, oid_tt = r_tt.get_json()["online_url"].split("t=")[1], r_tt.get_json()["offer_id"]
    nastav_priv(oid_tt, weight_complete=False, weight_kg=15.0)
    t_neuplna = toptrans(tok_tt, delivery_zip="11000", qty=1)
    over("T1 neuplna hmotnost konfigurace (dnes chybi laminodeska, supliky...): Toptrans 409 weight_incomplete s vetou pro zakaznika - poddimenzovana cena by byla horsi nez zadna",
         t_neuplna.status_code == 409 and t_neuplna.get_json()["code"] == "weight_incomplete" and "individuálně" in t_neuplna.get_json()["error"], (t_neuplna.status_code, t_neuplna.get_json()))
    nastav_priv(oid_tt, weight_complete=True, weight_kg=40.0)
    t_plna = toptrans(tok_tt, delivery_zip="11000", qty=2)
    over("T2 uplna hmotnost: Toptrans se pocita z hmotnosti konfigurace x ks (40 kg x 2 = 80 kg), ne z radku nabidky", t_plna.status_code == 200 and t_plna.get_json()["weight_kg"] == 80.0, (t_plna.status_code, t_plna.get_json()))
    nastav_priv(oid_tt, weight_complete=False)
    sql("UPDATE scene_offers SET offer_options=%s WHERE id=%s", (json.dumps(dict(opt(oid_tt), manual_assembled_shipping_czk=2500.0)), oid_tt))
    t_man = toptrans(tok_tt, delivery_zip="", delivery_state="smontovano")
    over("T3 rucni cena dopravy 'Smontovano' (zadava zamestnanec) funguje i pri neuplne hmotnosti: 2500 Kc primo, zadny vypocet z hmotnosti", t_man.status_code == 200 and t_man.get_json()["price_czk"] == 2500 and t_man.get_json()["basis"] == "manual", (t_man.status_code, t_man.get_json()))
    t_stara = toptrans(token_stara, delivery_zip="11000", qty=1)
    over("T4 starsi (scenova) nabidka beze zmeny: Toptrans se pocita jako dosud (z hmotnosti radku, tady 0), zadne omezeni konfigurace", t_stara.status_code == 200, (t_stara.status_code, t_stara.get_json()))
    nastav_priv(oid_tt, weight_complete=False)
    o_poskozena = opt(oid_tt)
    o_poskozena.pop("config_private")
    o_poskozena.pop("manual_assembled_shipping_czk", None)
    sql("UPDATE scene_offers SET offer_options=%s WHERE id=%s", (json.dumps(o_poskozena), oid_tt))
    t_poskozena = toptrans(tok_tt, delivery_zip="11000", qty=1)
    over("T5 nabidka z konfigurace s poskozenym snimkem se bere jako neuplna (fail closed): 409", t_poskozena.status_code == 409, (t_poskozena.status_code, t_poskozena.get_json()))

    # ------------------------------------------------------------------------------------------------------------------------- objednavka z prijate nabidky nese snimek konfigurace
    zname = None
    c0 = ostre()
    try:
        with c0.cursor() as cur0:
            cur0.execute("SELECT c.email, c.user_id FROM shop_customers c JOIN app_users u ON u.id = c.user_id WHERE c.email IS NOT NULL AND c.email <> '' LIMIT 1")
            zname = cur0.fetchone()
            if zname:
                cur0.execute("SELECT * FROM app_users WHERE id=%s", (zname["user_id"],))
                zname_user = cur0.fetchone()
    finally:
        c0.close()
    if zname:
        if not jedno("SELECT id FROM app_users WHERE id=%s", (zname["user_id"],)):
            sql(f"INSERT INTO app_users ({', '.join(zname_user)}) VALUES ({', '.join(['%s'] * len(zname_user))})", list(zname_user.values()))
        def objednej(offer_id, kusu):
            with real.cursor() as cur:
                oid_, onum_ = ordersmod.create_order_from_scene_offer(cur, jedno("SELECT * FROM scene_offers WHERE id=%s", (offer_id,)), name="Test Jednatel", company_ico="12345678", company_name="Test Firma s.r.o.",
                                                                       company_dic="CZ12345678", company_address="Testovací 1, Praha", contact_email=zname["email"], contact_phone="123456789",
                                                                       total_czk=UNIT * kusu, qty_multiplier=kusu)
            real.commit()
            return oid_, jedno("SELECT * FROM shop_order_items WHERE order_id=%s", (oid_,))
        oid_obj, radek = objednej(j1["offer_id"], 2)
        sn = json.loads(radek["configuration_json"]) if radek and radek["configuration_json"] else {}
        over("O1 OBJEDNAVKA z prijate nabidky: jeden radek bez product_id (vyroba na zakazku), cena a mnozstvi z nabidky (2 ks), a SNIMEK konfigurace (vyber, neutralni kusovnik, cenovy souhrn, kod, hash) na radku jako u kosiku",
             radek is not None and radek["product_id"] is None and radek["qty"] == 2 and float(radek["unit_price_czk"]) == float(UNIT) and float(radek["line_total_czk"]) == float(UNIT * 2)
             and radek["configuration_code"] == res["kod"] and sn.get("hash") == res["hash"] and sn["selection"] == res["selection"] and sn["price_summary"]["total_czk"] == UNIT and sn["bom"] == res["bom"]
             and sn["zdroj"] == "nabidka" and res["kod"] in radek["product_name_snapshot"]
             and jedno("SELECT source_scene_offer_id FROM shop_orders WHERE id=%s", (oid_obj,))["source_scene_offer_id"] == j1["offer_id"], radek)
        oid_stara, radek_stara = objednej(sid, 1)
        over("O2 starsi (scenova) nabidka se do objednavky prevede jako dosud: sloupce konfigurace zustanou NULL", radek_stara["configuration_json"] is None and radek_stara["configuration_code"] is None, radek_stara)
        sql("UPDATE scene_offers SET offer_options=%s WHERE id=%s", (json.dumps(o_poskozena), oid_tt))
        oid_p, radek_p = objednej(oid_tt, 1)
        over("O3 nabidka z konfigurace s poskozenym snimkem: objednavka se presto zalozi (radek bez snimku), chyba snimku objednavku nezastavi", radek_p is not None and radek_p["configuration_json"] is None and radek_p["configuration_code"] is None, radek_p)
        over("O4 snapshot_pro_objednavku: None pro ne-konfiguracni nabidku, pro poskozenou a bez config_private; kompletni vrati kod, hash, vyber, souhrn, bom, zdroj=nabidka",
             nz.snapshot_pro_objednavku({}) is None and nz.snapshot_pro_objednavku({"source": "configurator"}) is None and nz.snapshot_pro_objednavku(None) is None
             and nz.snapshot_pro_objednavku(opts)["hash"] == res["hash"] and nz.snapshot_pro_objednavku(opts)["selection"] == res["selection"], None)
    else:
        over("O1 objednavka z nabidky (PRESKOCENO: v databazi neni zadny zakaznik pro dedup)", True)

    # ------------------------------------------------------------------------------------------------------------------------- rate limit, bez e-mailu, mutace
    puvodni_limit = nz.LIMIT_NA_UZIVATELE
    nz.LIMIT_NA_UZIVATELE = (2, 3600)
    appmod._rate_limit_buckets.clear()
    kody = [cl.open(URL, method="POST", headers=cookie(ADMIN), json={"product_id": 4934, "configuration": {"selection": sel30}}).status_code for _ in range(3)]
    nz.LIMIT_NA_UZIVATELE = puvodni_limit
    appmod._rate_limit_buckets.clear()
    over("L1 limit nabidek na uzivatele: pri limitu 2/hod je treti pozadavek 429 rate_limited", kody == [201, 201, 429], kody)
    zdroj = open(os.path.join(TAPI, "nabidka_z_konfigurace.py"), encoding="utf-8").read()
    over("L2 modul nikam neposila e-mail (zadny smtp/send_mail/_auto_email/sendmail) - pravidlo 16", not re.search(r"smtp|send_mail|sendmail|_auto_email|email_queue", zdroj, re.I), None)
    over("L3 modul nepouziva zadnou cenu ani kusovnik z pozadavku (v tele se cte jen product_id, configuration, qty, montaz_pct, delivery_country, customer, hash a u vykresu views)",
         set(re.findall(r'body\.get\("(\w+)"', zdroj)) == {"product_id", "configuration", "qty", "montaz_pct", "delivery_country", "customer", "hash", "views"}, set(re.findall(r'body\.get\("(\w+)"', zdroj)))
    puvodni_verejne = so._verejne_offer_options
    so._verejne_offer_options = lambda o: o
    unik = vol("GET", f"/api/public/offers/{token}", None).get_json()
    so._verejne_offer_options = puvodni_verejne
    over("MUT1 mutace: bez filtru verejneho JSON by config_private unikla (test P7 ji tedy opravdu hlida)", "config_private" in (unik.get("offer_options") or {}), list((unik.get("offer_options") or {}).keys()))
    zdroj_so = open(os.path.join(TAPI, "scene_offers.py"), encoding="utf-8").read()
    zdroj_or = open(os.path.join(TAPI, "orders.py"), encoding="utf-8").read()
    over("MUT3 staticky: orders.create_order_from_scene_offer zapisuje snimek konfigurace na radek (UPDATE configuration_json/configuration_code); dynamicky ho hlida O1",
         "UPDATE shop_order_items SET configuration_json=%s, configuration_code=%s WHERE id=%s" in zdroj_or, None)
    over("MUT2 staticky: admin_scene_offer_update zachovava vsechny 3 klice snimku (cyklus pres source/config/config_private); dynamicky ho hlidaji U1 a U2",
         'for _k in ("source", "config", "config_private"):' in zdroj_so, None)
finally:
    with real.cursor() as cur:
        for t in TABS:
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `{t}`")
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `_tpl_{t}`")
    real.commit()
    shutil.rmtree(tmp, ignore_errors=True)
    for d in (so.OFFER_MODELS_DIR, so.OFFER_IMAGES_DIR, so.DRIVE_FILES_DIR):
        shutil.rmtree(d, ignore_errors=True)

print(f"\nVYSLEDEK nabidka z konfigurace: {sum(vysl)}/{len(vysl)} OK")
sys.exit(0 if all(vysl) else 1)
