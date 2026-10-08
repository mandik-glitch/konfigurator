#!/usr/bin/env python3
"""Pripojeni domeny verejneho mini-shopu (bot16, 2026-10-03; zadani Robert pres bot3: SK shop ZIVE na baliace-stoly.top).

Postup je stejny jako u autovych mini-webu (PRISTUPY.md, AGENTS_LOG bot14), jen s OMEZENYM nginx vhostem (scripts/gen_miniweb_vhost.py):
  1. zona   - Cloudflare zona + DNS A (apex a www, proxied = oranzovy mrak, origin IP se navenek neukaze)
  2. ns     - nameservery domeny u OpenProvidera -> Cloudflare (PUT /v1beta/domains/<id>)
  3. aktivace - pockat, az zona prejde pending -> active (rádově minuty)
  4. cert   - Origin CA certifikat (hostnames: domena + *.domena, 15 let) + AOP leaf do zony; soubory do private-files/cloudflare-origin-ca/
  5. nginx  - ROOT krok (sandbox zapis do /etc/nginx a reload blokuje): scripts/miniweb_nginx_install.sh <domena> (jediny prikaz pro Roberta)
  6. overit - kontrola zive: HTTPS, noindex, whitelist, sken znacky (Logiman/konfigurator/vandrawee) na vsech vydavanych souborech

Vsechny kroky jsou DEFAULTNE JEN PLAN (nic se nezmeni); zmena jen s --apply. Tajemstvi (CLOUDFLARE_API_TOKEN, OPENPROVIDER_*) se cetou z
api/.env v procesu a NIKDY se nevypisuji.

POUZITI:
  scripts/miniweb_domena.py plan baliace-stoly.top            # jen cteni: stav vsech kroku
  scripts/miniweb_domena.py zona baliace-stoly.top [--apply]
  scripts/miniweb_domena.py ns baliace-stoly.top [--apply]
  scripts/miniweb_domena.py aktivace baliace-stoly.top
  scripts/miniweb_domena.py cert baliace-stoly.top [--apply]
  scripts/miniweb_domena.py overit baliace-stoly.top [--origin]   # --origin = mimo DNS primo na tenhle server (127.0.0.1)
"""
import argparse
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import urllib.error
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CA_DIR = os.path.join(REPO, "private-files", "cloudflare-origin-ca")
ORIGIN_IP = "75.119.132.164"
CF = "https://api.cloudflare.com/client/v4"
OP = "https://api.openprovider.eu/v1beta"
BRAND_RE = re.compile(r"logiman|konfigur[aá]tor|vandrawee|logi\s*(?:<[^>]*>\s*)*man\b", re.IGNORECASE)


def load_env():
    env = {}
    p = os.path.join(REPO, "api", ".env")
    for line in open(p, encoding="utf-8"):
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            env[k.strip()] = v
    return env


ENV = None


def _req(url, headers, data=None, method=None, timeout=90):
    body = json.dumps(data).encode() if data is not None else None
    r = urllib.request.Request(url, data=body, headers=dict({"Content-Type": "application/json"}, **headers), method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as x:
            return json.load(x)
    except urllib.error.HTTPError as e:
        try:
            return {"_http": e.code, "_body": json.loads(e.read().decode("utf-8", "replace"))}
        except Exception:
            return {"_http": e.code, "_body": "?"}


def cf(method, path, data=None):
    global ENV
    ENV = ENV or load_env()
    return _req(CF + path, {"Authorization": "Bearer " + ENV["CLOUDFLARE_API_TOKEN"]}, data, method)


_op_token = None


def op(method, path, data=None):
    global ENV, _op_token
    ENV = ENV or load_env()
    if not _op_token:
        t = _req(OP + "/auth/login", {}, {"username": ENV["OPENPROVIDER_USERNAME"], "password": ENV["OPENPROVIDER_PASSWORD"]})
        _op_token = (t.get("data") or {}).get("token")
        if not _op_token:
            raise SystemExit("OpenProvider login selhal (API access u kontaktu musi byt zapnuty, viz PRISTUPY.md)")
    return _req(OP + path, {"Authorization": "Bearer " + _op_token}, data, method)


def err(r):
    return "HTTP %s %s" % (r.get("_http"), json.dumps(r.get("_body"), ensure_ascii=False)[:300]) if isinstance(r, dict) and "_http" in r else None


def get_zone(domain):
    r = cf("GET", "/zones?name=" + domain)
    if err(r):
        raise SystemExit("Cloudflare: " + err(r))
    res = r.get("result") or []
    return res[0] if res else None


def account_id():
    r = cf("GET", "/zones?per_page=1")
    res = r.get("result") or []
    if not res:
        raise SystemExit("Nelze zjistit account id (zadna existujici zona v uctu)")
    return res[0]["account"]["id"]


def dns_records(zone_id):
    r = cf("GET", "/zones/%s/dns_records?per_page=100" % zone_id)
    return r.get("result") or []


def op_domain(domain):
    r = op("GET", "/domains?full_name=" + domain)
    res = (r.get("data") or {}).get("results") or []
    return res[0] if res else None


def cmd_plan(a):
    d = a.domain
    z = get_zone(d)
    print("Domena:", d)
    print(" [%s] Cloudflare zona: %s" % ("OK" if z else "  ", ("%s (%s) NS %s" % (z["id"][:8], z["status"], ", ".join(z.get("name_servers") or []))) if z else "neexistuje -> krok 'zona'"))
    if z:
        recs = [(r["type"], r["name"], r["content"], r["proxied"]) for r in dns_records(z["id"]) if r["type"] in ("A", "AAAA", "CNAME")]
        have = {(t, n) for t, n, c, p in recs if c == ORIGIN_IP and p}
        print(" [%s] DNS A %s a www.%s proxied -> origin: %s" % ("OK" if {("A", d), ("A", "www." + d)} <= have else "  ", d, d, recs or "zadne"))
    o = op_domain(d)
    nss = [n.get("name") for n in (o.get("name_servers") or [])] if o else None
    cf_ns = (z.get("name_servers") or []) if z else []
    print(" [%s] OpenProvider NS: %s%s" % ("OK" if o and cf_ns and sorted(nss) == sorted(cf_ns) else "  ", nss if o else "domena v uctu neni", "" if (o and cf_ns and sorted(nss) == sorted(cf_ns)) else " -> krok 'ns'"))
    print(" [%s] zona aktivni (NS delegace dobehla): %s" % ("OK" if z and z["status"] == "active" else "  ", z["status"] if z else "-"))
    pem = os.path.join(CA_DIR, "miniweb-origin-ca.pem")
    print(" [%s] Origin CA cert v private-files: %s" % ("OK" if os.path.isfile(pem) else "  ", "ano" if os.path.isfile(pem) else "ne -> krok 'cert' (az je zona active)"))
    print(" [%s] /etc/nginx/ssl/miniweb-origin-ca.pem: %s" % ("OK" if os.path.isfile("/etc/nginx/ssl/miniweb-origin-ca.pem") else "  ", "ano" if os.path.isfile("/etc/nginx/ssl/miniweb-origin-ca.pem") else "ne"))
    vh = "/etc/nginx/sites-enabled/miniweb-" + d
    print(" [%s] nginx vhost %s: %s" % ("OK" if os.path.exists(vh) else "  ", vh, "ano" if os.path.exists(vh) else "ne -> krok 'nginx' (root, jediny prikaz pro Roberta)"))
    try:
        sys.path.insert(0, os.path.join(REPO, "scripts"))
        from _env import get_conn
        c = get_conn()
        with c.cursor() as cur:
            cur.execute("SELECT id, slug, kind, status, lang FROM car_storefronts WHERE primary_domain=%s", (d,))
            sf = cur.fetchall()
            ms = []
            if sf:
                cur.execute("SELECT storefront_id, family, price_mode, currency, countries, inquiry_enabled FROM miniweb_shops WHERE storefront_id=%s", (sf[0]["id"],))
                ms = cur.fetchall()
        c.close()
        print(" [%s] storefront v DB (bot5): %s" % ("OK" if sf and ms else "  ", ("%s | miniweb_shops: %s" % (sf, ms)) if sf else "zadny radek car_storefronts s primary_domain=%s -> bot5" % d))
    except Exception as e:  # noqa: BLE001
        print(" [??] storefront v DB: nelze zjistit (%s)" % str(e)[:100])
    try:
        ns = subprocess.run(["dig", "+short", "NS", d, "@1.1.1.1"], capture_output=True, text=True, timeout=10).stdout.split()
        print(" [..] verejne NS (1.1.1.1): %s" % (ns or "zadne"))
    except Exception:
        pass
    return 0


def cmd_zona(a):
    d = a.domain
    z = get_zone(d)
    if not z:
        print("zona neexistuje -> %s" % ("VYTVORIM (account %s...)" % account_id()[:8] if a.apply else "vytvorila by se (bez --apply nic)"))
        if a.apply:
            r = cf("POST", "/zones", {"name": d, "account": {"id": account_id()}, "type": "full"})
            if err(r):
                raise SystemExit("Cloudflare: " + err(r))
            z = r["result"]
            print("zona vytvorena: %s (%s) NS %s" % (z["id"][:8], z["status"], ", ".join(z.get("name_servers") or [])))
    else:
        print("zona uz existuje: %s (%s) NS %s" % (z["id"][:8], z["status"], ", ".join(z.get("name_servers") or [])))
    if not z:
        return 0
    have = {(r["type"], r["name"]): r for r in dns_records(z["id"])}
    for name in (d, "www." + d):
        rec = have.get(("A", name))
        if rec and rec["content"] == ORIGIN_IP and rec["proxied"]:
            print("DNS A %s OK (proxied)" % name)
            continue
        print("DNS A %s -> %s" % (name, ("zapisu (proxied)" if a.apply else "zapsal bych (proxied)")))
        if a.apply:
            body = {"type": "A", "name": name, "content": ORIGIN_IP, "proxied": True, "ttl": 1}
            r = cf("PUT", "/zones/%s/dns_records/%s" % (z["id"], rec["id"]), body) if rec else cf("POST", "/zones/%s/dns_records" % z["id"], body)
            if err(r):
                raise SystemExit("Cloudflare DNS: " + err(r))
    return 0


def cmd_ns(a):
    d = a.domain
    z = get_zone(d)
    if not z:
        raise SystemExit("zona neexistuje - nejdriv krok 'zona'")
    want = z.get("name_servers") or []
    o = op_domain(d)
    if not o:
        raise SystemExit("domena %s neni v uctu OpenProvider" % d)
    cur = [n.get("name") for n in (o.get("name_servers") or [])]
    print("OpenProvider NS ted:", cur, "-> chci:", want)
    # DNSSEC: OpenProvider u nekterych TLD zapne podepsanou delegaci (DS zaznam v registru). Po presunu NS na Cloudflare by DS ukazoval na
    # STARE klice -> validujici resolvery vraci SERVFAIL a zona se neaktivuje (zjisteno 2026-10-03 u baliace-stoly.top). DS se proto
    # odstrani (is_dnssec_enabled=false); DNSSEC jde zapnout znovu az v Cloudflare (DS od Cloudflare).
    if o.get("is_dnssec_enabled"):
        print("DNSSEC u OpenProvidera ZAPNUTY (signedDelegation) ->", "VYPNU (odstrani se DS z registru)" if a.apply else "vypnul bych (bez --apply nic)")
        if a.apply:
            r = op("PUT", "/domains/%s" % o["id"], {"is_dnssec_enabled": False, "dnssec_keys": []})
            if err(r):
                raise SystemExit("OpenProvider DNSSEC: " + err(r))
            print("DNSSEC vypnut")
    if sorted(cur) == sorted(want):
        print("NS uz nastaveno")
        return 0
    if not a.apply:
        print("bez --apply nic nemenim")
        return 0
    r = op("PUT", "/domains/%s" % o["id"], {"name_servers": [{"name": n, "seq_nr": i + 1} for i, n in enumerate(want)]})
    if err(r):
        raise SystemExit("OpenProvider: " + err(r))
    print("NS prepnuty u OpenProvidera; zona prejde na active za minuty az hodiny (krok 'aktivace')")
    return 0


def cmd_aktivace(a):
    z = get_zone(a.domain)
    if not z:
        raise SystemExit("zona neexistuje")
    if z["status"] != "active":
        cf("PUT", "/zones/%s/activation_check" % z["id"])      # popostrci kontrolu; kdyz token nema pravo, jen se ignoruje
        z = get_zone(a.domain)
    print("zona %s: %s" % (a.domain, z["status"]))
    return 0 if z["status"] == "active" else 2


def _san_cert(pem):
    """DNS jmena v subjectAltName certifikatu (prazdny seznam, kdyz soubor chybi / nejde precist)."""
    if not os.path.isfile(pem):
        return []
    r = subprocess.run(["openssl", "x509", "-in", pem, "-noout", "-ext", "subjectAltName"], capture_output=True, text=True)
    return sorted(set(re.findall(r"DNS:([^,\s]+)", r.stdout)))


def cmd_cert(a):
    """Jeden SDILENY Origin CA certifikat pro VSECHNY mini-shopy (soubor miniweb-origin-ca.pem, nginx vhosty na nej odkazuji): hostnames = vsechny uz pokryte domeny + nova
    (+ wildcard). Kdyz nova domena v certifikatu chybi, vyda se novy KOMBINOVANY (stary zustane vedle jako .bak-<datum>, stejny klic); jinak se nic nevydava. Navic se do zony
    (idempotentne) nahraje AOP leaf, pokud ho zona nema (u prvni domeny to delal tenhle krok, dalsi zony ho dosud nedostaly) - bot16, 2026-10-07 (druha domena: packing-tables.top)."""
    d = a.domain
    z = get_zone(d)
    if not z or z["status"] != "active":
        raise SystemExit("zona musi byt active (Origin CA cert jinak Cloudflare odmitne kodem 1010) - krok 'aktivace'")
    key, csr, pem = [os.path.join(CA_DIR, "miniweb-origin-ca." + x) for x in ("key", "csr", "pem")]
    mam = _san_cert(pem)
    chce = sorted(set(mam) | {d, "*." + d})
    if os.path.isfile(pem) and set(chce) == set(mam):
        print("cert uz pokryva %s (sdileny %s: %s)" % (d, pem, ", ".join(mam)))
    else:
        print("hostnames noveho kombinovaneho certifikatu: %s (platnost 15 let, soubory %s; puvodne: %s)" % (", ".join(chce), CA_DIR, ", ".join(mam) or "nic"))
        if not a.apply:
            print("bez --apply nic nevytvarim")
        else:
            os.makedirs(CA_DIR, exist_ok=True)
            if not os.path.isfile(key):
                subprocess.run(["openssl", "req", "-new", "-newkey", "rsa:2048", "-nodes", "-keyout", key, "-out", csr, "-subj", "/CN=%s" % d], check=True, capture_output=True)
                os.chmod(key, 0o600)
            else:
                subprocess.run(["openssl", "req", "-new", "-key", key, "-out", csr, "-subj", "/CN=%s" % (mam[0] if mam else d)], check=True, capture_output=True)       # stejny klic, nove CSR
            r = cf("POST", "/certificates", {"hostnames": chce, "requested_validity": 5475, "request_type": "origin-rsa", "csr": open(csr).read()})
            if err(r):
                raise SystemExit("Cloudflare Origin CA: " + err(r))
            if os.path.isfile(pem):
                import datetime
                os.replace(pem, pem + ".bak-" + datetime.date.today().isoformat())
            open(pem, "w").write(r["result"]["certificate"])
            os.chmod(pem, 0o644)
            print("Origin CA cert vydan (hostnames %s), ulozen: %s" % (", ".join(_san_cert(pem)), pem))
            print("DALSI KROK (root, nasazeni certifikatu do nginx): bash scripts/miniweb_nginx_install.sh %s [--index <jazyk>] - zkopiruje novy cert pro VSECHNY vhosty a nginx -t s rollbackem" % d)
    # AOP leaf do zony (idempotentne)
    leaf, leafkey = os.path.join(CA_DIR, "aop-leaf.pem"), os.path.join(CA_DIR, "aop-leaf.key")
    ex = cf("GET", "/zones/%s/origin_tls_client_auth" % z["id"], None)
    if err(ex):
        print("AOP leaf: nelze zjistit stav zony (%s)" % err(ex))
    elif (ex.get("result") or []):
        print("AOP leaf v zone uz je (%d)" % len(ex["result"]))
    elif not a.apply:
        print("AOP leaf v zone chybi -> nahral by se (bez --apply nic)")
    else:
        r = cf("POST", "/zones/%s/origin_tls_client_auth" % z["id"], {"certificate": open(leaf).read(), "private_key": open(leafkey).read()})
        print("AOP leaf do zony:", err(r) or "OK")
    return 0


def _fetch(host, path, origin, method="GET", body=None, hdr=None):
    import http.client
    ctx = ssl.create_default_context()
    if origin:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        c = http.client.HTTPSConnection("127.0.0.1", 443, context=ctx, timeout=20)
    else:
        c = http.client.HTTPSConnection(host, 443, context=ctx, timeout=20)
    c.request(method, path, body=body, headers=dict({"Host": host, "User-Agent": "miniweb-overit/1"}, **(hdr or {})))
    r = c.getresponse()
    return r.status, {k.lower(): v for k, v in r.getheaders()}, r.read()


def cmd_overit(a):
    d, bad = a.domain, 0

    def ok(c, t):
        nonlocal bad
        bad += (not c)
        print("[%s] %s" % ("OK   " if c else "CHYBA", t))
    s, h, b = _fetch(d, "/", a.origin)
    ok(s == 200 and b"mwMain" in b, "HTTPS / vydava uvod mini-shopu (HTTP %s)" % s)
    # SEO vhost (gen_miniweb_vhost.py --index) se pozna podle robots.txt se Sitemap: -> indexace je zamerna, noindex se nema cekat (flag --index to jen vynuti)
    rs, _rh, rb = _fetch(d, "/robots.txt", a.origin)
    index_mode = a.index or (rs == 200 and b"Sitemap:" in rb)
    ok(("noindex" in h.get("x-robots-tag", "")) == (not index_mode), "X-Robots-Tag: %s (ocekavano %s)" % (h.get("x-robots-tag"), "bez noindex (SEO rezim)" if index_mode else "noindex"))
    scanned, files = [], ["/", "/miniweb/miniweb.js", "/miniweb/miniweb-pages.js", "/miniweb/miniweb.css", "/js/product-configurator.js", "/js/client-errors.js", "/css/product-configurator.css", "/css/v3d.css", "/js/v3d/viewer3d.js"]
    i18n_dir = os.path.join(REPO, "webapp", "miniweb", "i18n")
    for lg in sorted(f[:-5] for f in os.listdir(i18n_dir) if re.match(r"^[a-z]{2}\.json$", f)):       # vsechny jazykove soubory (sk, en, cs, de, hu ...) - demo.*.json se tu neskenuje, ma vlastni kontrolu nize
        files.append("/miniweb/i18n/%s.json" % lg)
    files += ["/miniweb/index.html", "/miniweb/category.html", "/miniweb/product.html", "/miniweb/cart.html", "/miniweb/contact.html", "/miniweb/legal.html"]
    for f in files:
        s, h, b = _fetch(d, f, a.origin)
        if s != 200:
            continue
        scanned.append(f)
        t = b.decode("utf-8", "replace")
        m = BRAND_RE.search(t)
        ok(not m, "bez znacky: %s%s" % (f, "" if not m else "  <-- %r" % t[max(0, m.start() - 30):m.end() + 30]))
    ok(len(scanned) >= 12, "skenovano souboru: %d" % len(scanned))
    for p in ("/product.html", "/login.html", "/admin.html", "/scene.html", "/api/auth/me", "/api/products", "/miniweb/demo-api.js", "/miniweb/config.sk.json", "/miniweb/i18n/demo.sk.json", "/katalog/product_4934.glb"):
        s, h, b = _fetch(d, p, a.origin)
        ok(s == 404, "zablokovano: %s -> %s" % (p, s))
    for p in ("/api/miniweb/config", "/api/miniweb/categories", "/api/miniweb/products", "/api/miniweb/legal"):
        s, h, b = _fetch(d, p, a.origin)
        t = b.decode("utf-8", "replace")
        ok(s == 200, "API %s -> %s" % (p, s))
        if s == 200:
            if p == "/api/miniweb/config":
                # nazev prodejce (zakonna identifikace z company_info, Robert ji vyslovne chce v kontaktu) neni "znacka v textu" - pred kontrolou se z config vyradi
                jc = json.loads(t)
                (jc.get("contact") or {}).pop("name", None)
                ok(not BRAND_RE.search(json.dumps(jc, ensure_ascii=False)), "API %s bez znacky (mimo nazev prodejce v kontaktu)" % p)
            elif p != "/api/miniweb/legal":
                ok(not BRAND_RE.search(t), "API %s bez znacky" % p)
            if p == "/api/miniweb/config":
                j = json.loads(t)
                ok(j.get("preview") is False and "email" not in (j.get("contact") or {}), "config: preview=false, bez e-mailu (preview=%s)" % j.get("preview"))
            if "@" in t and p != "/api/miniweb/legal":
                ok(not re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", t), "API %s neobsahuje e-mailovou adresu" % p)
    print("\n==> %s" % ("VSE OK" if not bad else "%d CHYB" % bad))
    return 1 if bad else 0


def cmd_cache(a):
    """Cloudflare cache zony mini-shopu: (1) Browser Cache TTL = 0 ("respektovat hlavicky originu" - jinak CF posila prohlizeci max-age 4 h i kdyz origin
    vraci no-cache a po zmene robots.txt/sitemap/JS zustane svet u stare verze), (2) purge celé cache zony (zona je jen tenhle shop). Bez --apply jen vypise stav."""
    z = get_zone(a.domain)
    if not z:
        raise SystemExit("zona neexistuje")
    r = cf("GET", "/zones/%s/settings/browser_cache_ttl" % z["id"])
    print("Browser Cache TTL: %s" % (err(r) or r["result"]["value"]))
    if not a.apply:
        print("(bez --apply nic nemenim; s --apply nastavim 0 = respektovat hlavicky originu a smazu cache zony)")
        return 0
    r = cf("PATCH", "/zones/%s/settings/browser_cache_ttl" % z["id"], {"value": 0})
    print("nastaveni Browser Cache TTL = 0:", err(r) or "OK")
    r = cf("POST", "/zones/%s/purge_cache" % z["id"], {"purge_everything": True})
    print("purge cache zony:", err(r) or "OK")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["plan", "zona", "ns", "aktivace", "cert", "overit", "cache"])
    ap.add_argument("domain")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--origin", action="store_true")
    ap.add_argument("--index", action="store_true", help="overit: ocekava se, ze noindex je vypnuty")
    a = ap.parse_args()
    return {"plan": cmd_plan, "zona": cmd_zona, "ns": cmd_ns, "aktivace": cmd_aktivace, "cert": cmd_cert, "overit": cmd_overit, "cache": cmd_cache}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
