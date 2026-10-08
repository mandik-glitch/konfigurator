#!/opt/konfigurator/api/venv/bin/python
# -*- coding: utf-8 -*-
"""SSR hacky IT/EN verze webu (api/storefront_pages.py + api/web_i18n.py) proti SKUTECNE aplikaci a DB (jen cteni) - bot16, 2026-10-08.
A) CESTINA SE NEZMENI: stranky a JSON na ceskem hostu jsou bajt po bajtu stejne, at je modul web_i18n nacteny (import v app.py) nebo ne (dva procesy, porovnani otisku).
B) zamestnanec s ?jazyk=en|it: uvodni strana (titulky karuselu, bloky, strom kategorii, uvodni text), kategorie (H1, uvod, podkategorie, strom, JSON-LD, <title>), produkt (<title>, popis, JSON-LD) jsou v jazyce, blok 7 (dodavatel) neni,
   zadna cena v Kc v SSR, <html lang>, noindex.
Spusteni:  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-08_web_jazyky_testy/test_web_i18n_ssr.py
Kandidat pred nasazenim: --setenv=KOREN=<strom s api/ a webapp/>  (puvodni kod bez hacku: test B musi selhat)"""
import hashlib
import json
import os
import re
import subprocess
import sys

KORENOVY = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
KOREN = os.environ.get("KOREN") or KORENOVY
STRANKY = ["/", "/vestavby-do-dodavek-aut", "/produkt/regal-na-euroboxy-citroen-jumpy-l1-od-2016", "/produkt/uhelnikova-spojka-30x30", "/kontakt.html", "/robots.txt", "/panel/neexistuje-xyz"]
JSONY = ["/api/categories", "/api/categories/184/content", "/api/shop/products/3045", "/api/shipping-methods", "/api/payment-methods", "/api/sidebar-blocks"]
HOST = "autovestavby.logiman.cz"


def klient(app_mod, staff=False):
    c = app_mod.app.test_client()
    c._staff_cookie = None
    if staff:
        with c.session_transaction() as s:
            s["user_id"] = 1
        c._staff_cookie = c.get_cookie("session").value
    return c


def get(c, cesta, host=HOST):
    if getattr(c, "_staff_cookie", None):
        c.set_cookie("session", c._staff_cookie, domain=host)
    return c.get(cesta, base_url="https://" + host, headers={"X-Forwarded-Proto": "https"})


if len(sys.argv) > 1 and sys.argv[1] == "--otisky":          # podproces: vypise otisky ceskych stranek (s modulem / bez)
    sys.path.insert(0, KOREN + "/api")
    sys.dont_write_bytecode = True
    import app as appmod
    if sys.argv[2] == "s":
        import web_i18n  # noqa: F401
    c = klient(appmod)
    out = {}
    for cesta in STRANKY + JSONY:
        r = get(c, cesta)
        data = r.get_data()
        if cesta == "/":              # nahodne vybrane fotky v dlazdicich galerie na homepage (src, alt, rozmery) se meni kazdym pozadavkem
            data = re.sub(rb'<img[^>]*hp-gallery-img[^>]*>', b'<img GALERIE>', data)
        out[cesta] = [r.status_code, hashlib.sha256(data).hexdigest()[:16], len(data)]
    print(json.dumps(out))
    sys.exit(0)

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:500]))


# ===== A: cestina beze zmeny (dva procesy) =====
def otisky(rezim):
    p = subprocess.run([sys.executable, os.path.abspath(__file__), "--otisky", rezim], capture_output=True, text=True, env=dict(os.environ, KOREN=KOREN), timeout=600)
    radek = [l for l in p.stdout.strip().split("\n") if l.startswith("{")]
    if not radek:
        raise SystemExit("podproces %s selhal: %s" % (rezim, (p.stderr or p.stdout)[-800:]))
    return json.loads(radek[-1])


bez, s = otisky("bez"), otisky("s")
for cesta in STRANKY + JSONY:
    over("A %s: cesky host je stejny s modulem i bez nej (%s, %s B)" % (cesta, bez[cesta][0], bez[cesta][2]), bez[cesta] == s[cesta], (bez[cesta], s[cesta]))

# ===== B: zamestnanec EN / IT =====
sys.path.insert(0, KOREN + "/api")
sys.dont_write_bytecode = True
import app as appmod  # noqa: E402
import web_i18n as W  # noqa: E402


def preklad(klic, lang="en"):
    conn = appmod.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT `text` FROM web_i18n WHERE klic=%s AND lang=%s AND zastarale=0", (klic, lang))
            r = cur.fetchone()
            return r["text"] if r else None
    finally:
        conn.close()


def holy(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h))


st = klient(appmod, staff=True)
for lang in ("en", "it"):
    r = get(st, "/?jazyk=" + lang)
    h = r.get_data(as_text=True)
    over("B1 %s uvodni strana: lang, noindex, i18n.js, 200" % lang, r.status_code == 200 and ('<html lang="%s"' % lang) in h and 'name="robots" content="noindex, nofollow"' in h and "/js/i18n.js?v=" in h, (r.status_code, h[:200]))
    tree = re.search(r'id="catTree"[^>]*>(.*?)</div>\s*<div class="cat-empty"', h, re.S)
    kat298 = preklad("kat:298:name", lang)
    over("B2 %s strom kategorii v SSR je v jazyce (Naposledy pridane -> %r)" % (lang, kat298), kat298 and (">" + kat298 + "<") in h and "Naposledy přidané" not in re.sub(r"<script.*?</script>", "", h, flags=re.S).split('id="catTree"')[1][:3000], kat298)
    over("B3 %s karusel: titulek 1. slidu preložen" % lang, bool(re.search(r'hp-carousel', h)) and "Modulární stavebnice do dodávek" not in h.split("hpCarousel")[1][:3000], None)
    bloky = re.findall(r'class="hp-block-card"', h)
    over("B4 %s dlazdice 'Dogus Kalip' (blok 7) se nerenderuje, tj. zadny odkaz /blok/zastupujeme-vyrobce-dogus-kalip" % lang, "zastupujeme-vyrobce-dogus-kalip" not in h and "Dogus" not in holy(h), len(bloky))
    over("B5 %s uvodni text homepage je v jazyce" % lang, "Pracovní vestavby do užitkových" not in h and "vestavby do užitkových vozidel" not in h, None)

    r = get(st, "/vestavby-do-dodavek-aut")
    h = r.get_data(as_text=True)
    n184 = preklad("kat:184:name", lang)
    t184 = preklad("str:184:intro_html", lang)
    over("B6 %s kategorie 184: H1 = %r" % (lang, n184), n184 and re.search(r'id="catTitle">\s*' + re.escape(n184.replace("&", "&amp;")) + r'\s*</h1>', h) is not None, re.search(r'id="catTitle">(.*?)</h1>', h, re.S).group(1)[:80] if re.search(r'id="catTitle">(.*?)</h1>', h, re.S) else None)
    over("B7 %s kategorie 184: uvodni text (intro_html) je preložený, cesky text tam neni" % lang, t184 and holy(t184)[:60] in holy(h) and "Vestavba do dodávky je individuální" not in h, None)
    titul = re.search(r"<title[^>]*>(.*?)</title>", h, re.S).group(1)
    mt184 = preklad("kat:184:meta_title", lang) or n184
    over("B8 %s kategorie 184: <title> = preložený meta_title a v hlavicce neni cesky nazev kategorie" % lang, titul.startswith(mt184[:20]) and "Vestavby do dodávek, aut" not in h.split("</head>")[0], titul[:120])
    over("B9 %s kategorie 184: podkategorie v jazyce (Regaly do auta -> %r)" % (lang, preklad("kat:247:name", lang)), preklad("kat:247:name", lang) and preklad("kat:247:name", lang) in h and ">Regály do auta<" not in h, None)
    over("B10 %s kategorie 184: v SSR neni zadna cena v Kc" % lang, " Kč" not in holy(h.split('id="productGrid"')[1][:20000]) if 'id="productGrid"' in h else True, None)

    r = get(st, "/produkt/regal-na-euroboxy-citroen-jumpy-l1-od-2016")
    h = r.get_data(as_text=True)
    n3947 = preklad("kar:3947:name", lang)
    over("B11 %s produkt 3947: <title> je preklad nazvu (%r)" % (lang, n3947), n3947 and re.search(r"<title[^>]*>(.*?)</title>", h, re.S).group(1).startswith((preklad("kar:3947:meta_title", lang) or n3947)[:30]), re.search(r"<title[^>]*>(.*?)</title>", h, re.S).group(1)[:120])
    ld = " ".join(re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S))
    over("B12 %s produkt: JSON-LD ma preložený nazev a zadnou cenu v Kc / CZK" % lang, n3947 and n3947[:25] in ld and "CZK" not in ld and "Regál na euroboxy" not in ld, ld[:300])
    over("B13 %s produkt: meta description bez Kc a bez ceskeho textu karty" % lang, " Kč" not in re.search(r'name="description" content="([^"]*)"', h).group(1), re.search(r'name="description" content="([^"]*)"', h).group(1)[:200])

# ===== C: ceska stranka zamestnance po ?jazyk=cs zustane cesky =====
r = get(st, "/?jazyk=cs")
h = r.get_data(as_text=True)
over("C1 ?jazyk=cs: cesky obsah, zadne i18n.js, zadny noindex", "i18n.js" not in h and "Naposledy přidané" in h and 'name="robots" content="noindex' not in h, None)

print("\n==> %d/%d kontrol OK" % (sum(vysl), len(vysl)))
sys.exit(0 if all(vysl) else 1)
