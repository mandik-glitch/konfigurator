"""Server-side HTML pro verejny mini-shop (SEO): title, description, canonical, hreflang, robots, og/twitter, JSON-LD a staticky H1/uvod/FAQ -
bot16, 2026-10-03; sablony textu bot7 (api/miniweb_seo_sablony.json), zadani Robert pres bot3 ("KOMPLETNI SEO ... noindex pryc u live shopu").

Stranky mini-shopu se kresli v JS (webapp/miniweb/*.html = shell); bez tohohle modulu by Google videl prazdny shell s noindex. Modul bere shell, vlozi do <head>
meta a do <main> staticky obsah z verejneho API (stejne zdroje a stejna pravidla jako to, co vidi navstevnik: schvalene texty, live shop) a vrati ho.
nginx vhost (scripts/gen_miniweb_vhost.py) posila hezke adresy sem:  /  /kategoria/<slug>  /produkt/<slug>  /kontakt  /pravne-informacie  /kosik  + /sitemap.xml /robots.txt.

Pravidla: indexace JEN kdyz je shop live (config.preview == false; draft nevidi anonym vubec -> 404 a Disallow); kosik/pokladna noindex; zadna znacka, zadny
e-mail, zadna cena v meta ani JSON-LD, og:image se nepouziva; canonical bez ?shop/?lang/?drafts/?demo. Data se berou volanim verejneho API pres test_client
(jedna logika viditelnosti pro web i SEO), cache 60 s."""
import hashlib
import html
import json
import os
import re
import time

from flask import Response, request

from app import app, get_conn
import miniweb

BASE = os.path.dirname(os.path.abspath(__file__))
WEBAPP = os.path.join(os.path.dirname(BASE), "webapp", "miniweb")
SABLONY = json.load(open(os.path.join(BASE, "miniweb_seo_sablony.json"), encoding="utf-8"))

# cesty podle jazyka shopu (slugy jsou spolecne pro vsechny jazyky); musi sedet s PATHS v webapp/miniweb/miniweb.js a s regexy ve vhostu
PATHS = {
    "sk": {"category": "/kategoria/", "product": "/produkt/", "contact": "/kontakt", "legal": "/pravne-informacie", "cart": "/kosik", "shop": "/obchod"},
    "en": {"category": "/category/", "product": "/product/", "contact": "/contact", "legal": "/legal-information", "cart": "/cart", "shop": "/shop"},
    "cs": {"category": "/kategorie/", "product": "/produkt/", "contact": "/kontakt", "legal": "/pravni-informace", "cart": "/kosik", "shop": "/obchod"},
    # dalsi jazyky (Robert 2026-10-07: nemecka a madarska kopie shopu; cesty bez diakritiky, navrh bot16, SEO potvrzuje bot7; jazyky bez zaznamu dostanou anglicke cesty, viz PATHS.get nize)
    "de": {"category": "/kategorie/", "product": "/produkt/", "contact": "/kontakt", "legal": "/rechtliche-informationen", "cart": "/warenkorb", "shop": "/shop"},
    "hu": {"category": "/kategoria/", "product": "/termek/", "contact": "/kapcsolat", "legal": "/jogi-informaciok", "cart": "/kosar", "shop": "/bolt"},
}
SHELL = {"home": "index.html", "category": "category.html", "shop": "category.html", "product": "product.html", "contact": "contact.html", "legal": "legal.html", "cart": "cart.html"}
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,120}$")
_CACHE = {}
TTL = 60
# skripty a styly s verzi podle obsahu (Cloudflare drzi statiku v prohlizeci 4 h; viz scripts/miniweb_verze.py - tady stejny vypocet za behu)
ASSETS = ["/miniweb/miniweb.css", "/miniweb/miniweb.js", "/miniweb/miniweb-pages.js", "/js/product-configurator.js", "/miniweb/pdc-layout.js", "/css/product-configurator.css", "/css/v3d.css", "/js/v3d/viewer3d.js", "/js/v3d-ovladani.js", "/js/pripni-cokoli-tile.js"]
_VER = {}


def _ver(url):
    f = os.path.join(os.path.dirname(WEBAPP), url.lstrip("/"))
    try:
        m = os.path.getmtime(f)
    except OSError:
        return "0"
    hit = _VER.get(url)
    if not hit or hit[0] != m:
        hit = _VER[url] = (m, hashlib.md5(open(f, "rb").read()).hexdigest()[:10])
    return hit[1]


def _versioned(src):
    for u in ASSETS:
        src = re.sub(re.escape(u) + r"(\?v=[0-9a-f]{10})?(?=[\"'])", lambda m, u=u: u + "?v=" + _ver(u), src)
    return src


def _api(path, host):
    key = (host, path)
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < TTL:
        return hit[1], hit[2]
    r = app.test_client().get(path, headers={"Host": host}, base_url="https://" + host, environ_overrides={"miniweb.interni": True})
    data = r.get_json(silent=True)
    if r.status_code == 200:                       # chyby (404 draft, 429 limit) se necachuji
        if len(_CACHE) > 200:
            _CACHE.clear()
        _CACHE[key] = (now, r.status_code, data)
    return r.status_code, data


def _all_products(host):
    """Vsechny viditelne produkty shopu (API strankuje po MAX_LIMIT): hezke adresy i mapa stranek nesmi koncit u prvni stranky."""
    out, offset = [], 0
    while offset < 5000:
        st, d = _api("/api/miniweb/products?limit=200&offset=%d" % offset, host)
        items = (d or {}).get("products") or []
        out += items
        total = (d or {}).get("total") or 0
        offset += 200
        if st != 200 or not items or len(out) >= total:
            break
    return out


def _host():
    return (request.host or "").split(":")[0].lower()      # jen Host (nginx ho posila z server_name whitelistu), ne X-Forwarded-Host


def _bare(host):
    return host[4:] if host.startswith("www.") else host


def _i18n(lang):
    for cand in (lang, lang.split("-")[0], "en"):
        p = os.path.join(WEBAPP, "i18n", cand + ".json")
        if re.match(r"^[a-z-]+$", cand) and os.path.isfile(p):
            return json.load(open(p, encoding="utf-8"))
    return {}


def _esc(s):
    return html.escape(str(s), quote=True)


def _sub(tpl, **vars_):
    out = tpl
    for k, v in vars_.items():
        out = out.replace("{" + k + "}", str(v))
    return out


def _trunc(s, n):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _ld(obj):
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False).replace("<", "\\u003c") + "</script>"


def _paragraphs(text):
    return "".join("<p>%s</p>" % _esc(p) for p in str(text or "").split("\n") if p.strip())


def _classify(path, paths):
    """-> (kind, slug|None) nebo (None, None)"""
    p = path.split("?")[0]
    if len(p) > 1:
        p = p.rstrip("/")
    if p in ("", "/"):
        return "home", None
    for kind in ("category", "product"):
        pre = paths[kind]
        if p.startswith(pre) and SLUG.match(p[len(pre):]):
            return kind, p[len(pre):]
    for kind in ("contact", "legal", "cart", "shop"):
        if p == paths[kind]:
            return kind, None
    return None, None


class _Redirect(Exception):
    def __init__(self, url):
        self.url = url


def _render(rest):
    host = _host()
    bare = _bare(host)
    st, cfg = _api("/api/miniweb/config", host)
    if st != 200 or not cfg:
        return _draft_shell(host, rest)
    lang = (cfg.get("lang") or "en").lower()
    paths = PATHS.get(lang.split("-")[0], PATHS["en"])
    tpl = SABLONY.get(lang.split("-")[0]) or SABLONY["en"]
    i18n = _i18n(lang)
    live = cfg.get("preview") is False
    brand = i18n.get("brand.name") or tpl.get("brand") or bare
    canon_base = "https://" + bare
    kind, slug = _classify("/" + rest, paths)

    cats = (_api("/api/miniweb/categories", host)[1] or {}).get("categories") or []
    prods = _all_products(host)
    cat = next((c for c in cats if c.get("slug") == slug), None) if kind == "category" else None
    prod = next((p for p in prods if p.get("slug") == slug), None) if kind == "product" else None
    if kind in ("category", "product") and not (cat or prod):
        # stary (zakladni) slug -> 301 na slug v jazyce shopu; API u polozky s jazykovym slugem posila `slug_alt` = [zakladni slug]
        alias = next((x for x in (cats if kind == "category" else prods) if slug in (x.get("slug_alt") or []) and x.get("slug")), None)
        if alias:
            raise _Redirect(canon_base + paths[kind] + alias["slug"])
        kind = None
    if kind == "shop":
        cat = None
    if kind is None:
        return _page(host, cfg, lang, i18n, brand, "not_found", tpl["not_found"]["title"], tpl["not_found"]["description"], "noindex,follow", canon_base + "/", paths, "<h1>%s</h1>" % _esc(tpl["not_found"]["title"]), [], 404), 404

    t = tpl["category" if kind == "shop" else kind]
    body, ld, canon = "", [], canon_base + ("/" if kind == "home" else "")
    title, desc, robots = t["title"], t["description"], t.get("robots", "index,follow")
    home_item = {"@type": "ListItem", "position": 1, "name": i18n.get("nav.home", "Home"), "item": canon_base + "/"}
    if kind == "home":
        i18n = _varianta(i18n, len(prods))
        body = _home_body(i18n, prods, paths)
        ld = [{"@context": "https://schema.org", "@type": "WebSite", "name": brand, "url": canon_base + "/", "inLanguage": lang},
              {"@context": "https://schema.org", "@type": "Organization", "name": brand, "url": canon_base + "/"}]
        faq = _faq(i18n)
        if faq:
            ld.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]})
    elif kind == "shop":
        canon = canon_base + paths["shop"]
        name = i18n.get("nav.shop", brand)
        title = _sub(t["title"], **{"category.name": name})
        body = "<h1>%s</h1><ul>%s</ul>" % (_esc(name), "".join('<li><a href="%s">%s</a></li>' % (_esc(paths["product"] + p["slug"]), _esc(p["name"])) for p in prods))
        ld = [{"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [home_item, {"@type": "ListItem", "position": 2, "name": name, "item": canon}]}]
    elif kind == "category":
        canon = canon_base + paths["category"] + cat["slug"]
        title, desc = _sub(t["title"], **{"category.name": cat["name"]}), t["description"]
        items = "".join('<li><a href="%s">%s</a></li>' % (_esc(paths["product"] + p["slug"]), _esc(p["name"])) for p in prods if p.get("category_id") in {cat["id"]} | {c["id"] for c in cats if c.get("parent_id") == cat["id"]})
        body = "<h1>%s</h1><ul>%s</ul>" % (_esc(cat["name"]), items)
        ld = [{"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [home_item, {"@type": "ListItem", "position": 2, "name": cat["name"], "item": canon}]}]
    elif kind == "product":
        canon = canon_base + paths["product"] + prod["slug"]
        title, desc = prod["name"], prod.get("summary") or t["description"]
        specs = "".join("<tr><th>%s</th><td>%s</td></tr>" % (_esc(s.get("name")), _esc(s.get("value"))) for s in (prod.get("specs") or []))
        body = "<h1>%s</h1><p>%s</p>%s%s%s" % (_esc(prod["name"]), _esc(prod.get("summary") or ""), _paragraphs(prod.get("description")),
                                                ("<p>%s</p>" % _esc(prod["delivery"])) if prod.get("delivery") else "", ("<table>%s</table>" % specs) if specs else "")
        pc = next((c for c in cats if c["id"] == prod.get("category_id")), None)
        crumbs = [home_item] + ([{"@type": "ListItem", "position": 2, "name": pc["name"], "item": canon_base + paths["category"] + pc["slug"]}] if pc else [])
        crumbs.append({"@type": "ListItem", "position": len(crumbs) + 1, "name": prod["name"], "item": canon})
        product_ld = {"@context": "https://schema.org", "@type": "Product", "name": prod["name"], "description": _trunc(prod.get("summary") or "", 300), "url": canon}
        if prod.get("sku"):
            product_ld["sku"] = prod["sku"]
        if pc:
            product_ld["category"] = pc["name"]
        if cfg.get("price_mode") == "shown" and prod.get("price_from") and prod.get("currency"):   # jen kdyz je cena na strance viditelna (bot7)
            product_ld["offers"] = {"@type": "AggregateOffer", "lowPrice": str(prod["price_from"]), "priceCurrency": prod["currency"],
                                    "priceSpecification": {"@type": "PriceSpecification", "valueAddedTaxIncluded": False}}
        ld = [product_ld, {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": crumbs}]
    elif kind in ("contact", "legal"):
        canon = canon_base + paths[kind]
        body = "<h1>%s</h1>" % _esc(i18n.get("contact.title" if kind == "contact" else "legal.title", title))
        ld = [{"@context": "https://schema.org", "@type": "WebPage", "name": title, "url": canon}]
        if kind == "legal":
            docs = ((_api("/api/miniweb/legal", host)[1] or {}).get("documents")) or []
            body += "".join("<section><h2>%s</h2>%s</section>" % (_esc(d.get("title") or ""), _paragraphs(d.get("body"))) for d in docs if d.get("body"))
    elif kind == "cart":
        canon = canon_base + paths["cart"]
        body = "<h1>%s</h1>" % _esc(i18n.get("cart.title", title))
        ld = []
    if not live:
        robots = "noindex,nofollow"                                    # koncept shopu (vidi ho jen staff) se neindexuje nikdy
    return _page(host, cfg, lang, i18n, brand, kind, title, desc, robots, canon, paths, body, ld, 200, slug=slug,
                  boot_extra={"id": prod["id"]} if prod else ({"cat": cat["slug"]} if cat else {})), 200


def _varianta(i18n, pocet):
    """Texty s priponou ".multi" nahrazuji zakladni klic, kdyz jsou v obchode verejne 2 a vice produktu (dva stoly), ".multi3" kdyz jsou 3 a vice (tri stoly; prepise i ".multi") - totez pravidlo
    ma klient v webapp/miniweb/miniweb-pages.js (P.home). `pocet` = pocet verejnych produktu."""
    if pocet < 2:
        return i18n
    out = dict(i18n)
    for k, v in i18n.items():
        if k.endswith(".multi"):
            out[k[:-6]] = v
    if pocet >= 3:
        for k, v in i18n.items():
            if k.endswith(".multi3"):
                out[k[:-7]] = v
    return out


def _faq(i18n):
    out, n = [], 1
    while ("faq.%d.q" % n) in i18n:
        out.append((i18n["faq.%d.q" % n], i18n.get("faq.%d.a" % n, "")))
        n += 1
    return out


def _home_body(i18n, prods, paths):
    h = ["<h1>%s</h1>" % _esc(i18n.get("home.h1") or i18n.get("home.title", "")), "<p>%s</p>" % _esc(i18n.get("home.lead", ""))]
    usp = [(i18n.get("home.usp%d.t" % n), i18n.get("home.usp%d.d" % n)) for n in range(1, 5) if i18n.get("home.usp%d.t" % n)]
    if usp:
        h.append("<h2>%s</h2><ul>%s</ul>" % (_esc(i18n.get("home.why_title", "")), "".join("<li><strong>%s</strong> %s</li>" % (_esc(a), _esc(b)) for a, b in usp)))
    if prods:
        h.append("<h2>%s</h2><ul>%s</ul>" % (_esc(i18n.get("home.products", "")), "".join('<li><a href="%s">%s</a></li>' % (_esc(paths["product"] + p["slug"]), _esc(p["name"])) for p in prods)))
    faq = _faq(i18n)
    if faq:
        h.append("<h2>%s</h2>%s" % (_esc(i18n.get("home.faq_title", "")), "".join("<details><summary>%s</summary><p>%s</p></details>" % (_esc(q), _esc(a)) for q, a in faq)))
    return "".join(h)


def _page(host, cfg, lang, i18n, brand, kind, title, desc, robots, canon, paths, body, ld, status, slug=None, boot_extra=None):
    shell = SHELL.get(kind) or "index.html"
    src = _versioned(open(os.path.join(WEBAPP, shell), encoding="utf-8").read())
    title = _trunc(title, 70)
    desc = _trunc(desc, 160)
    head = ['<link rel="canonical" href="%s">' % _esc(canon), '<meta name="description" content="%s">' % _esc(desc)]
    alts = cfg.get("alternates") or []
    if kind == "home" and alts and robots.startswith("index"):
        head.append('<link rel="alternate" hreflang="%s" href="%s">' % (_esc(lang.split("-")[0]), _esc(canon)))
        for a in alts:
            if a.get("lang") and a.get("href"):
                head.append('<link rel="alternate" hreflang="%s" href="%s">' % (_esc(a["lang"]), _esc(a["href"])))
        en = next((a for a in alts if a.get("lang") == "en"), None)
        if en or lang.split("-")[0] == "en":                                       # x-default = anglicka verze; na ANGLICKE strance ukazuje na ni samu (kazda stranka sady nese stejne odkazy)
            head.append('<link rel="alternate" hreflang="x-default" href="%s">' % _esc(en["href"] if en else canon))
    og_type = "product" if kind == "product" else "website"
    head += ['<meta property="og:site_name" content="%s">' % _esc(brand), '<meta property="og:type" content="%s">' % og_type, '<meta property="og:title" content="%s">' % _esc(title),
             '<meta property="og:description" content="%s">' % _esc(desc), '<meta property="og:url" content="%s">' % _esc(canon), '<meta property="og:locale" content="%s">' % _esc((cfg.get("locale") or lang).replace("-", "_")),
             '<meta name="twitter:card" content="summary">', '<meta name="twitter:title" content="%s">' % _esc(title), '<meta name="twitter:description" content="%s">' % _esc(desc)]
    head += [_ld(o) for o in ld]
    boot = {"page": kind if kind in SHELL else "home", "slug": slug, "pretty": True, "paths": paths}
    boot.update(boot_extra or {})
    out = re.sub(r'<html lang="[^"]*">', '<html lang="%s">' % _esc(lang), src, count=1)
    out = re.sub(r'<meta name="robots" content="[^"]*">', '<meta name="robots" content="%s">' % _esc(robots.replace(",", ", ")), out, count=1)
    out = re.sub(r"<title>.*?</title>", "<title>%s</title>" % _esc(title), out, count=1, flags=re.S)
    out = out.replace("</head>", "\n".join(head) + "\n</head>", 1)
    out = re.sub(r'(<main id="mwMain"[^>]*>).*?(</main>)', lambda m: m.group(1) + body + m.group(2), out, count=1, flags=re.S)
    out = re.sub(r'(<script src="/miniweb/miniweb\.js[^"]*"></script>)', lambda m: "<script>window.MW_BOOT=%s;</script>\n%s" % (json.dumps(boot, ensure_ascii=False).replace("<", "\\u003c"), m.group(1)), out, count=1)
    return out


def _draft_shell(host, rest):
    """Shop, ktery anonym nevidi (koncept): staticky shell BEZ meta (zustava noindex) + MW_BOOT, ať nahled pro staff funguje i na hezkych adresach (JS si
    produkt/kategorii dohleda podle slugu pod prihlasenym uzivatelem). Neznamy host = 404."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            sf = miniweb._storefront_by_host(cur, host)
    finally:
        conn.close()
    if not sf:
        return _not_found_plain(), 404
    lang = (sf.get("lang") or "en").lower()
    paths = PATHS.get(lang.split("-")[0], PATHS["en"])
    kind, slug = _classify("/" + rest, paths)
    if kind is None:
        return _not_found_plain(), 404
    src = _versioned(open(os.path.join(WEBAPP, SHELL[kind]), encoding="utf-8").read())
    boot = {"page": kind, "slug": slug, "pretty": True, "paths": paths}
    out = re.sub(r'(<script src="/miniweb/miniweb\.js[^"]*"></script>)', lambda m: "<script>window.MW_BOOT=%s;</script>\n%s" % (json.dumps(boot).replace("<", "\\u003c"), m.group(1)), src, count=1)
    return out, 200


def _not_found_plain():
    return "<!doctype html><meta name=robots content=noindex><title>404</title><h1>404</h1>"


@app.get("/api/miniweb/seo/", defaults={"rest": ""})
@app.get("/api/miniweb/seo/<path:rest>")
def miniweb_seo_page(rest):
    if rest in ("robots.txt", "sitemap.xml"):
        return _robots_or_sitemap(rest)
    try:
        text, status = _render(rest)
    except _Redirect as e:
        return Response("", status=301, headers={"Location": e.url, "Cache-Control": "public, max-age=3600"})
    resp = Response(text, status=status, mimetype="text/html")
    if status != 200 or 'name="robots" content="noindex' in text[:3000]:
        resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    resp.headers["Cache-Control"] = "public, max-age=300" if status == 200 else "no-store"
    return resp


def _robots_or_sitemap(which):
    host = _host()
    bare = _bare(host)
    st, cfg = _api("/api/miniweb/config", host)
    live = st == 200 and cfg and cfg.get("preview") is False
    if which == "robots.txt":
        txt = "User-agent: *\nDisallow: /\n"
        if live:
            paths = PATHS.get((cfg.get("lang") or "en").split("-")[0], PATHS["en"])
            txt = "User-agent: *\nDisallow: %s\nDisallow: /miniweb/cart.html\nDisallow: /*?*drafts=\nDisallow: /*?*shop=\nDisallow: /*?*preview=\nSitemap: https://%s/sitemap.xml\n" % (paths["cart"], bare)
        return Response(txt, mimetype="text/plain", headers={"Cache-Control": "public, max-age=300"})
    if not live:
        return Response("not found", status=404, mimetype="text/plain")
    paths = PATHS.get((cfg.get("lang") or "en").split("-")[0], PATHS["en"])
    cats = (_api("/api/miniweb/categories", host)[1] or {}).get("categories") or []
    prods = _all_products(host)
    urls = ["https://%s/" % bare] + ["https://%s%s%s" % (bare, paths["category"], c["slug"]) for c in cats] + ["https://%s%s%s" % (bare, paths["product"], p["slug"]) for p in prods] \
        + ["https://%s%s" % (bare, paths["contact"]), "https://%s%s" % (bare, paths["legal"])]
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join("  <url><loc>%s</loc></url>\n" % _esc(u) for u in urls) + "</urlset>\n"
    return Response(xml, mimetype="application/xml", headers={"Cache-Control": "public, max-age=300"})
