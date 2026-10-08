#!/usr/bin/env python3
"""Mini-shop: nova kategorie + produkt SYSTEM 40 (karta 4954) - jak to bude vypadat PO SCHVALENI textu Robertem, bez zasahu do provozu (bot16, 2026-10-04).
Importovane DRAFT texty (miniweb_import.py) se na jednom spojeni v DOCASNYCH kopiich tabulek miniweb_* oznaci jako approved a nad skutecnym kodem
(api/miniweb.py verejne API, api/miniweb_seo.py server-side HTML) se zkontroluje, co by zakaznik videl. Ostre tabulky se jen CTOU (druhym spojenim) a na konci se porovna,
ze se nezmenily (texty zustaly draft). Server-side HTML a API se volaji pres Flask test_client s Host baliace-stoly.top (SK shop).
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator \
  api/venv/bin/python3 scripts/2026-10-04_miniweb_system40_testy/test_system40_mini.py"""
import json, os, re, sys, threading
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(REPO)
if not os.environ.get("DB_HOST"):
    print("CHYBA: chybi DB_* v prostredi"); sys.exit(2)
_orig = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _orig(self, *a, **k)
sys.path.insert(0, os.path.join(REPO, "api"))
try:
    import pymysql
    import app as appmod
    import miniweb  # noqa: F401  (registruje /api/miniweb/*)
    import miniweb_seo  # noqa: F401  (registruje /api/miniweb/seo/*)
finally:
    threading.Thread.start = _orig

HOST = "baliace-stoly.top"
TABULKY = ("miniweb_categories", "miniweb_category_texts", "miniweb_products", "miniweb_product_texts")
bad = total = 0


def ok(cond, text):
    global bad, total
    total += 1
    bad += 0 if cond else 1
    print("[%s] %s" % ("OK   " if cond else "CHYBA", text))


def ostre():                                     # druhe spojeni = skutecne tabulky
    c = pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"], charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)
    try:
        with c.cursor() as cur:
            out = {}
            for t in TABULKY:
                cur.execute(f"CHECKSUM TABLE `{t}`"); out[t] = list(cur.fetchone().values())[1]
            cur.execute("SELECT miniweb_product_id AS id, lang, status FROM miniweb_product_texts WHERE miniweb_product_id=2 ORDER BY lang"); out["texty2"] = [(r["lang"], r["status"]) for r in cur.fetchall()]
            return out
    finally:
        c.close()


PRED = ostre()
wrap = appmod.get_conn(); real = object.__getattribute__(wrap, "_real")


def sql(q, params=None):
    with real.cursor() as cur:
        cur.execute(q, params or ())
        return cur.fetchall()


for t in TABULKY:                                # docasne kopie na TOMTO spojeni (stejny nazev stinuje ostrou tabulku)
    sql(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`"); sql(f"INSERT INTO `_tpl_{t}` SELECT * FROM `{t}`")
    sql(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`"); sql(f"INSERT INTO `{t}` SELECT * FROM `_tpl_{t}`")
    r = sql(f"SHOW CREATE TABLE `{t}`")[0]
    assert list(r.values())[1].startswith("CREATE TEMPORARY TABLE"), t + " neni docasna - STOP"
sql("UPDATE miniweb_category_texts SET status='approved' WHERE miniweb_category_id=2")
sql("UPDATE miniweb_product_texts SET status='approved' WHERE miniweb_product_id=2")
real.commit()
client = appmod.app.test_client()


def api(path):
    for t in TABULKY:                            # pojistka pred kazdym dotazem: porad docasne
        assert list(sql(f"SHOW CREATE TABLE `{t}`")[0].values())[1].startswith("CREATE TEMPORARY TABLE"), t
    r = client.get(path, base_url="https://" + HOST)
    return r.status_code, (r.get_json(silent=True) if "json" in (r.content_type or "") else r.get_data(as_text=True))


def tag(html, pat):
    m = re.search(pat, html, re.S)
    return m.group(1) if m else None


# ---- verejne API
sc, cats = api("/api/miniweb/categories")
slugs = [c["slug"] for c in cats["categories"]]
ok(sc == 200 and slugs == ["baliace-a-pracovne-stoly", "robustny-baliaci-stol-system-40"], "A1 kategorie v SK shopu: obě, SK slug (url_slug) u nové: %s" % slugs)
sc, prods = api("/api/miniweb/products")
pl = {p["id"]: p for p in prods["products"]}
ok(sc == 200 and sorted(pl) == [1, 2] and prods.get("total") == 2, "A2 produkty: 1 (systém 30) a 2 (systém 40)")
p2 = pl.get(2) or {}
ok(p2.get("slug") == "konfigurovatelny-robustny-baliaci-stol" and p2.get("name") == "Konfigurovateľný robustný baliaci stôl" and p2.get("sku") == "PWB-002", "A3 produkt 2: SK slug, název, kód PWB-002")
ok((p2.get("configurator") or {}).get("available") is True and (p2.get("configurator") or {}).get("product_id") == 4954, "A4 produkt 2 má generátor karty 4954: %s" % json.dumps(p2.get("configurator")))
ok(p2.get("profil_mm") == 40 and p2.get("cross_section_label") == "40×40" and p2.get("groove_family") == "10", "A5 štítky profilu 40×40, drážka 10: %s / %s / %s" % (p2.get("profil_mm"), p2.get("cross_section_label"), p2.get("groove_family")))
ok(pl[1].get("profil_mm") == 30 and pl[1].get("configurator", {}).get("product_id") == 4934, "A6 produkt 1 (systém 30) beze změny")
ok(isinstance(p2.get("price_from"), (int, float)) and p2["price_from"] > pl[1]["price_from"], "A7 cena od u systému 40 je vyšší než u 30 (z generátoru karty 4954): %s vs %s EUR" % (p2.get("price_from"), pl[1].get("price_from")))
ok(not re.search(r"logiman|vandr|dogus|superlight|konfigurator\b", json.dumps(p2, ensure_ascii=False), re.I), "A8 v textu produktu 2 není značka ani dodavatelský název řady")
sc, one = api("/api/miniweb/products/2")
ok(sc == 200 and (one.get("product") or one).get("id") == 2, "A9 detail produktu 2 podle id")
sc, in_cat = api("/api/miniweb/products?category=robustny-baliaci-stol-system-40")
ok(sc == 200 and [p["id"] for p in in_cat["products"]] == [2], "A10 výpis kategorie system 40 obsahuje jen produkt 2: %s" % [p["id"] for p in in_cat.get("products", [])])

# ---- server-side HTML (SEO)
for cesta, co in (("/api/miniweb/seo/", "domov"), ("/api/miniweb/seo/kategoria/robustny-baliaci-stol-system-40", "kategorie"), ("/api/miniweb/seo/produkt/konfigurovatelny-robustny-baliaci-stol", "produkt"),
                  ("/api/miniweb/seo/produkt/konfigurovatelny-baliaci-a-pracovny-stol", "produkt 1")):
    sc, h = api(cesta)
    ok(sc == 200 and isinstance(h, str) and "<title>" in h, "S %s: 200 a vykreslený HTML" % co)
    if co == "produkt":
        ok("Robustný" in (tag(h, r"<title>(.*?)</title>") or "") or "robustný" in h, "S produkt: v titulku/obsahu je název produktu systému 40")
        ok("40 × 40" in h, "S produkt: v popisu je profil 40 × 40")
        ok("30 × 30 mm" in h and "druhý stôl je zo 30 × 30" in h, "S produkt: věta o druhém stole z profilů 30 × 30 je v popisu (odlišení od produktu 1)")
        canon = tag(h, r'<link rel="canonical" href="([^"]+)"')
        ok(canon == "https://baliace-stoly.top/produkt/konfigurovatelny-robustny-baliaci-stol", "S produkt: canonical %s" % canon)
    if co == "kategorie":
        ok("Robustný baliaci stôl system 40" in h, "S kategorie: název kategorie v HTML")
# ---- uvod domovske stranky: text podle poctu VEREJNYCH produktu (".multi" varianty od bot7), server-side HTML i JSON-LD FAQ
sc, home2 = api("/api/miniweb/seo/")
lead2 = tag(home2, r"<h1>.*?</h1><p>(.*?)</p>") or ""
ok("40 × 40 mm" in lead2 and "Z čoho je rám stola a ako sa líšia oba stoly?" in home2 and "robustnejší zo 40 × 40 mm" in home2, "H1 dva produkty: úvod, USP i FAQ mluví o obou stolech (30 × 30 i 40 × 40): " + lead2[:90])
ok('"name": "Z čoho je rám stola a ako sa líšia oba stoly?"' in home2.replace('":"', '": "') or "Z čoho je rám stola a ako sa líšia oba stoly?" in home2, "H2 JSON-LD FAQ nese dvoustolovou otázku")
sql("UPDATE miniweb_product_texts SET status='draft' WHERE miniweb_product_id=2")           # druhy produkt zatim neschvaleny = verejne jediny stul
real.commit(); miniweb_seo._CACHE.clear()
sc, home1 = api("/api/miniweb/seo/")
lead1 = tag(home1, r"<h1>.*?</h1><p>(.*?)</p>") or ""
ok(sc == 200 and "40 × 40" not in lead1 and "Z čoho je rám stola?" in home1 and "Hliníkový rám 30 × 30 mm" in home1, "H3 jediný veřejný produkt: původní text pro jeden stůl (30 × 30), bez zmínky o druhém: " + lead1[:90])
sql("UPDATE miniweb_product_texts SET status='approved' WHERE miniweb_product_id=2"); real.commit(); miniweb_seo._CACHE.clear()

sc, sm = api("/api/miniweb/seo/sitemap.xml")
ok(sc == 200 and "/kategoria/robustny-baliaci-stol-system-40" in sm and "/produkt/konfigurovatelny-robustny-baliaci-stol" in sm, "S sitemap.xml obsahuje novou kategorii i produkt")

PO = ostre()
ok(PO == PRED and PO["texty2"] == [("en", "draft"), ("sk", "draft")], "K ostré tabulky mini-shopu se testem nezměnily (CHECKSUM stejný, texty produktu 2 zůstaly draft)")
print("\n==> %d/%d kontrol OK" % (total - bad, total))
sys.exit(1 if bad else 0)
