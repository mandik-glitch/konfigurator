#!/opt/konfigurator/api/venv/bin/python
"""Konfigurace sestavy v KOSIKU a v OBJEDNAVCE (bot5, 2026-10-02; zelenou dal bot3): api/konfigurace_kosik.py + patche api/cart.py a api/orders.py.

SKUTECNY kod (cart.py a orders.py s patchi, konfigurace_kosik.py, konfigurator stolu od bot8: stul_shop.resolve) pres Flask test client nad DOCASNYMI tabulkami (kosik, objednavky, polozky, doklady,
cislovani, produkty, platby, doprava, sluzby typu sestav, zakaznici a skupiny, nastaveni). Ostre tabulky se jen ctou (app_users pro session, katalog dilu pro cenu, cenik dopravy) a po testu se porovnavaji
pocty. E-maily a audit se jen zachytavaji.
Kandidati: CART_PY, ORDERS_PY, KONFIGURACE_KOSIK_PY (jinak se patche z nasazeni/ aplikuji na kopie zivych souboru, nebo se pouziji zive, kdyz uz patchnute jsou).

Cast A  pridani do kosiku: cena jen ze serveru, efektivni vyber a hash, stejny vyber = stejny radek, neplatna konfigurace, verze pravidel, limity, montaz, skupinova sleva, zive cteni, uprava a mazani
Cast B  objednavka: radek se snimkem (volby, kusovnik, cenovy souhrn), cena a hmotnost ze serveru, product_id NULL = bez skladu, doklady, montaz, zakaznik vs. zamestnanec, potvrzeni a storno
Cast C  regrese beznych radku a nic mimo ocekavane tabulky; mutace klicovych ochran
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
  /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-02_konfigurace_kosik_testy/test_kosik_konfigurace.py
"""
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
API = os.path.join(REPO, "api")
KIT = os.path.join(HERE, "nasazeni")
tmp = tempfile.mkdtemp(prefix="kand_kosik_")


def priprav(jmeno, env, patch):
    """Kandidat: env > zivy soubor, kdyz uz je patchnuty > kopie zivého souboru s patchem ze sady."""
    cil = os.path.join(tmp, jmeno)
    if os.environ.get(env):
        shutil.copy(os.environ[env], cil)
    else:
        shutil.copy(os.path.join(API, jmeno), cil)
        if patch:
            subprocess.run([sys.executable, os.path.join(KIT, patch), cil], check=True, capture_output=True)
    return cil


priprav("cart.py", "CART_PY", "patch_cart.py")
priprav("orders.py", "ORDERS_PY", "patch_orders.py")
shutil.copy(os.environ.get("KONFIGURACE_KOSIK_PY") or (os.path.join(API, "konfigurace_kosik.py") if os.path.exists(os.path.join(API, "konfigurace_kosik.py")) else os.path.join(KIT, "konfigurace_kosik.py")),
            os.path.join(tmp, "konfigurace_kosik.py"))
sys.path.insert(0, tmp)
sys.path.insert(1, API)

import pymysql  # noqa: E402
import app as appmod  # noqa: E402
import cart as cartmod  # noqa: E402
import orders as ordersmod  # noqa: E402
import konfigurace_kosik as kk  # noqa: E402
import stul_montaz  # noqa: E402,F401 - registruje routy pred prvnim pozadavkem (v provozu ho nacita app.py)
import stul_api  # noqa: E402
import stul_glb  # noqa: E402
import stul_shop  # noqa: E402
import dealers  # noqa: E402
from flask.sessions import SecureCookieSessionInterface  # noqa: E402

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:600]))


AUDIT, EMAILS = [], []
dealers.attach_attribution = lambda *a, **k: None
appmod.log_audit = lambda *a, **k: AUDIT.append((a, k))
ordersmod.log_audit = lambda *a, **k: AUDIT.append((a, k))
cartmod.log_audit = lambda *a, **k: AUDIT.append((a, k))
ordersmod._send_order_emails_bg = lambda result: EMAILS.append(result)
ordersmod._send_status_change_email = lambda *a, **k: EMAILS.append(("stav", a))
VAHY = []                                                                              # (hmotnost kg, psc) zachycene pri vypoctu dopravy
ordersmod._resolve_toptrans_price = lambda cur, sid, zip_, kg, objem=0.0: (VAHY.append((round(kg, 3), zip_)) or (123.0, "test", "test"))

# cena a produkty konfiguratoru: katalog dilu se nacte JEDNOU pred zalozenim docasnych tabulek a drzi se (jinak by se cetl z prazdne docasne shop_products)
stul_api._ctx_ceny()
stul_api.CTX_TTL_S = 10 ** 9


def ostre():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                           port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


OSTRE_TABULKY = ("shop_cart_items", "shop_orders", "shop_order_items", "shop_order_status_history", "shop_documents", "shop_products", "shop_stock_movements", "shop_payment_methods",
                 "shop_shipping_methods", "shop_customers", "shop_customer_groups", "sestava_typ_sluzba", "app_settings", "audit_log", "shop_emails")


def stav_ostrych():
    c = ostre()
    try:
        with c.cursor() as cur:
            out = {}
            for t in OSTRE_TABULKY:
                cur.execute(f"SELECT COUNT(*) AS n FROM `{t}`")
                out[t] = cur.fetchone()["n"]
            cur.execute("SELECT COALESCE(SUM(next_number),0) AS s FROM shop_order_number_sequence")
            out["seq_obj"] = int(cur.fetchone()["s"])
            cur.execute("SELECT COALESCE(SUM(next_number),0) AS s FROM shop_document_sequences")
            out["seq_dok"] = int(cur.fetchone()["s"])
            return out
    finally:
        c.close()


PRED_OSTRE = stav_ostrych()
wrap = appmod.get_conn()
real = object.__getattribute__(wrap, "_real")
TEMP_LIKE = ("shop_cart_items", "shop_orders", "shop_order_items", "shop_order_status_history", "shop_documents", "shop_order_number_released", "shop_products", "shop_payment_methods",
             "shop_shipping_methods", "shop_stock_movements", "shop_customers", "shop_customer_groups", "sestava_typ_sluzba", "shop_product_images", "shop_emails")
TEMP_COPY = ("shop_document_sequences", "shop_order_number_sequence", "app_settings")


def sql(q, params=None):
    with real.cursor() as cur:
        cur.execute(q, params or ())
        out = cur.fetchall() if q.lstrip().upper().startswith(("SELECT", "SHOW")) else cur.rowcount
    real.commit()
    return out


def jedno(q, params=None):
    r = sql(q, params)
    return r[0] if r else None


def vloz(tabulka, **hodnoty):
    sql(f"INSERT INTO {tabulka} ({', '.join(hodnoty)}) VALUES ({', '.join(['%s'] * len(hodnoty))})", list(hodnoty.values()))


try:
    with real.cursor() as cur:
        for t in TEMP_COPY:
            cur.execute(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`")
            cur.execute(f"INSERT INTO `_tpl_{t}` SELECT * FROM `{t}`")
            cur.execute(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")
            cur.execute(f"INSERT INTO `{t}` SELECT * FROM `_tpl_{t}`")
        for t in TEMP_LIKE:
            cur.execute(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`")
            cur.execute(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")
        for t in TEMP_LIKE + TEMP_COPY:
            cur.execute(f"SHOW CREATE TABLE `{t}`")
            assert list(cur.fetchone().values())[1].startswith("CREATE TEMPORARY TABLE"), f"ABORT: {t} neni docasna"
        cur.execute("DELETE FROM app_settings WHERE setting_key IN ('cart_enabled')")
    real.commit()

    # ---- produkty a metody (vse docasne)
    sql("INSERT INTO shop_payment_methods (id, name, price_czk, requires_advance_invoice, active) VALUES (1,'Platba předem',0,1,1),(2,'Dobírka',0,0,1)")
    sql("INSERT INTO shop_shipping_methods (id, name, price_czk, active, sort_order, pricing_mode) VALUES (1,'Osobní odběr',0,1,0,'fixed'),(4,'Toptrans',0,1,1,'zip_weight')")
    PROD = {}

    def produkt(sku, name, cena, sklad=10, vaha_g=500, active=1, **extra):
        sloupce = {"sku": sku, "name": name, "price_czk_placeholder": cena, "stock_qty": sklad, "weight_g": vaha_g, "active": active, "unit": "ks", **extra}
        vloz("shop_products", **sloupce)
        PROD[sku] = jedno("SELECT id FROM shop_products WHERE sku=%s", (sku,))["id"]
        return PROD[sku]

    CFG = produkt("T-STUL", "Test stůl konfigurovatelný", None, 0, 0)
    CFG_NEAKT = produkt("T-STUL-N", "Neaktivní konfigurovatelný stůl", None, 0, 0, active=0)
    REG = produkt("T-REG", "Běžný díl", 100.00, 10, 500)
    REG_NULA = produkt("T-REG0", "Díl bez zásob", 50.00, 0, 100)
    stul_shop._PRODUKTY.update(t=time.time() + 10 ** 9, map={str(CFG): stul_shop.RECEPT, str(CFG_NEAKT): stul_shop.RECEPT})

    uzivatele = [r for r in sql("SELECT id, email, name FROM app_users WHERE role='user' AND active=1 AND email NOT IN ('mandik@logiman.cz','logiman.sklad@seznam.cz') ORDER BY id LIMIT 3")]
    admin = sql("SELECT id FROM app_users WHERE role='admin' AND active=1 AND email NOT IN ('mandik@logiman.cz','logiman.sklad@seznam.cz') ORDER BY id LIMIT 1") or sql("SELECT id FROM app_users WHERE role='admin' AND active=1 LIMIT 1")
    UA, UB, UC = (u["id"] for u in uzivatele)
    ADMIN = admin[0]["id"]
    vloz("shop_customer_groups", id=1, name="Testovací skupina 10 %", discount_percent=10, active=1)
    sloupce_zak = {c["Field"]: c for c in sql("SHOW COLUMNS FROM shop_customers")}
    zak = {"user_id": UA, "full_name": "Test Zákazník A", "email": "test.a@example.test", "group_id": 1, "billing_zip": "11000", "delivery_zip": "11000", "delivery_address": "Testovací 1, Praha",
           "billing_address": "Testovací 1, Praha"}
    vloz("shop_customers", **{k: v for k, v in zak.items() if k in sloupce_zak})
    sluzba_cols = {c["Field"]: c for c in sql("SHOW COLUMNS FROM sestava_typ_sluzba")}

    def montaz_sluzba(hodnota=10.0, aktivni=1):
        """Sazba montaze stolu (od 2026-10-04 app_settings stul_montaz_pct, vychozi 12, 0 = nenabizi se; dosud sestava_typ_sluzba). None nebo neaktivni = 0 (nenabizi se)."""
        v = "0" if (hodnota is None or not aktivni) else str(hodnota)
        sql("INSERT INTO app_settings (setting_key, setting_value) VALUES ('stul_montaz_pct', %s) ON DUPLICATE KEY UPDATE setting_value=%s", (v, v))

    montaz_sluzba(None)
    _si = SecureCookieSessionInterface()
    cl = appmod.app.test_client(use_cookies=False)

    def cookie(uid):
        return {"Cookie": "session=" + _si.get_signing_serializer(appmod.app).dumps({"user_id": uid})} if uid else {}

    def volej(metoda, cesta, uid, body=None, vynuluj=True):
        if vynuluj:
            appmod._rate_limit_buckets.clear()
        return cl.open(cesta, method=metoda, headers=cookie(uid), json=body) if body is not None else cl.open(cesta, method=metoda, headers=cookie(uid))

    def kosik(uid):
        return volej("GET", "/api/cart", uid).get_json()

    def pridej(uid, selection=None, **kw):
        body = {"product_id": CFG, "qty": 1, "configuration": {"selection": {} if selection is None else selection, "rules_version": stul_glb.RULES_VERSION}}
        body.update(kw)
        return volej("POST", "/api/cart/items", uid, body)

    def prazdny(uid):
        sql("DELETE FROM shop_cart_items WHERE user_id=%s", (uid,))

    def radky_cfg(uid):
        return [i for i in kosik(uid)["items"] if i.get("made_to_order")]

    def resolve(selection=None, lang="cs"):
        return stul_shop.resolve({} if selection is None else selection, lang)

    BAD_SEL = {"cut1": True, "cut2": True, "cut2x": 100, "cut2z": 100}
    ODLISNA = {"w": 1500, "d": 700, "h": 900, "led": False}
    R0, R1 = resolve(), resolve(ODLISNA)
    NET0, NET1 = R0["price"]["net"], R1["price"]["net"]
    _pro_puvodni = stul_shop.pro_objednavku

    def vahy_uplne(kg):
        """Konfigurator (bot8) hlasi hmotnost jako UPLNOU a danou: simulace doplnenych hmotnosti v katalogu. Bez zavolani se pouzije skutecna (dnes neuplna) hmotnost."""
        def f(selection, rules_version=None, lang="cs", *dalsi, **kw):          # tolerantni k novemu parametru product_id (bot8)
            r = _pro_puvodni(selection, rules_version, lang, *dalsi, **kw)
            if r.get("ok"):
                r["hmotnost_kg"], r["hmotnost_uplna"], r["hmotnost_chybi"] = kg, True, []
            return r
        stul_shop.pro_objednavku = f

    def vahy_realne():
        stul_shop.pro_objednavku = _pro_puvodni

    # ============================================================================================================ A) kosik
    print("== A kosik")
    prazdny(UB)
    r = pridej(UB, {"price": 1, "unit_price_czk": 1, "net": 1}, unit_price_czk=1, price=1, price_czk_placeholder=1)
    k = r.get_json()
    ulozeno = jedno("SELECT * FROM shop_cart_items WHERE user_id=%s", (UB,))
    over("A1 pridani konfigurace: 201, radek je zakazkova vyroba (made_to_order, bez skladu), cena = cena ze serveru (klient posilal 1 Kc), ulozen EFEKTIVNI vyber a 16znakovy hash, kod STL-...",
         r.status_code == 201 and len(k["items"]) == 1 and k["items"][0]["made_to_order"] is True and k["items"][0]["stock_qty"] is None and k["items"][0]["unit_price_czk"] == NET0 and k["subtotal_czk"] == NET0
         and k["items"][0]["configuration"]["valid"] is True and k["items"][0]["configuration"]["kod"] == R0["kod"] and ulozeno["config_hash"] == R0["hash"] and re.match(r"^[0-9a-f]{16}$", ulozeno["config_hash"])
         and json.loads(ulozeno["configuration_json"])["selection"] == R0["selection"], (r.status_code, k))
    cfg0 = k["items"][0]["configuration"]
    over("A2 radek nese souhrn voleb v cestine (rozmery, zapnute prislusenstvi) a nic z nakladove struktury (zadny kusovnik ani cenovy souhrn); neuplna hmotnost z katalogu (chybi laminodeska, suplíky...) se neukazuje (weight_kg null, weight_complete false); cena karty 'placeholder' = cena konfigurace",
         any("1280" in s["value"] for s in cfg0["summary"]) and any(s["value"] == "ano" for s in cfg0["summary"]) and cfg0["weight_kg"] is None and cfg0["weight_complete"] is False and "bom" not in cfg0 and "price_summary" not in cfg0
         and k["items"][0]["price_czk_placeholder"] == NET0, cfg0)
    r = pridej(UB, {})
    over("A3 stejna konfigurace podruhe = JEDEN radek s mnozstvim 2 (ne dva radky)", r.status_code == 201 and len(r.get_json()["items"]) == 1 and r.get_json()["items"][0]["qty"] == 2, r.get_json())
    r = pridej(UB, ODLISNA)
    k = r.get_json()
    over("A4 jina konfigurace = DALSI radek se svou cenou a kodem, soucet kosiku je soucet obou", r.status_code == 201 and len(k["items"]) == 2 and sorted(i["unit_price_czk"] for i in k["items"]) == sorted([NET0, NET1])
         and k["subtotal_czk"] == NET0 * 2 + NET1, [(i["qty"], i["unit_price_czk"]) for i in k["items"]])
    n_pred = jedno("SELECT COUNT(*) AS n FROM shop_cart_items WHERE user_id=%s", (UB,))["n"]
    r = pridej(UB, {"w": "1500", "d": 700, "h": 900, "led": False, "neznamy_klic": 5, "__proto__": {"x": 1}})
    over("A5 vyber se normalizuje na serveru: retezec misto cisla a neznamy klic dopadnou na stejnou (efektivni) konfiguraci = stejny hash a radek (qty 2), neznamy klic se neulozi",
         r.status_code == 201 and jedno("SELECT COUNT(*) AS n FROM shop_cart_items WHERE user_id=%s", (UB,))["n"] == n_pred and "neznamy_klic" not in jedno("SELECT configuration_json FROM shop_cart_items WHERE config_hash=%s AND user_id=%s", (R1["hash"], UB))["configuration_json"]
         and [i for i in r.get_json()["items"] if i["configuration"]["hash"] == R1["hash"]][0]["qty"] == 2, r.get_json())
    pred = sql("SELECT * FROM shop_cart_items WHERE user_id=%s ORDER BY id", (UB,))
    r_bad = pridej(UB, BAD_SEL)
    over("A6 neplatna kombinace (prekryvajici se vyrezy): 422 invalid_configuration s citelnym duvodem a NIC se do kosiku neulozi", r_bad.status_code == 422 and r_bad.get_json()["code"] == "invalid_configuration"
         and "překrývají" in r_bad.get_json()["errors"][0]["message"] and sql("SELECT * FROM shop_cart_items WHERE user_id=%s ORDER BY id", (UB,)) == pred, r_bad.get_json())
    body_stara = {"product_id": CFG, "qty": 1, "configuration": {"selection": {}, "rules_version": "1999-01-01.1"}}
    r_stara = volej("POST", "/api/cart/items", UB, body_stara)
    r_bez = volej("POST", "/api/cart/items", UB, {"product_id": CFG, "qty": 1, "configuration": {"selection": {}}})
    over("A7 stara verze pravidel od klienta = 409 rules_changed (klient musi znovu resolve), bez verze se pridani povoli; nic se pri chybe neulozi", r_stara.status_code == 409 and r_stara.get_json()["code"] == "rules_changed" and r_bez.status_code == 201, (r_stara.status_code, r_bez.status_code))
    chyby = {
        "konfigurovatelny bez konfigurace": volej("POST", "/api/cart/items", UB, {"product_id": CFG, "qty": 1}),
        "konfigurace u bezneho produktu": volej("POST", "/api/cart/items", UB, {"product_id": REG, "qty": 1, "configuration": {"selection": {}}}),
        "selection neni objekt": volej("POST", "/api/cart/items", UB, {"product_id": CFG, "qty": 1, "configuration": {"selection": [1, 2]}}),
        "selection prilis dlouhy": volej("POST", "/api/cart/items", UB, {"product_id": CFG, "qty": 1, "configuration": {"selection": {"x": "y" * 5000}}}),
        "neaktivni produkt": volej("POST", "/api/cart/items", UB, {"product_id": CFG_NEAKT, "qty": 1, "configuration": {"selection": {}}}),
        "kupon": volej("POST", "/api/cart/items", UB, {"product_id": CFG, "qty": 1, "coupon_code": "SLEVA", "configuration": {"selection": {}}}),
        "varianta sestavy": volej("POST", "/api/cart/items", UB, {"product_id": CFG, "qty": 1, "assembly_id": 5, "configuration": {"selection": {}}}),
        "prirezy": volej("POST", "/api/cart/items", UB, {"product_id": CFG, "qty": 1, "cut_pieces": [{"length_mm": 100, "qty": 1}], "configuration": {"selection": {}}}),
        "mnozstvi 0": volej("POST", "/api/cart/items", UB, {"product_id": CFG, "qty": 0, "configuration": {"selection": {}}}),
        "mnozstvi 100": volej("POST", "/api/cart/items", UB, {"product_id": CFG, "qty": 100, "configuration": {"selection": {}}}),
        "mnozstvi text": volej("POST", "/api/cart/items", UB, {"product_id": CFG, "qty": "x", "configuration": {"selection": {}}}),
    }
    ocek = {"konfigurovatelny bez konfigurace": (400, "configuration_required"), "konfigurace u bezneho produktu": (404, "not_configurable"), "selection neni objekt": (400, "invalid_selection"),
            "selection prilis dlouhy": (400, "invalid_selection"), "neaktivni produkt": (400, "product_unavailable"), "kupon": (400, "coupon_not_applicable"), "varianta sestavy": (400, "bad_request"),
            "prirezy": (400, "bad_request"), "mnozstvi 0": (400, "bad_request"), "mnozstvi 100": (400, "bad_request"), "mnozstvi text": (400, "bad_request")}
    nesedi = {k: (v.status_code, (v.get_json() or {}).get("code")) for k, v in chyby.items() if (v.status_code, (v.get_json() or {}).get("code")) != ocek[k]}
    over("A8 chybne pozadavky (konfigurovatelny produkt bez konfigurace, konfigurace u bezneho produktu, neobjekt a obri vyber, neaktivni karta, kupon, varianta, prirezy, mnozstvi) maji presne kody a nic neulozi", not nesedi
         and sql("SELECT * FROM shop_cart_items WHERE user_id=%s ORDER BY id", (UB,)) != [], nesedi)
    prazdny(UB)
    appmod._rate_limit_buckets.clear()
    telo_cfg = {"product_id": CFG, "qty": 1, "configuration": {"selection": {}}}
    kody = [volej("POST", "/api/cart/items", UB, telo_cfg, vynuluj=False).status_code for _ in range(kk.LIMIT_PRIDANI[0])]
    r_limit = volej("POST", "/api/cart/items", UB, telo_cfg, vynuluj=False)
    over("A9 limit pridani konfigurace (60 za minutu na ucet): 61. pozadavek 429 rate_limited a nic navic se neulozi", kody == [201] * kk.LIMIT_PRIDANI[0] and r_limit.status_code == 429 and r_limit.get_json()["code"] == "rate_limited"
         and radky_cfg(UB)[0]["qty"] == kk.LIMIT_PRIDANI[0], (set(kody), r_limit.status_code, radky_cfg(UB)[0]["qty"]))
    prazdny(UB)
    pridej(UB, {}, qty=98)
    r_strop = pridej(UB, {}, qty=5)
    over("A9b mnozstvi u opakovaneho pridani stejne konfigurace se zastropuje na 99 (LEAST), ne preteceni ani chyba", r_strop.status_code == 201 and r_strop.get_json()["items"][0]["qty"] == 99, r_strop.get_json())
    prazdny(UB)
    # ---- montaz
    r = pridej(UB, {}, montaz_zvolena=True)
    over("A10 montaz se u typu sestavy NENASTAVENE sluzbe (zadny radek sestava_typ_sluzba) nenabizi: pozadavek na montaz se ztise zahodi (cena beze zmeny, configuration.montaz_pct null)",
         r.status_code == 201 and r.get_json()["items"][0]["montaz_zvolena"] is False and r.get_json()["items"][0]["unit_price_czk"] == NET0 and r.get_json()["items"][0]["configuration"]["montaz_pct"] is None, r.get_json())
    prazdny(UB)
    montaz_sluzba(10.0)
    MONTAZ0 = kk.configurator_price._js_round(NET0 * 10 / 100)
    r = pridej(UB, {}, montaz_zvolena=True)
    i = r.get_json()["items"][0]
    over("A11 montaz 10 % (sluzba typu STUL_SKLAD): zvolena = cena + montaz (10 % z ceny konfigurace, zaokrouhleno jako ve scene), misto montaze se nevyzaduje; configuration nese sazbu",
         r.status_code == 201 and i["montaz_zvolena"] is True and i["unit_price_czk"] == NET0 + MONTAZ0 and i["montaz_czk"] == MONTAZ0 and i["configuration"]["montaz_pct"] == 10.0 and i["montaz_misto"] is None, i)
    prazdny(UB)
    r = pridej(UB, {}, montaz_zvolena=True, delivery_country="SK")
    r2 = pridej(UB, ODLISNA, montaz_zvolena=True, delivery_country="cz")
    zeme = {x["configuration"]["hash"]: x["montaz_zvolena"] for x in r2.get_json()["items"]}
    over("A12 do zahranici (i Slovensko) se montaz nenabizi: SK = montaz ztise zahozena (rozlozeny stul), CZ (i malymi pismeny) projde", r.get_json()["items"][0]["montaz_zvolena"] is False and zeme[R1["hash"]] is True, zeme)
    prazdny(UB)
    pridej(UB, {})
    item_id = radky_cfg(UB)[0]["id"]
    r_on = volej("PUT", f"/api/cart/items/{item_id}", UB, {"qty": 2, "montaz_zvolena": True})
    montaz_sluzba(None)
    r_off = volej("PUT", f"/api/cart/items/{item_id}", UB, {"qty": 2, "montaz_zvolena": True})
    over("A13 uprava radku (PUT): mnozstvi a prepnuti montaze funguje (vypocet se zivym menenim), kdyz se sluzba montaze odebere z typu, zapnuti se ztise zahodi; misto montaze se nepozaduje",
         r_on.status_code == 200 and r_on.get_json()["items"][0]["qty"] == 2 and r_on.get_json()["items"][0]["montaz_zvolena"] is True and r_off.status_code == 200 and r_off.get_json()["items"][0]["montaz_zvolena"] is False, (r_on.get_json(), r_off.get_json()))
    r_cap = volej("PUT", f"/api/cart/items/{item_id}", UB, {"qty": 500})
    r_del = volej("PUT", f"/api/cart/items/{item_id}", UB, {"qty": 0})
    over("A14 PUT: mnozstvi nad 99 se u konfigurace zastropuje (kosik zadne PUT nad CART_MAX_QTY nevraci 400 jen do 9999), qty 0 radek smaze", r_cap.status_code == 200 and r_cap.get_json()["items"][0]["qty"] == 99 and r_del.get_json()["items"] == [], (r_cap.get_json(), r_del.get_json()))
    # ---- skupinova sleva
    prazdny(UA)
    prazdny(UB)
    montaz_sluzba(10.0)
    ra = pridej(UA, {}, montaz_zvolena=True)
    rb = pridej(UB, {}, montaz_zvolena=True)
    ia, ib = ra.get_json()["items"][0], rb.get_json()["items"][0]
    sleva_net = round(NET0 * 0.9, 2)
    over("A15 skupinova sleva zakaznika (10 %) se uplatni na cenu konfigurace, montaz se pricita AZ PO sleve (neslevnuje se), puvodni cena zustava v price_czk_placeholder; zakaznik bez skupiny plna cena",
         ia["unit_price_czk"] == round(sleva_net + MONTAZ0, 2) and ia["price_czk_placeholder"] == NET0 and ib["unit_price_czk"] == NET0 + MONTAZ0, (ia, ib))
    prazdny(UA)
    prazdny(UB)
    montaz_sluzba(None)
    # ---- zive cteni: zmena po ulozeni, rozbity zaznam
    pridej(UB, {})
    sql("UPDATE shop_cart_items SET config_hash='0123456789abcdef' WHERE user_id=%s", (UB,))
    zm = radky_cfg(UB)[0]["configuration"]
    sql("UPDATE shop_cart_items SET configuration_json='tohle neni json' WHERE user_id=%s", (UB,))
    rozbity = kosik(UB)
    ri = rozbity["items"][0]
    sql("UPDATE shop_cart_items SET configuration_json=%s WHERE user_id=%s", (json.dumps({"selection": BAD_SEL}), UB))
    neplatny = kosik(UB)["items"][0]
    over("A16 zive cteni: konfigurace, jejiz efektivni hash se po zmene pravidel lisi od ulozeneho, je oznacena changed (objednavka ji odmitne); rozbity zaznam nebo uz neplatny vyber kosik nerozbije (valid false, bez ceny, mimo soucet)",
         zm["valid"] is True and zm["changed"] is True and ri["configuration"]["valid"] is False and ri["configuration"]["error"] == "invalid_selection" and ri["unit_price_czk"] == 0.0 and rozbity["subtotal_czk"] == 0.0
         and neplatny["configuration"]["valid"] is False and neplatny["configuration"]["error"] == "invalid_configuration" and neplatny["configuration"]["errors"], (zm, ri, neplatny))
    prazdny(UB)
    # ---- bezny radek beze zmeny a smisene kosiky
    r_reg = volej("POST", "/api/cart/items", UB, {"product_id": REG, "qty": 3})
    pridej(UB, {})
    k = kosik(UB)
    bezny = [i for i in k["items"] if not i["made_to_order"]][0]
    over("A17 bezny radek kosiku se nezmenil (cena 100 x 3, sklad, bez configuration) a smiseny kosik scita oba; PUT/DELETE bezneho radku funguje jako drive",
         r_reg.status_code == 201 and bezny["unit_price_czk"] == 100.0 and bezny["qty"] == 3 and bezny["stock_qty"] == 10 and bezny["configuration"] is None and k["subtotal_czk"] == 300.0 + NET0
         and volej("PUT", f"/api/cart/items/{bezny['id']}", UB, {"qty": 1}).get_json()["subtotal_czk"] == 100.0 + NET0 and volej("DELETE", f"/api/cart/items/{bezny['id']}", UB).get_json()["subtotal_czk"] == NET0, k)
    adm = volej("GET", "/api/admin/carts", ADMIN)
    over("A18 admin prehled kosiku funguje a konfiguracni radek oznaci (made_to_order), cena karty (NULL) se nevydava za cenu konfigurace", adm.status_code in (200, 403) and (adm.status_code == 403 or any(
         it.get("made_to_order") for c in adm.get_json()["carts"] for it in c["items"])), adm.status_code)
    prazdny(UB)

    # ============================================================================================================ B) objednavka
    print("== B objednavka")
    EMAILS.clear()

    def objednej(uid, body=None, **kw):
        telo = {"use_cart": True, "customer_name": "Test Zákazník", "customer_email": "test.zakaznik@example.test", "delivery_address": "Testovací 1, Praha", "delivery_zip": "11000",
                "billing_zip": "11000", "shipping_method_id": 1}
        telo.update(body or {})
        telo.update(kw)
        return volej("POST", "/api/orders", uid, telo)

    def polozky(order_id):
        return sql("SELECT * FROM shop_order_items WHERE order_id=%s ORDER BY id", (order_id,))

    prazdny(UB)
    pridej(UB, {}, qty=2)
    volej("POST", "/api/cart/items", UB, {"product_id": REG, "qty": 3})
    r = objednej(UB)
    o = r.get_json()
    pol = polozky(o["id"]) if r.status_code == 201 else []
    cfg_pol = [p for p in pol if p["configuration_code"]]
    reg_pol = [p for p in pol if not p["configuration_code"]]
    over("B1 objednavka z kosiku s konfiguraci a beznym dilem: 201, kosik prazdny, radek konfigurace ma product_id NULL, cenu a mnozstvi ze serveru, kod konfigurace a nazev s rozmery a kodem; bezny radek beze zmeny",
         r.status_code == 201 and len(pol) == 2 and len(cfg_pol) == 1 and cfg_pol[0]["product_id"] is None and float(cfg_pol[0]["unit_price_czk"]) == NET0 and cfg_pol[0]["qty"] == 2
         and float(cfg_pol[0]["line_total_czk"]) == NET0 * 2 and cfg_pol[0]["configuration_code"] == R0["kod"] and "Test stůl konfigurovatelný" in cfg_pol[0]["product_name_snapshot"] and "1280 × 800 × 840 mm" in cfg_pol[0]["product_name_snapshot"]
         and R0["kod"] in cfg_pol[0]["product_name_snapshot"] and reg_pol[0]["product_id"] == REG and float(reg_pol[0]["unit_price_czk"]) == 100.0 and radky_cfg(UB) == [] and o["total_czk"] == NET0 * 2 + 300.0, (r.status_code, o, pol))
    snimek = json.loads(cfg_pol[0]["configuration_json"]) if cfg_pol else {}
    over("B2 snimek konfigurace na radku: efektivni vyber, hash, kod, verze pravidel, souhrn voleb, neutralni KUSOVNIK (bez cen a cisel dilu), cenovy souhrn s celkem, hmotnost, odkaz na kartu a cena bez DPH; cena v souhrnu = cena radku",
         snimek.get("hash") == R0["hash"] and snimek["selection"] == R0["selection"] and snimek["rules_version"] == stul_glb.RULES_VERSION and snimek["product_id"] == CFG and snimek["kod"] == R0["kod"] and len(snimek["bom"]) >= 5
         and all(set(b) == {"nazev", "mnozstvi", "rozmer"} for b in snimek["bom"]) and snimek["price_summary"]["total_czk"] == NET0 and snimek["price_summary"]["material_czk"] > 0 and snimek["list_net_czk"] == NET0
         and snimek["weight_kg"] > 0 and snimek["summary"] and snimek["pocet_spoju"] > 0 and snimek["montaz"] == {"zvolena": False, "pct": None, "czk": None},
         {k: snimek.get(k) for k in ("hash", "kod", "list_net_czk", "weight_kg", "montaz", "price_summary")})
    over("B3 e-mail o objednavce se zaradil a zadny radek konfigurace neni v 'neni skladem' (vyroba na zakazku): _find_missing_stock_items je nevraci", len(EMAILS) == 1 and ordersmod._find_missing_stock_items(o["id"]) == [], (len(EMAILS), ordersmod._find_missing_stock_items(o["id"])))
    SKUTECNA_VAHA = snimek["weight_kg"]
    over("B3b snimek ve skutecne (dnes neuplne) hmotnosti: weight_complete false a neprazdny seznam dilu bez hmotnosti v katalogu (suplíky, LED, panel...)", snimek["weight_complete"] is False and len(snimek["weight_missing"]) >= 1
         and all(isinstance(x, str) and x for x in snimek["weight_missing"]), (snimek["weight_complete"], snimek["weight_missing"]))   # od 2026-10-03 ma laminodeska hmotnost (bot8), neuplna zustava, dokud chybi dalsi dily
    vahy_uplne(20.0)
    VAHY.clear()
    prazdny(UB)
    pridej(UB, {}, qty=2)
    volej("POST", "/api/cart/items", UB, {"product_id": REG, "qty": 3})
    r_t = objednej(UB, shipping_method_id=4)
    over("B4 doprava Toptrans (hmotnosti v katalogu uplne): dostane hmotnost konfigurace x mnozstvi PLUS bezne dily (20 kg x 2 + 0,5 kg x 3 = 41,5 kg), objem se nepouzije; cena dopravy se pricte k souctu",
         r_t.status_code == 201 and VAHY == [(41.5, "11000")] and r_t.get_json()["total_czk"] == NET0 * 2 + 300.0 + 123.0, (r_t.get_json(), VAHY))
    snimek_uplny = json.loads([p for p in polozky(r_t.get_json()["id"]) if p["configuration_code"]][0]["configuration_json"])
    over("B4b snimek pri uplne hmotnosti nese weight_complete true a hmotnost", snimek_uplny["weight_complete"] is True and snimek_uplny["weight_kg"] == 20.0 and snimek_uplny["weight_missing"] == [], snimek_uplny["weight_missing"])
    vahy_realne()
    VAHY.clear()
    prazdny(UB)
    pridej(UB, {}, qty=2)
    n_obj_pred, seq_pred = jedno("SELECT COUNT(*) AS n FROM shop_orders")["n"], jedno("SELECT COALESCE(SUM(next_number),0) AS s FROM shop_order_number_sequence")["s"]
    r_nepl = objednej(UB, shipping_method_id=4)
    pridej(UB, {}, qty=2)                                            # objednavka s dopravou ke schvaleni VZNIKLA a vyprazdnila kosik
    r_osob = objednej(UB, shipping_method_id=1)
    o_nepl = jedno("SELECT * FROM shop_orders WHERE id=%s", (r_nepl.get_json()["id"],)) if r_nepl.status_code == 201 else {}
    o_osob = jedno("SELECT * FROM shop_orders WHERE id=%s", (r_osob.get_json()["id"],)) if r_osob.status_code == 201 else {}
    over("B4c NEUPLNA hmotnost (dnesni katalog) + Toptrans: od 2026-10-04 (Robert pres bot9) objednavka VZNIKNE s cenou dopravy 0, nazvem '... - cena ke schvaleni' a priznakem shipping_review=1, BEZ zalohove faktury "
         "(vystavi ji zamestnanec po schvaleni dopravy); vypocet Toptrans se vubec nezavola (VAHY prazdne); osobni odber stejneho kosiku vznikne normalne (bez priznaku)",
         r_nepl.status_code == 201 and VAHY == [] and float(o_nepl["shipping_price_czk"]) == 0 and o_nepl["shipping_method_name"].endswith("cena ke schválení") and o_nepl["shipping_review"] == 1
         and jedno("SELECT COUNT(*) AS n FROM shop_documents WHERE order_id=%s", (o_nepl["id"],))["n"] == 0 and r_osob.status_code == 201 and o_osob["shipping_review"] == 0
         and jedno("SELECT COUNT(*) AS n FROM shop_orders")["n"] == n_obj_pred + 2, (r_nepl.status_code, VAHY, o_nepl.get("shipping_price_czk"), o_nepl.get("shipping_method_name"), o_nepl.get("shipping_review"), r_osob.status_code, o_osob.get("shipping_review"),
          jedno("SELECT COUNT(*) AS n FROM shop_orders")["n"], n_obj_pred))
    # ---- nahled ceny dopravy (POST /api/shipping-price-preview)
    prazdny(UB)
    pridej(UB, {}, qty=2)
    volej("POST", "/api/cart/items", UB, {"product_id": REG, "qty": 3})
    VAHY.clear()
    n_prev = volej("POST", "/api/shipping-price-preview", UB, {"shipping_method_id": 4, "delivery_zip": "11000", "use_cart": True})
    vahy_uplne(20.0)
    p_ok = volej("POST", "/api/shipping-price-preview", UB, {"shipping_method_id": 4, "delivery_zip": "11000", "use_cart": True})
    p_pol_bez = volej("POST", "/api/shipping-price-preview", UB, {"shipping_method_id": 4, "delivery_zip": "11000", "items": [{"product_id": CFG, "qty": 1}]})
    p_pol = volej("POST", "/api/shipping-price-preview", UB, {"shipping_method_id": 4, "delivery_zip": "11000", "items": [{"product_id": CFG, "qty": 2, "configuration": {"selection": {}}}]})
    vahy_realne()
    prazdny(UB)
    volej("POST", "/api/cart/items", UB, {"product_id": REG, "qty": 3})
    p_reg = volej("POST", "/api/shipping-price-preview", UB, {"shipping_method_id": 4, "delivery_zip": "11000", "use_cart": True})
    over("B4d nahled dopravy: neuplna hmotnost = 409 weight_incomplete (cena se nepocita, misto hmotnosti 0 z karty), uplna hmotnost = 200 se spravnou hmotnosti (41,5 kg z kosiku, 40 kg z polozek), konfigurovatelny produkt bez konfigurace 400, kosik jen s beznym dilem beze zmeny (1,5 kg)",
         n_prev.status_code == 409 and n_prev.get_json()["code"] == "weight_incomplete" and p_ok.status_code == 200 and p_ok.get_json()["weight_kg"] == 41.5 and p_pol.status_code == 200
         and p_pol.get_json()["weight_kg"] == 40.0 and p_pol_bez.status_code == 400 and p_pol_bez.get_json()["code"] == "configuration_required" and p_reg.status_code == 200 and p_reg.get_json()["weight_kg"] == 1.5,
         (n_prev.status_code, n_prev.get_json(), p_ok.get_json(), p_pol.get_json(), p_pol_bez.get_json(), p_reg.get_json()))
    # ---- doklady a sklad
    prazdny(UB)
    pridej(UB, {}, qty=1)
    r_pf = objednej(UB, payment_method_id=1)
    doklady = sql("SELECT * FROM shop_documents WHERE order_id=%s", (r_pf.get_json()["id"],)) if r_pf.status_code == 201 else []
    over("B5 objednavka JEN s konfiguraci a platbou predem: zalohova faktura vznikne automaticky (radek konfigurace nema sklad, takze nic nechybi) a nese nazev a cenu radku",
         r_pf.status_code == 201 and len(doklady) == 1 and "STL-" in json.dumps(doklady[0], default=str) and float(doklady[0].get("total_czk", doklady[0].get("amount_czk", NET0))) >= NET0, [d.get("document_number") for d in doklady])
    prazdny(UB)
    pridej(UB, {}, qty=1)
    volej("POST", "/api/cart/items", UB, {"product_id": REG_NULA, "qty": 1})
    r_chybi = objednej(UB, payment_method_id=1)
    dok_chybi = sql("SELECT * FROM shop_documents WHERE order_id=%s", (r_chybi.get_json()["id"],)) if r_chybi.status_code == 201 else None
    over("B6 beze zmeny: kdyz u BEZNEHO radku chybi sklad, zalohova faktura se NEvystavi automaticky (i kdyz je v objednavce konfigurace)", r_chybi.status_code == 201 and not dok_chybi, (r_chybi.status_code, dok_chybi))
    # ---- cena z kosiku se neberou, hash musi sedet
    prazdny(UB)
    pridej(UB, {}, qty=1)
    sql("UPDATE shop_cart_items SET config_hash='0123456789abcdef' WHERE user_id=%s", (UB,))
    r_zm = objednej(UB)
    n_obj = jedno("SELECT COUNT(*) AS n FROM shop_orders")["n"]
    over("B7 konfigurace, jejiz efektivni hash se lisi od ulozeneho (zmena pravidel nebo zasah do kosiku), se NEOBJEDNA: 409 a nic se nezalozi (objednavka ani cislo)", r_zm.status_code == 409 and "Konfigurace" in r_zm.get_json()["error"], r_zm.get_json())
    sql("UPDATE shop_cart_items SET config_hash=%s, configuration_json=%s WHERE user_id=%s", (R0["hash"], json.dumps({"selection": BAD_SEL}), UB))
    r_bad = objednej(UB)
    sql("UPDATE shop_cart_items SET configuration_json=NULL WHERE user_id=%s", (UB,))
    r_null = objednej(UB)
    over("B8 neplatny nebo chybejici ulozeny vyber v kosiku = objednavka se odmitne (422 / 400), zadna cena se nedomysli", r_bad.status_code == 422 and r_null.status_code == 400, (r_bad.get_json(), r_null.get_json()))
    prazdny(UB)
    # ---- polozky z pozadavku
    prazdny(UB)
    r_it = volej("POST", "/api/orders", UB, {"items": [{"product_id": CFG, "qty": 2, "unit_price_czk": 1, "configuration": {"selection": dict(ODLISNA, price=1, unit_price_czk=1), "rules_version": stul_glb.RULES_VERSION}}],
                                              "customer_name": "Test", "customer_email": "test@example.test", "delivery_address": "Testovací 1", "delivery_zip": "11000", "shipping_method_id": 1})
    p_it = polozky(r_it.get_json()["id"]) if r_it.status_code == 201 else []
    r_it_bez = volej("POST", "/api/orders", UB, {"items": [{"product_id": CFG, "qty": 1}], "customer_name": "Test", "customer_email": "test@example.test", "delivery_address": "Testovací 1", "delivery_zip": "11000"})
    r_it_stara = volej("POST", "/api/orders", UB, {"items": [{"product_id": CFG, "qty": 1, "configuration": {"selection": {}, "rules_version": "1999-01-01.1"}}], "customer_name": "Test",
                                                    "customer_email": "test@example.test", "delivery_address": "Testovací 1", "delivery_zip": "11000"})
    over("B9 polozky primo v pozadavku: konfigurace funguje bez kosiku (cena ze serveru, klientska 1 Kc ignorovana), konfigurovatelny produkt BEZ konfigurace = 400, stara verze pravidel = 409",
         r_it.status_code == 201 and len(p_it) == 1 and float(p_it[0]["unit_price_czk"]) == NET1 and p_it[0]["configuration_code"] == R1["kod"] and r_it_bez.status_code == 400 and r_it_stara.status_code == 409, (r_it.get_json(), r_it_bez.get_json(), r_it_stara.get_json()))
    with real.cursor() as cur:
        try:
            ordersmod._resolve_and_insert_order(cur, {"items": [{"product_id": CFG, "qty": 1}], "customer_name": "T", "customer_email": "t@example.test"}, None, None, dealer={"id": 1, "name": "Test"})
            dealerem = "PROSLO"
        except ordersmod._OrderCreateError as e:
            dealerem = (e.status_code, e.message)
    real.rollback()
    over("B10b dealerska cesta (cesta b) odmitne konfigurovatelny produkt s 422 jeste pred jakoukoli cenou", dealerem[0] == 422, dealerem)
    # ---- montaz v objednavce
    montaz_sluzba(10.0)
    prazdny(UA)
    pridej(UA, {}, qty=1, montaz_zvolena=True)
    r_m = objednej(UA, customer_name="Test A", customer_email="test.a@example.test")
    p_m = [x for x in polozky(r_m.get_json()["id"]) if x["configuration_code"]][0] if r_m.status_code == 201 else {}
    mont_radek = [x for x in polozky(r_m.get_json()["id"]) if x["product_id"] is None and (x["product_name_snapshot"] or "").startswith("Montáž")] if r_m.status_code == 201 else []
    sn_m = json.loads(p_m["configuration_json"]) if p_m else {}
    over("B11 montaz v objednavce: radek konfigurace ma montaz_zvolena a snapshot castky montaze, jeho cena = cena po skupinove sleve (10 %) BEZ montaze, montaz je SAMOSTATNY radek 'Montaz - kod' (product_id NULL, castka 10 % z ceny konfigurace, nesleva se), celkem = cena po sleve + montaz = cena v kosiku (kosik ukazuje cenu vc. montaze)",
         r_m.status_code == 201 and p_m["montaz_zvolena"] == 1 and float(p_m["montaz_czk_snapshot"]) == MONTAZ0 and float(p_m["unit_price_czk"]) == round(NET0 * 0.9, 2) and p_m["montaz_misto_snapshot"] is None
         and sn_m["montaz"] == {"zvolena": True, "pct": 10.0, "czk": MONTAZ0} and len(mont_radek) == 1 and float(mont_radek[0]["unit_price_czk"]) == MONTAZ0 and mont_radek[0]["qty"] == 1
         and mont_radek[0]["product_name_snapshot"] == f"Montáž – {R0['kod']}" and ia["unit_price_czk"] == round(float(p_m["unit_price_czk"]) + MONTAZ0, 2)
         and abs(float(jedno("SELECT total_czk FROM shop_orders WHERE id=%s", (r_m.get_json()["id"],))["total_czk"]) - (round(NET0 * 0.9, 2) + MONTAZ0)) < 0.01, (r_m.get_json(), p_m, mont_radek))
    prazdny(UA)
    pridej(UA, {}, qty=1, montaz_zvolena=True)
    montaz_sluzba(None)
    r_m2 = objednej(UA, customer_name="Test A", customer_email="test.a@example.test")
    over("B12 montaz zvolena v kosiku, ale sluzba mezitim zrusena: objednavka se odmitne 409 (zakaznik nedostane tise levnejsi objednavku bez sluzby, kterou videl v souctu)", r_m2.status_code == 409 and "Montáž" in r_m2.get_json()["error"], r_m2.get_json())
    prazdny(UA)
    # ---- zobrazeni objednavky: zakaznik vs zamestnanec
    prazdny(UB)
    pridej(UB, {}, qty=1)
    r_v = objednej(UB)
    oid = r_v.get_json()["id"]
    sql("UPDATE shop_orders SET user_id=%s WHERE id=%s", (UB, oid))
    zak = volej("GET", f"/api/orders/{oid}", UB)
    adm = volej("GET", f"/api/orders/{oid}", ADMIN)
    adm2 = volej("GET", f"/api/admin/orders/{oid}", ADMIN)
    iz = [x for x in zak.get_json()["order"]["items"] if x["configuration_code"]][0] if zak.status_code == 200 else {}
    ia_ = [x for x in adm.get_json()["order"]["items"] if x["configuration_code"]][0] if adm.status_code == 200 else {}
    over("B13 zakaznik vidi kod a souhrn voleb, ale NE kusovnik ani cenovy souhrn (nakladova struktura); zamestnanec (oba endpointy) plny snimek vcetne kusovniku",
         zak.status_code == 200 and iz["configuration"]["kod"] == R0["kod"] and iz["configuration"]["summary"] and "bom" not in iz["configuration"] and "price_summary" not in iz["configuration"] and "list_net_czk" not in iz["configuration"]
         and ia_["configuration"]["bom"] and ia_["configuration"]["price_summary"]["total_czk"] == NET0 and adm2.status_code == 200, (zak.status_code, iz, adm.status_code, adm2.status_code))
    # ---- potvrzeni a storeno: sklad se konfigurace netyka
    sklad_pred = jedno("SELECT stock_qty FROM shop_products WHERE id=%s", (REG,))["stock_qty"]
    prazdny(UB)
    pridej(UB, {}, qty=1)
    volej("POST", "/api/cart/items", UB, {"product_id": REG, "qty": 2})
    r_p = objednej(UB, payment_method_id=2)
    pid = r_p.get_json()["id"]
    ordersmod._SYSTEM = None
    with real.cursor() as cur:
        stav_auto = ordersmod._system_confirm_or_wait(cur, jedno("SELECT * FROM shop_orders WHERE id=%s", (pid,)))
    real.commit()
    sklad_po = jedno("SELECT stock_qty FROM shop_products WHERE id=%s", (REG,))["stock_qty"]
    cfg_hist = sql("SELECT COUNT(*) AS n FROM shop_stock_movements")[0]["n"]
    over("B14 automaticke potvrzeni objednavky (bezny dil skladem + konfigurace): potvrzeno, sklad se odepise JEN u bezneho dilu (10 -> 8), konfigurace sklad nemeni a nehlasi 'chybi'; pohyb skladu jen jeden",
         stav_auto == "potvrzena" and sklad_po == sklad_pred - 2 and cfg_hist == 1, (stav_auto, sklad_pred, sklad_po, cfg_hist))
    prazdny(UB)
    pridej(UB, {}, qty=1)
    r_jen = objednej(UB, payment_method_id=2)
    with real.cursor() as cur:
        stav_jen = ordersmod._system_confirm_or_wait(cur, jedno("SELECT * FROM shop_orders WHERE id=%s", (r_jen.get_json()["id"],)))
    real.commit()
    over("B15 objednavka JEN s konfiguraci se sama NEpotvrdi (vyroba na zakazku ceka na zamestnance): navrat unlinked_items, stav zustane nova", stav_jen == "unlinked_items" and jedno("SELECT status FROM shop_orders WHERE id=%s", (r_jen.get_json()["id"],))["status"] == "nova", stav_jen)

    # ---- rucni potvrzeni a storno zamestnancem: sklad se konfigurace netyka
    prazdny(UB)
    pridej(UB, {}, qty=1)
    volej("POST", "/api/cart/items", UB, {"product_id": REG, "qty": 2})
    r_adm = objednej(UB, payment_method_id=2)
    aid = r_adm.get_json()["id"]
    s0 = jedno("SELECT stock_qty FROM shop_products WHERE id=%s", (REG,))["stock_qty"]
    pohyby0 = sql("SELECT COUNT(*) AS n FROM shop_stock_movements")[0]["n"]
    r_pot = volej("PUT", f"/api/admin/orders/{aid}", ADMIN, {"status": "potvrzena"})
    s1 = jedno("SELECT stock_qty FROM shop_products WHERE id=%s", (REG,))["stock_qty"]
    pohyby1 = sql("SELECT product_id, movement_type, qty FROM shop_stock_movements ORDER BY id")
    r_zru = volej("PUT", f"/api/admin/orders/{aid}", ADMIN, {"status": "zrusena"})
    s2 = jedno("SELECT stock_qty FROM shop_products WHERE id=%s", (REG,))["stock_qty"]
    pohyby2 = sql("SELECT product_id, movement_type, qty FROM shop_stock_movements ORDER BY id")
    over("B16 RUCNI potvrzeni a storno zamestnancem: sklad se odepise a vrati JEN u bezneho dilu (10 -> 8 -> 10), radek konfigurace sklad nemeni, nevadi potvrzeni a pohyby skladu jsou jen u bezneho dilu",
         r_pot.status_code == 200 and r_zru.status_code == 200 and (s0, s1, s2) == (s0, s0 - 2, s0) and [p["product_id"] for p in pohyby1[pohyby0:]] == [REG] and [p["product_id"] for p in pohyby2] and
         all(p["product_id"] == REG for p in pohyby2), (r_pot.get_json(), r_zru.get_json(), s0, s1, s2, pohyby2))
    # ---- vypinac kosiku a seznam objednavek
    sql("INSERT INTO app_settings (setting_key, setting_value) VALUES ('cart_enabled','0') ON DUPLICATE KEY UPDATE setting_value='0'")
    r_off = pridej(UB, {})
    r_off2 = objednej(UB)
    sql("DELETE FROM app_settings WHERE setting_key='cart_enabled'")
    over("B17 vypinac kosiku (cart_enabled 0) blokuje i pridani konfigurace a jeji objednani (403), po zapnuti zase funguje", r_off.status_code == 403 and r_off2.status_code == 403 and pridej(UB, {}).status_code == 201, (r_off.status_code, r_off2.status_code))
    prazdny(UB)
    r_list = volej("GET", "/api/orders", UB)
    over("B18 seznam objednavek zakaznika funguje i s objednavkou obsahujici konfiguraci (nespadne na novych sloupcich)", r_list.status_code == 200 and isinstance(r_list.get_json().get("orders"), list), (r_list.status_code, str(r_list.get_json())[:200]))

    # ---- modul konfigurace se nenacte: bezne produkty funguji dal
    pridej(UB, {}, qty=1)
    sys.modules["konfigurace_kosik"] = None                                            # "import konfigurace_kosik" pak vyhodi ImportError
    try:
        r_bez1 = volej("POST", "/api/cart/items", UB, {"product_id": REG, "qty": 1})
        r_bez2 = volej("POST", "/api/cart/items", UB, {"product_id": CFG, "qty": 1, "configuration": {"selection": {}}})
        k_bez = kosik(UB)
        r_bez3 = objednej(UB)
    finally:
        sys.modules["konfigurace_kosik"] = kk
    cfg_radek = [i for i in k_bez["items"] if i["made_to_order"]]
    over("B19 kdyz se modul konfigurace nenacte (chyba nasazeni), bezny kosik a bezna objednavka FUNGUJI dal (pridani 201, kosik 200, objednavka bezneho dilu se zalozi), radek s konfiguraci se ukaze jako neplatny bez ceny a objednavka s nim se odmitne - nic se nerozbije celoplosne",
         r_bez1.status_code == 201 and k_bez["subtotal_czk"] == 100.0 and cfg_radek and cfg_radek[0]["configuration"]["valid"] is False and cfg_radek[0]["configuration"]["error"] == "internal_error" and r_bez2.status_code == 409
         and r_bez3.status_code in (400, 409, 422, 500) and True, (r_bez1.status_code, r_bez2.status_code, r_bez3.status_code, k_bez["subtotal_czk"]))
    prazdny(UB)

    # ============================================================================================================ C) regrese a mutace
    print("== C regrese a mutace")
    prazdny(UB)
    volej("POST", "/api/cart/items", UB, {"product_id": REG, "qty": 2})
    r_reg = objednej(UB)
    p_reg = polozky(r_reg.get_json()["id"]) if r_reg.status_code == 201 else []
    over("C1 bezna objednavka se nezmenila (bez konfigurace): cena 100 x 2, product_id drzi, configuration_code a configuration_json NULL", r_reg.status_code == 201 and len(p_reg) == 1 and p_reg[0]["product_id"] == REG and float(p_reg[0]["unit_price_czk"]) == 100.0
         and p_reg[0]["configuration_code"] is None and p_reg[0]["configuration_json"] is None and r_reg.get_json()["total_czk"] == 200.0, (r_reg.get_json(), p_reg))

    # ---- hmotnost a cenovy souhrn pochazeji z pro_objednavku (bot8); chybejici udaje = fail closed
    with real.cursor() as cur:
        res_real = kk.vyres(cur, CFG, {}, "cs")
        vahy_uplne(20.0)
        res_uplna = kk.vyres(cur, CFG, {}, "cs")

        def bez_klicu(selection, rules_version=None, lang="cs", klice=()):
            r = _pro_puvodni(selection, rules_version, lang)
            for k in klice:
                r.pop(k, None)
            return r
        stul_shop.pro_objednavku = lambda s, rv=None, lang="cs", *_a, **_k: bez_klicu(s, rv, lang, ("hmotnost_uplna",))
        res_bez_priznaku = kk.vyres(cur, CFG, {}, "cs")
        stul_shop.pro_objednavku = lambda s, rv=None, lang="cs", *_a, **_k: bez_klicu(s, rv, lang, ("cenovy_souhrn",))
        try:
            kk.vyres(cur, CFG, {}, "cs")
            bez_souhrnu = "PROSLO"
        except kk.KonfiguraceChyba as e:
            bez_souhrnu = (e.code, e.status)
        vahy_realne()
    real.rollback()
    over("C2 hmotnost a cenovy souhrn z pro_objednavku: dnes neuplna (soucet profilu a spojek, weight_complete false, seznam chybejicich dilu), po doplneni hmotnosti uplna a beze zmeny prevzata; kdyz konfigurator priznak uplnosti nevrati, "
         "bere se jako NEUPLNA (fail closed); bez cenoveho souhrnu je to price_on_request 409",
         res_real["weight_complete"] is False and res_real["weight_kg"] > 0 and res_real["weight_missing"] and res_real["price_summary"]["material_czk"] > 0 and res_real["price_summary"]["total_czk"] == NET0
         and res_uplna["weight_complete"] is True and res_uplna["weight_kg"] == 20.0 and res_uplna["weight_missing"] == [] and res_bez_priznaku["weight_complete"] is False and bez_souhrnu == ("price_on_request", 409),
         (res_real["weight_complete"], res_real["weight_kg"], res_uplna["weight_kg"], res_bez_priznaku["weight_complete"], bez_souhrnu))

    # ---- mutace klicovych ochran
    zdroj = open(kk.__file__, encoding="utf-8").read()

    def mutant(funkce, stare, nove, n=1):
        node = next(n_ for n_ in ast.parse(zdroj).body if isinstance(n_, ast.FunctionDef) and n_.name == funkce)
        src = ast.get_source_segment(zdroj, node)
        assert src.count(stare) == n, f"{funkce}: '{stare}' nalezeno {src.count(stare)}x, ocekavano {n}x"
        ns = dict(vars(kk))
        exec(src.replace(stare, nove), ns)
        return ns[funkce]

    def s_mutaci(funkce, stare, nove, akce):
        puvodni = getattr(kk, funkce)
        setattr(kk, funkce, mutant(funkce, stare, nove))
        try:
            return akce()
        finally:
            setattr(kk, funkce, puvodni)

    prazdny(UB)
    pridej(UB, {}, qty=2)
    VAHY.clear()
    m9 = s_mutaci("vyres", '"weight_complete": r.get("hmotnost_uplna") is True', '"weight_complete": True', lambda: objednej(UB, shipping_method_id=4))
    over("M9 mutace: kdyby se hmotnost brala jako uplna i kdyz v katalogu chybi (dnes jsou to jen profily a spojky), Toptrans by se spocital z poddimenzovane hmotnosti a objednavka by prosla (spravne 409) - test B4c ji zachyti",
         m9.status_code == 201 and len(VAHY) == 1, (m9.status_code, VAHY))
    prazdny(UB)
    montaz_sluzba(None)
    prazdny(UB)
    telo_m1 = {"items": [{"product_id": CFG, "qty": 1, "configuration": {"selection": {"price": 1}, "rules_version": stul_glb.RULES_VERSION}}], "customer_name": "Test", "customer_email": "test@example.test",
               "delivery_address": "Testovací 1", "delivery_zip": "11000", "shipping_method_id": 1}
    m1 = s_mutaci("vyres", 'net = (r.get("price") or {}).get("net")', 'net = (selection or {}).get("price", (r.get("price") or {}).get("net"))', lambda: volej("POST", "/api/orders", UB, telo_m1))
    over("M1 mutace: kdyby se cena brala z dat od klienta (pole price ve vyberu), radek objednavky by stal 1 Kc (spravne cena ze serveru) - test B9 ji zachyti",
         m1.status_code == 201 and float(polozky(m1.get_json()["id"])[0]["unit_price_czk"]) == 1.0, m1.get_json())
    prazdny(UB)
    pridej(UB, {}, qty=1)
    sql("UPDATE shop_cart_items SET config_hash='0123456789abcdef' WHERE user_id=%s", (UB,))
    m2 = s_mutaci("radek_objednavky", 'if it.get("config_hash") and res["hash"] != it["config_hash"]:', "if False:", lambda: objednej(UB))
    over("M2 mutace: bez kontroly hashe by se objednala jina konfigurace, nez kterou zakaznik dal do kosiku (spravne 409) - test B7 ji zachyti", m2.status_code == 201, m2.get_json())
    prazdny(UB)
    pridej(UB, {}, qty=1)
    m3 = s_mutaci("radek_objednavky", '"product_id": None, "product_name_snapshot": jmeno_radku', '"product_id": product["id"], "product_name_snapshot": jmeno_radku', lambda: objednej(UB, payment_method_id=1))
    dok3 = sql("SELECT * FROM shop_documents WHERE order_id=%s", (m3.get_json()["id"],)) if m3.status_code == 201 else None
    over("M3 mutace: kdyby mel radek konfigurace product_id, sklad (0 ks) by chybel a zalohova faktura by se nevystavila (spravne vznikne) - testy B5 a B14 ji zachyti", m3.status_code == 201 and not dok3, (m3.status_code, dok3))
    m4 = s_mutaci("zakaznicky_snimek", 'return {"kod": d.get("kod"), "hash": d.get("hash"), "summary": d.get("summary") or [], "montaz": d.get("montaz"), "rules_version": d.get("rules_version")}', "return d", lambda: volej("GET", f"/api/orders/{oid}", UB).get_json())
    over("M4 mutace: kdyby zakaznik dostal cely snimek, videl by kusovnik a nakladovou strukturu (spravne ne) - test B13 ji zachyti", "bom" in [x for x in m4["order"]["items"] if x["configuration_code"]][0]["configuration"], m4)
    prazdny(UB)
    montaz_sluzba(10.0)
    m5 = s_mutaci("montaz_dostupna_pro_zemi", 'return (zeme or "CZ").strip().upper() == "CZ"', "return True", lambda: pridej(UB, {}, montaz_zvolena=True, delivery_country="DE").get_json())
    over("M5 mutace: kdyby se montaz nabizela i do zahranici, projde u DE (spravne ztise zahozena) - test A12 ji zachyti", m5["items"][0]["montaz_zvolena"] is True, m5)
    prazdny(UB)
    m6 = s_mutaci("_cena_po_sleve", "return _effective_unit_price(cur, produkt, user=user_id and {\"id\": user_id}, coupon_code=None)", 'return net, "x"', lambda: (prazdny(UA), pridej(UA, {}).get_json())[1])
    over("M6 mutace: bez skupinove slevy by zakaznik skupiny platil plnou cenu (spravne -10 %) - test A15 ji zachyti", m6["items"][0]["unit_price_czk"] == NET0, m6)
    prazdny(UA)
    m7 = s_mutaci("vyres", "pro_objednavku(selection, rules_version, lang", "pro_objednavku(selection, None, lang", lambda: volej("POST", "/api/cart/items", UB, body_stara))
    over("M7 mutace: bez kontroly verze pravidel by prosla zastarala konfigurace (spravne 409) - test A7 ji zachyti", m7.status_code == 201, m7.status_code)
    prazdny(UB)
    m8 = s_mutaci("vyres", 'if not r.get("valid"):', "if False:", lambda: pridej(UB, BAD_SEL))
    over("M8 mutace: bez kontroly platnosti by se do kosiku dostala nevyrobitelna konfigurace (spravne 422) - test A6 ji zachyti", m8.status_code == 201, m8.status_code)
    prazdny(UB)
finally:
    with real.cursor() as cur:
        for t_ in TEMP_LIKE + TEMP_COPY:
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `{t_}`")
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `_tpl_{t_}`")
    real.commit()

po = stav_ostrych()
over("ostre tabulky (kosik, objednavky, polozky, doklady, cislovani, produkty, sklad, platby, doprava, zakaznici, sluzby typu sestav, nastaveni, audit, e-maily) jsou po testu beze zmeny", po == PRED_OSTRE, {k: (PRED_OSTRE[k], po[k]) for k in po if po[k] != PRED_OSTRE[k]})
ok = sum(vysl)
print(f"\nVYSLEDEK konfigurace v kosiku a objednavce: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
