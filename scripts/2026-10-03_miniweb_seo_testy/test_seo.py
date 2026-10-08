#!/usr/bin/env python3
"""Test server-side SEO mini-shopu (api/miniweb_seo.py, bot16 2026-10-03). Kandidatni modul se importuje RUCNE (app.py ho zatim nenacita), data katalogu
jsou podstrcena v pameti (_api), DB se jen cte (hledani storefrontu podle hostu v zalozni vetvi). Nic se nezapisuje.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator \\
  api/venv/bin/python3 scripts/2026-10-03_miniweb_seo_testy/test_seo.py"""
import json, os, re, sys, threading
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(REPO)
if not os.environ.get("DB_HOST"):
    print("CHYBA: chybi DB_* v prostredi"); sys.exit(2)
_orig = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _orig(self, *a, **k)
sys.path.insert(0, os.path.join(REPO, "api"))
try:
    import app as appmod
    import miniweb_seo as S
finally:
    threading.Thread.start = _orig

HOST = "baliace-stoly.top"
CFG = {"shop": "packstations-sk", "lang": "sk", "locale": "sk-SK", "currency": "EUR", "price_mode": "hidden", "preview": False, "alternates": [{"lang": "en", "href": "https://packing-tables.top/"}]}
CATS = {"categories": [{"id": 1, "parent_id": None, "slug": "stoly", "name": "Stoly", "count": 2}, {"id": 2, "parent_id": 1, "slug": "baliace", "name": "Baliace stoly", "count": 1}]}
PRODS = {"products": [
    {"id": 4934, "slug": "baliaci-stol-na-mieru", "sku": "PS-1", "category_id": 2, "name": "Baliaci stôl na mieru", "summary": "Baliaci stôl z hliníkových profilov, rozmery podľa vás.", "description": "Prvý odstavec.\nDruhý odstavec.",
     "price_from": 1290, "currency": "EUR", "delivery": "3–5 týždňov, rozložený", "configurator": {"available": True}, "specs": [{"name": "Šírka", "value": "500–3000 mm"}]},
    {"id": 7, "slug": "xss", "sku": None, "category_id": 1, "name": "Stôl <script>alert(1)</script>", "summary": "Test </script><b>x</b>", "description": "", "price_from": None, "currency": "EUR", "delivery": "", "configurator": {"available": False}, "specs": []}]}
LEGAL = {"documents": [{"kind": "terms", "title": "Obchodné podmienky", "body": "Text podmienok.\nDruhý riadok.", "updated": "2026-10-01"}]}
state = {"cfg": dict(CFG), "status": 200}


def fake(path, host):
    if host != HOST:
        return 404, None
    if path == "/api/miniweb/config":
        return (state["status"], state["cfg"] if state["status"] == 200 else None)
    if path.startswith("/api/miniweb/products"):                          # stránkování jako skutečné API (limit/offset, total)
        import urllib.parse as up
        q = up.parse_qs(up.urlparse(path).query); lim = int(q.get("limit", ["100"])[0]); off = int(q.get("offset", ["0"])[0])
        allp = PRODS["products"] + [dict(PRODS["products"][1], id=1000 + i, slug="hromadny-%d" % i, name="Hromadný %d" % i) for i in range(230)]
        return 200, {"products": allp[off:off + lim], "total": len(allp)}
    return 200, {"/api/miniweb/categories": CATS, "/api/miniweb/legal": LEGAL}[path]


S._api = fake
client = appmod.app.test_client()
bad = total = 0


def ok(cond, text):
    global bad, total
    total += 1
    bad += 0 if cond else 1
    print("[%s] %s" % ("OK   " if cond else "CHYBA", text))


def get(path, host=HOST):
    r = client.get("/api/miniweb/seo" + path, base_url="https://" + host)
    return r.status_code, r.get_data(as_text=True), r


def tag(html, pat):
    m = re.search(pat, html)
    return m.group(1) if m else None


FORBID = re.compile(r"logiman|konfigur[aá]tor|vandr|dogus|packstation|ponk|@[a-z0-9-]+\.[a-z]{2,}", re.I)
sc, h, r = get("/")
ok(sc == 200 and tag(h, r'<html lang="([^"]+)"') == "sk", "S1 domov: 200, <html lang=sk>")
ok(tag(h, r"<title>(.*?)</title>") == "Baliace a pracovné stoly – Navrhnite si vlastný baliaci stôl", "S2 title z šablony bot7 (≤ 70 znaků)")
ok("Ceny bez DPH" in (tag(h, r'<meta name="description" content="([^"]*)"') or ""), "S3 meta description z šablony")
ok('<link rel="canonical" href="https://baliace-stoly.top/">' in h and tag(h, r'<meta name="robots" content="([^"]*)"') == "index, follow", "S4 canonical + robots index, follow u live shopu")
ok('hreflang="sk" href="https://baliace-stoly.top/"' in h and 'hreflang="en" href="https://packing-tables.top/"' in h and 'hreflang="x-default" href="https://packing-tables.top/"' in h, "S5 hreflang sk + en + x-default (alternativa live)")
ok('og:type" content="website"' in h and 'twitter:card" content="summary"' in h and "og:image" not in h and "twitter:image" not in h, "S6 og/twitter bez obrázku, og:type website")
ld = [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S)]
FAQ_N = len({k.split(".")[1] for k in json.load(open(os.path.join(REPO, "webapp", "miniweb", "i18n", "sk.json"), encoding="utf-8")) if re.match(r"^faq\.\d+\.q$", k)})          # pocet otazek z i18n (bot7 FAQ doplnuje), ne pevne cislo
ok([x["@type"] for x in ld] == ["WebSite", "Organization", "FAQPage"] and len(ld[2]["mainEntity"]) == FAQ_N >= 8, "S7 JSON-LD WebSite + Organization + FAQPage (%d otázek podle i18n)" % FAQ_N)
ok("<h1>Baliace a pracovné stoly na mieru</h1>" in h and "<details>" in h, "S8 statický H1 + FAQ v HTML")
_t = re.sub(r"<script.*?</script>|<link[^>]*>", "", h, flags=re.S)
_m = FORBID.search(_t)
ok(not _m, "S9 v textu domovské stránky žádná zakázaná slova ani e-mail" + ("" if not _m else " | " + repr(_t[max(0, _m.start() - 50):_m.end() + 30])))
ok("window.MW_BOOT=" in h and '"pretty": true' in h, "S10 MW_BOOT s hezkými adresami")
sc2, h2, _ = get("/?shop=x&lang=en&drafts=1&demo=1")
ok('rel="canonical" href="https://baliace-stoly.top/"' in h2, "S11 canonical bez ?shop/?lang/?drafts/?demo")

sc, h, r = get("/produkt/baliaci-stol-na-mieru")
ok(sc == 200 and tag(h, r"<title>(.*?)</title>") == "Baliaci stôl na mieru" and "Baliaci stôl z hliníkových profilov" in tag(h, r'<meta name="description" content="([^"]*)"'), "P1 produkt: title = název, description = summary")
ok('rel="canonical" href="https://baliace-stoly.top/produkt/baliaci-stol-na-mieru"' in h and 'og:type" content="product"' in h, "P2 canonical /produkt/<slug>, og:type product")
ld = [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S)]
pr = ld[0]
ok(pr["@type"] == "Product" and pr["sku"] == "PS-1" and pr["category"] == "Baliace stoly" and "offers" not in pr and "image" not in pr, "P3 JSON-LD Product (sku, category), bez cen při skrytých cenách a bez obrázku")
ok([i["name"] for i in ld[1]["itemListElement"]] == ["Domov", "Baliace stoly", "Baliaci stôl na mieru"], "P4 BreadcrumbList Domov › kategorie › produkt")
ok('"id": 4934' in h and "<table>" in h and "Prvý odstavec." in h, "P5 MW_BOOT.id + statický popis a parametry")
state["cfg"] = dict(CFG, price_mode="shown")
sc, h, _ = get("/produkt/baliaci-stol-na-mieru")
pr = json.loads(re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S)[0])
ok(pr.get("offers", {}).get("lowPrice") == "1290" and pr["offers"]["priceSpecification"]["valueAddedTaxIncluded"] is False, "P6 při zobrazených cenách AggregateOffer bez DPH")
state["cfg"] = dict(CFG)
sc, h, _ = get("/produkt/xss")
ok("<script>alert(1)</script>" not in h and "&lt;script&gt;alert(1)&lt;/script&gt;" in h and "</script><b>" not in h, "P7 XSS: název i summary escapované v HTML i v JSON-LD")
PRODS["products"][0]["slug_alt"] = ["configurable-packing-station-and-workbench"]
CATS["categories"][1]["slug_alt"] = ["packing-tables-and-workbenches"]
sc, h, r = get("/produkt/configurable-packing-station-and-workbench")
ok(sc == 301 and r.headers["Location"] == "https://baliace-stoly.top/produkt/baliaci-stol-na-mieru", "A1 starý (základní) slug produktu → 301 na slovenský slug: %s %s" % (sc, r.headers.get("Location")))
sc, h, r = get("/kategoria/packing-tables-and-workbenches")
ok(sc == 301 and r.headers["Location"] == "https://baliace-stoly.top/kategoria/baliace", "A2 starý slug kategorie → 301 na slovenský slug")
sc, h, r = get("/produkt/hromadny-229")
ok(sc == 200 and "Hromadný 229" in h, "N1 produkt za první stovkou/dvěma stovkami (č. 232 z 232) má hezkou adresu")
sc, t, r = get("/sitemap.xml")
ok("/produkt/hromadny-229" in t and t.count("<loc>") >= 232, "N2 sitemap obsahuje všechny produkty (stránkování), ne jen první stránku: %d adres" % t.count("<loc>"))
sc, h, r = get("/produkt/neexistuje")
ok(sc == 404 and "noindex" in tag(h, r'<meta name="robots" content="([^"]*)"') and r.headers.get("X-Robots-Tag", "").startswith("noindex"), "P8 neznámý produkt: 404 + noindex")

sc, h, _ = get("/kategoria/baliace")
ok(sc == 200 and "Baliace stoly – Baliace a pracovné stoly" in h and "/produkt/baliaci-stol-na-mieru" in h and '"@type": "BreadcrumbList"' in h, "K1 kategorie: title, odkazy na produkty, drobečky")
sc, h, _ = get("/obchod")
ok(sc == 200 and "/produkt/xss" in h and 'rel="canonical" href="https://baliace-stoly.top/obchod"' in h, "K2 přehled obchodu /obchod")
sc, h, _ = get("/kontakt")
ok(sc == 200 and tag(h, r"<title>(.*?)</title>") == "Kontakt – Baliace a pracovné stoly" and "WebPage" in h, "C1 kontakt: title z šablony + WebPage")
sc, h, _ = get("/pravne-informacie")
ok(sc == 200 and "Obchodné podmienky" in h and "Text podmienok." in h, "C2 právní informace: schválené dokumenty staticky")
sc, h, r = get("/kosik")
ok(sc == 200 and tag(h, r'<meta name="robots" content="([^"]*)"') == "noindex, nofollow" and r.headers.get("X-Robots-Tag", "").startswith("noindex") and "ld+json" not in h, "C3 košík: noindex (meta i hlavička), bez JSON-LD")

state["cfg"] = dict(CFG, preview=True)
sc, h, r = get("/")
ok(tag(h, r'<meta name="robots" content="([^"]*)"') == "noindex, nofollow" and "hreflang" not in h, "D1 náhled (shop není live): noindex, bez hreflang")
state["cfg"] = dict(CFG)
state["status"] = 404
sc, h, r = get("/produkt/baliaci-stol-na-mieru")
ok(sc == 200 and 'content="noindex, nofollow"' in h and "rel=\"canonical\"" not in h and '"slug": "baliaci-stol-na-mieru"' in h and r.headers.get("X-Robots-Tag", "").startswith("noindex"), "D2 koncept (anonym ho nevidí): shell s noindex + MW_BOOT.slug pro JS, bez meta")
sc, h, _ = get("/", host="neznamy.example")
ok(sc == 404, "D3 neznámý host: 404")
sc, t, _ = get("/robots.txt")
ok(sc == 200 and t.strip() == "User-agent: *\nDisallow: /", "D4 robots.txt draftu: Disallow /")
sc, t, _ = get("/sitemap.xml")
ok(sc == 404, "D5 sitemap draftu: 404")
state["status"] = 200
sc, t, _ = get("/robots.txt")
ok(sc == 200 and "Sitemap: https://baliace-stoly.top/sitemap.xml" in t and "Disallow: /kosik" in t and "Disallow: /miniweb" not in t.replace("/miniweb/cart.html", "") and "Disallow: /api" not in t, "R1 robots.txt live: sitemap, košík zakázaný, /miniweb/ a /api/miniweb/ neblokované")
sc, t, r = get("/sitemap.xml")
locs = re.findall(r"<loc>(.*?)</loc>", t)
ok(sc == 200 and "application/xml" in r.content_type and "https://baliace-stoly.top/" in locs and "https://baliace-stoly.top/produkt/baliaci-stol-na-mieru" in locs and "https://baliace-stoly.top/kategoria/baliace" in locs
   and "https://baliace-stoly.top/kontakt" in locs and not any("kosik" in x or "?" in x for x in locs) and "priority" not in t and "lastmod" not in t, "R2 sitemap.xml: home, kategorie, produkty, kontakt, právní; bez košíku a parametrů")
print("\n==> %d/%d kontrol OK" % (total - bad, total))
sys.exit(1 if bad else 0)
