#!/opt/konfigurator/api/venv/bin/python
"""URL slugy po jazycich (bot5, 2026-10-03): klic url_slug v importu (kategorie, produkt), sloupec url_slug v texty tabulkach, API vraci slug v jazyce shopu + slug_alt, ?category= prijme oba, unikatnost v jazyce,
schvaleni spolu s textem (otisk). Kandidati: MINIWEB_PY, MINIWEB_ADMIN_PY (jinak zive soubory s patchem slug_*.py.patch ze sady, nebo uz patchnute zive). Sloupec url_slug se prida jen do DOCASNYCH tabulek.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-03_miniweb_objednavky_testy/test_miniweb_slugy.py"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
API = os.path.join(REPO, "api")
KIT = os.path.join(HERE, "nasazeni")
tmp = tempfile.mkdtemp(prefix="kand_mw_slug_")
os.makedirs(os.path.join(tmp, "api"))
for f, env, marker in (("miniweb.py", "MINIWEB_PY", "slug_alt"), ("miniweb_admin.py", "MINIWEB_ADMIN_PY", "_check_url_slugs")):
    if os.environ.get(env):
        shutil.copy(os.environ[env], os.path.join(tmp, f))
    else:
        shutil.copy(os.path.join(API, f), os.path.join(tmp, "api", f))
        if marker not in open(os.path.join(API, f), encoding="utf-8").read():
            subprocess.run(["patch", "-p1", "-s", "-d", tmp, "-i", os.path.join(KIT, "slug_" + f + ".patch")], check=True)
        shutil.copy(os.path.join(tmp, "api", f), os.path.join(tmp, f))
sys.path.insert(0, API)
sys.path.insert(0, tmp)

import pymysql  # noqa: E402
import app as appmod  # noqa: E402
import miniweb as mw  # noqa: E402
import miniweb_admin as mwa  # noqa: E402

assert "_check_url_slugs" in open(mwa.__file__, encoding="utf-8").read() and "slug_alt" in open(mw.__file__, encoding="utf-8").read(), "testuji se nasazene soubory, ne kandidati"
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:500]))


def ostre():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                           port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


TEMP = ("car_storefronts", "storefront_hosts", "miniweb_shops", "miniweb_categories", "miniweb_category_texts", "miniweb_products", "miniweb_product_texts", "miniweb_documents")


def stav():
    c = ostre()
    try:
        with c.cursor() as cur:
            out = {}
            for t in TEMP:
                cur.execute(f"SELECT COUNT(*) AS n FROM `{t}`")
                out[t] = cur.fetchone()["n"]
            for t in ("miniweb_category_texts", "miniweb_product_texts"):
                cur.execute("SELECT COUNT(*) AS n FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME='url_slug'", (t,))
                out["col_" + t] = cur.fetchone()["n"]
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
        for t in TEMP:
            cur.execute(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`")
            cur.execute(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")
            cur.execute(f"SHOW CREATE TABLE `{t}`")
            assert list(cur.fetchone().values())[1].startswith("CREATE TEMPORARY TABLE"), f"ABORT: {t} neni docasna"
        for t in ("miniweb_category_texts", "miniweb_product_texts"):
            cur.execute("SELECT COUNT(*) AS n FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME='url_slug'", (t,))
            if not list(cur.fetchone().values())[0]:                       # pred migraci: sloupec a index jen v DOCASNE tabulce
                cur.execute(f"ALTER TABLE `{t}` ADD COLUMN `url_slug` VARCHAR(100) DEFAULT NULL, ADD UNIQUE KEY `uq_lang_url_slug` (`lang`, `url_slug`)")
    real.commit()
    mwa._COL_CACHE.clear()

    sql("INSERT INTO car_storefronts (name, slug, primary_domain, status, lang) VALUES ('SK','packstations-sk','sk.example.top','live','sk'),('EN','packstations-en','en.example.top','live','en')")
    for sid in [r["id"] for r in sql("SELECT id FROM car_storefronts")]:
        sql("INSERT INTO miniweb_shops (storefront_id, family, price_mode, currency, countries, inquiry_enabled) VALUES (%s,'packstations','hidden','EUR','SK',1)", (sid,))

    def zaklad(lang, **extra):
        return {"version": 1, "family": "packstations", "lang": lang, **extra}

    CAT = {"slug": "packing-tables", "sort": 1}
    PROD = {"slug": "configurable-table", "sku": "PWB-001", "category": "packing-tables", "sort": 1, "configurator": {"available": False}}

    def katalog(lang, cat_extra=None, prod_extra=None, cname="Stoly", pname="Stôl", **zk):
        return zaklad(lang, categories=[{**CAT, "name": cname, **(cat_extra or {})}], products=[{**PROD, "name": pname, "summary": "S", "description": "D", "delivery": "3 týždne", **(prod_extra or {})}], **zk)

    def imp(data, apply=True, revise=False):
        conn = appmod.get_conn()
        cur = conn.cursor()
        rep = mwa.import_catalog(cur, data, apply=apply, revise_approved=revise)
        conn.commit()
        return rep

    def n(t):
        return jedno(f"SELECT COUNT(*) AS n FROM `{t}`")["n"]

    # --- import: platne url_slug
    r_en = imp(katalog("en", cname="Tables", pname="Table"))
    r_sk = imp(katalog("sk", {"url_slug": "baliace-a-pracovne-stoly"}, {"url_slug": "konfigurovatelny-baliaci-stol"}))
    over("I1 import SK s url_slug: bez chyb, kategorie i produkt ulozeny, EN beze slugu zustava (NULL)", not r_en["errors"] and not r_sk["errors"] and r_sk["texts"]["created"] == 2
         and jedno("SELECT url_slug FROM miniweb_category_texts WHERE lang='sk'")["url_slug"] == "baliace-a-pracovne-stoly" and jedno("SELECT url_slug FROM miniweb_product_texts WHERE lang='sk'")["url_slug"] == "konfigurovatelny-baliaci-stol"
         and jedno("SELECT url_slug FROM miniweb_category_texts WHERE lang='en'")["url_slug"] is None, (r_en["errors"], r_sk["errors"]))
    sql("UPDATE miniweb_category_texts SET status='approved'")
    sql("UPDATE miniweb_product_texts SET status='approved'")

    def get(host, cesta):
        appmod._rate_limit_buckets.clear()
        return appmod.app.test_client().get(cesta, base_url="https://" + host)

    cats_sk = get("sk.example.top", "/api/miniweb/categories").get_json()["categories"]
    cats_en = get("en.example.top", "/api/miniweb/categories").get_json()["categories"]
    over("A1 API kategorie: slovensky shop vraci slug v jazyce a slug_alt = [zakladni slug], anglicky zakladni slug a prazdne slug_alt", cats_sk[0]["slug"] == "baliace-a-pracovne-stoly" and cats_sk[0]["slug_alt"] == ["packing-tables"]
         and cats_en[0]["slug"] == "packing-tables" and cats_en[0]["slug_alt"] == [], (cats_sk, cats_en))
    p_sk = get("sk.example.top", "/api/miniweb/products").get_json()["products"][0]
    p_en = get("en.example.top", "/api/miniweb/products").get_json()["products"][0]
    over("A2 API produkt: slovensky slug v jazyce + slug_alt, anglicky zakladni; /products/<id> to samo", p_sk["slug"] == "konfigurovatelny-baliaci-stol" and p_sk["slug_alt"] == ["configurable-table"] and p_en["slug"] == "configurable-table"
         and p_en["slug_alt"] == [] and get("sk.example.top", f"/api/miniweb/products/{p_sk['id']}").get_json()["product"]["slug"] == "konfigurovatelny-baliaci-stol", (p_sk, p_en))
    f1 = get("sk.example.top", "/api/miniweb/products?category=baliace-a-pracovne-stoly").get_json()["total"]
    f2 = get("sk.example.top", "/api/miniweb/products?category=packing-tables").get_json()["total"]
    f3 = get("sk.example.top", "/api/miniweb/products?category=neexistuje").get_json()["total"]
    f4 = get("en.example.top", "/api/miniweb/products?category=packing-tables").get_json()["total"]
    f5 = get("en.example.top", "/api/miniweb/products?category=baliace-a-pracovne-stoly").get_json()["total"]
    over("A3 filtr ?category= prijme nove i zakladni slug (SK oba = 1 produkt), neznamy slug 0, EN zakladni 1, SK slug v EN shopu nic (slug patri jazyku)", (f1, f2, f3, f4, f5) == (1, 1, 0, 1, 0), (f1, f2, f3, f4, f5))

    ps1 = get("sk.example.top", "/api/miniweb/products?slug=konfigurovatelny-baliaci-stol").get_json()
    ps2 = get("sk.example.top", "/api/miniweb/products?slug=configurable-table").get_json()
    ps3 = get("sk.example.top", "/api/miniweb/products?slug=neexistuje").get_json()
    ps4 = get("en.example.top", "/api/miniweb/products?slug=konfigurovatelny-baliaci-stol").get_json()
    over("A4 detail podle slugu (?slug=): jazykovy i zakladni slug najdou produkt, neznamy 0, slug jineho jazyka v EN shopu nic (nezavisle na limitu seznamu; externi revize #10)",
         (ps1["total"], ps2["total"], ps3["total"], ps4["total"]) == (1, 1, 0, 0) and ps1["products"][0]["slug"] == "konfigurovatelny-baliaci-stol", (ps1["total"], ps2["total"], ps3["total"], ps4["total"]))

    # --- nevalidni a nebezpecne
    zlo = {"velka pismena": "Baliace-Stoly", "mezera": "a b", "azbuka": "stôl", "znacka": "logiman-stoly", "prilis dlouhy": "a" * 101, "cislo": 5, "uvozovka": "a'b"}
    n0 = (n("miniweb_category_texts"), n("miniweb_product_texts"))
    odp = {k: imp(katalog("sk", {"url_slug": v})) for k, v in zlo.items()}
    over("I2 neplatny url_slug (velka pismena, mezera, diakritika, znacka, prilis dlouhy, ne-retezec, uvozovka) = chyba, nic se nezapise", all(r["errors"] for r in odp.values()) and (n("miniweb_category_texts"), n("miniweb_product_texts")) == n0,
         {k: r["errors"] for k, r in odp.items() if not r["errors"]})
    r_unk = imp({**katalog("sk"), "categories": [{**CAT, "name": "X", "slug_url": "abc"}]})
    over("I2b preklep v klici (slug_url) odmitne cely soubor (striktni parser)", bool(r_unk["errors"]), r_unk["errors"])

    # --- kolize
    r1 = imp(katalog("sk", {"url_slug": "konfigurovatelny-baliaci-stol"}, {"url_slug": "konfigurovatelny-baliaci-stol"}), apply=False)
    two = imp(zaklad("sk", categories=[{**CAT, "name": "A", "url_slug": "stoly"}, {"slug": "druha", "name": "B", "url_slug": "stoly"}], products=[]), apply=False)
    sql("INSERT INTO miniweb_categories (family, slug, sort_order) VALUES ('packstations','druha',2)")
    cid2 = jedno("SELECT id FROM miniweb_categories WHERE slug='druha'")["id"]
    sql("INSERT INTO miniweb_category_texts (miniweb_category_id, lang, name, status) VALUES (%s,'sk','Druha','draft')", (cid2,))
    clash = imp(zaklad("sk", categories=[{**CAT, "name": "A", "url_slug": "druha"}], products=[]), apply=False)
    other_lang = imp(zaklad("en", categories=[{**CAT, "name": "Tables", "url_slug": "baliace-a-pracovne-stoly"}], products=[{"slug": "x", "sku": "X-1", "category": "packing-tables", "configurator": {"available": False}, "name": "X"}]), apply=False)
    over("I3 unikatnost v jazyce: dve polozky se stejnym url_slug v souboru = chyba, url_slug shodny se zakladnim slugem JINE polozky tez, stejny slug v jinem jazyce je v poradku",
         not r1["errors"] and bool(two["errors"]) and bool(clash["errors"]) and not other_lang["errors"], (r1["errors"], two["errors"], clash["errors"], other_lang["errors"]))
    sql("DELETE FROM miniweb_category_texts WHERE miniweb_category_id=%s", (cid2,))
    sql("DELETE FROM miniweb_categories WHERE id=%s", (cid2,))
    try:
        radek = jedno("SELECT miniweb_category_id, lang, name, status, url_slug FROM miniweb_category_texts WHERE lang='sk'")
        sql("INSERT INTO miniweb_category_texts (miniweb_category_id, lang, name, status, url_slug) VALUES (%s,%s,%s,%s,%s)", (radek["miniweb_category_id"] + 100, radek["lang"], radek["name"], radek["status"], radek["url_slug"]))
        dup_ok = True
    except pymysql.err.IntegrityError:
        dup_ok = False
    over("I3b databaze samotna drzi unikatnost (lang + url_slug) - duplicitni zapis mimo kontrolu importu selze", dup_ok is False, dup_ok)

    # --- schvaleni spolu s textem
    r_zmena = imp(katalog("sk", {"url_slug": "baliace-stoly"}, {"url_slug": "konfigurovatelny-baliaci-stol"}))
    over("S1 zmena url_slug u SCHVALENEHO textu bez revise: NEPREPSANO (skipped_approved), v DB puvodni slug", r_zmena["texts"]["skipped_approved"] == 1 and jedno("SELECT url_slug FROM miniweb_category_texts WHERE lang='sk'")["url_slug"] == "baliace-a-pracovne-stoly", r_zmena["texts"])
    rev_pred = [i for i in mwa.build_overview(appmod.get_conn().cursor(), "sk")["items"] if i["kind"] == "category"][0]["rev"]
    r_rev = imp(katalog("sk", {"url_slug": "baliace-stoly"}, {"url_slug": "konfigurovatelny-baliaci-stol"}), revise=True)
    it = [i for i in mwa.build_overview(appmod.get_conn().cursor(), "sk")["items"] if i["kind"] == "category"][0]
    over("S2 s revise: slug zmenen a text zpet v DRAFTU (verejne zmizi do dalsiho schvaleni), otisk se zmenil (slug je soucasti schvalovaneho obsahu), item nese url_slug", r_rev["texts"]["revised"] == 1 and it["status"] == "draft"
         and it["url_slug"] == "baliace-stoly" and it["rev"] != rev_pred and len(get("sk.example.top", "/api/miniweb/categories").get_json()["categories"]) == 0, (r_rev["texts"], it["status"], it.get("url_slug")))
    conn = appmod.get_conn()
    cur = conn.cursor()
    stary = mwa.apply_status_change(cur, 1, [{"kind": "category", "id": it["id"], "lang": "sk", "rev": rev_pred}], True)
    conn.rollback()
    nove = mwa.apply_status_change(cur, 1, [{"kind": "category", "id": it["id"], "lang": "sk", "rev": it["rev"]}], True)
    conn.commit()
    over("S3 schvaleni se starym otiskem (pred zmenou slugu) = changed, nic se neschvali; s novym otiskem projde a SK kategorie je verejna se slugem baliace-stoly", stary[0] == 0 and stary[1][0]["reason"] == "changed" and nove[0] == 1
         and get("sk.example.top", "/api/miniweb/categories").get_json()["categories"][0]["slug"] == "baliace-stoly", (stary, nove))

    # --- otisky bez slugu beze zmeny, bezpecnost API
    blob = json.dumps(["N", "S", "D", "T", []], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    over("R1 otisk textu BEZ url_slug je stejny jako pred zavedenim slugu (stavajici schvaleni zustavaji platna)", mwa.text_rev("N", "S", "D", "T", []) == hashlib.sha1(blob.encode()).hexdigest()[:16] and mwa.text_rev("N", "S", "D", "T", [], "x") != mwa.text_rev("N", "S", "D", "T", []), None)
    sql("UPDATE miniweb_product_texts SET url_slug='Logiman-x' WHERE lang='sk'")
    p_bad = get("sk.example.top", "/api/miniweb/products").get_json()["products"]
    sql("UPDATE miniweb_product_texts SET url_slug='logiman-stol' WHERE lang='sk'")
    p_brand = get("sk.example.top", "/api/miniweb/products").get_json()["products"]
    over("R2 poskozeny nebo znackovy url_slug v DB se verejne NEVYDA (API spadne na zakladni slug, produkt zustane viditelny)", p_bad and p_bad[0]["slug"] == "configurable-table" and p_brand and p_brand[0]["slug"] == "configurable-table", (p_bad, p_brand))
    mwa._COL_CACHE.clear()
    orig = mwa.has_url_slug_column
    mwa.has_url_slug_column = lambda cur_, table: False
    try:
        r_nocol = imp(katalog("sk", {"url_slug": "x-y"}), apply=False)
        r_nourl = imp(katalog("sk"), apply=False)
    finally:
        mwa.has_url_slug_column = orig
    over("R3 bez sloupce v DB (pred migraci): import s url_slug = srozumitelna chyba o migraci, import BEZ url_slug funguje jako driv", any("migrace" in e for e in r_nocol["errors"]) and not r_nourl["errors"], (r_nocol["errors"], r_nourl["errors"]))
finally:
    with real.cursor() as cur:
        for t in TEMP:
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `{t}`")
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `_tpl_{t}`")
    real.commit()
over("ostre tabulky a sloupce beze zmeny (sloupec url_slug se pridal jen do docasnych kopii)", stav() == PRED, (PRED, stav()))
ok = sum(vysl)
print(f"\nVYSLEDEK URL slugy po jazycich: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
