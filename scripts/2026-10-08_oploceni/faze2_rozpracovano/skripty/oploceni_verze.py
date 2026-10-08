#!/usr/bin/env python3
"""Verze (?v=<hash obsahu>) u skriptu a stylu stranky Generator 06 - ochranny kryt a oploceni (bot8, 2026-10-08) - stejny princip jako scripts/stul_verze.py a scripts/miniweb_verze.py.
PROC: za Cloudflare se po oprave JS dlouho ukazuje stary kod z cache; URL s novou verzi je nova polozka cache. Spust po KAZDE uprave webapp/js/oploceni-host.js, js/product-configurator.js,
js/pdc-layout.js, css/product-configurator.css, css/v3d.css, js/v3d/viewer3d.js, miniweb/miniweb.css:
  api/venv/bin/python3 scripts/2026-10-08_oploceni/oploceni_verze.py [koren repa [slozka webapp k prepsani]]
    (idempotentni; prepise ?v= v webapp/oploceni-konfigurator.html a v assets v webapp/js/oploceni-host.js; hashe cte z <koren>/webapp, pripadne z druhe slozky, kdyz tam soubor je)
Poradi: nejdriv assets uvnitr oploceni-host.js, az potom HTML (ten odkazuje na oploceni-host.js, jehoz obsah se tim zmenil). Koren repa je vychozi ten, ve kterem lezi tento skript (zivy strom, nebo kandidat).
Druhy argument = slozka `webapp` s kopiemi dvou souboru stranky (apply_f2.sh: vypocet v docasne slozce, zivy strom se nemeni, dokud se vse neoveri)."""
import hashlib
import os
import re
import sys

ROOT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
WEB = os.path.join(ROOT, "webapp")
OUT = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else WEB
ASSETS_V_HOSTU = ["/css/product-configurator.css", "/css/v3d.css", "/js/v3d/viewer3d.js"]
ASSETS_V_HTML = ["/miniweb/miniweb.css", "/js/product-configurator.js", "/js/pdc-layout.js", "/js/oploceni-host.js"]


def verze(url):
    cesta = OUT + url if os.path.isfile(OUT + url) else WEB + url
    return hashlib.md5(open(cesta, "rb").read()).hexdigest()[:10]


def prepis(soubor, urls):
    cesta = os.path.join(OUT, soubor)
    s = open(cesta, encoding="utf-8").read()
    out = s
    for u in urls:
        out, n = re.subn(re.escape(u) + r"(\?v=[0-9a-f]{1,10})?(?=[\"'])", u + "?v=" + verze(u), out)
        if n == 0:
            raise SystemExit(f"CHYBA: v {soubor} se nenasel odkaz na {u}")
    if out != s:
        open(cesta, "w", encoding="utf-8").write(out)
    return out != s


if __name__ == "__main__":
    a = prepis("js/oploceni-host.js", ASSETS_V_HOSTU)
    b = prepis("oploceni-konfigurator.html", ASSETS_V_HTML)
    print("js/oploceni-host.js:", "prepsano" if a else "beze zmeny", "| oploceni-konfigurator.html:", "prepsano" if b else "beze zmeny")
