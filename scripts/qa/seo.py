#!/usr/bin/env python3
"""
scripts/qa/seo.py - SEO + a11y crawl verejneho webu (bot15, 2026-09-02,
"kontrolni mechanismy na cely system konfiguratoru", oblast (F) SEO/a11y,
zadani Roberta pres bot3).

Co kontroluje (vsechno jen ctenim verejnych stranek - GET/HEAD, zadne
formulare, zadne e-maily, zadna testovaci data, zadny zapis do DB):

  1. sitemap.xml: kazda URL https + na stejne domene, lastmod platny,
     kazda URL vraci 200 bez presmerovani (HEAD, fallback GET), zadny
     X-Robots-Tag noindex, image:image tagy vraci 200 image/*,
     query-string URL (?id=) v sitemape, robots.txt odkazuje sitemapu
     a neblokuje nic z ni (ani obrazky).
  2. hluboky vzorek stranek: vsechny kategorie + N nahodnych produktu
     (+ vzdy sestava /produkt/jumpy-l3-...) + staticke stranky. Na kazde:
     title/description (delka + duplicity napric vzorkem), canonical
     (https, self, bez query), <html lang>, viewport, prave jedno h1,
     poradi nadpisu, OG title/description/image (obrazek 200 + rozmery
     >= 1200x630), Twitter card, JSON-LD (parse + @type, Product
     name/image/description/offers, BreadcrumbList), hreflang, img bez
     alt, hero img s width/height a bez lazy, lazy-loading pod ohybem,
     nechtene noindex, "zde"/prazdne odkazy, mixed content, velikost
     HTML, doba odezvy, presmerovani, SSR placeholder ("Nacitam...") v h1.
  3. interni odkazy ze vzorku -> HEAD (unikatni, limit --max-links) -> 404.
  4. presmerovaci retezy http/https/www, soft-404 (neexistujici URL -> 200).
  5. a11y bez prohlizece: pole formulare bez <label>/aria-label, tlacitka
     bez textu, odkazy bez textu (jen ikona), tabulky bez th, iframe bez
     title, skip-link (jen info).
  6. "otevrena doporuceni" z AUDIT_SEO_AI_VISIBILITY_2026-08-28.md a
     SEO_GEO_AUDIT_2026-08-18.md, ktera jdou zmerit automaticky
     (Organization/WebSite JSON-LD, FAQPage u .seo-faq bloku, rozmery
     v Product JSON-LD, konstantni lastmod) - jen severity info, aby
     nekazily status, dokud je bot3/Robert neschvali k oprave.

Pouziti (QA venv, NE produkcni api/venv - bs4/lxml tam nejsou):
  scripts/qa/.venv/bin/python scripts/qa/seo.py                # lidsky text
  scripts/qa/.venv/bin/python scripts/qa/seo.py --json         # JSON kontrakt (_common.py)
  scripts/qa/.venv/bin/python scripts/qa/seo.py --sample 40 --seed 1
  scripts/qa/.venv/bin/python scripts/qa/seo.py --full         # hluboka kontrola VSECH URL ze sitemapy (dlouhe)
  scripts/qa/.venv/bin/python scripts/qa/seo.py --base http://127.0.0.1:8090 --host autovestavby.logiman.cz
  scripts/qa/.venv/bin/python scripts/qa/seo.py --cwv          # + LCP/CLS 3 stranek pres Playwright (volitelne)

Zavislosti (scripts/qa/.venv): requests, beautifulsoup4, lxml, pillow,
pymysql (jen kvuli importu _common). Zadne prihlasovaci udaje.

Setrnost: max 4 soubezne pozadavky, User-Agent KonfiguratorQA/1.0,
kazda URL se v jednom behu stahuje jen jednou (cache).

Exit kod: 0 ok, 1 warn, 2 fail, 3 skript sam selhal. JSON report se
navic uklada do qa-reports/seo-<cas>.json (+ seo-latest.json).
"""
import argparse
import collections
import datetime
import io
import json
import os
import random
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.robotparser
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (QA_REPORTS_DIR, REPO_ROOT, finding, now_iso,  # noqa: E402
                     overall_status, ram_watchdog_alert_active, run_suite)

USER_AGENT = "KonfiguratorQA/1.0 (+read-only SEO/a11y audit)"
MAX_WORKERS = 4
TIMEOUT = 20

# Sestava s otocnym nahledem - vzdy ve vzorku (SSR hero, 6 obrazku v
# JSON-LD, OG 16:9) - zadani bot3.
ALWAYS_PRODUCTS = ["/produkt/jumpy-l3-ci26-boxy43-270x4-170x3-120x9"]
# Verejne staticke stranky mimo sitemapu (webapp/*.html, bez admin/login/
# scene, ktere robots.txt zakazuje).
STATIC_PAGES = [
    "/", "/kontakt.html", "/realizace.html", "/remeslo.html",
    "/remeslo-nabidka-online.html", "/remeslo-srovnavac.html",
    "/remeslo-spolupracovnik.html",
]
# Sablony pro Flask SSR, ktere NEMAJI byt dostupne jako samostatne stranky
# (viz SEO_RAW_TEMPLATE_SERVED v check_host_redirects).
RAW_TEMPLATES = ["/blok.html", "/storefront-hub.html", "/storefront-default.html"]
GENERIC_ANCHORS = {"zde", "tady", "klikněte zde", "klikni zde", "více", "vice",
                   "více zde", "here", "click here", "read more", "link", "odkaz"}
TITLE_MIN, TITLE_MAX = 30, 65
DESC_MIN, DESC_MAX = 70, 160
HTML_WARN_BYTES = 300 * 1024
HTML_INFO_BYTES = 150 * 1024
TIME_WARN_S, TIME_CRIT_S = 2.0, 5.0
OG_MIN_W, OG_MIN_H = 1200, 630
LAZY_INFO_MIN_IMGS = 6  # pod tolik obrazku nema smysl resit lazy-loading
AGG_MIN_PAGES = 3  # stejny kod na >= tolika strankach -> jeden souhrnny nalez (detail v reportu)


# ---------------------------------------------------------------- fetcher
class Fetcher:
    """requests.Session + cache na cely beh + zamek. Vsechno GET/HEAD."""

    def __init__(self, base, host_header=None, timeout=TIMEOUT):
        self.base = base.rstrip("/")
        self.host = urllib.parse.urlsplit(self.base).netloc
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.session.headers["Accept-Language"] = "cs,en;q=0.5"
        if host_header:
            self.session.headers["Host"] = host_header
        # Pres --base http://127.0.0.1:8090 --host ... dostane aplikace
        # X-Forwarded-Proto=http (nginx :8090), takze canonical/og:url vyjdou
        # s http:// - to neni chyba produkce, jen testovaciho vstupu.
        self.lenient_scheme = bool(host_header)
        self.cache = {}
        self.lock = threading.Lock()
        self.requests_made = 0
        self.bytes_downloaded = 0

    def abs(self, url):
        return urllib.parse.urljoin(self.base + "/", url)

    def to_local(self, url):
        """Verejna https URL (canonical, sitemap) -> URL, kterou fyzicky
        stahujeme (kvuli --base http://127.0.0.1:8090 --host ...)."""
        parts = urllib.parse.urlsplit(url)
        if self.session.headers.get("Host") and parts.netloc == self.session.headers["Host"]:
            return urllib.parse.urlunsplit(urllib.parse.urlsplit(self.base)[:2] + parts[2:])
        return url

    def is_internal(self, url):
        netloc = urllib.parse.urlsplit(url).netloc
        return netloc in ("", self.host, self.session.headers.get("Host", self.host),
                          "www." + self.host.removeprefix("www."))

    def _do(self, method, url, follow):
        key = (method, url, follow)
        with self.lock:
            if key in self.cache:
                return self.cache[key]
        started = time.monotonic()
        try:
            r = self.session.request(method, self.to_local(url), allow_redirects=follow,
                                     timeout=self.timeout, stream=(method == "GET"))
            if method == "GET":
                body = r.content  # dotahne stream
            else:
                body = b""
                r.close()
            res = {
                "url": url, "status": r.status_code, "final_url": r.url,
                "headers": {k.lower(): v for k, v in r.headers.items()},
                "history": [(h.status_code, h.headers.get("Location", "")) for h in r.history],
                "body": body, "elapsed": time.monotonic() - started, "error": None,
                "location": r.headers.get("Location", ""),
            }
        except requests.RequestException as e:
            res = {"url": url, "status": None, "final_url": url, "headers": {}, "history": [],
                   "body": b"", "elapsed": time.monotonic() - started, "error": repr(e),
                   "location": ""}
        with self.lock:
            self.cache[key] = res
            self.requests_made += 1
            self.bytes_downloaded += len(res["body"])
        return res

    def get(self, url, follow=True):
        return self._do("GET", url, follow)

    def head(self, url, follow=False):
        """HEAD bez presmerovani; kdyz server HEAD neumi (405/501/nic),
        fallback na GET (stale bez presmerovani)."""
        r = self._do("HEAD", url, follow)
        if r["status"] in (405, 501, None) or (r["status"] == 400 and r["error"] is None):
            r = self._do("GET", url, follow)
        return r

    def head_status(self, url):
        r = self.head(url)
        # 404 na HEAD u nekterych aplikaci != 404 na GET - overit GETem,
        # aby nalez "sitemap URL -> 404" byl vzdy potvrzeny realnym GET.
        if r["status"] and r["status"] >= 400 and r["status"] not in (405, 501):
            r = self._do("GET", url, False)
        return r

    def pmap(self, fn, items):
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            return list(ex.map(fn, items))


# ---------------------------------------------------------------- helpers
def _text(el):
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip() if el else ""


def _norm_url(u):
    """Pro srovnani canonical vs. self: bez fragmentu, bez koncoveho '/',
    s malym hostem."""
    p = urllib.parse.urlsplit(u.strip())
    path = p.path.rstrip("/") or "/"
    return urllib.parse.urlunsplit((p.scheme.lower(), p.netloc.lower(), path, p.query, ""))


def _classify(path):
    if path.startswith("/produkt/") or path.startswith("/product.html"):
        return "product"
    if path.startswith("/kategorie/") or path.startswith("/category.html"):
        return "category"
    if path in ("/", "/index.html"):
        return "home"
    return "static"


def _image_size(data):
    try:
        from PIL import Image
        with Image.open(io.BytesIO(data)) as im:
            return im.size
    except Exception:  # noqa: BLE001 - jen informativni
        return None


def _iter_ld_nodes(node):
    """Prochazi JSON-LD vcetne @graph a poli, vraci dict uzly s @type."""
    if isinstance(node, list):
        for n in node:
            yield from _iter_ld_nodes(n)
    elif isinstance(node, dict):
        if "@type" in node:
            yield node
        for k, v in node.items():
            if k in ("@graph", "mainEntity", "itemListElement", "hasPart") and isinstance(v, (list, dict)):
                yield from _iter_ld_nodes(v)


def _types(node):
    t = node.get("@type")
    return t if isinstance(t, list) else [t]


def _valid_lastmod(s):
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M%z"):
        try:
            d = datetime.datetime.strptime(s.replace("Z", "+0000"), fmt)
            return d
        except ValueError:
            continue
    return None


def _has_accessible_name(el):
    if (el.get("aria-label") or "").strip() or el.get("aria-labelledby") or (el.get("title") or "").strip():
        return True
    if _text(el):
        return True
    for img in el.find_all("img"):
        if (img.get("alt") or "").strip():
            return True
    for svg in el.find_all("svg"):
        if svg.find("title") and _text(svg.find("title")):
            return True
        if (svg.get("aria-label") or "").strip():
            return True
    return False


def _el_desc(el):
    bits = [el.name]
    for a in ("id", "name", "type", "placeholder", "class", "href", "src"):
        v = el.get(a)
        if v:
            if isinstance(v, list):
                v = " ".join(v)
            bits.append(f'{a}="{str(v)[:40]}"')
    return "<" + " ".join(bits) + ">"


# ---------------------------------------------------------------- sitemap
def check_sitemap_and_robots(fetcher, findings, stats, rp_holder):
    base = fetcher.base
    sm = fetcher.get(base + "/sitemap.xml")
    entries = []
    if sm["status"] != 200 or not sm["body"]:
        findings.append(finding("critical", "SEO_SITEMAP_UNREACHABLE", "sitemap.xml nejde stáhnout",
                                f"status={sm['status']} chyba={sm['error']}", base + "/sitemap.xml",
                                "Zkontrolovat route /sitemap.xml v api/app.py a nginx."))
        return entries
    try:
        root = ET.fromstring(sm["body"])
    except ET.ParseError as e:
        findings.append(finding("critical", "SEO_SITEMAP_INVALID_XML", "sitemap.xml není platné XML",
                                repr(e), base + "/sitemap.xml"))
        return entries
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9",
          "image": "http://www.google.com/schemas/sitemap-image/1.1"}
    if root.tag.endswith("sitemapindex"):
        findings.append(finding("info", "SEO_SITEMAP_INDEX", "sitemap.xml je index (sitemapindex)",
                                "Skript zatím čte jen plochý <urlset>; dílčí sitemapy nejsou procházeny.",
                                base + "/sitemap.xml"))
        return entries
    for u in root.findall("s:url", ns):
        loc = (u.findtext("s:loc", default="", namespaces=ns) or "").strip()
        entries.append({
            "loc": loc,
            "lastmod": u.findtext("s:lastmod", default=None, namespaces=ns),
            "priority": u.findtext("s:priority", default=None, namespaces=ns),
            "images": [(im.findtext("image:loc", default="", namespaces=ns) or "").strip()
                       for im in u.findall("image:image", ns)],
        })
    stats["sitemap_urls"] = len(entries)
    stats["sitemap_image_tags"] = sum(len(e["images"]) for e in entries)
    stats["sitemap_bytes"] = len(sm["body"])
    if len(sm["body"]) > 50 * 1024 * 1024 or len(entries) > 50000:
        findings.append(finding("critical", "SEO_SITEMAP_TOO_BIG", "sitemap.xml překračuje limit 50 MB / 50 000 URL",
                                f"{len(sm['body'])} B, {len(entries)} URL", base + "/sitemap.xml",
                                "Rozdělit na sitemapindex."))

    seen = collections.Counter(e["loc"] for e in entries)
    dups = [loc for loc, c in seen.items() if c > 1]
    if dups:
        findings.append(finding("warning", "SEO_SITEMAP_DUPLICATE_LOC", "Duplicitní <loc> v sitemapě",
                                f"{len(dups)}× např. {dups[:3]}", base + "/sitemap.xml"))
    non_https = [e["loc"] for e in entries if not e["loc"].startswith("https://")]
    if non_https:
        findings.append(finding("warning", "SEO_SITEMAP_NOT_HTTPS", "URL v sitemapě nejsou https",
                                f"{len(non_https)}× např. {non_https[:3]}", base + "/sitemap.xml",
                                "Generovat loc vždy s https:// (kanonické schéma)."))
    host = urllib.parse.urlsplit(base).netloc
    if fetcher.session.headers.get("Host"):
        host = fetcher.session.headers["Host"]
    foreign = [e["loc"] for e in entries if urllib.parse.urlsplit(e["loc"]).netloc != host]
    if foreign:
        findings.append(finding("warning", "SEO_SITEMAP_FOREIGN_HOST", "URL v sitemapě na jiném hostu",
                                f"{len(foreign)}× např. {foreign[:3]}", base + "/sitemap.xml"))
    query_urls = [e["loc"] for e in entries if "?" in e["loc"]]
    if query_urls:
        findings.append(finding("warning", "SEO_SITEMAP_QUERY_URL",
                                "URL s query stringem v sitemapě (produkt bez slugu)",
                                f"{len(query_urls)}× např. {query_urls[:5]} - _product_rel_url() padá na "
                                "/product.html?id= u produktů bez slugu (SEO_GEO_AUDIT 3.3).",
                                base + "/sitemap.xml",
                                "Doplnit slug u těchto produktů (admin) nebo generovat slug automaticky z názvu."))
    stats["sitemap_query_urls"] = len(query_urls)

    today = datetime.date.today()
    bad_lastmod, future, lastmods = [], [], collections.Counter()
    for e in entries:
        if e["lastmod"] is None:
            continue
        d = _valid_lastmod(e["lastmod"])
        if d is None:
            bad_lastmod.append((e["loc"], e["lastmod"]))
        elif d.date() > today + datetime.timedelta(days=1):
            future.append((e["loc"], e["lastmod"]))
        lastmods[e["lastmod"].strip()[:10]] += 1
    if bad_lastmod:
        findings.append(finding("warning", "SEO_SITEMAP_BAD_LASTMOD", "Neplatný lastmod v sitemapě",
                                f"{len(bad_lastmod)}× např. {bad_lastmod[:3]}", base + "/sitemap.xml",
                                "lastmod musí být W3C datetime (YYYY-MM-DD nebo ISO 8601)."))
    if future:
        findings.append(finding("warning", "SEO_SITEMAP_FUTURE_LASTMOD", "lastmod v budoucnosti",
                                f"{len(future)}× např. {future[:3]}", base + "/sitemap.xml"))
    without = sum(1 for e in entries if e["lastmod"] is None)
    stats["sitemap_without_lastmod"] = without
    if lastmods:
        top_day, top_cnt = lastmods.most_common(1)[0]
        stats["sitemap_lastmod_top"] = f"{top_day} ({top_cnt}×)"
        if top_cnt > 0.5 * len(entries) and (today - datetime.date.fromisoformat(top_day)).days > 14:
            findings.append(finding("info", "SEO_SITEMAP_LASTMOD_STALE",
                                    "Většina lastmod má stejné, starší datum",
                                    f"{top_cnt}/{len(entries)} URL má lastmod {top_day} - vypadá to na datum "
                                    "importu, ne skutečnou změnu (AUDIT_SEO_AI_VISIBILITY: lastmod pevně).",
                                    base + "/sitemap.xml",
                                    "lastmod brát z updated_at produktu/kategorie, ne z created_at/importu."))

    # robots.txt
    rb = fetcher.get(base + "/robots.txt")
    rp = urllib.robotparser.RobotFileParser()
    if rb["status"] != 200:
        findings.append(finding("warning", "SEO_ROBOTS_MISSING", "robots.txt není dostupný",
                                f"status={rb['status']}", base + "/robots.txt"))
        rp.parse([])
    else:
        text = rb["body"].decode("utf-8", "replace")
        rp.parse(text.splitlines())
        sitemap_lines = [ln.split(":", 1)[1].strip() for ln in text.splitlines()
                         if ln.lower().startswith("sitemap:")]
        want = f"https://{host}/sitemap.xml"
        if not sitemap_lines:
            findings.append(finding("warning", "SEO_ROBOTS_NO_SITEMAP", "robots.txt neodkazuje na sitemapu",
                                    "Chybí řádek `Sitemap: https://.../sitemap.xml`.", base + "/robots.txt"))
        elif want not in sitemap_lines:
            findings.append(finding("info", "SEO_ROBOTS_SITEMAP_MISMATCH", "Sitemap v robots.txt má jinou URL",
                                    f"robots: {sitemap_lines}, očekáváno {want}", base + "/robots.txt"))
        if re.search(r"^\s*Disallow:\s*/\s*$", text, re.M):
            findings.append(finding("critical", "SEO_ROBOTS_DISALLOW_ALL", "robots.txt obsahuje `Disallow: /`",
                                    "Celý web je zakázaný pro roboty.", base + "/robots.txt"))
        blocked = [e["loc"] for e in entries if not rp.can_fetch("Googlebot", e["loc"])]
        if blocked:
            findings.append(finding("critical", "SEO_ROBOTS_BLOCKS_SITEMAP_URL",
                                    "robots.txt blokuje URL, které jsou v sitemapě",
                                    f"{len(blocked)}× např. {blocked[:5]}", base + "/robots.txt",
                                    "Buď URL ze sitemapy vyřadit, nebo Disallow uvolnit."))
        blocked_img = [im for e in entries for im in e["images"] if im and not rp.can_fetch("Googlebot", im)]
        if blocked_img:
            findings.append(finding("warning", "SEO_ROBOTS_BLOCKS_SITEMAP_IMAGE",
                                    "robots.txt blokuje obrázky ze sitemapy",
                                    f"{len(blocked_img)}× např. {blocked_img[:3]}", base + "/robots.txt"))
    rp_holder["rp"] = rp

    # HEAD na kazdou URL (200 bez presmerovani, X-Robots-Tag)
    def probe(e):
        return e["loc"], fetcher.head_status(e["loc"])

    results = fetcher.pmap(probe, entries)
    by_status = collections.Counter()
    not_ok, redirected, noindex_hdr, errors = [], [], [], []
    for loc, r in results:
        by_status[str(r["status"])] += 1
        if r["error"]:
            errors.append((loc, r["error"][:80]))
        elif r["status"] in (301, 302, 303, 307, 308):
            redirected.append((loc, r["status"], r["location"]))
        elif r["status"] != 200:
            not_ok.append((loc, r["status"]))
        xr = r["headers"].get("x-robots-tag", "")
        if "noindex" in xr.lower():
            noindex_hdr.append((loc, xr))
    stats["sitemap_status_counts"] = dict(by_status)
    if errors:
        findings.append(finding("critical", "SEO_SITEMAP_URL_ERROR", "URL ze sitemapy nešla stáhnout (síťová chyba)",
                                f"{len(errors)}× např. {errors[:3]}", base + "/sitemap.xml"))
    if not_ok:
        sev = "critical" if any(s and s >= 400 for _, s in not_ok) else "warning"
        findings.append(finding(sev, "SEO_SITEMAP_URL_NOT_200", "URL ze sitemapy nevrací 200",
                                f"{len(not_ok)}× např. {not_ok[:5]}", base + "/sitemap.xml",
                                "Neaktivní/smazané produkty a kategorie vyřadit z generování sitemapy."))
    if redirected:
        findings.append(finding("warning", "SEO_SITEMAP_URL_REDIRECT", "URL ze sitemapy přesměrovává",
                                f"{len(redirected)}× např. {redirected[:5]}", base + "/sitemap.xml",
                                "Do sitemapy patří jen cílové (kanonické) URL."))
    if noindex_hdr:
        findings.append(finding("critical", "SEO_SITEMAP_URL_NOINDEX_HEADER",
                                "URL ze sitemapy má X-Robots-Tag noindex",
                                f"{len(noindex_hdr)}× např. {noindex_hdr[:3]}", base + "/sitemap.xml"))

    # obrazky ze sitemapy
    imgs = sorted({im for e in entries for im in e["images"] if im})

    def probe_img(u):
        r = fetcher.head_status(u)
        return u, r["status"], r["headers"].get("content-type", ""), r["error"]

    bad_imgs = []
    for u, st, ct, err in fetcher.pmap(probe_img, imgs):
        if st != 200 or not ct.startswith("image/"):
            bad_imgs.append((u, st, ct or err))
    stats["sitemap_images_checked"] = len(imgs)
    if bad_imgs:
        findings.append(finding("critical", "SEO_SITEMAP_IMAGE_BROKEN", "Obrázek ze sitemapy nevrací 200 image/*",
                                f"{len(bad_imgs)}× např. {bad_imgs[:3]}", base + "/sitemap.xml"))
    non_https_img = [im for im in imgs if not im.startswith("https://")]
    if non_https_img:
        findings.append(finding("warning", "SEO_SITEMAP_IMAGE_NOT_HTTPS", "image:loc není https",
                                f"{len(non_https_img)}× např. {non_https_img[:3]}", base + "/sitemap.xml"))
    return entries


# ---------------------------------------------------------------- page analysis
class PageResult:
    def __init__(self, url):
        self.url = url
        self.findings = []
        self.title = None
        self.description = None
        self.internal_links = set()
        self.has_skip_link = False
        self.elapsed = None
        self.size = None
        self.kind = _classify(urllib.parse.urlsplit(url).path)
        self.indexable = True
        self.ok = False


def _f(pr, sev, code, title, detail, fix=None):
    pr.findings.append(finding(sev, code, title, detail, pr.url, fix))


def analyze_page(fetcher, url, in_sitemap, rp):
    pr = PageResult(url)
    r = fetcher.get(url)
    pr.elapsed = r["elapsed"]
    if r["error"] or r["status"] is None:
        _f(pr, "critical", "SEO_PAGE_FETCH_ERROR", "Stránku nejde stáhnout", f"{r['error']}")
        return pr
    if r["history"]:
        chain = " -> ".join(f"{s} {loc}" for s, loc in r["history"]) + f" -> {r['status']} {r['final_url']}"
        sev = "warning" if in_sitemap else "info"
        _f(pr, sev, "SEO_PAGE_REDIRECT", "Stránka přesměrovává", chain,
           "Odkazovat/sitemapovat rovnou cílovou URL.")
    if r["status"] != 200:
        _f(pr, "critical", "SEO_PAGE_NOT_200", "Stránka nevrací 200", f"status={r['status']}")
        return pr
    ct = r["headers"].get("content-type", "")
    if "html" not in ct:
        _f(pr, "warning", "SEO_PAGE_NOT_HTML", "Stránka nemá Content-Type text/html", ct)
        return pr
    body = r["body"]
    pr.size = len(body)
    pr.ok = True
    if pr.elapsed > TIME_CRIT_S:
        _f(pr, "critical", "SEO_SLOW_RESPONSE", "Velmi pomalá odezva", f"{pr.elapsed:.2f} s (limit {TIME_CRIT_S} s)")
    elif pr.elapsed > TIME_WARN_S:
        _f(pr, "warning", "SEO_SLOW_RESPONSE", "Pomalá odezva", f"{pr.elapsed:.2f} s (limit {TIME_WARN_S} s)")
    if pr.size > HTML_WARN_BYTES:
        _f(pr, "warning", "SEO_HTML_TOO_BIG", "HTML odpověď je příliš velká",
           f"{pr.size // 1024} kB (limit {HTML_WARN_BYTES // 1024} kB)",
           "Přesunout inline CSS/JS/data do externích cachovaných souborů (SEO_GEO_AUDIT 3.2).")
    elif pr.size > HTML_INFO_BYTES:
        _f(pr, "info", "SEO_HTML_BIG", "HTML odpověď je velká",
           f"{pr.size // 1024} kB (nad {HTML_INFO_BYTES // 1024} kB)",
           "Inline <style>/<script> se u každé stránky stahují znovu - zvážit externí soubory.")
    xr = r["headers"].get("x-robots-tag", "")
    if "noindex" in xr.lower():
        pr.indexable = False
        _f(pr, "critical" if in_sitemap else "info", "SEO_NOINDEX_HEADER", "X-Robots-Tag: noindex", xr)

    soup = BeautifulSoup(body, "lxml")
    head = soup.head or soup
    html = soup.find("html")

    # --- zakladni head
    lang = (html.get("lang") if html else None) or ""
    if not lang.strip():
        _f(pr, "warning", "SEO_HTML_NO_LANG", "<html> nemá atribut lang", "Chybí lang=\"cs\".",
           "Doplnit <html lang=\"cs\">.")
    if not head.find("meta", attrs={"name": "viewport"}):
        _f(pr, "warning", "SEO_NO_VIEWPORT", "Chybí <meta name=viewport>", "Stránka nebude mobile-friendly.",
           "Doplnit <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">.")

    titles = head.find_all("title")
    title = _text(titles[0]) if titles else ""
    pr.title = title or None
    if not title:
        _f(pr, "critical", "SEO_NO_TITLE", "Chybí <title>", "Stránka nemá titulek.")
    else:
        if len(titles) > 1:
            _f(pr, "warning", "SEO_MULTIPLE_TITLE", "Více <title> v hlavičce", f"{len(titles)}×")
        if len(title) < TITLE_MIN:
            # kratky titulek neskodi (neorizne se), jen nevyuziva prostor -> info
            _f(pr, "info", "SEO_TITLE_SHORT", "Krátký <title>", f"{len(title)} znaků: „{title}“",
               f"Cíl {TITLE_MIN}-{TITLE_MAX} znaků.")
        elif len(title) > TITLE_MAX:
            _f(pr, "warning", "SEO_TITLE_LONG", "Dlouhý <title>", f"{len(title)} znaků: „{title[:90]}…“",
               f"Cíl {TITLE_MIN}-{TITLE_MAX} znaků (Google ořízne ~60).")
        if "načítám" in title.lower() or "loading" in title.lower():
            _f(pr, "critical", "SEO_TITLE_PLACEHOLDER", "<title> je placeholder", f"„{title}“")

    # meta robots NEJDRIV - u zamerne noindex stranky (aplikacni stranky
    # Remesla apod.) nema smysl hlasit chybejici description/canonical/OG/
    # twitter, ty jsou jen pro indexovatelne stranky (bot15, 2026-09-02,
    # po bloku 1 oprav: 7x SEO_NO_CANONICAL apod. bylo z poloviny sum
    # z noindex stranek).
    robots_meta = [m for m in head.find_all("meta") if (m.get("name") or "").lower() in ("robots", "googlebot")]
    for m in robots_meta:
        c = (m.get("content") or "").lower()
        if "noindex" in c:
            pr.indexable = False
            _f(pr, "critical" if in_sitemap else "info", "SEO_NOINDEX_META",
               "meta robots noindex" + (" na URL ze sitemapy" if in_sitemap else ""), c,
               "Buď stránku vyřadit ze sitemapy, nebo noindex odstranit.")
        if "nofollow" in c and "noindex" not in c:
            _f(pr, "warning", "SEO_NOFOLLOW_META", "meta robots nofollow na indexovatelné stránce", c,
               "nofollow zahazuje interní PageRank - použít jen vědomě.")

    descs = [m for m in head.find_all("meta") if (m.get("name") or "").lower() == "description"]
    desc = (descs[0].get("content") or "").strip() if descs else ""
    pr.description = desc or None
    if not desc:
        if pr.indexable:
            _f(pr, "warning", "SEO_NO_DESCRIPTION", "Chybí meta description", "Vyhledávač si vymyslí vlastní snippet.",
               "Doplnit <meta name=\"description\">.")
    else:
        if len(descs) > 1:
            _f(pr, "warning", "SEO_MULTIPLE_DESCRIPTION", "Více meta description", f"{len(descs)}×")
        if len(desc) < DESC_MIN:
            _f(pr, "info", "SEO_DESCRIPTION_SHORT", "Krátká meta description", f"{len(desc)} znaků: „{desc}“",
               f"Cíl {DESC_MIN}-{DESC_MAX} znaků.")
        elif len(desc) > DESC_MAX:
            _f(pr, "info", "SEO_DESCRIPTION_LONG", "Dlouhá meta description", f"{len(desc)} znaků",
               f"Cíl {DESC_MIN}-{DESC_MAX} znaků (bude oříznuta).")

    canon = [ln for ln in head.find_all("link") if "canonical" in [x.lower() for x in (ln.get("rel") or [])]]
    if not canon:
        if pr.indexable:
            _f(pr, "warning", "SEO_NO_CANONICAL", "Chybí <link rel=canonical>",
               "Bez canonical hrozí duplicitní indexace (www/non-www, ?id=, /index.html).",
               "Doplnit canonical na kanonickou https URL bez query (vzor _render_og_page).")
    else:
        if len(canon) > 1:
            _f(pr, "warning", "SEO_MULTIPLE_CANONICAL", "Více canonical", f"{len(canon)}×")
        href = (canon[0].get("href") or "").strip()
        if not href:
            _f(pr, "warning", "SEO_CANONICAL_EMPTY", "Prázdný canonical href", "")
        else:
            cabs = fetcher.abs(href)
            if fetcher.lenient_scheme:
                cabs = re.sub(r"^http://", "https://", cabs)
            if not cabs.startswith("https://"):
                _f(pr, "warning", "SEO_CANONICAL_NOT_HTTPS", "canonical není https", cabs)
            if urllib.parse.urlsplit(cabs).query:
                _f(pr, "warning", "SEO_CANONICAL_HAS_QUERY", "canonical obsahuje query string", cabs)
            expected = _norm_url(url)
            got = _norm_url(cabs)
            # /index.html -> / je v poradku
            if got != expected and not (expected.endswith("/index.html") and got == expected[: -len("/index.html")] + "/"):
                sev = "info" if pr.kind == "product" and "?" in url else "warning"
                _f(pr, sev, "SEO_CANONICAL_NOT_SELF", "canonical ukazuje jinam než na sebe",
                   f"canonical={cabs}", "U kanonické URL má canonical ukazovat sám na sebe.")

    # --- nadpisy
    h1s = soup.find_all("h1")
    if not h1s:
        _f(pr, "warning", "SEO_NO_H1", "Stránka nemá <h1>", "Chybí hlavní nadpis.",
           "Doplnit jeden <h1> s hlavním klíčovým slovem (SEO_GEO_AUDIT 2.1 - homepage).")
    elif len(h1s) > 1:
        _f(pr, "warning", "SEO_MULTIPLE_H1", "Více než jeden <h1>",
           f"{len(h1s)}×: {[_text(h)[:40] for h in h1s[:4]]}")
    if h1s:
        h1t = _text(h1s[0])
        if not h1t:
            _f(pr, "warning", "SEO_EMPTY_H1", "<h1> je prázdný v SSR odpovědi",
               "Robot bez JS vidí prázdný hlavní nadpis.")
        elif re.search(r"načítám|loading", h1t, re.I):
            _f(pr, "critical", "SEO_H1_PLACEHOLDER", "<h1> obsahuje placeholder „Načítám…“ (chybí SSR)",
               f"h1=„{h1t}“ - robot/AI bez JS vidí místo názvu produktu text Načítám (SEO_GEO_AUDIT 1.1).",
               "Doplnit body_replacements pro #pdTitle/breadcrumb/#pdDesc v _product_page_response "
               "(stejný vzor jako _category_page_response).")
    levels = [int(h.name[1]) for h in soup.find_all(re.compile(r"^h[1-6]$"))]
    prev = 0
    skips = []
    for lv in levels:
        if prev and lv > prev + 1:
            skips.append(f"h{prev}->h{lv}")
        prev = lv
    if skips:
        _f(pr, "info", "SEO_HEADING_SKIP", "Přeskočená úroveň nadpisů",
           f"{len(skips)}× např. {skips[:4]}", "Nadpisy mají jít po úrovních (h1 → h2 → h3).")

    # --- OG / Twitter
    og = {}
    for m in head.find_all("meta"):
        p = (m.get("property") or m.get("name") or "").lower()
        if p.startswith("og:") or p.startswith("twitter:"):
            og.setdefault(p, (m.get("content") or "").strip())
    for key, code in (("og:title", "SEO_NO_OG_TITLE"), ("og:description", "SEO_NO_OG_DESCRIPTION"),
                      ("og:image", "SEO_NO_OG_IMAGE")):
        if not og.get(key) and pr.indexable:
            _f(pr, "warning", code, f"Chybí {key}", "Sdílení na sociálních sítích bude bez náhledu/textu.",
               "Doplnit OG tagy (vzor _render_og_page).")
    if og.get("og:image"):
        img_url = fetcher.abs(og["og:image"])
        if not img_url.startswith("https://"):
            _f(pr, "warning", "SEO_OG_IMAGE_NOT_HTTPS", "og:image není https", img_url)
        ir = fetcher.get(img_url)
        ict = ir["headers"].get("content-type", "")
        if ir["status"] != 200 or not ict.startswith("image/"):
            _f(pr, "critical", "SEO_OG_IMAGE_BROKEN", "og:image nevrací 200 image/*",
               f"{img_url} -> status={ir['status']} ct={ict or ir['error']}")
        else:
            size = _image_size(ir["body"])
            if size:
                w, h = size
                if w < OG_MIN_W or h < OG_MIN_H:
                    _f(pr, "warning", "SEO_OG_IMAGE_SMALL", "og:image je menší než 1200×630",
                       f"{img_url} = {w}×{h}", "Facebook/LinkedIn doporučují min. 1200×630 (1.91:1).")
                ratio = w / h if h else 0
                if not (1.7 <= ratio <= 2.0):
                    _f(pr, "info", "SEO_OG_IMAGE_RATIO", "og:image nemá poměr ~1.91:1 / 16:9",
                       f"{img_url} = {w}×{h} (poměr {ratio:.2f})",
                       "Sociální sítě ořezávají; ideál 1200×630 nebo 1920×1080.")
                dw, dh = og.get("og:image:width"), og.get("og:image:height")
                if dw and dh and (str(w) != dw or str(h) != dh):
                    _f(pr, "warning", "SEO_OG_IMAGE_DIMENSION_MISMATCH",
                       "og:image:width/height neodpovídá skutečnému obrázku",
                       f"deklarováno {dw}×{dh}, skutečnost {w}×{h}")
            if rp is not None and not rp.can_fetch("Googlebot", img_url):
                _f(pr, "warning", "SEO_OG_IMAGE_BLOCKED_BY_ROBOTS", "og:image blokuje robots.txt", img_url)
    if not og.get("twitter:card") and pr.indexable:
        _f(pr, "warning", "SEO_NO_TWITTER_CARD", "Chybí twitter:card", "Bez něj X/Twitter použije jen OG fallback.",
           "Doplnit <meta name=\"twitter:card\" content=\"summary_large_image\">.")
    if og.get("og:url"):
        ogu = fetcher.abs(og["og:url"])
        if fetcher.lenient_scheme:
            ogu = re.sub(r"^http://", "https://", ogu)
        if _norm_url(ogu) != _norm_url(url) and not (pr.kind == "product" and "?" in url):
            _f(pr, "info", "SEO_OG_URL_MISMATCH", "og:url se liší od URL stránky", og["og:url"])

    # --- hreflang
    alts = [ln for ln in head.find_all("link") if ln.get("hreflang")]
    if alts:
        codes = {(ln.get("hreflang") or "").lower() for ln in alts}
        hrefs = {_norm_url(fetcher.abs(ln.get("href") or "")) for ln in alts}
        if "x-default" not in codes:
            _f(pr, "info", "SEO_HREFLANG_NO_XDEFAULT", "hreflang bez x-default", str(sorted(codes)))
        if _norm_url(url) not in hrefs:
            _f(pr, "warning", "SEO_HREFLANG_NO_SELF", "hreflang neobsahuje odkaz sám na sebe", str(sorted(codes)))

    # --- JSON-LD
    ld_types = []
    ld_nodes = []
    for s in soup.find_all("script", attrs={"type": re.compile(r"^application/ld\+json$", re.I)}):
        raw = s.string or s.get_text() or ""
        try:
            data = json.loads(raw)
        except ValueError as e:
            _f(pr, "critical", "SEO_JSONLD_INVALID", "JSON-LD není platný JSON", f"{e}: {raw[:120]!r}")
            continue
        for node in _iter_ld_nodes(data):
            ld_nodes.append(node)
            ld_types.extend(t for t in _types(node) if t)
    if pr.kind == "product":
        products = [n for n in ld_nodes if "Product" in _types(n)]
        if not products:
            _f(pr, "warning", "SEO_PRODUCT_NO_JSONLD", "Produktová stránka bez JSON-LD Product",
               f"@type nalezeno: {sorted(set(ld_types))}", "Doplnit Product+Offer (vzor _product_page_response).")
        for p in products[:1]:
            missing = [k for k in ("name", "image", "description") if not p.get(k)]
            if missing:
                _f(pr, "warning", "SEO_PRODUCT_JSONLD_INCOMPLETE", "Product JSON-LD bez povinných polí",
                   f"chybí {missing}", "Doplnit name/image/description.")
            offers = p.get("offers")
            if not offers:
                _f(pr, "warning", "SEO_PRODUCT_NO_OFFERS",
                   "Product JSON-LD nemá offers (cena/dostupnost)",
                   "Bez Offer Google nezobrazí cenu v rich results. U sestav (cena 0/placeholder) je to "
                   "očekávané - pak přidat aspoň offers s priceSpecification/„na dotaz“ nebo AggregateOffer.",
                   "U produktů s reálnou cenou vždy Offer{price, priceCurrency, availability}; u sestav "
                   "zvážit Offer s price 0 vynechat a použít `potentialAction`/`ContactPoint`.")
            else:
                o = offers[0] if isinstance(offers, list) else offers
                price = o.get("price") if isinstance(o, dict) else None
                try:
                    if float(price) <= 0:
                        _f(pr, "info", "SEO_PRODUCT_ZERO_PRICE", "Offer má cenu 0", f"price={price}",
                           "Cena 0 v Offer je pro Google nevalidní - u sestav Offer raději vynechat.")
                except (TypeError, ValueError):
                    _f(pr, "warning", "SEO_PRODUCT_BAD_PRICE", "Offer má nečíselnou/chybějící cenu", f"price={price!r}")
                if isinstance(o, dict) and not o.get("priceCurrency"):
                    _f(pr, "warning", "SEO_PRODUCT_NO_CURRENCY", "Offer bez priceCurrency", str(o)[:120])
                if isinstance(o, dict) and not o.get("availability"):
                    _f(pr, "info", "SEO_PRODUCT_NO_AVAILABILITY", "Offer bez availability", str(o)[:120])
            if not any(p.get(k) for k in ("width", "height", "depth", "size")):
                _f(pr, "info", "SEO_REC_PRODUCT_NO_DIMENSIONS", "Product JSON-LD bez rozměrů (GEO doporučení)",
                   "SEO_GEO_AUDIT 4.1: shop_products.length_mm/width_mm/height_mm existují, v JSON-LD nejsou.",
                   "Doplnit width/height/depth jako QuantitativeValue (unitCode MMT).")
            imgs = p.get("image")
            if isinstance(imgs, str):
                imgs = [imgs]
            for iu in (imgs or [])[:8]:
                iu = iu.get("url") if isinstance(iu, dict) else iu
                if not iu:
                    continue
                ir = fetcher.head_status(fetcher.abs(iu))
                if ir["status"] != 200 or not ir["headers"].get("content-type", "").startswith("image/"):
                    _f(pr, "critical", "SEO_JSONLD_IMAGE_BROKEN", "Obrázek z Product JSON-LD nevrací 200 image/*",
                       f"{iu} -> {ir['status']} {ir['headers'].get('content-type') or ir['error']}")
    if pr.kind in ("product", "category") and "BreadcrumbList" not in ld_types:
        _f(pr, "warning", "SEO_NO_BREADCRUMB_JSONLD", "Chybí BreadcrumbList JSON-LD",
           f"@type nalezeno: {sorted(set(ld_types))}", "Doplnit BreadcrumbList (vzor kategorie).")
    if pr.kind == "category" and "CollectionPage" not in ld_types and "ItemList" not in ld_types:
        _f(pr, "info", "SEO_CATEGORY_NO_COLLECTION_JSONLD", "Kategorie bez CollectionPage/ItemList JSON-LD",
           f"@type nalezeno: {sorted(set(ld_types))}")
    if pr.kind == "home":
        if not any(t in ld_types for t in ("Organization", "LocalBusiness", "Store", "OnlineStore")):
            _f(pr, "info", "SEO_REC_NO_ORGANIZATION_JSONLD", "Homepage bez Organization/LocalBusiness JSON-LD",
               f"@type nalezeno: {sorted(set(ld_types))} (AUDIT_SEO_AI_VISIBILITY bod 1, SEO_GEO_AUDIT 2.2).",
               "Doplnit Organization + WebSite site-wide (vzor sesterský projekt api/app.py _org_jsonld).")
        if "WebSite" not in ld_types:
            _f(pr, "info", "SEO_REC_NO_WEBSITE_JSONLD", "Homepage bez WebSite JSON-LD", "")
    if soup.select(".seo-faq") and "FAQPage" not in ld_types:
        _f(pr, "info", "SEO_REC_FAQ_WITHOUT_JSONLD", "Stránka má FAQ blok (.seo-faq), ale ne FAQPage JSON-LD",
           f"{len(soup.select('.seo-faq'))}× .seo-faq (AUDIT_SEO_AI_VISIBILITY bod 2).",
           "Generovat FAQPage z existujících otázek/odpovědí bloku.")

    # --- obrazky
    all_imgs = soup.find_all("img")
    content_root = soup.find("main") or soup.body or soup
    no_alt = [im for im in all_imgs if im.get("alt") is None]
    empty_alt = [im for im in all_imgs if im.get("alt") is not None and not im.get("alt").strip()]
    if no_alt:
        _f(pr, "warning", "A11Y_IMG_NO_ALT", "<img> bez atributu alt",
           f"{len(no_alt)}/{len(all_imgs)} např. {[(im.get('src') or im.get('data-src') or '')[:80] for im in no_alt[:3]]}",
           "Každý img potřebuje alt (popisný, nebo alt=\"\" u dekorace).")
    if empty_alt:
        _f(pr, "info", "A11Y_IMG_EMPTY_ALT", "<img> s prázdným alt (dekorativní?)",
           f"{len(empty_alt)}/{len(all_imgs)} např. {[(im.get('src') or '')[:80] for im in empty_alt[:3]]}",
           "OK jen u čistě dekorativních obrázků; u produktových fotek doplnit název.")
    hero = None
    for im in content_root.find_all("img"):
        if im.find_parent(["header", "nav", "template", "noscript"]):
            continue
        src = im.get("src") or ""
        if not src or src.startswith("data:"):
            continue
        hero = im
        break
    if hero is not None:
        # U kategorie je prvni obrazek jen dlazdice mrizky (cp-image/cs-thumb),
        # ne skutecny hero - tam jen info; na home/produktu/statice je to LCP kandidat.
        hero_sev = "info" if pr.kind == "category" else "warning"
        if not (hero.get("width") and hero.get("height")):
            _f(pr, hero_sev, "SEO_HERO_IMG_NO_DIMENSIONS", "První obrázek obsahu bez width/height (CLS)",
               _el_desc(hero), "Doplnit width/height (nebo CSS aspect-ratio), aby se layout neposouval.")
        if (hero.get("loading") or "").lower() == "lazy":
            _f(pr, hero_sev, "SEO_HERO_IMG_LAZY", "První obrázek obsahu má loading=lazy (zpomaluje LCP)",
               _el_desc(hero), "Hero/LCP obrázek načítat eager (+ fetchpriority=high).")
    if len(all_imgs) >= LAZY_INFO_MIN_IMGS:
        below = [im for im in all_imgs[3:] if im is not hero and (im.get("src") or "").strip()
                 and not (im.get("src") or "").startswith("data:")]
        not_lazy = [im for im in below if (im.get("loading") or "").lower() != "lazy"]
        if below and len(not_lazy) > len(below) * 0.5:
            _f(pr, "info", "SEO_IMAGES_NOT_LAZY", "Obrázky pod ohybem bez loading=lazy",
               f"{len(not_lazy)}/{len(below)} např. {[(im.get('src') or '')[:60] for im in not_lazy[:3]]}",
               "Přidat loading=\"lazy\" na obrázky mimo první obrazovku.")

    # --- mixed content
    mixed_active, mixed_passive = [], []
    for tag, attr in (("script", "src"), ("link", "href"), ("iframe", "src"), ("img", "src"),
                      ("source", "src"), ("video", "src"), ("audio", "src"), ("img", "srcset")):
        for el in soup.find_all(tag):
            v = el.get(attr) or ""
            if tag == "link" and "stylesheet" not in [x.lower() for x in (el.get("rel") or [])]:
                continue
            if "http://" in v:
                (mixed_active if tag in ("script", "link", "iframe") else mixed_passive).append(f"{tag} {v[:80]}")
    if mixed_active:
        _f(pr, "critical", "SEO_MIXED_CONTENT_ACTIVE", "Aktivní mixed content (http:// skript/CSS/iframe)",
           f"{len(mixed_active)}× např. {mixed_active[:3]}", "Prohlížeč to zablokuje - přepnout na https://.")
    if mixed_passive:
        _f(pr, "warning", "SEO_MIXED_CONTENT_PASSIVE", "Pasivní mixed content (http:// obrázek/médium)",
           f"{len(mixed_passive)}× např. {mixed_passive[:3]}")

    # --- odkazy
    empty_links, generic, no_text_links = [], [], []
    for a in soup.find_all("a"):
        href = (a.get("href") or "").strip()
        if a.find_parent(["template", "noscript"]):
            continue
        if not href or href == "#" or href.lower().startswith("javascript:"):
            if a.get("role") == "button" or a.get("onclick") or a.get("data-action"):
                continue  # vedome JS "tlacitko" ve forme odkazu
            empty_links.append(_el_desc(a) + " „" + _text(a)[:30] + "“")
            continue
        if href.startswith("#"):
            if re.search(r"obsah|skip|přeskoč|preskoc", _text(a), re.I):
                pr.has_skip_link = True
            continue
        if href.startswith(("mailto:", "tel:", "sms:")):
            continue
        absu = fetcher.abs(href)
        if fetcher.is_internal(absu):
            pr.internal_links.add(absu.split("#", 1)[0])
        t = _text(a).lower().strip(" .!:")
        if t in GENERIC_ANCHORS:
            generic.append(f"„{_text(a)}“ -> {href[:60]}")
        elif not _has_accessible_name(a):
            no_text_links.append(_el_desc(a))
    if empty_links:
        _f(pr, "info", "SEO_EMPTY_LINK", "Odkazy bez cíle (href prázdný/#/javascript:)",
           f"{len(empty_links)}× např. {empty_links[:3]}",
           "Buď skutečná URL, nebo <button> místo <a>.")
    if generic:
        _f(pr, "info", "SEO_GENERIC_ANCHOR", "Nepopisný text odkazu („zde“, „více“)",
           f"{len(generic)}× např. {generic[:3]}", "Text odkazu má říkat, kam vede.")
    if no_text_links:
        _f(pr, "warning", "A11Y_LINK_NO_TEXT", "Odkaz bez textu/aria-label (jen ikona)",
           f"{len(no_text_links)}× např. {no_text_links[:3]}",
           "Doplnit aria-label nebo vizuálně skrytý text.")

    # --- a11y formulare/tlacitka/tabulky
    label_for = {lb.get("for") for lb in soup.find_all("label") if lb.get("for")}
    unlabeled = []
    for fld in soup.find_all(["input", "select", "textarea"]):
        typ = (fld.get("type") or "text").lower()
        if typ in ("hidden", "submit", "button", "reset", "image"):
            continue
        if fld.find_parent(["template", "noscript"]):
            continue
        if fld.get("id") and fld.get("id") in label_for:
            continue
        if fld.get("aria-label") or fld.get("aria-labelledby") or fld.get("title"):
            continue
        if fld.find_parent("label"):
            continue
        unlabeled.append(_el_desc(fld))
    if unlabeled:
        _f(pr, "warning", "A11Y_FIELD_NO_LABEL", "Pole formuláře bez <label>/aria-label",
           f"{len(unlabeled)}× např. {unlabeled[:3]} (placeholder není náhrada popisku)",
           "Přidat <label for=id> nebo aria-label.")
    silent_buttons = []
    for b in soup.find_all("button") + soup.find_all("input", attrs={"type": re.compile("^(submit|button|image)$", re.I)}):
        if b.find_parent(["template", "noscript"]):
            continue
        if b.name == "input":
            if b.get("value") or b.get("aria-label") or b.get("alt") or b.get("title"):
                continue
            silent_buttons.append(_el_desc(b))
        elif not _has_accessible_name(b):
            silent_buttons.append(_el_desc(b))
    if silent_buttons:
        _f(pr, "warning", "A11Y_BUTTON_NO_TEXT", "Tlačítko bez textu/aria-label",
           f"{len(silent_buttons)}× např. {silent_buttons[:3]}", "Doplnit aria-label nebo text.")
    tables_no_th = [t for t in soup.find_all("table") if not t.find("th") and t.find("td")
                    and not t.find_parent(["template", "noscript"])]
    if tables_no_th:
        _f(pr, "info", "A11Y_TABLE_NO_TH", "Tabulka bez hlavičkových buněk <th>",
           f"{len(tables_no_th)}× např. {[_el_desc(t) for t in tables_no_th[:2]]}",
           "Datové tabulky potřebují <th scope=col/row>; layoutové tabulky nahradit CSS.")
    iframes_no_title = [f for f in soup.find_all("iframe") if not (f.get("title") or "").strip()]
    if iframes_no_title:
        _f(pr, "info", "A11Y_IFRAME_NO_TITLE", "iframe bez title",
           f"{len(iframes_no_title)}× např. {[(f.get('src') or '')[:60] for f in iframes_no_title[:2]]}")
    return pr


# ---------------------------------------------------------------- site-level
def check_host_redirects(fetcher, findings, stats):
    """http -> https, www vs. non-www, retezy, soft-404, /index.html."""
    host = fetcher.session.headers.get("Host") or fetcher.host
    bare = host.removeprefix("www.")
    canonical_home = fetcher.base + "/"
    variants = [f"http://{bare}/", f"http://www.{bare}/", f"https://www.{bare}/"]
    if fetcher.session.headers.get("Host"):
        variants = []  # pres lokalni base nema smysl testovat DNS varianty
    for v in variants:
        if _norm_url(v) == _norm_url(canonical_home):
            continue
        r = fetcher.get(v, follow=True)
        chain = [(s, loc) for s, loc in r["history"]]
        stats.setdefault("host_redirects", {})[v] = " -> ".join(f"{s} {loc}" for s, loc in chain) + f" -> {r['status']}"
        if r["error"]:
            findings.append(finding("warning", "SEO_HOST_VARIANT_ERROR", "Varianta hostu neodpovídá",
                                    f"{v}: {r['error'][:100]}", v,
                                    "DNS/nginx: www i non-www mají existovat a přesměrovávat na kanonický host."))
            continue
        final = _norm_url(r["final_url"])
        if not chain:
            sev = "critical" if v.startswith("http://") else "warning"
            detail = (f"{v} vrací {r['status']} přímo (duplicitní obsah; " +
                      ("http bez https" if v.startswith("http://") else "www i non-www indexovatelné") + ")")
            # Kdyz varianta navic ma canonical sama na sebe, je to plnohodnotny
            # duplicitni web (Google si vybere sam, ktery host indexuje).
            chref = ""
            try:
                soup = BeautifulSoup(r["body"], "lxml")
                for ln in (soup.head or soup).find_all("link"):
                    if "canonical" in [x.lower() for x in (ln.get("rel") or [])]:
                        chref = (ln.get("href") or "").strip()
                        break
            except Exception:  # noqa: BLE001
                pass
            if chref and _norm_url(chref) != _norm_url(canonical_home):
                sev = "critical"
                detail += f"; canonical na téhle variantě = {chref} (ukazuje sám na sebe, ne na {canonical_home})"
            # Kdyz varianta vydava i vlastni sitemapu s URL na sobe, robot
            # dostane kompletni druhy web k indexaci.
            sm = fetcher.get(v + "sitemap.xml", follow=True)
            if sm["status"] == 200 and sm["body"]:
                vhost = urllib.parse.urlsplit(v).netloc
                locs = re.findall(rb"<loc>\s*([^<\s]+)", sm["body"])
                own = [x for x in locs if urllib.parse.urlsplit(x.decode("utf-8", "replace")).netloc == vhost]
                if own:
                    sev = "critical"
                    detail += (f"; {v}sitemap.xml vrací 200 a {len(own)}/{len(locs)} URL v ní je na {vhost} "
                               f"(např. {own[0].decode('utf-8', 'replace')})")
            findings.append(finding(sev, "SEO_HOST_VARIANT_NO_REDIRECT",
                                    "Varianta hostu se nepřesměrovává na kanonickou URL", detail, v,
                                    f"nginx: 301 {v} -> {canonical_home} (server_name www.* do vlastního "
                                    "server bloku s return 301); canonical/og:url/sitemap/JSON-LD generovat "
                                    "z pevné kanonické domény (konstanta/env), ne z request.host_url "
                                    "(api/app.py: _render_og_page, sitemap, robots)."))
        else:
            if final != _norm_url(canonical_home):
                findings.append(finding("warning", "SEO_HOST_VARIANT_WRONG_TARGET",
                                        "Varianta hostu končí jinde než na kanonické URL",
                                        f"{v} -> {r['final_url']}", v, f"Cíl má být {canonical_home}"))
            if len(chain) > 1:
                findings.append(finding("warning", "SEO_REDIRECT_CHAIN", "Přesměrovací řetěz (více než 1 skok)",
                                        f"{v}: " + " -> ".join(f"{s} {loc}" for s, loc in chain), v,
                                        "Přesměrovat rovnou na https://kanonický-host/ (jeden 301)."))
            if any(s in (302, 303, 307) for s, _ in chain):
                findings.append(finding("info", "SEO_REDIRECT_TEMPORARY", "Přesměrování hostu je dočasné (302/307)",
                                        f"{v}: {chain}", v, "Pro trvalé přesměrování použít 301/308."))
    # soft 404
    probe = fetcher.base + "/qa-neexistujici-stranka-" + "".join(random.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(10))
    r = fetcher.get(probe, follow=True)
    stats["soft404_probe_status"] = r["status"]
    if r["status"] == 200:
        findings.append(finding("warning", "SEO_SOFT_404", "Neexistující URL vrací 200 (soft 404)",
                                f"{probe} -> 200, {len(r['body'])} B" + (" (obsah homepage)" if b"<title>" in r["body"] else ""),
                                probe, "Neznámé cesty mají vracet 404 (nebo 410) s vlastní chybovou stránkou; "
                                       "SPA fallback na index.html indexuje nekonečno duplicit."))
    elif r["status"] in (301, 302) or r["history"]:
        findings.append(finding("info", "SEO_404_REDIRECTS", "Neexistující URL přesměrovává místo 404",
                                f"{probe} -> {r['history']} -> {r['status']}", probe))
    for probe2 in (fetcher.base + "/produkt/qa-neexistujici-produkt-xyz", fetcher.base + "/kategorie/qa-neexistujici-kategorie-xyz"):
        r2 = fetcher.get(probe2, follow=True)
        if r2["status"] == 200:
            findings.append(finding("warning", "SEO_SOFT_404", "Neexistující produkt/kategorie vrací 200 (soft 404)",
                                    f"{probe2} -> 200, {len(r2['body'])} B", probe2,
                                    "Neznámý slug má vracet 404."))
    # Syrove SSR sablony (bot15, 2026-09-02): webapp/blok.html, storefront-*.html
    # jsou jen sablony pro Flask (_render_og_page nahrazuje OG_TAGS_PLACEHOLDER),
    # nginx `location /` je ale servíroval primo ze souboru = indexovatelna
    # stranka bez h1/OG s default title (duplicita s homepage).
    for path in RAW_TEMPLATES:
        r3 = fetcher.get(fetcher.base + path, follow=True)
        if r3["status"] == 200 and b"OG_TAGS_PLACEHOLDER" in r3["body"]:
            findings.append(finding("warning", "SEO_RAW_TEMPLATE_SERVED", "Syrová SSR šablona je dostupná jako stránka",
                                    f"{path} -> 200 s nenahrazeným OG_TAGS_PLACEHOLDER ({len(r3['body'])} B)",
                                    fetcher.base + path,
                                    "nginx: `location ~ ^/(blok|storefront-[a-z0-9-]+)\\.html$ { return 404; }` "
                                    "- sablony se maji renderovat jen pres Flask (/blok/<slug>, storefront domeny)."))


def check_internal_links(fetcher, pages, known_ok, findings, stats, max_links):
    where = collections.defaultdict(list)
    for p in pages:
        for ln in p.internal_links:
            if ln in known_ok:
                continue
            path = urllib.parse.urlsplit(ln).path
            if path.startswith("/api/"):
                continue
            where[ln].append(p.url)
    cands = sorted(where)
    stats["internal_links_unique_unknown"] = len(cands)
    if len(cands) > max_links:
        random.shuffle(cands)
        cands = sorted(cands[:max_links])
    stats["internal_links_checked"] = len(cands)

    def probe(u):
        return u, fetcher.head_status(u)

    broken, redirects = [], []
    for u, r in fetcher.pmap(probe, cands):
        if r["error"] or (r["status"] and r["status"] >= 400):
            broken.append((u, r["status"] or r["error"][:40], where[u][:2]))
        elif r["status"] in (301, 302, 307, 308):
            redirects.append((u, r["status"], r["location"], where[u][:1]))
    if broken:
        findings.append(finding("critical" if any(s == 404 for _, s, _ in broken) else "warning",
                                "SEO_INTERNAL_LINK_BROKEN", "Interní odkaz vede na 404/chybu",
                                f"{len(broken)}× (cíl, status, kde): {broken[:6]}", None,
                                "Opravit href / doplnit přesměrování."))
    if redirects:
        findings.append(finding("info", "SEO_INTERNAL_LINK_REDIRECT", "Interní odkaz vede přes přesměrování",
                                f"{len(redirects)}× např. {redirects[:4]}", None,
                                "Odkazovat rovnou na cílovou URL (šetří skok, PageRank)."))


def aggregate_page_findings(page_findings, total_pages):
    """Stejny kod+zavaznost na >= AGG_MIN_PAGES strankach -> jeden souhrnny
    nalez (pocet, rozpad podle typu stranky, 3 priklady). Jinak by report
    mel stovky radku "totez na kazde strance" a skutecne jednotlive chyby
    by v nem zapadly. Plny seznam zustava v report souboru (page_findings)."""
    groups = collections.OrderedDict()
    for f in page_findings:
        groups.setdefault((f["code"], f["severity"]), []).append(f)
    out = []
    for (code, sev), fs in groups.items():
        if len(fs) < AGG_MIN_PAGES:
            out.extend(fs)
            continue
        kinds = collections.Counter(_classify(urllib.parse.urlsplit(f["where"] or "").path) for f in fs)
        examples = " | ".join(f"{f['where']}: {f['detail'][:110]}" for f in fs[:3])
        out.append(finding(
            sev, code, f"{fs[0]['title']} ({len(fs)}× ve vzorku)",
            f"{len(fs)}/{total_pages} stránek ({', '.join(f'{k}: {n}' for k, n in kinds.most_common())}); "
            f"např. {examples}",
            fs[0]["where"], fs[0].get("fix_hint")))
    return out


def check_duplicates(pages, findings):
    for attr, code, label in (("title", "SEO_DUPLICATE_TITLE", "<title>"),
                              ("description", "SEO_DUPLICATE_DESCRIPTION", "meta description")):
        groups = collections.defaultdict(list)
        for p in pages:
            v = getattr(p, attr)
            if v:
                groups[v.strip().lower()].append(p.url)
        dup = {k: v for k, v in groups.items() if len(v) > 1}
        for k, urls in sorted(dup.items(), key=lambda kv: -len(kv[1]))[:10]:
            findings.append(finding("warning", code, f"Duplicitní {label} na více URL",
                                    f"„{k[:90]}“ na {len(urls)} URL: {urls[:5]}", urls[0],
                                    f"Každá indexovatelná stránka má mít unikátní {label}."))
        if len(dup) > 10:
            findings.append(finding("info", code + "_MORE", f"Dalších {len(dup) - 10} skupin duplicitních {label}",
                                    "Viz report soubor.", None))


def cwv_estimate(fetcher, urls, stats, findings):
    """Volitelne: LCP/CLS pres Playwright (node, chromium), sekvencne."""
    if ram_watchdog_alert_active():
        stats["cwv"] = "přeskočeno: /run/ram-watchdog-alert aktivní"
        return
    pw = os.path.join(REPO_ROOT, "node_modules", "playwright")
    if not os.path.isdir(pw):
        stats["cwv"] = "přeskočeno: node_modules/playwright chybí"
        return
    js = r"""
const { chromium } = require(process.argv[1]);
(async () => {
  const urls = JSON.parse(process.argv[2]);
  const out = [];
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  for (const url of urls) {
    const ctx = await browser.newContext({ userAgent: 'KonfiguratorQA/1.0 (Playwright)', viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    await page.addInitScript(() => {
      window.__qa = { lcp: 0, cls: 0 };
      new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__qa.lcp = e.startTime; }).observe({ type: 'largest-contentful-paint', buffered: true });
      new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__qa.cls += e.value; }).observe({ type: 'layout-shift', buffered: true });
    });
    const t0 = Date.now();
    let err = null;
    try { await page.goto(url, { waitUntil: 'load', timeout: 45000 }); await page.waitForTimeout(2500); } catch (e) { err = String(e).slice(0, 120); }
    const m = await page.evaluate(() => {
      const nav = performance.getEntriesByType('navigation')[0] || {};
      return { lcp_ms: Math.round(window.__qa.lcp), cls: Math.round(window.__qa.cls * 1000) / 1000,
               ttfb_ms: Math.round(nav.responseStart || 0), dcl_ms: Math.round(nav.domContentLoadedEventEnd || 0),
               load_ms: Math.round(nav.loadEventEnd || 0), transfer_kb: Math.round((nav.transferSize || 0) / 1024) };
    }).catch(() => ({}));
    out.push(Object.assign({ url, wall_ms: Date.now() - t0, error: err }, m));
    await ctx.close();
  }
  await browser.close();
  console.log(JSON.stringify(out));
})().catch((e) => { console.error(e); process.exit(1); });
"""
    try:
        p = subprocess.run(["node", "-e", js, pw, json.dumps(urls)], capture_output=True, text=True,
                           timeout=240, cwd=REPO_ROOT)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        stats["cwv"] = f"selhalo: {e!r}"[:200]
        return
    if p.returncode != 0:
        stats["cwv"] = f"selhalo: {p.stderr.strip()[-300:]}"
        return
    try:
        data = json.loads(p.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        stats["cwv"] = f"nečitelný výstup: {p.stdout[-200:]}"
        return
    stats["cwv"] = data
    for d in data:
        if d.get("error"):
            continue
        if d.get("lcp_ms", 0) > 4000:
            findings.append(finding("warning", "CWV_LCP_POOR", "LCP nad 4 s (lab, Chromium bez CDN)",
                                    f"LCP {d['lcp_ms']} ms, TTFB {d.get('ttfb_ms')} ms", d["url"],
                                    "Zmenšit hero obrázek/inline CSS, preload LCP obrázku."))
        elif d.get("lcp_ms", 0) > 2500:
            findings.append(finding("info", "CWV_LCP_NEEDS_IMPROVEMENT", "LCP 2.5-4 s (lab)",
                                    f"LCP {d['lcp_ms']} ms", d["url"]))
        if d.get("cls", 0) > 0.25:
            findings.append(finding("warning", "CWV_CLS_POOR", "CLS nad 0.25 (lab)", f"CLS {d['cls']}", d["url"],
                                    "Rezervovat místo obrázkům/widgetům (width/height, aspect-ratio)."))
        elif d.get("cls", 0) > 0.1:
            findings.append(finding("info", "CWV_CLS_NEEDS_IMPROVEMENT", "CLS 0.1-0.25 (lab)", f"CLS {d['cls']}", d["url"]))


# ---------------------------------------------------------------- main
def build_collect(args):
    def collect():
        findings, stats = [], {}
        fetcher = Fetcher(args.base, args.host, args.timeout)
        public_base = f"https://{args.host}" if args.host else fetcher.base
        rp_holder = {}
        entries = check_sitemap_and_robots(fetcher, findings, stats, rp_holder)
        rp = rp_holder.get("rp")
        sitemap_set = {e["loc"] for e in entries}

        # vzorek
        cats = sorted(e["loc"] for e in entries if _classify(urllib.parse.urlsplit(e["loc"]).path) == "category")
        prods = sorted(e["loc"] for e in entries if _classify(urllib.parse.urlsplit(e["loc"]).path) == "product")
        rng = random.Random(args.seed)
        if args.full:
            sample_prods = prods
        else:
            sample_prods = rng.sample(prods, min(args.sample, len(prods)))
        for ap in ALWAYS_PRODUCTS:
            u = public_base + ap
            if u not in sample_prods:
                sample_prods.append(u)
        statics = [public_base + s for s in STATIC_PAGES] + [fetcher.abs(x) for x in (args.page or [])]
        sample = []
        for u in statics + cats + sample_prods:
            if u not in sample:
                sample.append(u)
        stats["sample_pages"] = len(sample)
        stats["sample_categories"] = len(cats)
        stats["sample_products"] = len(sample_prods)
        stats["sample_static"] = len(statics)

        pages = fetcher.pmap(lambda u: analyze_page(fetcher, u, u in sitemap_set, rp), sample)
        page_findings = [f for p in pages for f in p.findings]
        findings.extend(aggregate_page_findings(page_findings, len(pages)))
        stats["page_hits_by_code"] = dict(collections.Counter(f["code"] for f in page_findings).most_common())
        ok_pages = [p for p in pages if p.ok]
        if ok_pages:
            times = sorted(p.elapsed for p in ok_pages)
            sizes = [p.size for p in ok_pages]
            stats["response_time_s"] = {"avg": round(sum(times) / len(times), 3), "p90": round(times[int(0.9 * (len(times) - 1))], 3),
                                        "max": round(times[-1], 3)}
            stats["html_kb"] = {"avg": round(sum(sizes) / len(sizes) / 1024), "max": round(max(sizes) / 1024)}
        check_duplicates(ok_pages, findings)
        if not any(p.has_skip_link for p in ok_pages if p.kind == "home"):
            findings.append(finding("info", "A11Y_NO_SKIP_LINK", "Chybí skip-link („Přeskočit na obsah“)",
                                    "Homepage nemá odkaz pro přeskočení navigace klávesnicí.", public_base + "/",
                                    "Přidat <a href=\"#main\" class=\"skip-link\">Přeskočit na obsah</a> jako první prvek body."))
        # staticke stranky mimo sitemapu
        missing_in_sm = [p.url for p in ok_pages if p.kind in ("static", "home") and p.indexable
                         and p.url not in sitemap_set and _norm_url(p.url) not in {_norm_url(s) for s in sitemap_set}]
        if missing_in_sm:
            findings.append(finding("info", "SEO_INDEXABLE_PAGE_NOT_IN_SITEMAP",
                                    "Indexovatelná statická stránka chybí v sitemapě",
                                    f"{len(missing_in_sm)}×: {missing_in_sm}", public_base + "/sitemap.xml",
                                    "Přidat do generování sitemapy (kontakt, realizace, blok, remeslo…) nebo dát noindex."))
        if not args.no_links:
            check_internal_links(fetcher, ok_pages, sitemap_set, findings, stats, args.max_links)
        check_host_redirects(fetcher, findings, stats)
        if args.cwv:
            cwv_urls = [public_base + "/", cats[0] if cats else public_base + "/", public_base + ALWAYS_PRODUCTS[0]]
            cwv_estimate(fetcher, cwv_urls, stats, findings)

        stats["http_requests"] = fetcher.requests_made
        stats["downloaded_mb"] = round(fetcher.bytes_downloaded / 1024 / 1024, 1)
        stats["findings_by_code"] = dict(collections.Counter(f["code"] for f in findings).most_common())
        stats["base"] = args.base
        stats["seed"] = args.seed
        stats["full"] = bool(args.full)

        # report do qa-reports/
        if not args.no_report:
            ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            report = {"suite": "seo", "ran_at": now_iso(), "status": overall_status(findings),
                      "findings": findings, "stats": stats,
                      "page_findings": page_findings,  # nesouhrnne, po strankach
                      "sample": sample}
            for name in (f"seo-{ts}.json", "seo-latest.json"):
                try:
                    with open(os.path.join(QA_REPORTS_DIR, name), "w", encoding="utf-8") as f:
                        json.dump(report, f, ensure_ascii=False, indent=1)
                except OSError as e:
                    stats["report_error"] = repr(e)
            stats["report_file"] = os.path.join(QA_REPORTS_DIR, f"seo-{ts}.json")
        return findings, stats
    return collect


def main():
    ap = argparse.ArgumentParser(description="SEO + a11y crawl (read-only) - viz docstring")
    ap.add_argument("--json", action="store_true", help="výstup jako JSON (kontrakt _common.py)")
    ap.add_argument("--base", default="https://autovestavby.logiman.cz", help="základní URL (default https://autovestavby.logiman.cz)")
    ap.add_argument("--host", default=None, help="Host hlavička (pro --base http://127.0.0.1:8090 --host autovestavby.logiman.cz)")
    ap.add_argument("--sample", type=int, default=40, help="počet náhodných produktů v hlubokém vzorku (default 40)")
    ap.add_argument("--full", action="store_true", help="hluboká kontrola VŠECH produktů ze sitemapy (dlouhé)")
    ap.add_argument("--seed", type=int, default=None, help="seed náhodného výběru (opakovatelnost)")
    ap.add_argument("--page", action="append", help="další URL/cesta do vzorku (opakovatelné)")
    ap.add_argument("--max-links", type=int, default=200, help="max. unikátních interních odkazů k ověření (default 200)")
    ap.add_argument("--no-links", action="store_true", help="přeskočit kontrolu interních odkazů")
    ap.add_argument("--cwv", action="store_true", help="navíc LCP/CLS 3 stránek přes Playwright (node, chromium)")
    ap.add_argument("--timeout", type=int, default=TIMEOUT)
    ap.add_argument("--no-report", action="store_true", help="neukládat JSON do qa-reports/")
    args = ap.parse_args()
    run_suite("seo", build_collect(args), args.json)


if __name__ == "__main__":
    main()
