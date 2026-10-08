#!/opt/konfigurator/api/venv/bin/python
"""Dealersky program, krok 4 (bot5, 2026-10-02): OBJEDNAVKA Z WEBU DEALERA pres API - api/dealer_orders.py + dealerska vetev v orders._resolve_and_insert_order nad DOCASNYMI tabulkami.

Skutecny kod (nebo kandidati: DEALER_ORDERS_PY, ORDERS_PY, APP_PY) bezi pres Flask test client nad TEMPORARY kopiemi: shop_orders, shop_order_items, shop_order_status_history,
shop_documents, citace cisel (objednavky, doklady), dealers, dealer_rates, dealer_keys, shop_products, content_categories, product_assemblies, shop_product_images, platebni a dopravni metody,
app_settings. Cenik dopravy (shop_shipping_price_rules, shop_zip_distance_bands) a cfg_dily se jen ctou. E-maily (_send_order_emails_bg) a audit se jen zachytavaji, nic se neodesila.

Cast A  overeni klice a opravneni (klic, scope, IP, limit, dealer pozastaveny/jina cesta)
Cast B  kalkulace /quote (dealerska cena: produkt > kategorie > vychozi, nadrazena kategorie, akce, zaokrouhleni, doprava, DPH, chyby, nic se nezapisuje, nic neuniká)
Cast C  objednavka (zapis, doklad na dealera, doruceni koncovemu zakaznikovi, shoda quote = objednavka = zalohova faktura, nedostatek skladu)
Cast D  idempotence (replay, konflikt), zmena ceny, limity, validace vstupu (znacky < >), izolace dealeru, stav a seznam
Cast E  jadro objednavky: dealerska vetev (brana produktu, zadny kosik/sestavy) a NEZMENENE chovani pro bezne zakazniky
Cast F  e-maily a audit, nic mimo ocekavane tabulky, mutace (chybne verze MUSI selhat)
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
  /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-02_dealeri_testy/test_objednavky.py     (kandidati: --setenv=DEALER_ORDERS_PY=... --setenv=ORDERS_PY=... --setenv=APP_PY=...)
"""
import ast
import copy
import datetime
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
API = os.path.join(REPO, "api")
KANDIDATI = {"dealer_orders.py": os.environ.get("DEALER_ORDERS_PY"), "orders.py": os.environ.get("ORDERS_PY"), "app.py": os.environ.get("APP_PY")}
if any(KANDIDATI.values()):
    tmp = tempfile.mkdtemp(prefix="kand_objednavky_")
    for jmeno, cesta in KANDIDATI.items():
        if cesta:
            shutil.copy(cesta, os.path.join(tmp, jmeno))
    sys.path.insert(0, tmp)
sys.path.insert(1 if any(KANDIDATI.values()) else 0, API)

import pymysql  # noqa: E402
import app as appmod  # noqa: E402

for sekce in ("dealeri", "dealer_provize", "dealer_klice"):
    if sekce not in appmod.PERMISSION_SECTIONS:
        appmod.PERMISSION_SECTIONS = tuple(appmod.PERMISSION_SECTIONS) + (sekce,)
import dealers  # noqa: E402
import documents  # noqa: E402
import orders as orders_mod  # noqa: E402
import dealer_orders as do  # noqa: E402
import dealer_commissions as dc  # noqa: E402

dealers.log_audit = lambda *a, **k: None
AUDIT, EMAILS = [], []
do.log_audit = lambda *a, **k: AUDIT.append((a, k))
orders_mod._send_order_emails_bg = lambda result: EMAILS.append(result)

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:400]))


def ostre():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                           port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


def stav_ostrych():
    c = ostre()
    try:
        with c.cursor() as cur:
            out = {}
            for t in ("shop_orders", "shop_order_items", "shop_documents", "shop_order_status_history", "shop_emails", "audit_log", "dealers", "dealer_keys", "dealer_rates",
                      "shop_products", "content_categories", "app_settings", "shop_payment_methods", "shop_shipping_methods"):
                cur.execute(f"SELECT COUNT(*) AS n FROM `{t}`")
                out[t] = cur.fetchone()["n"]
            cur.execute("SELECT COALESCE(SUM(next_number),0) AS s FROM shop_order_number_sequence")
            out["seq_obj"] = int(cur.fetchone()["s"])
            cur.execute("SELECT COALESCE(SUM(next_number),0) AS s FROM shop_document_sequences")
            out["seq_dok"] = int(cur.fetchone()["s"])
            cur.execute("SELECT COALESCE(SUM(active),0) AS s FROM shop_shipping_methods")
            out["aktivni_dopravy"] = int(cur.fetchone()["s"])
            return out
    finally:
        c.close()


PRED_OSTRE = stav_ostrych()
wrap = appmod.get_conn()
real = object.__getattribute__(wrap, "_real")

TEMP_LIKE = ("shop_orders", "shop_order_items", "shop_order_status_history", "shop_documents", "shop_order_number_released", "dealers", "dealer_rates", "dealer_keys",
             "dealer_domains", "dealer_clicks", "shop_products", "content_categories", "product_assemblies", "shop_product_images", "shop_payment_methods", "shop_shipping_methods")
TEMP_COPY = ("shop_document_sequences", "shop_order_number_sequence", "app_settings")


def sql(q, params=None):
    with real.cursor() as cur:
        cur.execute(q, params or ())
        out = cur.fetchall() if q.lstrip().upper().startswith("SELECT") else cur.rowcount
    real.commit()
    return out


def jedno(q, params=None):
    r = sql(q, params)
    return r[0] if r else None


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
        cur.execute("DELETE FROM app_settings WHERE setting_key LIKE 'dealer_api_%'")
    real.commit()

    sql("INSERT INTO shop_payment_methods (id, name, price_czk, requires_advance_invoice, active) VALUES (1,'Platba předem',0,1,1),(2,'Dobírka',0,0,1),(4,'QR platba',0,1,1)")
    sql("INSERT INTO shop_shipping_methods (id, name, price_czk, active, sort_order, pricing_mode) VALUES (1,'Osobní odběr',0,1,0,'fixed'),(4,'Toptrans',0,1,1,'zip_weight')")

    # ---- kategorie a produkty (vse docasne)
    sql("INSERT INTO content_categories (id, name, parent_id, is_visible) VALUES (9001,'Spojovací materiál',NULL,1),(9002,'Příslušenství',9001,1),(9003,'Skryté',NULL,0)")
    PROD = {}

    def produkt(sku, name, price, stock=10, weight_g=100, cat=None, active=1, **extra):
        cols = {"sku": sku, "name": name, "price_czk_placeholder": price, "stock_qty": stock, "weight_g": weight_g, "category_id": cat, "active": active, "unit": "ks", **extra}
        sql(f"INSERT INTO shop_products ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})", list(cols.values()))
        PROD[sku] = jedno("SELECT id FROM shop_products WHERE sku=%s", (sku,))["id"]
        return PROD[sku]

    produkt("T-SPOJKA", "Spojka L 30", 100.00, 50, 200, 9001, length_mm=30, width_mm=30, height_mm=30)
    produkt("T-PROFIL", "Profil 30x30 3 m", 1000.00, 5, 3000, None, is_profile_material=1, dealer_discount_percent=30, length_mm=30, width_mm=30, height_mm=3000)
    produkt("T-DESKA", "Deska PR10", 500.00, 0, 15000, None, is_board_material=1, board_sheet_width_mm=2800, board_sheet_height_mm=2070, length_mm=2800, width_mm=2070, height_mm=10)
    produkt("T-AKCE", "Akční díl", 200.00, 10, 100, None, sale_price_czk=150.00)
    produkt("T-ZAOKR", "Zaokrouhlovací díl", 33.33, 100, 50, None)
    produkt("T-PRISL", "Příslušenství k profilu", 50.00, 100, 50, 9002)
    produkt("T-HEAVY", "Těžký díl", 10.00, 100, 1000000, None)
    produkt("T-DRAHY", "Drahý díl", 100000.00, 100, 1000, None)
    pf = produkt("T-SESTAVA", "Regál sestava", 5000.00, 10, 1000, None)
    sql("INSERT INTO product_assemblies (name, data, shop_product_id) VALUES ('Sestava','{}',%s)", (pf,))
    produkt("VD-001", "Vandr regál", 5000.00, 10, 1000, None)
    produkt("T-BRAND", "Logiman držák", 100.00, 10, 100, None)
    produkt("T-NEAKT", "Neaktivní díl", 100.00, 10, 100, None, active=0)
    produkt("T-BEZCENY", "Díl bez ceny", None, 10, 100, None)
    produkt("T-SKRYTA", "Díl ve skryté kategorii", 100.00, 10, 100, 9003)

    # ---- dealeri a klice
    def dealer(name, ref, **kw):
        d = {"ref_code": ref, "name": name, "status": "active", "order_path": "dealer", "default_discount_pct": 10.0, "contact_email": f"{ref}@dealer.example", "contact_phone": "+420 111 222 333",
             "ico": "11111111", "dic": "CZ11111111", "billing_street": "Dealerská 1", "billing_city": "Brno", "billing_zip": "60200"}
        d.update(kw)
        sql(f"INSERT INTO dealers ({', '.join(d)}) VALUES ({', '.join(['%s'] * len(d))})", list(d.values()))
        return jedno("SELECT * FROM dealers WHERE ref_code=%s", (ref,))

    uzivatele = [r["id"] for r in sql("SELECT id FROM app_users WHERE role='user' AND active=1 ORDER BY id LIMIT 2")]
    A = dealer("Alfa s.r.o.", "alfa000001", user_id=uzivatele[0])
    B = dealer("Beta a.s.", "beta000002", default_discount_pct=None)
    Cd = dealer("Gama (provize)", "gama000003", order_path="our")
    Dd = dealer("Delta (pozastaven)", "delt000004", status="suspended")
    Ed = dealer("Epsilon (neuplny profil)", "epsi000005", ico=None)
    sql("INSERT INTO dealer_rates (dealer_id, category_id, discount_pct) VALUES (%s,9001,20.00),(%s,9001,15.00)", (A["id"], B["id"]))

    def klic(d, kind="api", scopes="orders,quote", ips=None, rate=6000):
        with real.cursor() as cur:
            row, secret, token = dealers._create_key(cur, d, kind, "test", scopes, ips, rate, None)
        real.commit()
        return token if kind != "widget" else row["public_id"]

    KREV = klic(A)
    sql("UPDATE dealer_keys SET revoked_at=NOW(), is_active=0 WHERE public_id=%s", (KREV.split("_")[0] + "_" + KREV.split("_")[1],))
    KA = klic(A)
    KQ, KO, KW, KF, KIP, KSLOW = klic(A, scopes="quote"), klic(A, scopes="orders"), klic(A, kind="widget"), klic(A, kind="feed"), klic(A, ips="10.0.0.1"), klic(A, rate=2)
    KB, KC, KD, KE = klic(B), klic(Cd), klic(Dd), klic(Ed)

    cl = appmod.app.test_client()

    def hl(token, ip="127.0.0.1"):
        h = {"X-Real-IP": ip}
        if token:
            h["Authorization"] = f"Bearer {token}"
        return h

    def quote(token, body, ip="127.0.0.1"):
        return cl.post("/api/dealer/v1/quote", json=body, headers=hl(token, ip))

    KEEP_RATE = [False]

    def objednej(token, body, ip="127.0.0.1"):
        if not KEEP_RATE[0]:
            appmod._rate_limit_buckets.clear()          # limit zapisu za minutu testuje jen D19, jinak by ho vycerpaly stovky pozadavku testu
        return cl.post("/api/dealer/v1/orders", json=body, headers=hl(token, ip))

    def pocet(t, where="1=1", params=()):
        return jedno(f"SELECT COUNT(*) AS n FROM {t} WHERE {where}", params)["n"]

    def seq():
        return (int(jedno("SELECT COALESCE(SUM(next_number),0) AS s FROM shop_order_number_sequence")["s"]), int(jedno("SELECT COALESCE(SUM(next_number),0) AS s FROM shop_document_sequences")["s"]))

    P = PROD
    RECIPIENT = {"name": "Jan Novák", "street": "Ulice 5", "city": "Praha", "zip": "110 00", "phone": "+420 777 123 456"}

    def telo(ref="REF-1", items=None, sid=4, **kw):
        b = {"external_ref": ref, "items": items or [{"product_id": P["T-SPOJKA"], "qty": 2}], "recipient": dict(RECIPIENT), "shipping_method_id": sid}
        b.update(kw)
        return b

    def cena_dealer(list_price, pct):
        return round(list_price * (1 - pct / 100.0), 2)

    def doprava(zip_code, kusy):
        """Nezavisly vypocet dopravy: hmotnost a objem podle fixtur (g a mm), cena z cenikove funkce Toptrans."""
        w = 0.0
        v = 0.0
        for s, q in kusy:
            w += float(HM[s]) / 1000.0 * q
            v += OB.get(s, 0.0) * q
        with real.cursor() as cur:
            return orders_mod._resolve_toptrans_price(cur, 4, zip_code, w, v)[0]

    HM = {"T-SPOJKA": 200, "T-PROFIL": 3000, "T-DESKA": 15000, "T-AKCE": 100, "T-ZAOKR": 50, "T-PRISL": 50, "T-HEAVY": 1000000, "T-DRAHY": 1000}
    OB = {"T-SPOJKA": (30 / 1000.0) * (30 / 1000.0) * (30 / 1000.0), "T-PROFIL": (30 / 1000.0) * (30 / 1000.0) * (3000 / 1000.0), "T-DESKA": (2800 / 1000.0) * (2070 / 1000.0) * (10 / 1000.0)}

    # ============================================================================================================ A) overeni
    print("== A overeni klice a opravneni")
    ok_body = {"items": [{"product_id": P["T-SPOJKA"], "qty": 1}], "delivery_zip": "60200"}
    over("A1 bez klice, se spatnym klicem, s widget klicem, s feed klicem a s odvolanym klicem: vzdy 401 invalid_key (quote i objednavka i seznam i stav)",
         all(f(None).status_code == 401 for f in (lambda t: quote(t, ok_body), lambda t: objednej(t, telo()), lambda t: cl.get("/api/dealer/v1/orders", headers=hl(t)), lambda t: cl.get("/api/dealer/v1/orders/REF-1", headers=hl(t))))
         and quote("sk_deadbeef_" + "x" * 40, ok_body).status_code == 401 and quote(KA[:-3] + "xyz", ok_body).status_code == 401 and quote(KW, ok_body).status_code == 401
         and quote(KF, ok_body).status_code in (401, 403) and quote(KREV, ok_body).status_code == 401 and quote(KW, ok_body).get_json()["code"] == "invalid_key", quote(KF, ok_body).status_code)
    over("A2 scope: klic jen s quote nesmi objednavat ani cist objednavky (403 scope_denied), klic jen s orders nesmi kalkulovat",
         quote(KQ, ok_body).status_code == 200 and objednej(KQ, telo()).status_code == 403 and objednej(KQ, telo()).get_json()["code"] == "scope_denied"
         and cl.get("/api/dealer/v1/orders", headers=hl(KQ)).status_code == 403 and quote(KO, ok_body).status_code == 403 and quote(KO, ok_body).get_json()["code"] == "scope_denied", None)
    over("A3 klic s povolenou IP 10.0.0.1: z jine IP 403 ip_not_allowed, z povolene projde", quote(KIP, ok_body, "127.0.0.1").status_code == 403 and quote(KIP, ok_body, "127.0.0.1").get_json()["code"] == "ip_not_allowed"
         and quote(KIP, ok_body, "10.0.0.1").status_code == 200, None)
    over("A4 dealer pozastaveny 403 dealer_inactive; dealer s cestou 'our' (provize) 403 order_path_not_dealer u quote i objednavky",
         quote(KD, ok_body).status_code == 403 and quote(KD, ok_body).get_json()["code"] == "dealer_inactive"
         and quote(KC, ok_body).status_code == 403 and quote(KC, ok_body).get_json()["code"] == "order_path_not_dealer" and objednej(KC, telo()).get_json()["code"] == "order_path_not_dealer", None)
    appmod._rate_limit_buckets.clear()
    odp = [quote(KSLOW, ok_body).status_code for _ in range(3)]
    over("A5 limit pozadavku na klic (2/min): treti pozadavek 429 rate_limited s hlavickou Retry-After", odp == [200, 200, 429] and quote(KSLOW, ok_body).headers.get("Retry-After") == "60", odp)
    appmod._rate_limit_buckets.clear()
    over("A6 odpovedi nesou Cache-Control no-store a zadne CORS hlavicky (server-to-server)", quote(KA, ok_body).headers.get("Cache-Control") == "private, no-store" and not any(h.lower().startswith("access-control") for h in quote(KA, ok_body).headers.keys()), None)

    # ============================================================================================================ B) kalkulace
    print("== B kalkulace (quote)")
    sada_pred = (pocet("shop_orders"), pocet("shop_order_items"), pocet("shop_documents"), seq())
    kusy = [("T-SPOJKA", 10), ("T-PROFIL", 2), ("T-DESKA", 1), ("T-AKCE", 4), ("T-ZAOKR", 3), ("T-PRISL", 5)]
    r = quote(KA, {"items": [{"product_id": P[s], "qty": q} for s, q in kusy], "delivery_zip": "602 00", "shipping_method_id": 4})
    q = r.get_json()
    L = {ln["product_id"]: ln for ln in q["items"]}
    over("B1 dealerska cena po radcich (A: kategorie 20 % > vychozi 10 %; vlastni sleva produktu 30 %; akce 150 < 180; nadrazena kategorie se dedi)",
         r.status_code == 200 and L[P["T-SPOJKA"]]["unit_price_net_czk"] == 80.0 and L[P["T-PROFIL"]]["unit_price_net_czk"] == 700.0 and L[P["T-DESKA"]]["unit_price_net_czk"] == 450.0
         and L[P["T-AKCE"]]["unit_price_net_czk"] == 150.0 and L[P["T-AKCE"]]["price_basis"] == "sale" and L[P["T-PRISL"]]["unit_price_net_czk"] == 40.0
         and L[P["T-SPOJKA"]]["price_basis"] == "dealer", q)
    over("B2 zaokrouhleni radku: 33,33 x 0,9 = 29,997 -> 30,00, x 3 ks = 90,00; soucet radku = soucet polozek", L[P["T-ZAOKR"]]["unit_price_net_czk"] == 30.0 and L[P["T-ZAOKR"]]["line_net_czk"] == 90.0
         and q["items_net_czk"] == round(10 * 80.0 + 2 * 700.0 + 450.0 + 4 * 150.0 + 90.0 + 5 * 40.0, 2), q["items_net_czk"])
    prepoc = doprava("60200", kusy)
    over("B3 doprava Toptrans podle PSC a hmotnosti: cena = cenikova funkce pro soucet hmotnosti a objemu, zvolena doprava je v odpovedi, nabidka obsahuje jen zip_weight metody (ne osobni odber)",
         q["shipping"] == {"id": 4, "name": "Toptrans", "price_net_czk": prepoc} and q["shipping_options"] == [{"id": 4, "name": "Toptrans", "price_net_czk": prepoc}] and prepoc > 0, (q["shipping"], prepoc))
    celkem = round(q["items_net_czk"] + prepoc + 0.0, 2)
    vat = documents._round2(sum(documents._round2(x * documents.VAT_RATE / 100) for x in [10 * 80.0, 2 * 700.0, 450.0, 4 * 150.0, 90.0, 5 * 40.0, prepoc]))
    over("B4 soucty: total_net = polozky + doprava + platba (0), sazba DPH 21, DPH po radcich, castka k uhrade zaokrouhlena na cele Kc (stejne jako zalohova faktura)",
         q["total_net_czk"] == celkem and q["vat_rate"] == 21.0 and q["vat_czk"] == vat and q["amount_due_czk"] == float(round(celkem + vat)) and q["currency"] == "CZK" and q["prices_include_vat"] is False
         and q["payment_method"] == "Platba předem", (q["total_net_czk"], celkem, q["vat_czk"], vat, q["amount_due_czk"]))
    q2 = quote(KA, {"items": [{"product_id": P["T-SPOJKA"], "qty": 1}], "delivery_zip": "60200"}).get_json()
    over("B5 bez shipping_method_id: jen nabidka dopravy a soucty BEZ dopravy (shipping null)", q2["shipping"] is None and len(q2["shipping_options"]) == 1 and q2["total_net_czk"] == 80.0, q2)
    q3 = quote(KA, {"items": [{"product_id": P["T-SPOJKA"], "qty": 1}, {"product_id": P["T-SPOJKA"], "qty": 4}, {"product_id": P["T-AKCE"], "qty": 1}], "delivery_zip": "60200"}).get_json()
    over("B6 stejny produkt vickrat se slouci (1 + 4 = 5 ks na jednom radku), radky podle product_id", [(ln["product_id"], ln["qty"]) for ln in q3["items"]] == sorted([(P["T-SPOJKA"], 5), (P["T-AKCE"], 1)]), q3["items"])
    over("B7 dostupnost: 'skladem' / 'na_dotaz' bez presneho poctu kusu, in_stock false kdyz neco chybi (deska ma sklad 0)", L[P["T-SPOJKA"]]["availability"] == "skladem" and L[P["T-DESKA"]]["availability"] != "skladem" and q["in_stock"] is False and q3["in_stock"] is True
         and all("stock" not in k for ln in q["items"] for k in ln), (L[P["T-DESKA"]], q["in_stock"]))
    odmitnuti = {}
    for nazev, pid in (("sestava", P["T-SESTAVA"]), ("VD", P["VD-001"]), ("znacka", P["T-BRAND"]), ("neaktivni", P["T-NEAKT"]), ("bez ceny", P["T-BEZCENY"]), ("skryta kategorie", P["T-SKRYTA"]), ("neexistuje", 999999)):
        rr = quote(KA, {"items": [{"product_id": pid, "qty": 1}], "delivery_zip": "60200"})
        odmitnuti[nazev] = (rr.status_code, rr.get_json().get("code"))
    over("B8 produkty mimo dealerskou nabidku (sestava, VD-*, znacka v nazvu, neaktivni, bez ceny, skryta kategorie, neexistujici) -> 422 product_not_available (fail closed)", set(odmitnuti.values()) == {(422, "product_not_available")}, odmitnuti)
    over("B9 dealer bez slevy pro produkt (B nema vychozi slevu a deska nema kategorii) -> 422 no_dealer_price; s kategorii (spojka, sleva 15 %) cena 85", quote(KB, {"items": [{"product_id": P["T-DESKA"], "qty": 1}], "delivery_zip": "60200"}).get_json()["code"] == "no_dealer_price"
         and quote(KB, {"items": [{"product_id": P["T-SPOJKA"], "qty": 1}], "delivery_zip": "60200"}).get_json()["items"][0]["unit_price_net_czk"] == 85.0, None)
    over("B10 osobni odber (fixni doprava) pro dealery 422 shipping_unavailable; neznama doprava totez", quote(KA, {**ok_body, "shipping_method_id": 1}).get_json()["code"] == "shipping_unavailable"
         and quote(KA, {**ok_body, "shipping_method_id": 999}).get_json()["code"] == "shipping_unavailable", None)
    rh = quote(KA, {"items": [{"product_id": P["T-HEAVY"], "qty": 4}], "delivery_zip": "60200"})
    over("B11 zasilka nad rozsah cenniku (4000 kg) -> 422 shipping_unavailable se zdrojovou zpravou, bez nabidky dopravy", rh.status_code == 422 and rh.get_json()["code"] == "shipping_unavailable" and "přesahuje" in rh.get_json()["error"], rh.get_json())
    spatne = {
        "qty 0": {"items": [{"product_id": P["T-SPOJKA"], "qty": 0}], "delivery_zip": "60200"},
        "qty zaporne": {"items": [{"product_id": P["T-SPOJKA"], "qty": -1}], "delivery_zip": "60200"},
        "qty desetinne": {"items": [{"product_id": P["T-SPOJKA"], "qty": 1.5}], "delivery_zip": "60200"},
        "qty bool": {"items": [{"product_id": P["T-SPOJKA"], "qty": True}], "delivery_zip": "60200"},
        "qty text": {"items": [{"product_id": P["T-SPOJKA"], "qty": "2"}], "delivery_zip": "60200"},
        "qty moc": {"items": [{"product_id": P["T-SPOJKA"], "qty": 10001}], "delivery_zip": "60200"},
        "product_id text": {"items": [{"product_id": "abc", "qty": 1}], "delivery_zip": "60200"},
        "bez items": {"delivery_zip": "60200"}, "prazdne items": {"items": [], "delivery_zip": "60200"}, "items ne seznam": {"items": {"product_id": 1}, "delivery_zip": "60200"},
        "psc kratke": {"items": [{"product_id": P["T-SPOJKA"], "qty": 1}], "delivery_zip": "602"}, "psc pismena": {"items": [{"product_id": P["T-SPOJKA"], "qty": 1}], "delivery_zip": "ABCDE"}, "bez psc": {"items": [{"product_id": P["T-SPOJKA"], "qty": 1}]},
        "cena od klienta": {"items": [{"product_id": P["T-SPOJKA"], "qty": 1, "unit_price": 1}], "delivery_zip": "60200"},
        "neznamy parametr": {"items": [{"product_id": P["T-SPOJKA"], "qty": 1}], "delivery_zip": "60200", "discount": 99},
        "kupon": {"items": [{"product_id": P["T-SPOJKA"], "qty": 1}], "delivery_zip": "60200", "coupon_code": "X"},
        "moc ruznych produktu": {"items": [{"product_id": 100000 + i, "qty": 1} for i in range(51)], "delivery_zip": "60200"},
    }
    kody = {}
    for n, b in spatne.items():
        rr = quote(KA, b)
        kody[n] = (rr.status_code, rr.get_json().get("code"))
    over("B12 neplatne vstupy (qty 0/zaporne/desetinne/bool/text/moc, product_id text, bez items, PSC, cena a kupon od klienta, neznamy parametr, 51 produktu) -> 400 (unknown_field u cizich poli)",
         all(s == 400 for s, c in kody.values()) and kody["cena od klienta"][1] == "unknown_field" and kody["neznamy parametr"][1] == "unknown_field" and kody["kupon"][1] == "unknown_field", kody)
    rj = cl.post("/api/dealer/v1/quote", data="neni json", headers={**hl(KA), "Content-Type": "application/json"})
    rv = cl.post("/api/dealer/v1/quote", data="x" * 70000, headers={**hl(KA), "Content-Type": "application/json"})
    over("B13 tělo ne-JSON 400 invalid_json, pole misto objektu 400, prilis velke tělo 413", rj.status_code == 400 and rj.get_json()["code"] == "invalid_json" and rv.status_code == 413 and quote(KA, [1, 2]).status_code == 400, (rj.status_code, rv.status_code))
    sada_po = (pocet("shop_orders"), pocet("shop_order_items"), pocet("shop_documents"), seq())
    over("B14 kalkulace nic nezapisuje: zadna objednavka, polozka, doklad ani cislo z citace (jen last_used klice)", sada_pred == sada_po, (sada_pred, sada_po))
    klice_v_odpovedi = set()
    for ln in q["items"]:
        klice_v_odpovedi |= set(ln)
    over("B15 nic neuniká: v odpovedi jsou jen whitelistovana pole (zadna cenikova cena, sleva, naklady, sklad, interni poznamky)",
         klice_v_odpovedi == {"product_id", "sku", "name", "unit", "qty", "unit_price_net_czk", "line_net_czk", "price_basis", "availability"} and set(q) == {"currency", "prices_include_vat", "vat_rate", "items", "items_net_czk",
         "shipping_options", "shipping", "payment_method", "total_net_czk", "vat_czk", "amount_due_czk", "in_stock"}, (klice_v_odpovedi, set(q)))

    # ============================================================================================================ C) objednavka
    print("== C objednavka")
    seq0 = seq()
    items_c = [("T-SPOJKA", 10), ("T-PROFIL", 2), ("T-AKCE", 4), ("T-ZAOKR", 3)]
    body_c = telo("ESHOP-1001", [{"product_id": P[s], "qty": qn} for s, qn in items_c], note="Zavolat před doručením")
    qc = quote(KA, {"items": body_c["items"], "delivery_zip": "11000", "shipping_method_id": 4}).get_json()
    rc = objednej(KA, body_c)
    oc = rc.get_json()
    o = oc["order"]
    row = jedno("SELECT * FROM shop_orders WHERE dealer_external_ref=%s", ("ESHOP-1001",))
    over("C1 objednavka vznikne (201), idempotent_replay false, status nova, cislo OBJ-RRRR-NNNNN, zapsana u dealera A s cestou 'dealer' a jeho external_ref",
         rc.status_code == 201 and oc["idempotent_replay"] is False and o["status"] == "nova" and re.match(r"^OBJ-\d{4}-\d{5}$", o["order_number"]) and row["dealer_id"] == A["id"] and row["order_path"] == "dealer"
         and row["dealer_click_id"] is None and o["external_ref"] == "ESHOP-1001", rc.get_json())
    over("C2 fakturace = DEALER (firma, ICO, DIC, adresa), kontakt = e-mail a telefon dealera (ne koncoveho zakaznika), objednavka patri uctu dealera, zadna skupinova sleva",
         row["billing_name"] == "Alfa s.r.o." and row["billing_ico"] == "11111111" and row["billing_dic"] == "CZ11111111" and row["billing_address"] == "Dealerská 1, 602 00 Brno" and row["customer_email"] == "alfa000001@dealer.example"
         and row["customer_phone"] == "+420 111 222 333" and row["customer_name"] == "Alfa s.r.o." and row["user_id"] == uzivatele[0] and not row["customer_discount_percent"] and row["customer_group_name"] is None, row)
    over("C3 dorucení koncovemu zakaznikovi: adresa 'jmeno, ulice, PSC mesto, tel.' a PSC cislice, doprava Toptrans, platba predem, poznamka",
         row["delivery_address"] == "Jan Novák, Ulice 5, 110 00 Praha, tel. +420 777 123 456" and row["delivery_zip"] == "11000" and row["shipping_method_name"] == "Toptrans" and row["payment_method_name"] == "Platba předem"
         and row["note"] == "Zavolat před doručením", row)
    pol = sql("SELECT * FROM shop_order_items WHERE order_id=%s ORDER BY id", (row["id"],))
    ocek = {P["T-SPOJKA"]: (80.0, 10), P["T-PROFIL"]: (700.0, 2), P["T-AKCE"]: (150.0, 4), P["T-ZAOKR"]: (30.0, 3)}
    over("C4 polozky: dealerska cena (ne cenikova), mnozstvi a soucet radku; zadne dalsi radky (prirezy, rezy, sluzby), zadna montaz/sestava/box",
         {p["product_id"]: (float(p["unit_price_czk"]), p["qty"]) for p in pol} == ocek and len(pol) == 4 and all(float(p["line_total_czk"]) == round(float(p["unit_price_czk"]) * p["qty"], 2) for p in pol)
         and all(not p["montaz_zvolena"] and p["assembly_id"] is None and p["cut_pieces_json"] is None for p in pol), [(p["product_id"], p["unit_price_czk"], p["qty"]) for p in pol])
    over("C5 SHODA: kalkulace == objednavka (total_czk) == odpoved; castka k uhrade a DPH sedi s kalkulaci", float(row["total_czk"]) == qc["total_net_czk"] == o["total_net_czk"] and o["amount_due_czk"] == qc["amount_due_czk"] and o["vat_czk"] == qc["vat_czk"], (row["total_czk"], qc["total_net_czk"], o["total_net_czk"]))
    pro = jedno("SELECT * FROM shop_documents WHERE order_id=%s AND document_type='proforma_invoice'", (row["id"],))
    rec = json.loads(pro["recipient_snapshot"])
    over("C6 zalohova faktura vznikla rovnou: castka == kalkulace, prijemce faktury = DEALER (ne koncovy zakaznik), doruceni = adresa koncoveho zakaznika, VS = cislo faktury",
         pro is not None and float(pro["amount_due_czk"]) == qc["amount_due_czk"] and rec["name"] == "Alfa s.r.o." and rec["ico"] == "11111111" and rec["email"] == "alfa000001@dealer.example" and "Jan Novák" not in json.dumps(rec, ensure_ascii=False)
         and json.loads(pro["delivery_snapshot"])["address"] == row["delivery_address"] and pro["variable_symbol"] == pro["document_number"], (pro and pro["amount_due_czk"], rec))
    pay = o["payment"]
    over("C7 odpoved nese platebni udaje: VS a cislo faktury, castka, splatnost, ucet a IBAN dodavatele, zpusob platby", pay and pay["variable_symbol"] == pro["variable_symbol"] and pay["document_number"] == pro["document_number"]
         and pay["amount_due_czk"] == float(pro["amount_due_czk"]) and pay["bank_account"] == documents.SUPPLIER["bank_account"] and (pay["iban"] or "").startswith("CZ") and pay["due_date"] and pay["method"] == "Platba předem", pay)
    hist = sql("SELECT * FROM shop_order_status_history WHERE order_id=%s", (row["id"],))
    over("C8 historie stavu: jeden zaznam 'nova' s poznamkou o API dealera a ref, bez uzivatele", len(hist) == 1 and hist[0]["status"] == "nova" and hist[0]["changed_by"] is None and "ESHOP-1001" in hist[0]["note"] and "Alfa s.r.o." in hist[0]["note"], hist)
    cs = cl.get("/api/dealer/v1/orders/ESHOP-1001", headers=hl(KA)).get_json()["order"]
    over("C9 GET stavu == odpoved z vytvoreni (stejny obsah), neni zaplaceno ani expedovano", cs == o and cs["paid"] is False and cs["shipped_at"] is None, cs)
    seq1 = seq()
    over("C10 citace: objednavka spotrebovala PRESNE jedno cislo objednavky a jedno cislo zalohove faktury", seq1 == (seq0[0] + 1, seq0[1] + 1), (seq0, seq1))
    with real.cursor() as cur:
        ov = dc.commission_overview(cur, [A["id"]], None, None, None, 1, 50)
    radek_prov = next((x for x in ov["commissions"] if x["order_id"] == row["id"]), None)
    over("C11 provize se u cesty 'dealer' nepocita (prehled provizi: status null, reason no_commission_path, 0 Kc, v souhrnu nic)",
         radek_prov is not None and radek_prov["status"] is None and radek_prov["reason"] == "no_commission_path" and radek_prov["commission_czk"] == 0.0 and radek_prov["order_path"] == "dealer" and ov["summary"] == {}, radek_prov)

    ser_admin, ser_zak = orders_mod._serialize_order(row), orders_mod._serialize_order_for_customer(row)
    over("C11b admin vidi puvod objednavky (dealer_id, order_path 'dealer', dealer_external_ref), zakaznicka serializace nic z toho nema",
         ser_admin["dealer_id"] == A["id"] and ser_admin["order_path"] == "dealer" and ser_admin["dealer_external_ref"] == "ESHOP-1001"
         and not ({"dealer_id", "order_path", "dealer_external_ref"} & set(ser_zak)), (ser_admin.get("dealer_id"), set(ser_zak)))

    # nedostatek skladu: bez zalohovky (stejne jako zakaznik), objednavka vznikne
    EMAILS.clear()
    rd = objednej(KA, telo("ESHOP-1002", [{"product_id": P["T-DESKA"], "qty": 2}]))
    od = rd.get_json()["order"]
    oradek = jedno("SELECT * FROM shop_orders WHERE dealer_external_ref=%s", ("ESHOP-1002",))
    over("C12 nedostatek skladu (deska 0 ks): objednavka vznikne, ale BEZ zalohove faktury (payment null, jako u zakaznika - po konzultaci dostupnosti), cena porad dealerska 450",
         rd.status_code == 201 and od["payment"] is None and pocet("shop_documents", "order_id=%s", (oradek["id"],)) == 0 and od["items"][0]["unit_price_net_czk"] == 450.0 and od["amount_due_czk"] > 0, rd.get_json())

    # ============================================================================================================ D) idempotence, limity, validace, izolace
    print("== D idempotence, limity, validace, izolace")
    seq2, n_obj = seq(), pocet("shop_orders")
    EMAILS.clear()
    AUDIT.clear()
    rp = objednej(KA, body_c)
    over("D1 stejny pozadavek znovu (stejny external_ref a obsah): 200 + Idempotent-Replayed, TATEZ objednavka, nic se nevytvori, citace se nehnou, e-mail ani audit se nezopakuje",
         rp.status_code == 200 and rp.headers.get("Idempotent-Replayed") == "true" and rp.get_json()["idempotent_replay"] is True and rp.get_json()["order"] == o and pocet("shop_orders") == n_obj and seq() == seq2 and not EMAILS and not AUDIT, rp.get_json())
    posun = copy.deepcopy(body_c)
    posun["items"] = [{"product_id": P["T-ZAOKR"], "qty": 3}, {"product_id": P["T-AKCE"], "qty": 4}, {"product_id": P["T-PROFIL"], "qty": 2},
                      {"product_id": P["T-SPOJKA"], "qty": 4}, {"product_id": P["T-SPOJKA"], "qty": 6}]
    over("D2 replay je odolny proti poradi a rozdeleni radku (stejny produkt 4 + 6 = 10 ks, jine poradi) a poznamce (poznamka se neporovnava)", objednej(KA, posun).status_code == 200 and objednej(KA, {**body_c, "note": "jina"}).status_code == 200, None)
    konflikty = {}
    for nazev, zmena in (("jine mnozstvi", lambda b: b["items"][0].update(qty=99)), ("jiny produkt", lambda b: b["items"][0].update(product_id=P["T-PRISL"])), ("jina adresa", lambda b: b["recipient"].update(street="Jina 9")),
                         ("jine PSC", lambda b: b["recipient"].update(zip="60200")), ("jine jmeno", lambda b: b["recipient"].update(name="Petr Novák")), ("jiny telefon", lambda b: b["recipient"].update(phone="+420 600 000 000")),
                         ("dalsi polozka", lambda b: b["items"].append({"product_id": P["T-PRISL"], "qty": 1}))):
        b = copy.deepcopy(body_c)
        zmena(b)
        rr = objednej(KA, b)
        konflikty[nazev] = (rr.status_code, rr.get_json().get("code"))
    over("D3 stejny external_ref s JINYM obsahem (mnozstvi, produkt, adresa, PSC, jmeno, telefon, dalsi polozka) -> 409 external_ref_conflict, nic se nezmeni ani nevytvori", set(konflikty.values()) == {(409, "external_ref_conflict")} and pocet("shop_orders") == n_obj and seq() == seq2, konflikty)
    pred_pc = (pocet("shop_orders"), seq())
    rpc = objednej(KA, telo("ESHOP-2001", expected_total_net_czk=1.0))
    over("D4 expected_total_net_czk se nerovna aktualni cene -> 409 price_changed s aktualnimi castkami, nic se nevytvori ani nespotrebuje (citace)", rpc.status_code == 409 and rpc.get_json()["code"] == "price_changed" and rpc.get_json()["current_total_net_czk"] > 1
         and (pocet("shop_orders"), seq()) == pred_pc, rpc.get_json())
    qo = quote(KA, {"items": [{"product_id": P["T-SPOJKA"], "qty": 2}], "delivery_zip": "11000", "shipping_method_id": 4}).get_json()
    rok = objednej(KA, telo("ESHOP-2002", expected_total_net_czk=qo["total_net_czk"]))
    over("D5 expected_total_net_czk shodne s kalkulaci (i jako cele cislo/float) -> objednavka vznikne", rok.status_code == 201 and rok.get_json()["order"]["total_net_czk"] == qo["total_net_czk"], rok.get_json())
    pred = (pocet("shop_orders"), seq())
    over("D6 neuplny profil dealera (chybi ICO) -> 409 dealer_profile_incomplete s vyctem chybejicich poli, nic se nevytvori", (lambda rr: rr.status_code == 409 and rr.get_json()["code"] == "dealer_profile_incomplete" and rr.get_json()["missing"] == ["ico"])(objednej(KE, telo("X-1")))
         and (pocet("shop_orders"), seq()) == pred, None)
    ref_chyby = ["", "a b", "x" * 65, "<script>", "ref/1", "-start", "čeština", None, 123, "ref\n1"]
    over("D7 neplatny external_ref (prazdny, mezera, 65 znaku, <, lomitko, pocatecni pomlcka, diakritika, null, cislo, novy radek) -> 400", all(objednej(KA, telo(ref=r_)).status_code == 400 for r_ in ref_chyby), [r_ for r_ in ref_chyby if objednej(KA, telo(ref=r_)).status_code != 400])
    over("D8 chybejici external_ref/recipient/shipping_method_id, recipient bez telefonu nebo s neplatnym PSC/telefonem -> 400", all(objednej(KA, b).status_code == 400 for b in (
        {k: v for k, v in telo().items() if k != "external_ref"}, {k: v for k, v in telo().items() if k != "recipient"}, {k: v for k, v in telo().items() if k != "shipping_method_id"},
        telo(recipient={k: v for k, v in RECIPIENT.items() if k != "phone"}), telo(recipient={**RECIPIENT, "zip": "1100"}), telo(recipient={**RECIPIENT, "phone": "abc"}), telo(recipient={**RECIPIENT, "name": "J"}),
        telo(recipient={**RECIPIENT, "extra": "x"}), telo(recipient="Jan Novák"), telo(shipping_method_id="4"))), None)
    pred = (pocet("shop_orders"), seq())
    hostile = {"name": "<img src='/etc/hostname'/>", "street": "Ulice <b>5</b>", "city": "Pra<ha", "phone": "+420 <1> 2"}
    chyby_znacky = {pole: objednej(KA, telo(f"H-{pole}", recipient={**RECIPIENT, pole: hodnota})).status_code for pole, hodnota in hostile.items()}
    chyby_znacky["poznamka"] = objednej(KA, telo("H-note", note="<font color='red'>x</font>")).status_code
    chyby_znacky["ridici znak"] = objednej(KA, telo("H-ctl", recipient={**RECIPIENT, "name": "Jan\x01Novák"})).status_code
    over("D9 znaky < > a ridici znaky v jmene, ulici, mestu, telefonu, poznamce se ODMITAJI (400) - PDF doklady nesmi dostat znacky; nic se nevytvori", set(chyby_znacky.values()) == {400} and (pocet("shop_orders"), seq()) == pred, chyby_znacky)
    rok2 = objednej(KA, telo("AMP-1", recipient={**RECIPIENT, "name": "Novák & syn R&D", "city": "Brno-Líšeň"}, note="řádek 1\nřádek 2"))
    ra = jedno("SELECT * FROM shop_orders WHERE dealer_external_ref='AMP-1'")
    pdfdoc = jedno("SELECT * FROM shop_documents WHERE order_id=%s AND document_type='proforma_invoice'", (ra["id"],))
    pdf = documents.render_document_pdf(pdfdoc)
    over("D10 & a diakritika projdou a ulozi se doslova (R&D), poznamka muze mit nove radky; PDF zalohove faktury se vygeneruje a neobsahuje obrazek",
         rok2.status_code == 201 and "Novák & syn R&D" in ra["delivery_address"] and ra["note"] == "řádek 1\nřádek 2" and pdf[:4] == b"%PDF" and b"/Subtype /Image" not in pdf, rok2.get_json())
    # izolace
    ob = objednej(KB, telo("ESHOP-1001", [{"product_id": P["T-SPOJKA"], "qty": 1}]))
    over("D11 stejny external_ref u JINEHO dealera je jina objednavka (unikatnost je na dealera), cena dealera B (15 %) = 85", ob.status_code == 201 and ob.get_json()["order"]["items"][0]["unit_price_net_czk"] == 85.0 and ob.get_json()["order"]["order_number"] != o["order_number"], ob.get_json())
    gb = cl.get("/api/dealer/v1/orders/ESHOP-1002", headers=hl(KB))
    lb = cl.get("/api/dealer/v1/orders", headers=hl(KB)).get_json()
    over("D12 dealer B nevidi objednavky dealera A: GET cizi reference 404 not_found, jeho seznam obsahuje jen jeho objednavku", gb.status_code == 404 and gb.get_json()["code"] == "not_found" and [x["external_ref"] for x in lb["orders"]] == ["ESHOP-1001"] and lb["total"] == 1, (gb.status_code, lb))
    over("D13 neexistujici/neplatna reference 404 (i nesmyslne znaky)", cl.get("/api/dealer/v1/orders/NENI", headers=hl(KA)).status_code == 404 and cl.get("/api/dealer/v1/orders/a%20b<", headers=hl(KA)).status_code == 404, None)
    # stav: zaplaceno, expedovano
    sql("UPDATE shop_orders SET payment_received_at='2026-11-06 10:00:00', payment_received_total_czk=%s WHERE id=%s", (qc["amount_due_czk"], row["id"]))
    sql("INSERT INTO shop_order_status_history (order_id, status, changed_at) VALUES (%s,'expedovana','2026-11-08 09:00:00')", (row["id"],))
    sql("UPDATE shop_orders SET status='expedovana' WHERE id=%s", (row["id"],))
    cs2 = cl.get("/api/dealer/v1/orders/ESHOP-1001", headers=hl(KA)).get_json()["order"]
    over("D14 stav objednavky: zaplaceno (paid, paid_at), expedovano (shipped_at z historie), status a cesky popisek", cs2["paid"] is True and cs2["paid_at"].startswith("2026-11-06") and cs2["shipped_at"].startswith("2026-11-08") and cs2["status"] == "expedovana"
         and cs2["status_label"] == "Expedovaná", cs2)
    lst = cl.get("/api/dealer/v1/orders", headers=hl(KA)).get_json()
    over("D15 seznam: nejnovejsi prvni, jen objednavky pres API, stranka a velikost (max 50), kratky tvar bez polozek", lst["orders"][0]["external_ref"] == "AMP-1" and lst["total"] == pocet("shop_orders", "dealer_id=%s AND dealer_external_ref IS NOT NULL", (A["id"],))
         and lst["page_size"] == 50 and "items" not in lst["orders"][0] and cl.get("/api/dealer/v1/orders?page_size=500", headers=hl(KA)).get_json()["page_size"] == 50
         and len(cl.get("/api/dealer/v1/orders?page=2&page_size=2", headers=hl(KA)).get_json()["orders"]) == 2 and cl.get("/api/dealer/v1/orders?page=x", headers=hl(KA)).status_code == 400, lst["orders"][:2])
    # limity
    sql("INSERT INTO app_settings (setting_key, setting_value) VALUES ('dealer_api_max_orders_per_day','%s') ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value)" % (pocet("shop_orders", "dealer_id=%s", (A["id"],)),))
    r_den = objednej(KA, telo("LIM-DEN"))
    sql("UPDATE app_settings SET setting_value='100' WHERE setting_key='dealer_api_max_orders_per_day'")
    over("D16 denni limit objednavek (nastaveni dealer_api_max_orders_per_day): po dosazeni 429 daily_limit, nic se nevytvori", r_den.status_code == 429 and r_den.get_json()["code"] == "daily_limit" and pocet("shop_orders", "dealer_external_ref='LIM-DEN'") == 0, r_den.get_json())
    nezaplacene = pocet("shop_orders", "dealer_id=%s AND order_path='dealer' AND status <> 'zrusena' AND payment_received_at IS NULL AND bank_paid=0", (A["id"],))
    sql("INSERT INTO app_settings (setting_key, setting_value) VALUES ('dealer_api_max_open_unpaid','%s') ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value)" % nezaplacene)
    r_open = objednej(KA, telo("LIM-OPEN"))
    sql("UPDATE shop_orders SET payment_received_at=NOW() WHERE dealer_id=%s AND payment_received_at IS NULL", (A["id"],))
    r_open2 = objednej(KA, telo("LIM-OPEN"))
    sql("UPDATE app_settings SET setting_value='30' WHERE setting_key='dealer_api_max_open_unpaid'")
    sql("UPDATE shop_orders SET payment_received_at=NOW() WHERE dealer_id=%s AND payment_received_at IS NULL", (A["id"],))          # dalsi cast testu potrebuje volny limit nezaplacenych
    over("D17 limit nezaplacenych objednavek: po dosazeni 429 open_orders_limit, po zaplaceni se zase objedna", r_open.status_code == 429 and r_open.get_json()["code"] == "open_orders_limit" and r_open2.status_code == 201, (r_open.get_json(), r_open2.status_code))
    r_big = objednej(KA, telo("LIM-BIG", [{"product_id": P["T-DRAHY"], "qty": 6}]))
    over("D18 limit hodnoty objednavky (500 000 Kc bez DPH): 6 x 90 000 = 540 000 -> 422 order_too_large, nic se nevytvori", r_big.status_code == 422 and r_big.get_json()["code"] == "order_too_large" and pocet("shop_orders", "dealer_external_ref='LIM-BIG'") == 0, r_big.get_json())
    sql("INSERT INTO app_settings (setting_key, setting_value) VALUES ('dealer_api_max_orders_per_day','1000'),('dealer_api_max_open_unpaid','1000') ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value)")
    appmod._rate_limit_buckets.clear()
    KEEP_RATE[0] = True
    odp = []
    for i in range(32):
        rr = objednej(KA, telo(f"RATE-{i}", [{"product_id": P["T-ZAOKR"], "qty": 1}]))
        odp.append((rr.status_code, rr.get_json().get("code")))
    KEEP_RATE[0] = False
    over("D19 limit zapisu objednavek za minutu na klic (30): prvnich 30 projde, dalsi 429 rate_limited s Retry-After", [s for s, c_ in odp[:30]] == [201] * 30 and odp[30:] == [(429, "rate_limited")] * 2, odp[28:])
    appmod._rate_limit_buckets.clear()
    sql("UPDATE app_settings SET setting_value='100' WHERE setting_key='dealer_api_max_orders_per_day'")
    sql("UPDATE app_settings SET setting_value='30' WHERE setting_key='dealer_api_max_open_unpaid'")
    sql("UPDATE shop_orders SET payment_received_at=NOW() WHERE dealer_id=%s AND payment_received_at IS NULL", (A["id"],))          # dalsi cast testu potrebuje volny limit nezaplacenych

    # ============================================================================================================ E) jadro objednavky
    print("== E jadro objednavky (orders._resolve_and_insert_order)")
    dealer_row = jedno("SELECT * FROM dealers WHERE id=%s", (A["id"],))
    zakl = {"customer_name": "X", "customer_email": "x@example.cz", "delivery_address": "Adresa 1", "delivery_zip": "11000", "billing_zip": "11000"}

    def jadro(body, dealer=None, user=None):
        with real.cursor() as cur, appmod.app.test_request_context("/"):
            try:
                res = orders_mod._resolve_and_insert_order(cur, {**zakl, **body}, attribute_user_id=user, profile_user_id=None, dealer=dealer)
                real.commit()
                return res
            except orders_mod._OrderCreateError as e:
                real.rollback()
                return ("chyba", e.status_code, e.message)

    n0 = pocet("shop_orders")
    r_cart = jadro({"use_cart": True}, dealer_row)
    r_ass = jadro({"items": [{"product_id": P["T-SPOJKA"], "qty": 1, "assembly_id": 5}]}, dealer_row)
    r_cut = jadro({"items": [{"product_id": P["T-SPOJKA"], "qty": 1, "montaz_zvolena": True}]}, dealer_row)
    r_brand = jadro({"items": [{"product_id": P["T-BRAND"], "qty": 1}]}, dealer_row)
    r_sestava = jadro({"items": [{"product_id": P["T-SESTAVA"], "qty": 1}]}, dealer_row)
    r_nodisc = jadro({"items": [{"product_id": P["T-DESKA"], "qty": 1}]}, jedno("SELECT * FROM dealers WHERE id=%s", (B["id"],)))
    over("E1 jadlo s dealerem: kosik, sestava, montaz, produkt se znackou, sestava jako produkt, dealer bez slevy -> _OrderCreateError (422/400), nic se nezapise",
         all(isinstance(x, tuple) and x[0] == "chyba" for x in (r_cart, r_ass, r_cut, r_brand, r_sestava, r_nodisc)) and r_brand[1] == 422 and r_sestava[1] == 422 and r_nodisc[1] == 422 and pocet("shop_orders") == n0, (r_cart, r_ass, r_cut, r_brand, r_sestava, r_nodisc))
    r_ok = jadro({"items": [{"product_id": P["T-SPOJKA"], "qty": 3}]}, dealer_row)
    over("E2 jadlo s dealerem pocita dealerskou cenu: 3 x 80 = 240 (ne cenikova 100)", not isinstance(r_ok, tuple) and r_ok["total"] == 240.0 and r_ok["order_items"][0]["unit_price_czk"] == 80.0, r_ok if isinstance(r_ok, tuple) else r_ok["total"])
    n1 = pocet("shop_orders")
    r_zak = jadro({"items": [{"product_id": P["T-SPOJKA"], "qty": 3}, {"product_id": P["T-AKCE"], "qty": 1}]}, None, None)
    rz = jedno("SELECT * FROM shop_orders WHERE id=%s", (r_zak["order_id"],))
    over("E3 BEZNY zakaznik (dealer=None) beze zmeny: cena z beznych pravidel (cenik 100, akce 150), zadna dealerska sleva, bez order_path/dealer_id/ref", r_zak["total"] == 450.0
         and [i["unit_price_czk"] for i in r_zak["order_items"]] == [100.0, 150.0] and rz["order_path"] in (None, "") and rz["dealer_id"] is None and rz["dealer_external_ref"] is None and pocet("shop_orders") == n1 + 1, r_zak["total"])
    r_sest = jadro({"items": [{"product_id": P["T-SESTAVA"], "qty": 1}]}, None, None)
    over("E4 bezny zakaznik muze koupit sestavu jako produkt (dealerska brana se na nej NEVZTAHUJE)", not isinstance(r_sest, tuple) and r_sest["total"] == 5000.0, r_sest if isinstance(r_sest, tuple) else r_sest["total"])
    zdroj_orders = open(orders_mod.__file__, encoding="utf-8").read()
    jadro_src = zdroj_orders[zdroj_orders.index("def _resolve_and_insert_order"):zdroj_orders.index('@app.post("/api/orders")')]
    over("E5 staticky: dealerska vetev je jen pri 'dealer is not None' (3 podminky; navic jen ochrana vetve konfigurace, ktera dealerskou cestu odmita), vychozi dealer=None a ostatni volajici (orders_create, admin_orders_create) dealera nepredavaji",
         (jadro_src.count("dealer is not None") - jadro_src.count("Konfigurovatelný produkt nelze objednat dealerskou cestou")) == 3 and "dealer=None):" in jadro_src[:300] and len(re.findall(r"= _resolve_and_insert_order\(", zdroj_orders)) == 2 and "dealer=dealer" not in zdroj_orders, (jadro_src.count("dealer is not None"), jadro_src[:200]))

    # ============================================================================================================ F) e-maily, audit, nic navic, mutace
    print("== F e-maily, audit, nic mimo ocekavane, mutace")
    EMAILS.clear()
    AUDIT.clear()
    rf = objednej(KA, telo("MAIL-1", [{"product_id": P["T-ZAOKR"], "qty": 2}]))
    rf_dup = objednej(KA, telo("MAIL-1", [{"product_id": P["T-ZAOKR"], "qty": 2}]))
    objednej(KA, telo("MAIL-1", [{"product_id": P["T-ZAOKR"], "qty": 3}]))
    objednej(KA, telo("MAIL-X", [{"product_id": 999999, "qty": 1}]))
    over("F1 e-mail objednavky jde do fronty jednou a JEN u uspesne nove objednavky (ne u replaye, konfliktu ani chyby), prijemce = e-mail DEALERA, ne koncoveho zakaznika",
         rf.status_code == 201 and rf_dup.status_code == 200 and len(EMAILS) == 1 and EMAILS[0]["customer_email"] == "alfa000001@dealer.example", [e["customer_email"] for e in EMAILS])
    over("F2 audit: jeden zaznam dealer_api_order s dealerem, klicem, ref, castkou a IP; zadny u replaye ani chyb", len(AUDIT) == 1 and AUDIT[0][0][1] == "dealer_api_order" and AUDIT[0][0][4]["dealer_id"] == A["id"] and AUDIT[0][0][4]["ref"] == "MAIL-1"
         and AUDIT[0][0][4]["key"].startswith("sk_") and "ip" in AUDIT[0][0][4] and AUDIT[0][0][0] is None, AUDIT)
    zdroj = open(do.__file__, encoding="utf-8").read()
    over("F3 modul nic nemaze a neposila e-maily primo: zadny DELETE/DROP/TRUNCATE, zadne send_email/smtp; zapisuje jen UPDATE shop_orders a INSERT shop_order_status_history (zbytek dela jadro objednavky)",
         not re.search(r"DELETE\s+FROM|DROP\s+TABLE|TRUNCATE|send_email|smtp|send_and_log", zdroj, re.I) and sorted(set(re.findall(r"(?:INSERT INTO|UPDATE)\s+(\w+)", zdroj))) == ["shop_order_status_history", "shop_orders"], sorted(set(re.findall(r"(?:INSERT INTO|UPDATE)\s+(\w+)", zdroj))))

    # pojistka shody: kdyby jadro spocitalo jinou cenu nez kalkulace, objednavka se NEvytvori
    orig = orders_mod._resolve_toptrans_price
    volani = {"n": 0}

    def zkresleny(cur, sid, zip_code, w, v=0.0):
        volani["n"] += 1
        p_, km, b_ = orig(cur, sid, zip_code, w, v)
        return (p_ + 1.0, km, b_) if volani["n"] > 1 else (p_, km, b_)

    pred_s = (pocet("shop_orders"), seq())
    orders_mod._resolve_toptrans_price = zkresleny
    try:
        rmm = objednej(KA, telo("MISMATCH-1", [{"product_id": P["T-ZAOKR"], "qty": 1}]))
    finally:
        orders_mod._resolve_toptrans_price = orig
    over("F4 pojistka: kdyby se kalkulace a jadro rozesly o jedinou korunu, objednavka se NEVYTVORI (500 price_mismatch, rollback vcetne citacu)", rmm.status_code == 500 and rmm.get_json()["code"] == "price_mismatch"
         and (pocet("shop_orders"), seq()) == pred_s, (rmm.status_code, volani))
    orders_mod._send_order_emails_bg = lambda result: EMAILS.append(result)
    # --- mutace
    def mutant(modul_zdroj, modul, funkce, stare, nove):
        t = ast.parse(modul_zdroj)
        node = next(n for n in t.body if isinstance(n, ast.FunctionDef) and n.name == funkce)
        src = ast.get_source_segment(modul_zdroj, node)
        assert src.count(stare) == 1, f"{funkce}: '{stare}' nalezeno {src.count(stare)}x"
        ns = dict(vars(modul))
        exec(src.replace(stare, nove), ns)
        return ns[funkce]

    with real.cursor() as cur:
        m1 = mutant(zdroj, do, "_same_request", "return (have == dict(items) and", "return (True or have == dict(items) and")
        oex = jedno("SELECT * FROM shop_orders WHERE dealer_external_ref='ESHOP-1001'")
        zmenene = copy.deepcopy(RECIPIENT)
        zmenene["zip"] = "60200"
        over("M1 mutace: _same_request vzdy pravda by u ZMENENEHO obsahu vratilo puvodni objednavku misto konfliktu (test D3 ji zachyti)", do._same_request(cur, oex, [(P["T-SPOJKA"], 10), (P["T-PROFIL"], 2), (P["T-AKCE"], 4), (P["T-ZAOKR"], 3)], zmenene, 4) is False
             and m1(cur, oex, [(P["T-SPOJKA"], 10), (P["T-PROFIL"], 2), (P["T-AKCE"], 4), (P["T-ZAOKR"], 3)], zmenene, 4) is True, None)
        m2 = mutant(zdroj, do, "price_order", "unit, basis = dealers.dealer_effective_price(cur, p, dealer)", "unit, basis = float(p['price_czk_placeholder']), 'dealer'")
        spravne = do.price_order(cur, jedno("SELECT * FROM dealers WHERE id=%s", (A["id"],)), [(P["T-SPOJKA"], 1)], "11000", 4)
        chybne = m2(cur, jedno("SELECT * FROM dealers WHERE id=%s", (A["id"],)), [(P["T-SPOJKA"], 1)], "11000", 4)
        over("M2 mutace: cenikova cena misto dealerske v kalkulaci by dala 100 misto 80 (testy B1, C5 a pojistka F4 ji zachyti)", spravne.lines[0]["unit_price_net_czk"] == 80.0 and chybne.lines[0]["unit_price_net_czk"] == 100.0, None)
        m3 = mutant(zdroj, do, "price_order", 'view = dealers.dealer_product_view(cur, pid, mode="none") if p else None', 'view = {"sku": p["sku"], "unit": "ks", "availability": "skladem"} if p else None')
        dealer_a = jedno("SELECT * FROM dealers WHERE id=%s", (A["id"],))
        try:
            do.price_order(cur, dealer_a, [(P["T-SESTAVA"], 1)], "11000", 4)
            spravne_pustilo = True
        except do.ApiError:
            spravne_pustilo = False
        try:
            m3(cur, dealer_a, [(P["T-SESTAVA"], 1)], "11000", 4)
            vyslo = True
        except Exception:
            vyslo = False
        over("M3 mutace: bez brany dealer_product_view by se kalkulovala i sestava (spravna verze ji odmitne; test B8 mutaci zachyti)", spravne_pustilo is False and vyslo is True, (spravne_pustilo, vyslo))
    zdroj_inp = zdroj
    over("M4 mutace: bez kontroly < > by hostilni jmeno proslo (regex _BAD_CHARS_RE ma < > a ridici znaky)", do._BAD_CHARS_RE.search("<img>") and do._BAD_CHARS_RE.search("a\x01b") and not do._BAD_CHARS_RE.search("Novák & syn R&D, Brno-Líšeň 5/2"), None)
    zdroj_auth = mutant(zdroj, do, "_auth", 'if dealer["order_path"] != "dealer":', "if False:")
    appmod._rate_limit_buckets.clear()
    with appmod.app.test_request_context("/api/dealer/v1/quote", headers=hl(KC)):
        try:
            zdroj_auth("quote")
            pustil = True
        except Exception:
            pustil = False
        try:
            do._auth("quote")
            spravne_pustil = True
        except Exception:
            spravne_pustil = False
    over("M5 mutace: bez kontroly cesty 'dealer' by dealer s provizni cestou mohl objednavat (test A4 ji zachyti)", pustil is True and spravne_pustil is False, (pustil, spravne_pustil))
    with real.cursor() as cur, appmod.app.test_request_context("/"):
        m6 = mutant(zdroj_orders, orders_mod, "_resolve_and_insert_order", 'unit_price, _price_basis = dealers.dealer_effective_price(cur, product_for_pricing, dealer)',
                    'unit_price, _price_basis = float(product_for_pricing["price_czk_placeholder"]), "base"')
        try:
            res6 = m6(cur, {**zakl, "items": [{"product_id": P["T-SPOJKA"], "qty": 3}]}, attribute_user_id=None, profile_user_id=None, dealer=dealer_row)
            real.commit()
            cena6 = res6["total"]
        except Exception as e:
            real.rollback()
            cena6 = repr(e)
    over("M6 mutace jadra: bez dealerske ceny v jadru by dealer dostal cenikovou cenu (300 misto 240; testy E2 a pojistka F4 ji zachyti)", cena6 == 300.0 and r_ok["total"] == 240.0, (cena6, r_ok["total"]))
finally:
    with real.cursor() as cur:
        for t in TEMP_LIKE + TEMP_COPY + tuple(f"_tpl_{x}" for x in TEMP_LIKE + TEMP_COPY):
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `{t}`")
    real.commit()

po = stav_ostrych()
over("ostre tabulky (objednavky, polozky, doklady, historie, e-maily, audit, dealeri, klice, produkty, kategorie, nastaveni, platby, dopravy, citace) jsou po testu beze zmeny", po == PRED_OSTRE, (PRED_OSTRE, po))
ok = sum(vysl)
print(f"\nVYSLEDEK dealersky program krok 4 - objednavka pres API: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
