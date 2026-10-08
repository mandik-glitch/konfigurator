#!/usr/bin/env python3
"""Verze (?v=<hash obsahu>) u skriptu a stylu stranky Generator stolu (bot8, 2026-10-04) - stejny princip jako scripts/miniweb_verze.py.
PROC: za Cloudflare se po oprave JS dlouho ukazuje stary kod z cache; URL s novou verzi je nova polozka cache. Spust po KAZDE uprave
webapp/js/stul-host.js, stul-luxy.js, lux/*.js, css/lux.css, stul-do-sceny.js, v3d-ovladani.js, js/product-configurator.js, css/product-configurator.css, css/v3d.css, js/v3d/viewer3d.js:
  api/venv/bin/python3 scripts/stul_verze.py          (idempotentni; prepise ?v= v webapp/stul-konfigurator.html, -40, -35 a -41 .html a v assets v js/stul-host.js)
Poradi: nejdriv assets uvnitr stul-host.js, az potom HTML (ten odkazuje na stul-host.js, jehoz obsah se tim zmenil)."""
import hashlib, os, re, sys
WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "webapp")
V = lambda url: hashlib.md5(open(WEB + url, "rb").read()).hexdigest()[:10]
ASSETS_V_HOSTU = ["/css/product-configurator.css", "/css/v3d.css", "/js/v3d/viewer3d.js", "/js/v3d-ovladani.js", "/js/v3d/env-picker.js", "/js/pripni-cokoli-tile.js"]
LUX_ASSETS = ["/js/lux/lux-core.js", "/js/lux/lux-data.js", "/js/lux/lux-plugin.js", "/css/lux.css"]                  # pocitadlo luxu: piny jsou uvnitr js/stul-luxy.js (nacita je az pri zapnuti)
ASSETS_V_HTML = ["/miniweb/miniweb.css", "/js/product-configurator.js", "/js/pdc-layout.js", "/js/stul-montaz-staff.js", "/js/stul-nabidka.js", "/js/stul-karta.js", "/js/stul-luxy.js", "/js/stul-host.js", "/js/stul-do-sceny.js"]


def prepis(soubor, urls):
    cesta = os.path.join(WEB, soubor)
    s = open(cesta, encoding="utf-8").read()
    out = s
    for u in urls:
        out = re.sub(re.escape(u) + r"(\?v=[0-9a-f]{1,10})?(?=[\"'])", u + "?v=" + V(u), out)
    if out != s:
        open(cesta, "w", encoding="utf-8").write(out)
    return out != s


if __name__ == "__main__":
    a0 = prepis("js/stul-luxy.js", LUX_ASSETS)                                                  # nejdriv piny uvnitr stul-luxy.js (HTML odkazuje na jeho hash)
    a = prepis("js/stul-host.js", ASSETS_V_HOSTU)
    b = prepis("stul-konfigurator.html", ASSETS_V_HTML)
    c = prepis("stul-konfigurator-40.html", ASSETS_V_HTML)                                     # generator stolu 02 (system 40): tatez stranka, jina data-system
    d = prepis("stul-konfigurator-35.html", ASSETS_V_HTML)                                     # generator stolu 03 (system 35): tatez stranka, jina data-system
    e = prepis("stul-konfigurator-41.html", ASSETS_V_HTML)                                     # generator stolu 04 (system 41, stul SSE): tatez stranka, jina data-system
    f = prepis("stul-konfigurator-45.html", ASSETS_V_HTML)                                     # generator stolu 05 (system 45, hluboky stul): tatez stranka, jina data-system
    print("js/stul-luxy.js:", "prepsano" if a0 else "beze zmeny", "| js/stul-host.js:", "prepsano" if a else "beze zmeny", "| stul-konfigurator.html:", "prepsano" if b else "beze zmeny", "| stul-konfigurator-40.html:", "prepsano" if c else "beze zmeny",
          "| stul-konfigurator-35.html:", "prepsano" if d else "beze zmeny", "| stul-konfigurator-41.html:", "prepsano" if e else "beze zmeny", "| stul-konfigurator-45.html:", "prepsano" if f else "beze zmeny")
