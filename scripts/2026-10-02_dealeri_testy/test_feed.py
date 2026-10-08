#!/opt/konfigurator/api/venv/bin/python
"""Dealersky program, krok 5 (bot5, 2026-10-02): FEED PRODUKTU pro dealery (CSV + XML) - api/dealer_feed.py + filtr obrazku se znackou v dealers.dealer_product_view, nad DOCASNYMI tabulkami.

Skutecny kod (nebo kandidati DEALER_FEED_PY, DEALERS_PY, APP_PY) bezi pres Flask test client. Docasne kopie: dealers, dealer_rates, dealer_keys, dealer_domains, dealer_clicks, shop_products, content_categories,
product_assemblies, shop_product_images, app_settings. Nic se nezapisuje do ostrych dat, nic se neodesila.

Cast A  autorizace (feed token v hlavicce i v ?token=, rozsah feed, widget/api klic, odvolany, pozastaveny dealer)
Cast B  konfigurace verejne adresy (503 dokud neni nastavena, http a znacka v adrese se odmitaji)
Cast C  obsah CSV: jen produkty z dealer_product_view (sestavy, VD-*, znacka, neaktivni, bez ceny, skryta kategorie, bez dealerske ceny), ceny cesty 'dealer' (dealerska cena x prirazka) a 'our' (verejna), odkazy a obrazky
Cast D  XML: dobre utvoreny dokument, stejne produkty, escapovani a rizici znaky; CSV: strednik, uvozovky, ochrana pred vzorci
Cast E  prirazka (povinna u 'dealer', meze), ETag a 304, cache (10 min, oddelena po dealerech, formatech a prirazkach)
Cast F  nic neuniká: dealerska cena bez prirazky, naklady, dodavatel ani znacka nikde ve vystupu; obrazek se znackou v nazvu souboru se vynecha; mutace
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
  /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-02_dealeri_testy/test_feed.py     (kandidati: --setenv=DEALER_FEED_PY=... --setenv=DEALERS_PY=... --setenv=APP_PY=...)
"""
import ast
import csv
import io
import os
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
API = os.path.join(REPO, "api")
KANDIDATI = {"dealer_feed.py": os.environ.get("DEALER_FEED_PY"), "dealers.py": os.environ.get("DEALERS_PY"), "app.py": os.environ.get("APP_PY")}
if any(KANDIDATI.values()):
    tmp = tempfile.mkdtemp(prefix="kand_feed_")
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
import dealer_feed as df  # noqa: E402

dealers.log_audit = lambda *a, **k: None
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:500]))


def ostre():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                           port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


def stav_ostrych():
    c = ostre()
    try:
        with c.cursor() as cur:
            out = {}
            for t in ("dealers", "dealer_keys", "dealer_rates", "shop_products", "shop_product_images", "content_categories", "app_settings", "shop_orders", "shop_emails", "audit_log"):
                cur.execute(f"SELECT COUNT(*) AS n FROM `{t}`")
                out[t] = cur.fetchone()["n"]
            return out
    finally:
        c.close()


PRED_OSTRE = stav_ostrych()
wrap = appmod.get_conn()
real = object.__getattribute__(wrap, "_real")
TEMP_LIKE = ("dealers", "dealer_rates", "dealer_keys", "dealer_domains", "dealer_clicks", "shop_products", "content_categories", "product_assemblies", "shop_product_images")
TEMP_COPY = ("app_settings",)


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
        cur.execute("DELETE FROM app_settings WHERE setting_key LIKE 'dealer_%'")
    real.commit()

    sql("INSERT INTO content_categories (id, name, parent_id, is_visible) VALUES (9001,'Spojovací materiál',NULL,1),(9002,'Příslušenství',9001,1),(9003,'Skryté',NULL,0)")
    PROD = {}

    def produkt(sku, name, price, stock=10, weight_g=100, cat=None, active=1, slug=None, description=None, **extra):
        cols = {"sku": sku, "name": name, "price_czk_placeholder": price, "stock_qty": stock, "weight_g": weight_g, "category_id": cat, "active": active, "unit": "ks", "slug": slug, "description": description, **extra}
        sql(f"INSERT INTO shop_products ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})", list(cols.values()))
        PROD[sku] = jedno("SELECT id FROM shop_products WHERE sku=%s", (sku,))["id"]
        return PROD[sku]

    def obrazky(sku, nazvy):
        for i, n in enumerate(nazvy):
            sql("INSERT INTO shop_product_images (product_id, filename, sort_order) VALUES (%s,%s,%s)", (PROD[sku], n, i))

    produkt("T-SPOJKA", "Spojka L 30", 100.00, 50, 200, 9001, slug="spojka-l-30", description="<p>Pevná <b>hliníková</b> spojka.</p>", length_mm=30, width_mm=30, height_mm=30)
    obrazky("T-SPOJKA", ["spojka-1.jpg", "spojka-2.jpg", "logiman-spojka.jpg", "spojka-3.jpg"])
    produkt("T-PROFIL", "Profil 30x30 3 m", 1000.00, 5, 3000, None, slug="profil-30x30", dealer_discount_percent=30, is_profile_material=1)
    produkt("T-DESKA", "Deska PR10", 500.00, 0, 15000, None, slug="deska-pr10", is_board_material=1, board_sheet_width_mm=2800, board_sheet_height_mm=2070)
    produkt("T-AKCE", "Akční díl", 200.00, 10, 100, None, slug="akcni-dil", sale_price_czk=150.00)
    produkt("T-ZAOKR", "Zaokrouhlovací díl", 33.33, 100, 50, None, slug="zaokr")
    produkt("T-VZOREC", "=SUM(1+1) díl", 10.00, 10, 10, None, slug="vzorec", description="-začíná pomlčkou; má středník, \"uvozovky\"\na nový řádek")
    produkt("T-XML", "Rám 30 & <40> \"x\"", 10.00, 10, 10, None, slug="xml-ram", description="Popis & <b>znaky</b>\x01skryté")
    produkt("T-OBR", "Díl se sedmi obrázky", 10.00, 10, 10, None, slug="obr")
    obrazky("T-OBR", [f"obr-{i}.jpg" for i in range(1, 8)])
    pf = produkt("T-SESTAVA", "Regál sestava", 5000.00, 10, 1000, None, slug="sestava")
    sql("INSERT INTO product_assemblies (name, data, shop_product_id) VALUES ('Sestava','{}',%s)", (pf,))
    produkt("VD-001", "Vandr regál", 5000.00, 10, 1000, None, slug="vd-1")
    produkt("T-BRAND", "Logiman držák", 100.00, 10, 100, None, slug="drzak")
    produkt("T-NEAKT", "Neaktivní díl", 100.00, 10, 100, None, active=0, slug="neakt")
    produkt("T-BEZCENY", "Díl bez ceny", None, 10, 100, None, slug="bez-ceny")
    produkt("T-SKRYTA", "Díl ve skryté kategorii", 100.00, 10, 100, 9003, slug="skryta")
    produkt("T-PRISL", "Příslušenství k profilu", 50.00, 100, 50, 9002, slug="prislusenstvi")

    def dealer(name, ref, **kw):
        d = {"ref_code": ref, "name": name, "status": "active", "order_path": "dealer", "default_discount_pct": 10.0, "contact_email": f"{ref}@dealer.example"}
        d.update(kw)
        sql(f"INSERT INTO dealers ({', '.join(d)}) VALUES ({', '.join(['%s'] * len(d))})", list(d.values()))
        return jedno("SELECT * FROM dealers WHERE ref_code=%s", (ref,))

    A = dealer("Alfa", "alfa000001")                                         # cesta 'dealer', sleva 10 %, kategorie 9001 sleva 20 %
    B = dealer("Beta", "beta000002", order_path="our", default_discount_pct=None)      # cesta 'our' (provize): verejne ceny + odkazy
    Cd = dealer("Gama", "gama000003", default_discount_pct=None)             # cesta 'dealer' bez slevy: vsechno bez ceny se vynecha
    Dd = dealer("Delta", "delt000004", status="suspended")
    sql("INSERT INTO dealer_rates (dealer_id, category_id, discount_pct) VALUES (%s,9001,20.00)", (A["id"],))

    def klic(d, kind="feed", scopes=None):
        with real.cursor() as cur:
            row, secret, token = dealers._create_key(cur, d, kind, "test", scopes, None, 6000, None)
        real.commit()
        return token if kind != "widget" else row["public_id"]

    KA, KB, KC, KD = klic(A), klic(B), klic(Cd), klic(Dd)
    KAPI = klic(A, "api", "orders,quote")
    KW = klic(A, "widget")
    KREV = klic(A)
    sql("UPDATE dealer_keys SET revoked_at=NOW(), is_active=0 WHERE public_id=%s", ("_".join(KREV.split("_")[:2]),))

    cl = appmod.app.test_client()

    def hl(token, ip="127.0.0.1"):
        h = {"X-Real-IP": ip}
        if token:
            h["Authorization"] = f"Bearer {token}"
        return h

    def feed(token, fmt="csv", params="", ip="127.0.0.1", headers=None):
        appmod._rate_limit_buckets.clear()
        h = {**hl(token, ip), **(headers or {})}
        return cl.get(f"/api/dealer/v1/feed.{fmt}{params}", headers=h)

    def tabulka(resp):
        text = resp.get_data(as_text=True)
        radky = list(csv.reader(io.StringIO(text), delimiter=";"))
        hlava = radky[0]
        return hlava, [dict(zip(hlava, r)) for r in radky[1:]], text

    def vymaz_cache():
        with df._CACHE_LOCK:
            df._CACHE.clear()

    BASE = "https://partner.example.cz"

    # ============================================================================================================ A) autorizace
    print("== A autorizace")
    sql("INSERT INTO app_settings (setting_key, setting_value) VALUES ('dealer_public_base_url', %s)", (BASE,))
    over("A1 bez tokenu, spatny token, widget klic, odvolany token: 401 invalid_key; api klic bez rozsahu feed 403 scope_denied",
         feed(None, params="?markup=25").status_code == 401 and feed("ft_deadbeef_" + "x" * 40, params="?markup=25").status_code == 401 and feed(KW, params="?markup=25").status_code == 401
         and feed(KREV, params="?markup=25").status_code == 401 and feed(KAPI, params="?markup=25").status_code == 403 and feed(KAPI, params="?markup=25").get_json()["code"] == "scope_denied", feed(KAPI, params="?markup=25").status_code)
    over("A2 token v hlavicce i v ?token= (pro importery bez hlavicky) funguje; hlavicka ma prednost; dealer pozastaveny 403 dealer_inactive",
         feed(KA, params="?markup=25").status_code == 200 and feed(None, params=f"?markup=25&token={KA}").status_code == 200 and feed(KB).status_code == 200
         and feed(KD, params="?markup=25").status_code == 403 and feed(KD, params="?markup=25").get_json()["code"] == "dealer_inactive"
         and feed("ft_deadbeef_" + "x" * 40, params=f"?markup=25&token={KA}").status_code == 401, None)
    over("A3 jen GET (POST na feed 405) a odpoved nese Cache-Control private no-cache, ETag, nosniff, Content-Disposition inline; zadne CORS hlavicky",
         cl.post("/api/dealer/v1/feed.csv", headers=hl(KA)).status_code == 405 and (lambda r: r.headers["Cache-Control"] == "private, no-cache" and r.headers["ETag"].startswith('"') and r.headers["X-Content-Type-Options"] == "nosniff"
         and "produkty.csv" in r.headers["Content-Disposition"] and not any(h.lower().startswith("access-control") for h in r.headers.keys()))(feed(KA, params="?markup=25")), None)

    # ============================================================================================================ B) konfigurace
    print("== B verejna adresa")
    nastaveni = {}
    for nazev, hodnota in (("nenastaveno", None), ("prazdne", ""), ("http", "http://partner.example.cz"), ("znacka v adrese", "https://logiman.cz"), ("dodavatel v adrese", "https://dogus-shop.example.cz"),
                           ("lomitka a prazdne", "https://"), ("mezera a skript", "https://x.cz/<script>"), ("jen host", "partner")):
        sql("DELETE FROM app_settings WHERE setting_key='dealer_public_base_url'")
        if hodnota is not None:
            sql("INSERT INTO app_settings (setting_key, setting_value) VALUES ('dealer_public_base_url', %s)", (hodnota,))
        vymaz_cache()
        r = feed(KA, params="?markup=25")
        nastaveni[nazev] = (r.status_code, (r.get_json() or {}).get("code"))
    over("B1 bez nastavene verejne adresy (nenastaveno, prazdna, http, znacka/dodavatel v adrese, nesmysl) feed vraci 503 feed_not_configured - zadne odkazy ani obrazky bez neutralni domeny", set(nastaveni.values()) == {(503, "feed_not_configured")}, nastaveni)
    sql("DELETE FROM app_settings WHERE setting_key='dealer_public_base_url'")
    sql("INSERT INTO app_settings (setting_key, setting_value) VALUES ('dealer_public_base_url', %s)", (BASE + "/",))
    vymaz_cache()
    over("B2 platna https adresa (i s koncovym lomitkem) funguje, adresa v odkazech je bez zdvojeneho lomitka", feed(KB).status_code == 200 and "https://partner.example.cz//" not in feed(KB).get_data(as_text=True), None)

    # ============================================================================================================ C) obsah CSV
    print("== C obsah CSV")
    vymaz_cache()
    r = feed(KA, params="?markup=25")
    hlava, radky, text = tabulka(r)
    skus = {x["sku"] for x in radky}
    ocek_sku = {"T-SPOJKA", "T-PROFIL", "T-DESKA", "T-AKCE", "T-ZAOKR", "T-VZOREC", "T-XML", "T-OBR", "T-PRISL"}
    over("C1 hlavicka a typ: UTF-8, text/csv, strednik, sloupce podle specifikace (vcetne image_1..image_5)", r.status_code == 200 and r.headers["Content-Type"] == "text/csv; charset=utf-8" and hlava == df.CSV_COLUMNS and len(hlava) == 21, (r.status_code, hlava))
    over("C2 jen produkty z dealer_product_view: ve feedu je 9 produktu, NENI sestava, VD-*, znacka v nazvu, neaktivni, bez ceny ani ve skryte kategorii", skus == ocek_sku, sorted(skus ^ ocek_sku))
    over("C3 pocet radku a unikatni id: kazdy produkt jednou, serazeno podle id", len(radky) == 9 and len({x["id"] for x in radky}) == 9 and [int(x["id"]) for x in radky] == sorted(int(x["id"]) for x in radky), len(radky))
    p = {x["sku"]: x for x in radky}
    over("C4 cesta 'dealer': cena = dealerska cena x (1 + 25 %): spojka 80 -> 100,00 (121,00 s DPH), profil 700 -> 875,00, deska 450 -> 562,50, akce min(180,150)=150 -> 187,50, zaokrouhleni 30,00 -> 37,50; DPH 21",
         (p["T-SPOJKA"]["price_net_czk"], p["T-SPOJKA"]["price_gross_czk"]) == ("100.00", "121.00") and p["T-PROFIL"]["price_net_czk"] == "875.00" and p["T-DESKA"]["price_net_czk"] == "562.50"
         and p["T-AKCE"]["price_net_czk"] == "187.50" and p["T-ZAOKR"]["price_net_czk"] == "37.50" and p["T-PRISL"]["price_net_czk"] == "50.00" and all(x["vat_rate"] == "21" and x["currency"] == "CZK" for x in radky), {k: v["price_net_czk"] for k, v in p.items()})
    over("C5 cesta 'dealer': zadne odkazy na nas (link prazdny), obrazky jen s absolutni neutralni adresou, nejvyse 5 obrazku, soubor se znackou v nazvu (logiman-spojka.jpg) vynechan",
         all(x["link"] == "" for x in radky) and p["T-SPOJKA"]["image_1"] == BASE + "/content-files/gallery/spojka-1.jpg" and p["T-SPOJKA"]["image_3"] == BASE + "/content-files/gallery/spojka-3.jpg" and p["T-SPOJKA"]["image_4"] == ""
         and all(p["T-OBR"][f"image_{i}"] for i in range(1, 6)) and "obr-6.jpg" not in text and "obr-7.jpg" not in text and "logiman" not in text.lower(), p["T-SPOJKA"])
    over("C6a popis jako cisty text (bez HTML) a kategorie jako cesta", p["T-SPOJKA"]["description"] == "Pevná hliníková spojka." and p["T-PRISL"]["category"] == "Spojovací materiál > Příslušenství", (p["T-SPOJKA"]["description"], p["T-PRISL"]["category"]))
    over("C6b rozmery a hmotnost jako cista cisla (30, 200), dostupnost 'skladem' nebo text dostupnosti karty (u skladu 0) bez presneho poctu kusu", p["T-SPOJKA"]["length_mm"] == "30" and p["T-SPOJKA"]["weight_g"] == "200" and p["T-SPOJKA"]["availability"] == "skladem"
         and p["T-DESKA"]["availability"] not in ("", "skladem"), (p["T-SPOJKA"]["length_mm"], p["T-SPOJKA"]["weight_g"], p["T-DESKA"]["availability"]))
    over("C6c zadny sloupec ani hodnota s pocty skladu", "stock" not in text.lower() and "sklad_" not in text.lower(), [m.group(0) for m in re.finditer(r".{0,20}stock.{0,20}", text.lower())][:3])
    sada = feed(KB)
    _h2, radky_b, text_b = tabulka(sada)
    pb = {x["sku"]: x for x in radky_b}
    over("C7 cesta 'our' (provize): verejne ceny (spojka 100/121, akce 150, bez prirazky ani dealerske slevy), markup se ignoruje, odkaz pres JEHO proklik /api/dealer/go/<ref>?to=/produkt/<slug>",
         pb["T-SPOJKA"]["price_net_czk"] == "100.00" and pb["T-SPOJKA"]["price_gross_czk"] == "121.00" and pb["T-AKCE"]["price_net_czk"] == "150.00" and pb["T-PROFIL"]["price_net_czk"] == "1000.00"
         and pb["T-SPOJKA"]["link"] == f"{BASE}/api/dealer/go/beta000002?to=/produkt/spojka-l-30" and feed(KB, params="?markup=300").get_data(as_text=True) == text_b and set(pb) == ocek_sku, pb["T-SPOJKA"])
    _h3, radky_c, _t3 = tabulka(feed(KC, params="?markup=25"))
    over("C8 cesta 'dealer' bez slevy (Gama) vynecha vsechno bez dealerske ceny; produkt s vlastni slevou na karte (profil 30 %) zustane: 700 x 1,25 = 875", [x["sku"] for x in radky_c] == ["T-PROFIL"] and radky_c[0]["price_net_czk"] == "875.00", [x["sku"] for x in radky_c])

    # ============================================================================================================ D) XML a CSV format
    print("== D XML a format CSV")
    rx = feed(KA, "xml", "?markup=25")
    try:
        koren = ET.fromstring(rx.get_data())
        xml_ok = True
    except ET.ParseError as e:
        koren, xml_ok = None, False
    over("D1 XML je dobre utvoreny dokument (application/xml; charset=utf-8) s atributy generated a count", rx.status_code == 200 and rx.headers["Content-Type"] == "application/xml; charset=utf-8" and xml_ok and koren.tag == "products" and koren.get("count") == "9" and len(koren.findall("product")) == 9, (rx.status_code, rx.get_data()[:200]))
    xp = {pr.findtext("sku"): pr for pr in koren.findall("product")} if xml_ok else {}
    over("D2 XML ma stejne produkty a ceny jako CSV (cena v atributech net/gross/vat_rate/currency), kategorie a obrazky jako podelementy", set(xp) == ocek_sku and xp["T-SPOJKA"].find("price").attrib == {"currency": "CZK", "vat_rate": "21", "net": "100.00", "gross": "121.00"}
         and [c.text for c in xp["T-PRISL"].find("categories")] == ["Spojovací materiál", "Příslušenství"] and [i.text for i in xp["T-SPOJKA"].find("images")] == [BASE + f"/content-files/gallery/spojka-{i}.jpg" for i in (1, 2, 3)], sorted(xp))
    over("D3 XML: znaky & < > \" v nazvu se escapuji a vrati se doslova, ridici znak (\\x01) se odstrani, zadny z nich nerozbije dokument", xp["T-XML"].findtext("name") == "Rám 30 & <40> \"x\"" and xp["T-XML"].findtext("description") == "Popis & znaky skryté" and b"\x01" not in rx.get_data(), xp["T-XML"].findtext("description"))
    over("D4 CSV: ochrana pred vzorci (nazev '=SUM...' dostane predponu apostrof), popis s novym radkem, stredniky a uvozovkami je spravne uvozen a precte se zpet, ridici znak odstranen", p["T-VZOREC"]["name"] == "'=SUM(1+1) díl"
         and p["T-VZOREC"]["description"].startswith("'-začíná pomlčkou;") and "\"uvozovky\"" in p["T-VZOREC"]["description"] and "\x01" not in text and p["T-XML"]["description"] == "Popis & znaky skryté", p["T-VZOREC"])

    # ============================================================================================================ E) prirazka, ETag, cache
    print("== E prirazka, ETag a cache")
    chyby = {m: (feed(KA, params=f"?markup={m}").status_code, (feed(KA, params=f"?markup={m}").get_json() or {}).get("code")) for m in ("", "abc", "-1", "500.5", "1e9", "nan")}
    chyby["chybi"] = (feed(KA).status_code, (feed(KA).get_json() or {}).get("code"))
    over("E1 prirazka je u cesty 'dealer' povinna a ma meze 0-500: chybi/prazdna/text/zaporna/nad 500/nan -> 400 invalid_request", all(v == (400, "invalid_request") for v in chyby.values()), chyby)
    over("E2 prirazka 0 dava dealerskou cenu (spojka 80), 500 dava 6x (480), desetinna carka funguje (12,5 %: 90,00), ostatni ceny odpovidaji",
         tabulka(feed(KA, params="?markup=0"))[1][0]["price_net_czk"] != "" and {x["sku"]: x["price_net_czk"] for x in tabulka(feed(KA, params="?markup=0"))[1]}["T-SPOJKA"] == "80.00"
         and {x["sku"]: x["price_net_czk"] for x in tabulka(feed(KA, params="?markup=500"))[1]}["T-SPOJKA"] == "480.00"
         and {x["sku"]: x["price_net_czk"] for x in tabulka(feed(KA, params="?markup=12,5"))[1]}["T-SPOJKA"] == "90.00", None)
    r1 = feed(KA, params="?markup=25")
    et = r1.headers["ETag"]
    r304 = feed(KA, params="?markup=25", headers={"If-None-Match": et})
    over("E3 ETag a podminene stazeni: stejny obsah + If-None-Match -> 304 bez tela s ETag; jiny ETag -> 200 s telem; jina prirazka ma jiny ETag", r304.status_code == 304 and r304.get_data() == b"" and r304.headers["ETag"] == et
         and feed(KA, params="?markup=25", headers={"If-None-Match": '"jiny"'}).status_code == 200 and feed(KA, params="?markup=30").headers["ETag"] != et, None)
    pocet = {"n": 0}
    orig_view = dealers.dealer_product_view

    def pocitadlo(*a, **k):
        pocet["n"] += 1
        return orig_view(*a, **k)

    dealers.dealer_product_view = pocitadlo
    try:
        vymaz_cache()
        feed(KA, params="?markup=25")
        n1 = pocet["n"]
        feed(KA, params="?markup=25")
        feed(KA, params="?markup=25", headers={"If-None-Match": et})
        n2 = pocet["n"]
        feed(KA, "xml", "?markup=25")
        n3 = pocet["n"]
        feed(KA, params="?markup=30")
        n4 = pocet["n"]
        feed(KC, params="?markup=25")
        n5 = pocet["n"]
    finally:
        dealers.dealer_product_view = orig_view
    over("E4 cache: prvni stazeni sestavi feed (vsechny aktivni produkty), dalsi stejna zadost (i podminena) ho vezme z pameti (0 novych pruchodu), jiny format, jina prirazka a JINY DEALER sestavuji znovu a nesdili si cache",
         n1 > 0 and n2 == n1 and n3 > n2 and n4 > n3 and n5 > n4, (n1, n2, n3, n4, n5))
    cl_ = df._now
    df._now = lambda: cl_() + df.CACHE_SECONDS + 5
    dealers.dealer_product_view = pocitadlo
    try:
        n6 = pocet["n"]
        feed(KA, params="?markup=25")
        n7 = pocet["n"]
    finally:
        df._now = cl_
        dealers.dealer_product_view = orig_view
    over("E5 po uplynuti 10 minut se feed sestavi znovu (cache vyprsi)", n7 > n6, (n6, n7))

    # --- strop pameti cache a limit sestavovani
    vymaz_cache()
    for m in range(0, 45):
        appmod._rate_limit_buckets.clear()
        feed(KA, params=f"?markup={m}")
    n_cache = len(df._CACHE)
    over("E6 cache ma strop (40 polozek): 45 ruznych prirazek nenarusti pamet, nejstarsi se vyhazuji", 0 < n_cache <= df.MAX_CACHE_ENTRIES, n_cache)
    vymaz_cache()
    appmod._rate_limit_buckets.clear()
    odp = []
    for m in range(0, 12):
        r_ = cl.get(f"/api/dealer/v1/feed.csv?markup={m}", headers=hl(KA))          # bez mazani limitu mezi pozadavky
        odp.append((r_.status_code, (r_.get_json() or {}).get("code") if r_.status_code != 200 else None))
    over("E7 limit sestavovani feedu: prvnich 10 ruznych prirazek za minutu projde, dalsi 429 rate_limited (nutit dealerem 2s prace dokola nejde); stejny feed z cache limit nepocita",
         [s for s, c_ in odp[:10]] == [200] * 10 and odp[10:] == [(429, "rate_limited")] * 2 and cl.get("/api/dealer/v1/feed.csv?markup=3", headers=hl(KA)).status_code == 200, odp)
    appmod._rate_limit_buckets.clear()

    # ============================================================================================================ F) nic neuniká
    print("== F nic neuniká")
    vsechno = text + text_b + rx.get_data(as_text=True)
    over("F1 ve vystupu (CSV i XML, obe cesty) neni zadna znacka ani dodavatel: logiman, konfigurator, vandrawee, dogus", not re.search(r"logiman|konfigur|vandr|dogus", vsechno, re.I), re.findall(r"logiman|konfigur|vandr|dogus", vsechno, re.I)[:3])
    dealerska = {"T-SPOJKA": "80.00", "T-PROFIL": "700.00", "T-DESKA": "450.00", "T-AKCE": "150.00", "T-ZAOKR": "30.00"}
    over("F2 dealerska cena bez prirazky se u cesty 'dealer' s prirazkou 25 % nikde neobjevi (zadny sloupec ani atribut nese 80,00 / 700,00 / 450,00 / 150,00 / 30,00 jako cenu)",
         all(p[s]["price_net_czk"] != cena and p[s]["price_gross_czk"] != cena for s, cena in dealerska.items()) and not any(f'net="{c}"' in rx.get_data(as_text=True) for c in dealerska.values()), None)
    over("F3 sloupce jsou jen povolene: zadne naklady, dodavatel, sklad, glb/fbx, interni poznamky, stav sestavy, dealerska sleva ani sazba provize", set(hlava) == set(df.CSV_COLUMNS) and not re.search(r"cost|supplier|dodavatel|glb|fbx|stock_qty|margin|discount|commission|note", ",".join(hlava) + rx.get_data(as_text=True)[:20000], re.I), hlava)
    over("F4 feed nic nezapisuje (jen last_used klice): zadne objednavky, e-maily ani audit; nic se neodesila (modul nema send_email/smtp/INSERT/UPDATE/DELETE)",
         not re.search(r"send_email|smtp|INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM", open(df.__file__, encoding="utf-8").read(), re.I), None)

    # mutace
    zdroj = open(df.__file__, encoding="utf-8").read()

    def mutant(funkce, stare, nove):
        t = ast.parse(zdroj)
        node = next(n for n in t.body if isinstance(n, ast.FunctionDef) and n.name == funkce)
        src = ast.get_source_segment(zdroj, node)
        assert src.count(stare) == 1, f"{funkce}: '{stare}' nalezeno {src.count(stare)}x"
        ns = dict(vars(df))
        exec(src.replace(stare, nove), ns)
        return ns[funkce]

    with real.cursor() as cur:
        dealer_a = jedno("SELECT * FROM dealers WHERE id=%s", (A["id"],))
        spravne = df.build_rows(cur, dealer_a, 25.0, BASE)
        m1 = mutant("build_rows", 'mode = "dealer_final" if dealer["order_path"] == "dealer" else "retail"', 'mode = "retail"')
        chybne = m1(cur, dealer_a, 25.0, BASE)
        cena_s = {r_["sku"]: r_["price_net_czk"] for r_ in spravne}["T-SPOJKA"]
        cena_m = {r_["sku"]: r_["price_net_czk"] for r_ in chybne}["T-SPOJKA"]
        over("M1 mutace: bez dealerskeho rezimu (verejna cena misto dealerska x prirazka) by profil mel 1000,00 misto 875,00 (testy C4 a F2 ji zachyti)",
             {r_["sku"]: r_["price_net_czk"] for r_ in spravne}["T-PROFIL"] == "875.00" and {r_["sku"]: r_["price_net_czk"] for r_ in chybne}["T-PROFIL"] == "1000.00", (cena_s, cena_m))
        m2 = mutant("build_rows", "if dealers._brand_hit(*[str(x) for x in row.values()]):", "if False:")
        pred_view = dealers.dealer_product_view
        dealers.dealer_product_view = lambda cur_, pid, **k: (lambda v: {**v, "images": [{"path": "/content-files/gallery/logiman-x.jpg"}]} if v else v)(pred_view(cur_, pid, **k))
        try:
            vyslo = df.build_rows(cur, dealer_a, 25.0, BASE)
            vyslo_m2 = m2(cur, dealer_a, 25.0, BASE)
        finally:
            dealers.dealer_product_view = pred_view
        over("M3 finalni kontrola je druha vrstva: kdyby view propustil adresu obrazku se znackou, radek se vynecha (build_rows vraci 0 radku), mutant bez kontroly je propusti vsechny", len(vyslo) == 0 and len(vyslo_m2) == len(spravne), (len(vyslo), len(vyslo_m2), len(spravne)))
        m4 = mutant("_csv_cell", 'if key in ("name", "description", "sku", "category") and _CSV_FORMULA_RE.match(s):', "if False:")
        over("M4 mutace: bez ochrany by se nazev '=SUM(...)' zapsal do CSV beze zmeny (test D4 ji zachyti)", df._csv_cell("name", "=SUM(1)") == "'=SUM(1)" and m4("name", "=SUM(1)") == "=SUM(1)", None)
finally:
    with real.cursor() as cur:
        for t in TEMP_LIKE + TEMP_COPY + tuple(f"_tpl_{x}" for x in TEMP_LIKE + TEMP_COPY):
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `{t}`")
    real.commit()

po = stav_ostrych()
over("ostre tabulky (dealeri, klice, sazby, produkty, obrazky, kategorie, nastaveni, objednavky, e-maily, audit) jsou po testu beze zmeny", po == PRED_OSTRE, (PRED_OSTRE, po))
ok = sum(vysl)
print(f"\nVYSLEDEK dealersky program krok 5 - feed produktu: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
