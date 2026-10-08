#!/usr/bin/env python3
"""Verze (?v=<hash obsahu>) u skriptu a stylu mini-shopu - bot16, 2026-10-03.
PROC: Cloudflare posila prohlizeci max-age=14400 (4 h) i kdyz origin vraci no-cache, takze po oprave JS vidi navstevnici stary kod az 4 hodiny. URL s novou
verzi je nova polozka cache. Spust po KAZDE uprave webapp/miniweb/*.js|css a js/product-configurator.js, css/product-configurator.css, css/v3d.css, js/v3d/viewer3d.js:
  api/venv/bin/python3 scripts/miniweb_verze.py          # prepise ?v= ve webapp/miniweb/*.html a v miniweb-pages.js (idempotentni)
Server-side SEO stranky (api/miniweb_seo.py) pocitaji stejnou verzi za behu ze stejnych souboru."""
import hashlib, os, re, sys
WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "webapp")
ASSETS = ["/miniweb/miniweb.css", "/miniweb/miniweb.js", "/miniweb/miniweb-pages.js", "/miniweb/stul-ulozeni.js", "/js/product-configurator.js", "/miniweb/pdc-layout.js", "/css/product-configurator.css", "/css/v3d.css", "/js/v3d/viewer3d.js", "/js/v3d-ovladani.js", "/js/pripni-cokoli-tile.js"]


def ver(url):
    return hashlib.md5(open(WEB + url, "rb").read()).hexdigest()[:10]


def rewrite(path, urls):
    s = open(path, encoding="utf-8").read()
    out = s
    for u in urls:
        out = re.sub(re.escape(u) + r"(\?v=[0-9a-f]{10})?(?=[\"'])", u + "?v=" + ver(u), out)
    if out != s:
        open(path, "w", encoding="utf-8").write(out)
        return True
    return False


def main():
    pages = os.path.join(WEB, "miniweb", "miniweb-pages.js")
    changed = [rewrite(pages, ["/css/product-configurator.css", "/css/v3d.css", "/js/v3d/viewer3d.js", "/js/v3d-ovladani.js", "/js/pripni-cokoli-tile.js"])]    # nejdriv to, co pages.js odkazuje (jeho hash na tom zavisi)
    for f in sorted(os.listdir(os.path.join(WEB, "miniweb"))):
        if f.endswith(".html"):
            changed.append(rewrite(os.path.join(WEB, "miniweb", f), ASSETS))
    # vlozitelny generator stolu (webapp/embed/stul.html + stul-embed.js, iframe na logiman.cz): nejdriv assety uvnitr JS, pak HTML
    changed.append(rewrite(os.path.join(WEB, "js", "stul-luxy.js"), ["/js/lux/lux-core.js", "/js/lux/lux-data.js", "/js/lux/lux-plugin.js", "/css/lux.css"]))      # pocitadlo luxu (stejny soubor prepisuje i stul_verze.py)
    changed.append(rewrite(os.path.join(WEB, "embed", "stul-embed.js"), ["/css/product-configurator.css", "/css/v3d.css", "/js/v3d/viewer3d.js", "/js/v3d-ovladani.js", "/js/pripni-cokoli-tile.js"]))
    changed.append(rewrite(os.path.join(WEB, "embed", "stul.html"), ["/miniweb/miniweb.css", "/css/product-configurator.css", "/js/pdc-layout.js", "/js/product-configurator.js", "/js/v3d/viewer3d.js", "/js/v3d-ovladani.js", "/miniweb/stul-ulozeni.js", "/embed/stul-embed-objednavka.js", "/js/stul-luxy.js", "/embed/stul-embed.js"]))
    print("zmeneno souboru:", sum(changed))
    for u in ASSETS:
        print(u, ver(u))
    # stranky Generatoru stolu (bot8/bot10: stul-konfigurator*.html) maji vlastni skript scripts/stul_verze.py a sdili product-configurator.js, css a viewer s mini-shopem:
    # kdyz tam zustal stary hash, upozornit (nechodi to samo; po zmene sdileneho souboru pustit obe)
    stare = []
    for f in ("stul-konfigurator.html", "stul-konfigurator-40.html", "stul-konfigurator-35.html", "stul-konfigurator-41.html", "stul-konfigurator-45.html"):
        cesta = os.path.join(WEB, f)
        if not os.path.isfile(cesta):
            continue
        h = open(cesta, encoding="utf-8").read()
        for u in ("/js/product-configurator.js", "/css/product-configurator.css"):
            m = re.search(re.escape(u) + r"\?v=([0-9a-f]{1,10})", h)
            if m and m.group(1) != ver(u):
                stare.append("%s: %s ma ?v=%s, aktualni %s" % (f, u, m.group(1), ver(u)))
    if stare:
        print("POZOR: stranky Generatoru stolu maji stary hash sdileneho souboru - pust i `api/venv/bin/python3 scripts/stul_verze.py`:")
        for x in stare:
            print("  " + x)


if __name__ == "__main__":
    sys.exit(main())
