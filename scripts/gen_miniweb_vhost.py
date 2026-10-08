#!/usr/bin/env python3
"""Generator OMEZENEHO nginx vhostu pro verejny mini-shop (webapp/miniweb) - bot16, 2026-10-03.

PROC NE gen_storefront_vhosts.py: autove mini-weby (car_storefronts kind model/brand_hub) servi pres `location /` cely webapp/ (nalez
bot16 2026-10-01: 13 stranek se znackou) a proxuji CELE /api/. Verejny mini-shop pro cizi trh (Robert 2026-10-03: SK shop ZIVE na
baliace-stoly.top, bez znacky) smi vydat JEN to, co potrebuje - WHITELIST, vse ostatni 404:
  /                         -> webapp/miniweb/index.html (kdyz URL zustava "/")
  /miniweb/*                -> staticke stranky mini-shopu (BEZ demo-api.js, demo.<jazyk>.json a config*.json = ukazkova data jen pro staff nahled)
  /js/product-configurator.js, /js/client-errors.js, /js/v3d/*, /css/product-configurator.css, /css/v3d.css   (modul voleb + 3D prohlizec)
  /api/miniweb/*            -> Flask (katalog, config, legal, poptavka)
  /api/shop/configurator/*  -> Flask (resolve, model, podepsany GLB)
  /api/shop/products/<id>/configurator -> Flask (schema voleb)
  /api/client-errors        -> Flask (hlaseni chyb prohlizece)
Dalsi vlastnosti: skutecna IP navstevnika za Cloudflare (set_real_ip_from + CF-Connecting-IP; BEZ toho by se limity aplikace - poptavka
5/10 min, resolve 120/min - pocitaly na IP Cloudflare uzlu a blokovaly by nesouvisejici navstevniky), X-Robots-Tag noindex + robots.txt
Disallow DOKUD se nespusti SEO (--index --lang <jazyk> je vypne), nosniff/referrer hlavicky, client_max_body_size 1m.
SEO rezim (--index): hezke adresy (/produkt/<slug>, /kategoria/<slug>, /kontakt ...), "/", /robots.txt a /sitemap.xml jdou do Flasku (api/miniweb_seo.py:
server-side title/description/canonical/hreflang/og/JSON-LD + staticky H1/uvod/FAQ). Flask sam rozhoduje o indexaci: index,follow JEN u shopu ve stavu live,
koncept dostane noindex + Disallow - vhost tedy muze byt v SEO rezimu uz pred spustenim shopu. Cesty podle jazyka se berou z api/miniweb_seo.py (PATHS).

POUZITI:
  scripts/gen_miniweb_vhost.py baliace-stoly.top                 # vypise vhost na stdout
  scripts/gen_miniweb_vhost.py baliace-stoly.top --index --lang sk   # SEO rezim (server-side meta, hezke adresy, sitemap, robots z Flasku)
  scripts/gen_miniweb_vhost.py baliace-stoly.top --out FILE      # zapise do souboru (zapis do /etc/nginx dela instalator, ne tenhle skript)
"""
import argparse
import ast
import os
import sys

GENERATED_HEADER = "# GENEROVANO gen_miniweb_vhost.py - RUCNI ZMENY SE PRI DALSIM SPUSTENI PRETISKNOU\n"
CERT_PEM = "/etc/nginx/ssl/miniweb-origin-ca.pem"
CERT_KEY = "/etc/nginx/ssl/miniweb-origin-ca.key"
AOP_CA = "/etc/nginx/ssl/storefronts-aop-ca.pem"
REALIP_SNIPPET = "/etc/nginx/snippets/cloudflare-realip.conf"
WEBAPP = "/opt/konfigurator/webapp"


def _proxy(extra=""):
    return f"""        proxy_pass http://konfigurator_api{extra};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;"""


def seo_paths(lang):
    """PATHS z api/miniweb_seo.py (jediny zdroj hezkych adres; modul se neimportuje, protoze tahne cely app)."""
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api", "miniweb_seo.py"), encoding="utf-8").read()
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "PATHS":
            return ast.literal_eval(node.value)[lang]
    raise SystemExit("PATHS v api/miniweb_seo.py nenalezeno")


def seo_locations(lang):
    paths = seo_paths(lang)
    exact = [paths[k] for k in ("contact", "legal", "cart", "shop")]
    prefix = [paths["category"], paths["product"]]
    regex = "^/(" + "|".join(p.strip("/") for p in prefix) + ")/[a-z0-9][a-z0-9-]{0,120}$"
    rewrite = "        rewrite ^/(.*)$ /api/miniweb/seo/$1 break;\n" + _proxy().replace("proxy_pass http://konfigurator_api;", "proxy_pass http://konfigurator_api;")
    out = f"""    # SEO: stranky renderuje Flask (api/miniweb_seo.py) - server-side meta, JSON-LD, staticky obsah; JS ho pak prevezme
    location = / {{
        rewrite ^ /api/miniweb/seo/ break;
{_proxy()}
    }}
    location = /robots.txt {{
        rewrite ^ /api/miniweb/seo/robots.txt break;
{_proxy()}
    }}
    location = /sitemap.xml {{
        rewrite ^ /api/miniweb/seo/sitemap.xml break;
{_proxy()}
    }}
    location ~ "{regex}" {{
{rewrite}
    }}
"""
    for pth in exact:
        out += f"""    location = {pth} {{
        rewrite ^/(.*)$ /api/miniweb/seo/$1 break;
{_proxy()}
    }}
"""
    out += "    # primy pristup k SEO endpointu zvenku neni (duplicity); interne se k nemu dostane jen rewrite vyse\n    location ^~ /api/miniweb/seo/ { return 404; }\n"
    return out


def locations(noindex=True, lang=None):
    robots = ""
    if noindex:
        robots = """    location = /robots.txt {
        default_type text/plain;
        return 200 "User-agent: *\\nDisallow: /\\n";
    }
"""
    return f"""    include {REALIP_SNIPPET};
    client_max_body_size 1m;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
{'    add_header X-Robots-Tag "noindex, nofollow" always;' if noindex else ''}

{robots}    location = /favicon.ico {{ return 204; }}

{seo_locations(lang) if lang and not noindex else f"""    # uvodni stranka na "/"
    location = / {{
        root {WEBAPP};
        rewrite ^ /miniweb/index.html break;
        expires -1;
    }}
"""}
    # staticke stranky mini-shopu; ukazkova data a nahled pro staff (demo) se NEVYDAVAJI
    location ^~ /miniweb/ {{
        root {WEBAPP};
        expires -1;
    }}
    location = /miniweb/demo-api.js {{ return 404; }}
    location ^~ /miniweb/i18n/demo. {{ return 404; }}
    location ^~ /miniweb/config {{ return 404; }}

    # modul voleb a 3D prohlizec (jen presne tyto cesty, ne cely /js a /css)
    location = /js/product-configurator.js {{ root {WEBAPP}; expires 1h; }}
    location = /js/client-errors.js {{ root {WEBAPP}; expires 1h; }}
    location ^~ /js/v3d/ {{ root {WEBAPP}; expires 1h; }}
    location = /js/pdc-layout.js {{ root {WEBAPP}; expires 1h; }}                     # mrizka oken karty stolu (sdilena se strankou Generator stolu; bot8)
    location = /js/v3d-ovladani.js {{ root {WEBAPP}; expires 1h; }}                  # ovladani primo ve 3D (tazeni uchytu, nabidka pravym tlacitkem; bot8)
    location = /css/product-configurator.css {{ root {WEBAPP}; expires 1h; }}
    location = /css/v3d.css {{ root {WEBAPP}; expires 1h; }}
    # zivy 3D prvek "Pripni cokoli" na karte stolu (bot10): skript + dva datove soubory, jen presne tyto cesty
    location = /js/pripni-cokoli-tile.js {{ root {WEBAPP}; expires 1h; }}
    location = /pripni-cokoli/texty.json {{ root {WEBAPP}; expires 1h; }}
    location = /pripni-cokoli/stavebnice-demo.glb {{ root {WEBAPP}; expires 1h; }}
    location = /pripni-cokoli/stavebnice-demo-30x30.glb {{ root {WEBAPP}; expires 1h; }}
    # schema hlavniho profilu v okne karty stolu (kresba prurezu od bot10): jen dva existujici rozmery
    location = /pripni-cokoli/schema-30x30-d8.svg {{ root {WEBAPP}; expires 1h; }}
    location = /pripni-cokoli/schema-40x40-d10.svg {{ root {WEBAPP}; expires 1h; }}

    # API: jen to, co mini-shop pouziva
    location ^~ /api/miniweb/ {{
{_proxy()}
    }}
    location ^~ /api/shop/configurator/ {{
{_proxy()}
    }}
    location ~ ^/api/shop/products/[0-9]+/configurator$ {{
{_proxy()}
    }}
    location = /api/client-errors {{
{_proxy()}
    }}

    # cokoli jineho: nic
    location / {{ return 404; }}"""


def render(domain, noindex=True, lang=None):
    loc = locations(noindex, lang)
    seo = bool(lang) and not noindex
    names = domain if seo else f"{domain} www.{domain}"       # SEO rezim: www ma vlastni server (301 na holou domenu, jedna kanonicka adresa)
    www = f"""
# www -> holá doména (301): jedna kanonická adresa, žádné duplicity pro vyhledávače
server {{
    listen 443 ssl;
    server_name www.{domain};
    ssl_certificate {CERT_PEM};
    ssl_certificate_key {CERT_KEY};
    return 301 https://{domain}$request_uri;
}}
server {{
    listen 80;
    server_name www.{domain};
    return 301 https://{domain}$request_uri;
}}
""" if seo else ""
    return f"""{GENERATED_HEADER}# verejny mini-shop {domain} (omezeny whitelist, viz scripts/gen_miniweb_vhost.py) - noindex={'ANO' if noindex else 'NE'}
# Cloudflare proxy/DNS/NS se resi mimo tenhle soubor (scripts/miniweb_domena.py).

server {{
    listen 443 ssl;
    server_name {names};
    ssl_certificate {CERT_PEM};
    ssl_certificate_key {CERT_KEY};
    ssl_client_certificate {AOP_CA};
    ssl_verify_client optional;

{loc}
}}

# port 80 servi stejny obsah (Cloudflare SSL mod Flexible = HTTP k originu; Full/Strict = HTTPS) - stejna robustnost jako autove mini-weby
server {{
    listen 80;
    server_name {names};

{loc}
}}
{www}"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("domain")
    ap.add_argument("--index", action="store_true", help="SEO rezim: bez statickeho noindex/robots, hezke adresy a meta z Flasku (vyzaduje --lang); indexuje se jen live shop")
    ap.add_argument("--lang", help="jazyk shopu (sk/en/cs) - cesty hezkych adres, se --index")
    ap.add_argument("--out", help="zapsat do souboru")
    a = ap.parse_args()
    if a.index and not a.lang:
        ap.error("--index vyzaduje --lang")
    text = render(a.domain, noindex=not a.index, lang=a.lang)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
