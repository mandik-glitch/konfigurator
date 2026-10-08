#!/usr/bin/env python3
"""Test omezeneho nginx vhostu (scripts/gen_miniweb_vhost.py) na ZKUSEBNI instanci nginx (vlastni prefix, porty 18080/18443, vlastni
samopodepsany cert, falesny upstream) - ostra sluzba ani /etc/nginx se nedotkne. Spusteni: api/venv/bin/python3 scripts/2026-10-03_miniweb_domena_testy/test_vhost.py"""
import http.client, json, os, shutil, signal, ssl, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import gen_miniweb_vhost as G

TMP = tempfile.mkdtemp(prefix="mwvh_", dir=os.environ.get("TESTTMP", "/tmp"))
bad = 0; total = 0
def ok(c, t):
    global bad, total
    total += 1; bad += (not c); print("[%s] %s" % ("OK   " if c else "CHYBA", t))

class Stub(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _do(self):
        n = int(self.headers.get("Content-Length") or 0); body = self.rfile.read(n) if n else b""
        out = json.dumps({"path": self.path, "xreal": self.headers.get("X-Real-IP"), "host": self.headers.get("Host"), "xff": self.headers.get("X-Forwarded-For"), "method": self.command, "len": len(body)}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(out))); self.end_headers(); self.wfile.write(out)
    do_GET = do_POST = _do

def run_case(noindex, lang=None):
    d = os.path.join(TMP, "i" if noindex else ("s" if lang else "x")); os.makedirs(d + "/logs", exist_ok=True)
    key, crt = d + "/t.key", d + "/t.crt"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", key, "-out", crt, "-days", "1", "-subj", "/CN=test"], check=True, capture_output=True)
    open(d + "/realip.conf", "w").write("set_real_ip_from 127.0.0.1;\nreal_ip_header CF-Connecting-IP;\n")
    vh = G.render("test.example", noindex=noindex, lang=lang).replace(G.CERT_PEM, crt).replace(G.CERT_KEY, key).replace(G.REALIP_SNIPPET, d + "/realip.conf")
    vh = vh.replace("ssl_client_certificate " + G.AOP_CA + ";", "").replace("ssl_verify_client optional;", "")
    vh = vh.replace("listen 443 ssl;", "listen 127.0.0.1:18443 ssl;").replace("listen 80;", "listen 127.0.0.1:18080;")
    open(d + "/vhost.conf", "w").write(vh)
    port = 18081
    conf = f"""worker_processes 1; daemon off; pid {d}/nginx.pid; error_log {d}/logs/error.log;
events {{ worker_connections 64; }}
http {{ include /etc/nginx/mime.types; access_log off; client_body_temp_path {d}/t1; proxy_temp_path {d}/t2; fastcgi_temp_path {d}/t3; uwsgi_temp_path {d}/t4; scgi_temp_path {d}/t5;
  upstream konfigurator_api {{ server 127.0.0.1:{port}; }}
  include {d}/vhost.conf; }}
"""
    open(d + "/nginx.conf", "w").write(conf)
    t = subprocess.run(["nginx", "-t", "-c", d + "/nginx.conf", "-p", d], capture_output=True, text=True)
    ok(t.returncode == 0, ("noindex" if noindex else "index") + ": nginx -t projde na vygenerovanem vhostu" + ("" if t.returncode == 0 else " | " + t.stderr[-300:]))
    if t.returncode != 0: return None
    proc = subprocess.Popen(["nginx", "-c", d + "/nginx.conf", "-p", d], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.2)
    return proc

def get(path, method="GET", body=None, hdr=None, port=18443):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    c = http.client.HTTPSConnection("127.0.0.1", port, context=ctx, timeout=10) if port == 18443 else http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.request(method, path, body=body, headers=dict({"Host": "test.example"}, **(hdr or {})))
    r = c.getresponse(); data = r.read(); h = {k.lower(): v for k, v in r.getheaders()}
    return r.status, h, data

srv = HTTPServer(("127.0.0.1", 18081), Stub); threading.Thread(target=srv.serve_forever, daemon=True).start()
procs = []
try:
    p = run_case(True)
    if p:
        procs.append(p)
        s, h, b = get("/")
        ok(s == 200 and b"mwMain" in b, "/ vydá úvodní stránku mini-shopu (URL zůstává /)")
        ok("noindex" in h.get("x-robots-tag", ""), "hlavička X-Robots-Tag: noindex, nofollow na každé odpovědi (/: %s)" % h.get("x-robots-tag"))
        s, h, b = get("/robots.txt"); ok(s == 200 and b"Disallow: /" in b, "robots.txt Disallow: / (dokud není SEO)")
        for path in ("/miniweb/miniweb.js", "/miniweb/miniweb-pages.js", "/miniweb/miniweb.css", "/miniweb/product.html", "/miniweb/i18n/sk.json", "/miniweb/i18n/en.json", "/js/product-configurator.js", "/js/client-errors.js", "/js/v3d/viewer3d.js", "/css/product-configurator.css", "/css/v3d.css"):
            s, h, b = get(path); ok(s == 200, "povoleno: " + path + " -> %s" % s)
        for path in ("/miniweb/demo-api.js", "/miniweb/i18n/demo.sk.json", "/miniweb/i18n/demo.en.json", "/miniweb/config.json", "/miniweb/config.sk.json"):
            s, h, b = get(path); ok(s == 404, "ukázková data / nahled se nevydávají: " + path + " -> %s" % s)
        for path in ("/product.html", "/login.html", "/admin.html", "/scene.html", "/index.html", "/js/track.js", "/js/app.js", "/css/brand-logo.css", "/katalog/product_4934.glb", "/api/auth/me", "/api/products", "/api/admin/users", "/api/shop/products/4934", "/api/shop/products/4934/turntable", "/api/cart", "/stul-konfigurator.html", "/.env", "/miniweb/../index.html", "/api/miniwebX/config", "/%2e%2e/etc/passwd"):
            s, h, b = get(path); ok(s == 404 or s == 400, "zablokováno (whitelist): " + path + " -> %s" % s)
        s, h, b = get("/api/miniweb/config", hdr={"CF-Connecting-IP": "203.0.113.9", "X-Forwarded-For": "6.6.6.6"}); j = json.loads(b) if s == 200 else {}
        ok(s == 200 and j.get("path") == "/api/miniweb/config" and j.get("host") == "test.example", "/api/miniweb/* se proxuje (Host zachován)")
        ok(j.get("xreal") == "203.0.113.9" and j.get("xff") == "203.0.113.9", "skutečná IP návštěvníka z CF-Connecting-IP (X-Real-IP i X-Forwarded-For), podvržený XFF se zahodí: real=%s xff=%s" % (j.get("xreal"), j.get("xff")))
        s, h, b = get("/api/miniweb/inquiry", "POST", json.dumps({"a": 1}), {"Content-Type": "application/json"}); ok(s == 200 and json.loads(b)["method"] == "POST", "POST /api/miniweb/inquiry se proxuje")
        s, h, b = get("/api/shop/configurator/resolve", "POST", "{}", {"Content-Type": "application/json"}); ok(s == 200, "POST /api/shop/configurator/resolve se proxuje")
        s, h, b = get("/api/shop/configurator/glb/abc"); ok(s == 200, "GET /api/shop/configurator/glb/<token> se proxuje")
        s, h, b = get("/api/shop/products/4934/configurator?lang=sk"); ok(s == 200 and json.loads(b)["path"].endswith("configurator?lang=sk"), "GET /api/shop/products/<id>/configurator?lang=sk se proxuje")
        s, h, b = get("/api/client-errors", "POST", "{}", {"Content-Type": "application/json"}); ok(s == 200, "POST /api/client-errors se proxuje")
        s, h, b = get("/api/miniweb/inquiry", "POST", "x" * 2_000_000, {"Content-Type": "application/json"}); ok(s == 413, "tělo nad 1 MB se odmítne (413): %s" % s)
        s, h, b = get("/", port=18080); ok(s == 200 and b"mwMain" in b, "port 80 servíruje stejný obsah (Cloudflare Flexible)")
        procs[0].send_signal(signal.SIGTERM); procs[0].wait(10)
    p = run_case(False)
    if p:
        procs.append(p)
        s, h, b = get("/"); ok(s == 200 and "x-robots-tag" not in h, "--index: bez X-Robots-Tag (indexace povolena)")
        s, h, b = get("/robots.txt"); ok(s == 404, "--index: robots.txt z vhostu se nevydává (404 - dodá se až s SEO vrstvou)")
        s, h, b = get("/product.html"); ok(s == 404, "--index: whitelist platí dál")
        procs[-1].send_signal(signal.SIGTERM); procs[-1].wait(10)
    p = run_case(False, "sk")
    if p:
        procs.append(p)
        def seen(path, **kw):
            s, h, b = get(path, **kw)
            try: return s, json.loads(b).get("path"), h, json.loads(b)
            except Exception: return s, None, h, {}
        s, pth, h, j = seen("/"); ok(s == 200 and pth == "/api/miniweb/seo/" and j["host"] == "test.example" and "x-robots-tag" not in h, "SEO: / jde do Flasku (api/miniweb/seo/), Host se zachová, bez statického noindex")
        for url in ("/produkt/baliaci-stol", "/kategoria/stoly", "/kontakt", "/pravne-informacie", "/kosik", "/obchod", "/robots.txt", "/sitemap.xml"):
            s, pth, h, j = seen(url); ok(s == 200 and pth == "/api/miniweb/seo" + url, "SEO: %s → /api/miniweb/seo%s" % (url, url))
        for url in ("/produkt/", "/produkt/A_b", "/produkt/a/b", "/kategoria/x/y", "/product/x", "/cart", "/kontakt/x"):
            s, pth, h, j = seen(url); ok(s == 404, "SEO: %s → 404 (mimo whitelist slugů sk)" % url)
        s, pth, h, j = seen("/api/miniweb/seo/produkt/x"); ok(s == 404, "SEO: přímý přístup na /api/miniweb/seo/ zvenku je zavřený (duplicity)")
        s, pth, h, j = seen("/api/miniweb/config"); ok(s == 200 and pth == "/api/miniweb/config", "SEO: /api/miniweb/ zůstává neblokované (Google potřebuje API)")
        s, h, b = get("/miniweb/miniweb.js"); ok(s in (200, 404) and "x-robots-tag" not in h, "SEO: statika /miniweb/ neblokovaná")
        for pth in ("/js/pripni-cokoli-tile.js", "/pripni-cokoli/texty.json", "/pripni-cokoli/stavebnice-demo.glb", "/pripni-cokoli/stavebnice-demo-30x30.glb", "/js/v3d-ovladani.js", "/js/pdc-layout.js"):
            s, h, b = get(pth); ok(s == 200, "SEO: prvek Připni cokoli – %s povoleno (%s)" % (pth, s))
        for pth in ("/pripni-cokoli/schema-30x30-d8.svg", "/pripni-cokoli/schema-40x40-d10.svg"):
            s, h, b = get(pth); ok(s == 200, "SEO: schéma profilu %s povoleno (okno Hlavní profil)" % pth)
        for pth in ("/pripni-cokoli.html", "/pripni-cokoli/", "/pripni-cokoli/schema-50x50-d10.svg"):
            s, h, b = get(pth); ok(s == 404, "SEO: %s zůstává zavřené (jen soubory prvku a dvě schémata)" % pth)
        s, h, b = get("/product.html"); ok(s == 404, "SEO: whitelist platí dál")
        conn = http.client.HTTPSConnection("127.0.0.1", 18443, context=ssl._create_unverified_context(), timeout=10)
        conn.request("GET", "/produkt/abc?x=1", headers={"Host": "www.test.example"}); r = conn.getresponse(); r.read()
        ok(r.status == 301 and r.getheader("Location") == "https://test.example/produkt/abc?x=1", "SEO: www.<doména> → 301 na holou doménu se zachováním cesty a dotazu: %s %s" % (r.status, r.getheader("Location")))
        procs[-1].send_signal(signal.SIGTERM); procs[-1].wait(10)
finally:
    for p in procs:
        try: p.kill()
        except Exception: pass
    srv.shutdown(); shutil.rmtree(TMP, ignore_errors=True)
print("\n==> %d/%d kontrol OK" % (total - bad, total))
sys.exit(1 if bad else 0)
