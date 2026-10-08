#!/usr/bin/env python3
"""
Generátor nginx vhostů pro car_storefronts (mini-eshopy per model auta).

Robert (přes toscanaccio-0b, 2026-08-29): "nemělo by to mít vlastní
administraci" - stejný princip platí i pro nasazení: přidání dalšího
mini-eshopu má být "přidej řádek do car_storefronts + spusť tenhle
skript", ne ruční kopírování/úprava nginx configu pro každou doménu
zvlášť (viz AGENTS_LOG.md pro celý návrh architektury).

CO TENHLE SKRIPT DĚLÁ: pro každý car_storefronts řádek se status='live'
vygeneruje/aktualizuje /etc/nginx/sites-available/storefront-<slug> a
symlink do sites-enabled/, pak (volitelně) reloadne nginx.

CO TENHLE SKRIPT NEDĚLÁ (mimo rozsah, chybí přístupy):
  - Nezakládá Cloudflare zónu, nenastavuje DNS proxy (oranžový mrak),
    negeneruje/nestahuje Cloudflare Origin CA certifikát. Robertovo
    schválené rozhodnutí (viz AGENTS_LOG.md) je Origin CA cert MÍSTO
    certbotu per doména - tenhle skript proto CÍLENĚ nevolá certbot,
    ale zatím ani Cloudflare API (bot14 k tomu nemá API token v
    api/.env - `grep -i cloudflare api/.env` nic nenašel). Dokud
    certifikát neexistuje na disku, vygenerovaný vhost na něj jen
    ukáže cestou (viz ORIGIN_CERT_*), nginx -t pak spadne, dokud
    soubor nevznikne - to je ZÁMĚRNĚ hlasitá chyba, ne tichý fallback
    na certbot/HTTP.
  - Nemění nameservery na OpenProvideru.
  Tyhle kroky viz AGENTS_LOG.md ("Doplněný návrh: Cloudflare vrstva") -
  potřebují Robertovo Cloudflare/OpenProvider API přihlášení, které
  tahle session nemá.

POUŽITÍ:
  scripts/gen_storefront_vhosts.py                # dry-run, jen vypíše na stdout
  scripts/gen_storefront_vhosts.py --write         # zapíše do sites-available/
  scripts/gen_storefront_vhosts.py --write --reload  # + nginx -t && systemctl reload nginx
  scripts/gen_storefront_vhosts.py --slug fiat-ducato  # jen 1 konkretni storefront

Bezpečnost: --write nikdy nemaže/nepřepisuje vhosty, které tenhle
skript nevygeneroval (pozná podle hlavičky "# GENEROVANO
gen_storefront_vhosts.py" v souboru) - ochrana proti přepsání ručně
upraveného configu (např. vandrawee, konfigurator, remeslnik-pro).
"""
import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

GENERATED_HEADER = "# GENEROVANO gen_storefront_vhosts.py - RUCNI ZMENY SE PRI DALSIM SPUSTENI PRETISKNOU\n"

SITES_AVAILABLE = "/etc/nginx/sites-available"
SITES_ENABLED = "/etc/nginx/sites-enabled"

# Cesty k Origin CA certifikatum, KLICOVANE podle
# car_storefronts.origin_cert_group (bot14, 2026-09-01 - pridano pri
# zakladani standalone domen per model auta vedle fiat-autovestavby.top,
# viz AGENTS_LOG.md "varianta C"). Kazda skupina domen ma VLASTNI
# Origin CA cert (izolace - reissue/rotace jedne skupiny se nedotkne
# certifikatu druhe), ale sdileji stejnou AOP CA (leaf cert se jen
# re-uploaduje do kazde nove zony, viz PRISTUPY.md).
CERT_GROUPS = {
    "fiat-autovestavby": (
        "/etc/nginx/ssl/storefronts-origin-ca.pem",
        "/etc/nginx/ssl/storefronts-origin-ca.key",
    ),
    "model-standalone": (
        "/etc/nginx/ssl/storefronts-standalone-origin-ca.pem",
        "/etc/nginx/ssl/storefronts-standalone-origin-ca.key",
    ),
}

# Authenticated Origin Pulls - CA, co podepsala leaf cert nahrany do
# Cloudflare (viz private-files/cloudflare-origin-ca/aop-ca.pem). Nginx
# timhle overuje, ze pripojeni skutecne prislo od Cloudflare (az bude
# AOP na Cloudflare strane zapnuty - viz PRISTUPY.md).
AOP_CA_CERT_PATH = "/etc/nginx/ssl/storefronts-aop-ca.pem"


def load_env(path):
    env = {}
    if not os.path.isfile(path):
        return env
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.lstrip().startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            env.setdefault(k, v)
    return env


def fetch_live_storefronts(slug_filter=None):
    for k, v in load_env(os.path.join(os.path.dirname(__file__), "..", "api", ".env")).items():
        os.environ.setdefault(k, v)
    import app  # noqa: E402 - az po naplneni os.environ z .env

    conn = app.get_conn()
    try:
        with conn.cursor() as cur:
            # kind 'miniweb' (verejny mini-shop, omezeny whitelist vhost) generuje scripts/gen_miniweb_vhost.py + miniweb_nginx_install.sh, ne tenhle autovy sablonovy vhost
            sql = "SELECT id, name, slug, primary_domain, origin_cert_group, status FROM car_storefronts WHERE status='live' AND kind IN ('model','brand_hub')"
            params = ()
            if slug_filter:
                sql += " AND slug=%s"
                params = (slug_filter,)
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


def _shared_locations():
    # Stejny upstream/webapp root jako existujici konfigurator/vandrawee
    # vhosty (viz /etc/nginx/sites-available/vandrawee) - zadny novy
    # backend proces, jen dalsi vstupni bod do stejne aplikace. Sdilene
    # mezi 80 i 443 blokem (viz render_vhost - proc oba servi stejny
    # obsah, ne jen redirect).
    return f"""    # skutecna IP navstevnika za Cloudflare (bot16 2026-10-03): BEZ toho by se limity aplikace (login, poptavky, kosik) pocitaly na IP
    # Cloudflare uzlu a blokovaly nesouvisejici navstevniky. Snippet vytvari scripts/nginx_cf_realip_install.sh (rozsahy z cloudflare.com/ips-*).
    include /etc/nginx/snippets/cloudflare-realip.conf;
    client_max_body_size 20M;

    location /api/ {{
        proxy_pass http://konfigurator_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }}

    location /content-files/ {{
        alias /opt/konfigurator/webapp/content-files/;
    }}

    # bot3 2026-09-08 (hloubkovy test po Robertove nalezu na mobilu):
    # scene.html by tady padalo do obecne "location /" nize a
    # servirovalo se ÚPLNĚ bez přihlášení, stejná díra jako na hlavní
    # domene autovestavby.logiman.cz (viz api/app.py::scene_html_gate
    # a AGENTS_LOG.md). Musi projit pres Flask, ne static root - stejna
    # staff-only politika (Robert 2026-09-03: "zákazníkům přístup do
    # scény neumožníme") plati na VŠECH vstupnich bodech, ne jen na
    # hlavni domene.
    location = /scene.html {{
        proxy_pass http://konfigurator_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}

    # bot14 2026-08-30 (skutecna chyba nalezena pri prvnim nasazeni):
    # PRESNA shoda na "/" MUSI byt zvlast, PRED obecnym "location /" -
    # try_files pro $uri="/" by jinak nasel existujici ADRESAR
    # /opt/konfigurator/webapp/ a nginx by kvuli vychozimu "index"
    # smerniku tise doservoval webapp/index.html (HLAVNI web) misto
    # padu na @storefront_ssr. Presne tenhle bug puvodne rozbil vsechny
    # prehledove stranky (hub i kazdy nameplate) - varianty (/l2h1 apod.)
    # fungovaly spravne, protoze pro ne zadny takovy soubor/adresar
    # neexistuje.
    location = / {{
        proxy_pass http://konfigurator_api/api/storefront-page;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}

    # Staticke soubory sdilene s hlavnim webem (login.html, spolecne CSS/
    # JS, ...) - try_files nejdriv zkusi realny soubor na disku, teprve
    # kdyz zadny neexistuje (napr. /l2h2, /ci14 - cista URL varianty),
    # spadne na pojmenovanou @storefront_ssr location nize. Diky tomu
    # netreba vyjmenovavat kazdou statickou stranku zvlast (na rozdil od
    # vandrawee vhostu, ktery ma vlastni try_files -> index.html SPA).
    #
    # bot10 2026-10-01: modely sestav (Vandr) a karoserii NESMI byt verejne
    # (ochrana 3D modelu) - pred touto opravou je mini-weby servirovaly 200.
    # Mini-weby je nepotrebuji, zamestnanci chodi pres autovestavby.logiman.cz
    # (tam staff_required + X-Accel).
    location ^~ /katalog/vandr/ {{ return 404; }}
    location ^~ /katalog/car_bodies/ {{ return 404; }}

    location / {{
        root /opt/konfigurator/webapp;
        add_header Cache-Control "no-cache";
        try_files $uri $uri/ @storefront_ssr;
    }}

    # SSR stranka (prehled nameplate / detail 1 varianty) - viz
    # api/car_storefronts.py::storefront_page_overview / _variant.
    # Interni named location (nedostupna zvenku primo), Host hlavicka
    # jde skrz beze zmeny - Flask si domenu resolvuje sam
    # (resolve_storefront()), takze $request_uri sedi 1:1 na verejnou URL.
    location @storefront_ssr {{
        proxy_pass http://konfigurator_api/api/storefront-page$request_uri;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}"""


def render_vhost(storefront):
    domain = storefront["primary_domain"]
    slug = storefront["slug"]
    locations = _shared_locations()
    cert_group = storefront.get("origin_cert_group") or "fiat-autovestavby"
    if cert_group not in CERT_GROUPS:
        raise SystemExit(f"Neznamy origin_cert_group '{cert_group}' u {domain} - doplnit do CERT_GROUPS v tomhle skriptu.")
    cert_path, cert_key_path = CERT_GROUPS[cert_group]
    return f"""{GENERATED_HEADER}# car_storefronts.id={storefront['id']} ({storefront['name']}) - {domain}
# origin_cert_group={cert_group}
# Cloudflare vrstva (proxy/orange cloud, DNS nameservery, WAF/AOP) neni
# soucasti tohohle souboru - resi se u registratora/Cloudflare, mimo git.
#
# bot14 2026-08-30: port 80 servi STEJNY obsah jako 443 (ne jen redirect
# na https) - Cloudflare SSL/TLS mod (Flexible = HTTP k originu, Full/
# Strict = HTTPS) se v dobe generovani nepodarilo overit/nastavit API
# tokenem (chybejici "Zone Settings" opravneni, viz PRISTUPY.md), takze
# vhost musi fungovat spravne v OBOU pripadech. Cloudflare sam navstevniku
# vzdy ukazuje https bez ohledu na to, jak sahne na origin - zadne
# bezpecnostni oslabeni pro navstevnika, jen origin-side robustnost.
# Authenticated Origin Pulls (AOP) leaf cert je nahrany a pripraveny
# (ssl_verify_client optional - meni se na "on" az bude AOP na Cloudflare
# strane skutecne zapnuty, viz PRISTUPY.md - "enable" krok blokovan
# ruznou autentizacni schematem API tokenu, ne opravnenim).

server {{
    listen 443 ssl;
    server_name {domain} www.{domain};
    ssl_certificate {cert_path};
    ssl_certificate_key {cert_key_path};
    ssl_client_certificate {AOP_CA_CERT_PATH};
    ssl_verify_client optional;

{locations}
}}

server {{
    listen 80;
    server_name {domain} www.{domain};

{locations}
}}
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="zapsat do /etc/nginx/sites-available (jinak jen dry-run na stdout)")
    ap.add_argument("--reload", action="store_true", help="po zapsani spustit 'nginx -t' a reload (jen s --write)")
    ap.add_argument("--slug", help="omezit jen na 1 konkretni storefront (car_storefronts.slug)")
    args = ap.parse_args()

    storefronts = fetch_live_storefronts(slug_filter=args.slug)
    if not storefronts:
        print("Zadny storefront se status='live' (pripadne s timhle slugem) nenalezen.", file=sys.stderr)
        return 1

    changed = []
    for sf in storefronts:
        vhost_name = f"storefront-{sf['slug']}"
        content = render_vhost(sf)
        if not args.write:
            print(f"\n===== {vhost_name} ({sf['primary_domain']}) - DRY RUN, nezapsano =====")
            print(content)
            continue

        target = os.path.join(SITES_AVAILABLE, vhost_name)
        if os.path.isfile(target):
            with open(target, encoding="utf-8") as f:
                existing_head = f.readline()
            if existing_head != GENERATED_HEADER:
                print(f"PRESKOCENO: {target} existuje a nebyl vygenerovan timhle skriptem (chybi hlavicka) - nechci prepsat rucni config.", file=sys.stderr)
                continue

        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        enabled_link = os.path.join(SITES_ENABLED, vhost_name)
        if not os.path.islink(enabled_link):
            os.symlink(target, enabled_link)
        changed.append(vhost_name)
        print(f"OK: {target} zapsan, {enabled_link} symlink hotovy.")

    if args.write and changed:
        used_groups = {sf.get("origin_cert_group") or "fiat-autovestavby" for sf in storefronts}
        missing = [
            g for g in used_groups
            if not (os.path.isfile(CERT_GROUPS[g][0]) and os.path.isfile(CERT_GROUPS[g][1]))
        ]
        if missing:
            print(
                f"\nUPOZORNENI: chybi Origin CA cert pro skupinu(y) {missing} "
                "(Origin CA certifikat musi nekdo s Cloudflare pristupem vygenerovat/nahrat rucne, "
                "viz AGENTS_LOG.md) - 'nginx -t' nize pravdepodobne selze, dokud nevzniknou.",
                file=sys.stderr,
            )
        if args.reload:
            subprocess.run(["nginx", "-t"], check=True)
            subprocess.run(["systemctl", "reload", "nginx"], check=True)
            print("nginx -t OK, reload proveden.")
        else:
            print("\nZbyva rucne: 'nginx -t' a 'systemctl reload nginx' (nebo spust znovu s --reload).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
