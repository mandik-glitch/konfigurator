"""Pravni stranky HLAVNIHO webu: /ochrana-osobnich-udaju a /obchodni-podminky (bot16, 2026-10-05; Robert: "zalozit ochranu osobnich udaju").

PROC: formular "Ulozit konfiguraci" (api/stul_ulozeni.py) a objednavka hosta v generatoru stolu (api/stul_objednavka_host.py) sbiraji osobni udaje a v embedu odkazuji na tyto dve adresy
(webapp/embed/stul-embed.js a stul-embed-objednavka.js: odkaz se ukaze JEN kdyz stranka existuje, HEAD probe). Na hlavnim webu byly dosud 404 (zjisteno 2026-10-05 po zapnuti ukladani).

Texty = miniweb_documents (family packstations, lang cs, status approved): tytez dokumenty (kind privacy | terms), ktere pro SK/EN schvaluje Robert u mini-shopu (miniweb-schvaleni.html);
CZ navrh od bot7 je docs/cz_pravni_navrh_objednavka_hosta.json (import: scripts/miniweb_import.py). Zadny text natvrdo v kodu (pravidlo 55). Stranka je verejna JEN kdyz je dokument
SCHVALENY; jinak 404 - dokud neni schvaleny `terms`, objednavka hosta dal pouziva docasne znění souhlasu bez odkazu (embed ma odkazy az kdyz existuji OBE stranky).

Znacka: dokument jmenuje spravce (LOGIMAN s.r.o.), proto se servi jen na hostech, kde smi byt znacka (site_brand._LOGO_HOSTS = hlavni web, www, IP vhost); na anonymnich domenach (storefronty)
je to 404 (TEXT_FILTR 5, jako u staticke stranky nesmi unikat znacka). Odpoved: samostatna HTML stranka, vse z DB escapovane, cache 5 min."""
import functools
import html
import re

from flask import Response, request

from app import app, get_conn, PUBLIC_BASE_URL
import site_brand

FAMILY, LANG = "packstations", "cs"
STRANKY = {"/ochrana-osobnich-udaju": "privacy", "/obchodni-podminky": "terms"}

CSS = """:root{color-scheme:light dark;--bg:#fff;--fg:#1c2530;--mut:#5a6672;--ln:#d9dee3;--ac:#0b7a6e}
@media (prefers-color-scheme:dark){:root{--bg:#10151b;--fg:#e4e8ec;--mut:#9aa6b2;--ln:#2a3440;--ac:#2dd4bf}}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif}
main{max-width:760px;margin:0 auto;padding:20px 16px 48px}
h1{font-size:1.6rem;line-height:1.25;margin:.4rem 0 1rem}h2{font-size:1.1rem;margin:1.6rem 0 .3rem}p{margin:.3rem 0;white-space:pre-line}
a{color:var(--ac)}.zpet{font-size:.9rem;margin:0}.datum{margin-top:2rem;color:var(--mut);font-size:.85rem;border-top:1px solid var(--ln);padding-top:.8rem}"""


def _bloky(text):
    """Cisty text s odstavci -> [(nadpis | None, odstavec)]. Blok = oddeleny prazdnym radkem; kdyz ma vic radku a prvni je kratky (<= 80 znaku, nekonci teckou ani dvojteckou), je to nadpis."""
    out = []
    for blok in re.split(r"\n\s*\n", (text or "").replace("\r\n", "\n").strip()):
        radky = [r.strip() for r in blok.split("\n") if r.strip()]
        if not radky:
            continue
        if len(radky) > 1 and len(radky[0]) <= 80 and not radky[0].endswith((".", ":", ";", ",")):
            out.append((radky[0], "\n".join(radky[1:])))
        else:
            out.append((None, "\n".join(radky)))
    return out


def _datum(dt):
    return "%d. %d. %d" % (dt.day, dt.month, dt.year) if dt else ""


def render(doc, cesta):
    e = html.escape
    telo = "".join(("<h2>%s</h2>" % e(h) if h else "") + "<p>%s</p>" % e(p) for h, p in _bloky(doc["body"]))
    kdy = _datum(doc.get("approved_at") or doc.get("updated_at"))
    canon = (PUBLIC_BASE_URL or "").rstrip("/") + cesta
    return ('<!doctype html>\n<html lang="cs"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>%s</title><meta name="robots" content="index,follow"><link rel="canonical" href="%s"><style>%s</style></head>'
            '<body><main><p class="zpet"><a href="/">&larr; Zp&#283;t na web</a></p><h1>%s</h1>%s%s</main></body></html>'
            % (e(doc["title"]), e(canon, quote=True), CSS, e(doc["title"]), telo, ('<p class="datum">Platné od %s</p>' % e(kdy)) if kdy else ""))


def _strana(kind, cesta):
    host = (request.host or "").split(":")[0].strip().lower()
    if host not in site_brand._LOGO_HOSTS:                         # anonymni domeny: zadna znacka, zadna stranka
        return Response("Stranka nenalezena.", status=404, mimetype="text/plain")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT title, body, approved_at, updated_at FROM miniweb_documents WHERE family=%s AND kind=%s AND lang=%s AND status='approved'", (FAMILY, kind, LANG))
            doc = cur.fetchone()
    finally:
        conn.close()
    if not doc or not (doc["body"] or "").strip():
        return Response("Stranka nenalezena.", status=404, mimetype="text/plain")
    r = Response(render(doc, cesta), mimetype="text/html")
    r.headers["Cache-Control"] = "public, max-age=300"
    r.headers["Content-Language"] = "cs"
    r.headers["X-Content-Type-Options"] = "nosniff"
    return r


for _cesta, _kind in STRANKY.items():
    app.add_url_rule(_cesta, endpoint="legal_page_" + _kind, view_func=functools.partial(_strana, _kind, _cesta), methods=["GET"])
