#!/usr/bin/env python3
"""Mini-shop: cesty hezkych adres a nginx vhost pro VSECHNY jazyky (bot16, 2026-10-07; Robert: anglicky 1:1 se slovenskym + nemecka a madarska kopie).

Jen cteni souboru (zadna DB, zadna sit, zadny nginx): kontroluje, ze kazdy jazyk s prekladovym souborem `webapp/miniweb/i18n/<jazyk>.json` ma v `api/miniweb_seo.py::PATHS`
vlastni sadu cest (jinak by shop dostal anglicke URL), ze cesty jsou ASCII bez kolizi s rezervovanymi prefixy, a ze generator vhostu (`scripts/gen_miniweb_vhost.py`) pro kazdy
jazyk vyda stejnou kostru jako pro slovenstinu (jen s jinymi cestami).
Spusteni z korene repa NEBO z izolovane kopie HEAD s kandidatem:  python3 scripts/2026-10-07_miniweb_jazyky_testy/test_cesty_jazyky.py
"""
import ast
import importlib.util
import os
import re
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:500]))


src = open(os.path.join(REPO, "api", "miniweb_seo.py"), encoding="utf-8").read()
PATHS = next(ast.literal_eval(n.value) for n in ast.parse(src).body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "PATHS")
KLICE = ("category", "product", "contact", "legal", "cart", "shop")
I18N_DIR = os.path.join(REPO, "webapp", "miniweb", "i18n")
JAZYKY_SOUBORU = sorted(f[:-5] for f in os.listdir(I18N_DIR) if re.match(r"^[a-z]{2}\.json$", f))
REZERVOVANE = ("miniweb", "api", "js", "css", "katalog", "img", "robots.txt", "sitemap.xml", "login", "admin", "index", "scene", "nabidka")

over("A1 PATHS ma aspon sk, en, cs, de, hu", all(l in PATHS for l in ("sk", "en", "cs", "de", "hu")), sorted(PATHS))
over("A2 kazdy jazyk s prekladovym souborem i18n/<jazyk>.json ma vlastni PATHS (jinak by shop dostal anglicke adresy): %s" % ", ".join(JAZYKY_SOUBORU),
     all(l in PATHS for l in JAZYKY_SOUBORU), [l for l in JAZYKY_SOUBORU if l not in PATHS])
for lg, p in sorted(PATHS.items()):
    over(f"B {lg}: presne klice {KLICE}", tuple(sorted(p)) == tuple(sorted(KLICE)), sorted(p))
    vse = list(p.values())
    over(f"B {lg}: cesty jsou ASCII male pismeno/cislice/pomlcka, zacinaji lomitkem, kategorie a produkt koncí lomitkem, ostatni ne",
         all(re.match(r"^/[a-z0-9]+(-[a-z0-9]+)*/?$", v) for v in vse) and p["category"].endswith("/") and p["product"].endswith("/")
         and not any(p[k].endswith("/") for k in ("contact", "legal", "cart", "shop")), vse)
    over(f"B {lg}: zadna cesta se nekryje s jinou ani s rezervovanym prefixem", len(set(vse)) == len(vse) and not any(v.strip("/").split("/")[0] in REZERVOVANE for v in vse), vse)

# vhost: stejna kostra pro vsechny jazyky
spec = importlib.util.spec_from_file_location("gen_miniweb_vhost", os.path.join(REPO, "scripts", "gen_miniweb_vhost.py"))
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)
ref = G.render("priklad.top", noindex=False, lang="sk")
over("C0 vhost pro sk obsahuje SEO rezim (/robots.txt, /sitemap.xml, /kategoria|produkt/ regex)", "location = /robots.txt" in ref and "location = /sitemap.xml" in ref and "kategoria|produkt" in ref, None)


def normalizuj(text, lg):
    """nahradi JEN cesty jazyka (regex kategorie|produkt a presne lokace), zbytek vhostu musi byt u vsech jazyku stejny"""
    p = PATHS[lg]
    t = text.replace("priklad.top", "DOMENA")
    t = t.replace("^/(%s|%s)/" % (p["category"].strip("/"), p["product"].strip("/")), "^/(<category>|<product>)/")
    for k in ("contact", "legal", "cart", "shop"):
        t = t.replace("location = " + p[k] + " ", "location = <" + k + "> ")
    return t


ref_n = normalizuj(ref, "sk")
for lg in sorted(PATHS):
    if lg == "sk":
        continue
    try:
        v = G.render("priklad.top", noindex=False, lang=lg)
    except Exception as e:                                                                   # noqa: BLE001
        over(f"C {lg}: vhost se vygeneroval", False, repr(e))
        continue
    p = PATHS[lg]
    over(f"C {lg}: vhost nese vsech 6 cest a regex kategorie/produkt tohoto jazyka", all(f"location = {p[k]} " in v for k in ("contact", "legal", "cart", "shop")) and f"{p['category'].strip('/')}|{p['product'].strip('/')}" in v, None)
    over(f"C {lg}: kostra vhostu je shodna s slovenskou (po nahrazeni cest a domeny)", normalizuj(v, lg) == ref_n, None)
    over(f"C {lg}: vhost bez --index (noindex rezim) se vygeneruje a ma noindex", "noindex" in G.render("priklad.top", noindex=True, lang=None).lower(), None)

ok = sum(vysl)
print(f"\nVYSLEDEK mini-shop cesty a vhost pro vsechny jazyky: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
