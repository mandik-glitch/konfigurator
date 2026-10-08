#!/usr/bin/env python3
"""Mini-shop: server-side SEO pro DALSI JAZYKY (en, de, hu, ...) - bot16, 2026-10-07 (Robert: EN 1:1 se SK, kopie v nemcine a madarstine).
Obdoba scripts/2026-10-03_miniweb_seo_testy/test_seo.py (ta je pevne slovenska), ale JAZYKOVE OBECNA: pro kazdy jazyk z JAZYKY (vychozi en,de,hu) vezme skutecne soubory
(`webapp/miniweb/i18n/<jazyk>.json`, sekce `<jazyk>` v `api/miniweb_seo_sablony.json`), a kdyz jeste neexistuji, podstrci SYNTETICKE (kopie slovenskych) - tak se overuje KOD
(cesty PATHS, odkazy, kanonicke adresy, hreflang, 301 ze starych slugu, sitemap, robots) uz pred dodanim textu. Skutecne soubory se pozna podle vypisu "(skutecne)" / "(syntetické)".
Katalog je podstrcen v pameti (`_api`), DB se jen cte (hledani storefrontu podle hostu), nic se nezapisuje.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator \\
  api/venv/bin/python3 scripts/2026-10-07_miniweb_jazyky_testy/test_seo_jazyky.py        (JAZYKY=de,hu pro vybrane)"""
import copy, json, os, re, sys, threading
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

JAZYKY = [x for x in os.environ.get("JAZYKY", "en,de,hu").split(",") if x]
I18N_DIR = os.path.join(REPO, "webapp", "miniweb", "i18n")
SK_I18N = json.load(open(os.path.join(I18N_DIR, "sk.json"), encoding="utf-8"))
CATS = {"categories": [{"id": 1, "parent_id": None, "slug": "tables", "name": "Tables", "count": 2}, {"id": 2, "parent_id": 1, "slug": "packing", "name": "Packing tables", "count": 1}]}
PRODS = {"products": [
    {"id": 4934, "slug": "packing-table-custom", "sku": "PS-1", "category_id": 2, "name": "Packing table made to measure", "summary": "Packing table from aluminium profiles, your dimensions.", "description": "First paragraph.\nSecond paragraph.",
     "price_from": 1290, "currency": "EUR", "delivery": "3-5 weeks, disassembled", "configurator": {"available": True}, "specs": [{"name": "Width", "value": "500-3000 mm"}]},
    {"id": 7, "slug": "xss", "sku": None, "category_id": 1, "name": "Table <script>alert(1)</script>", "summary": "Test </script><b>x</b>", "description": "", "price_from": None, "currency": "EUR", "delivery": "", "configurator": {"available": False}, "specs": []}]}
LEGAL = {"documents": [{"kind": "terms", "title": "Terms", "body": "Terms text.\nSecond line.", "updated": "2026-10-01"}]}
vysl = []
HOST = None
state = {}


def ok(cond, text):
    vysl.append(bool(cond))
    print("[%s] %s" % ("OK   " if cond else "CHYBA", text))


def fake(path, host):
    if host != HOST:
        return 404, None
    if path == "/api/miniweb/config":
        return (state["status"], state["cfg"] if state["status"] == 200 else None)
    if path.startswith("/api/miniweb/products"):
        return 200, {"products": PRODS["products"], "total": len(PRODS["products"])}
    return 200, {"/api/miniweb/categories": CATS, "/api/miniweb/legal": LEGAL}[path]


S._api = fake
client = appmod.app.test_client()


def get(path, host=None):
    r = client.get("/api/miniweb/seo" + path, base_url="https://" + (host or HOST))
    return r.status_code, r.get_data(as_text=True), r


def tag(html, pat):
    m = re.search(pat, html)
    return m.group(1) if m else None


_i18n_orig = S._i18n
for lang in JAZYKY:
    HOST = "test-%s.top" % lang
    real_i18n = os.path.isfile(os.path.join(I18N_DIR, lang + ".json"))
    sab_real = lang in S.SABLONY and isinstance(S.SABLONY[lang], dict) and "cart" in S.SABLONY[lang] and "not_found" in S.SABLONY[lang]
    print("==== jazyk %s (i18n %s, SEO šablony %s)" % (lang, "skutečné" if real_i18n else "syntetické", "skutečné" if sab_real else "syntetické"))
    if not sab_real:
        S.SABLONY[lang] = dict(copy.deepcopy(S.SABLONY["sk"]), host=HOST, lang=lang, locale=lang + "_" + lang.upper())
    S._i18n = (lambda l, _lang=lang: SK_I18N if (l or "").split("-")[0] == _lang else _i18n_orig(l)) if not real_i18n else _i18n_orig
    P = S.PATHS.get(lang)
    ok(P is not None, "%s: PATHS má jazyk (jinak by shop dostal anglické adresy)" % lang)
    if P is None:
        continue
    tpl = S.SABLONY[lang]
    CFG = {"shop": "packstations-" + lang, "lang": lang, "locale": lang + "-" + lang.upper(), "currency": "EUR", "price_mode": "hidden", "preview": False, "alternates": [{"lang": "xx", "href": "https://other-shop.top/"}]}
    state.update(cfg=dict(CFG), status=200)
    base = "https://" + HOST
    sc, h, r = get("/")
    ok(sc == 200 and tag(h, r'<html lang="([^"]+)"') == lang, "%s S1 domov: 200 a <html lang=%s>" % (lang, lang))
    ok(tag(h, r"<title>(.*?)</title>") and tag(h, r"<title>(.*?)</title>").replace("&amp;", "&") == tpl["home"]["title"][:70], "%s S2 <title> z SEO šablony jazyka" % lang)
    ok('<link rel="canonical" href="%s/">' % base in h and tag(h, r'<meta name="robots" content="([^"]*)"') == "index, follow", "%s S3 canonical + robots index, follow (shop live)" % lang)
    ok('hreflang="%s" href="%s/"' % (lang, base) in h and 'hreflang="xx" href="https://other-shop.top/"' in h, "%s S4 hreflang sám na sebe + sourozenec" % lang)
    ok(('hreflang="x-default" href="%s/"' % base in h) == (lang == "en"), "%s S4b x-default: anglická stránka ukazuje sama na sebe, ostatní jazyky ho z této sady (bez sourozence en) nenesou" % lang)
    ld = [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S)]
    ok([x["@type"] for x in ld][:2] == ["WebSite", "Organization"] and ld[0].get("inLanguage") == lang, "%s S5 JSON-LD WebSite (inLanguage=%s) + Organization" % (lang, lang))
    ok("<h1>" in h and "window.MW_BOOT=" in h and ('"paths": ' in h and P["product"] in h), "%s S6 statický H1 a MW_BOOT s cestami jazyka (%s)" % (lang, P["product"]))
    # produkt
    sc, h, r = get(P["product"] + "packing-table-custom")
    ok(sc == 200 and 'rel="canonical" href="%s%spacking-table-custom"' % (base, P["product"]) in h and 'og:type" content="product"' in h, "%s P1 produkt na %s<slug>: 200, canonical ve tvaru jazyka" % (lang, P["product"]))
    ld = [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S)]
    ok(ld and ld[0]["@type"] == "Product" and [i["item"] for i in ld[1]["itemListElement"]][-1] == "%s%spacking-table-custom" % (base, P["product"]), "%s P2 JSON-LD Product + BreadcrumbList s adresami jazyka" % lang)
    sc, h, r = get("/product/packing-table-custom") if P["product"] != "/product/" else (404, "", None)
    ok(sc == 404, "%s P3 anglická cesta /product/<slug> v jazyce %s NEfunguje (404, žádný únik angličtiny)" % (lang, lang) if P["product"] != "/product/" else "%s P3 (jazyk používá /product/)" % lang)
    sc, h, r = get(P["product"] + "xss")
    ok(sc == 200 and "<script>alert(1)</script>" not in h and "&lt;script&gt;alert(1)&lt;/script&gt;" in h, "%s P4 XSS: název i summary escapované" % lang)
    # kategorie, obchod, kontakt, pravni, kosik
    sc, h, _ = get(P["category"] + "packing")
    ok(sc == 200 and ('href="%spacking-table-custom"' % P["product"]) in h, "%s K1 kategorie na %s<slug>: odkazy na produkty s cestou jazyka" % (lang, P["category"]))
    sc, h, _ = get(P["shop"])
    ok(sc == 200 and 'rel="canonical" href="%s%s"' % (base, P["shop"]) in h, "%s K2 přehled obchodu na %s" % (lang, P["shop"]))
    sc, h, _ = get(P["contact"])
    ok(sc == 200 and tag(h, r"<title>(.*?)</title>") and tag(h, r"<title>(.*?)</title>").replace("&amp;", "&") == tpl["contact"]["title"][:70], "%s C1 kontakt na %s: title ze šablony" % (lang, P["contact"]))
    sc, h, _ = get(P["legal"])
    ok(sc == 200 and "Terms text." in h, "%s C2 právní informace na %s: dokument staticky" % (lang, P["legal"]))
    sc, h, r = get(P["cart"])
    ok(sc == 200 and tag(h, r'<meta name="robots" content="([^"]*)"') == "noindex, nofollow" and r.headers.get("X-Robots-Tag", "").startswith("noindex"), "%s C3 košík na %s: noindex (meta i hlavička)" % (lang, P["cart"]))
    # 301 ze zakladniho slugu
    PRODS["products"][0]["slug_alt"] = ["old-base-slug"]
    sc, h, r = get(P["product"] + "old-base-slug")
    ok(sc == 301 and r.headers.get("Location") == "%s%spacking-table-custom" % (base, P["product"]), "%s A1 starý slug → 301 na adresu jazyka: %s" % (lang, r.headers.get("Location")))
    PRODS["products"][0].pop("slug_alt", None)
    # robots + sitemap
    sc, t, _ = get("/robots.txt")
    ok(sc == 200 and "Sitemap: %s/sitemap.xml" % base in t and "Disallow: %s" % P["cart"] in t, "%s R1 robots.txt: sitemap a zakázaný košík %s" % (lang, P["cart"]))
    sc, t, r = get("/sitemap.xml")
    locs = re.findall(r"<loc>(.*?)</loc>", t)
    ok(sc == 200 and base + "/" in locs and "%s%spacking-table-custom" % (base, P["product"]) in locs and "%s%spacking" % (base, P["category"]) in locs and base + P["contact"] in locs and not any(P["cart"] in x for x in locs), "%s R2 sitemap: home, produkt, kategorie, kontakt s cestami jazyka, bez košíku" % lang)
    # draft shell + 404
    state["status"] = 404
    sc, h, r = get(P["product"] + "packing-table-custom")
    ok((sc == 200 and 'content="noindex, nofollow"' in h and 'rel="canonical"' not in h) or sc == 404, "%s D1 koncept (anonym nevidí): shell s noindex a bez canonical (404, když host není v DB jako storefront - synteticky host)" % lang)
    state["status"] = 200
    sc, h, r = get(P["product"] + "neexistuje")
    ok(sc == 404 and "noindex" in (tag(h, r'<meta name="robots" content="([^"]*)"') or ""), "%s D2 neznámý produkt: 404 + noindex" % lang)
S._i18n = _i18n_orig
print("\n==> %d/%d kontrol OK" % (sum(vysl), len(vysl)))
sys.exit(0 if all(vysl) else 1)
