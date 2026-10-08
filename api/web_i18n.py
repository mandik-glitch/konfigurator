"""Jazykove verze HLAVNIHO webu (EN = vandrawee.eu, IT = vandrawee.it) - bot16, 2026-10-08 (Robert; architektura a smlouva: docs/web_jazyky/README.md).

CO TENHLE MODUL DELA (a nic jineho; ostatni soubory se nemeni, jen `import web_i18n` na konci app.py):
  1. jazyk pozadavku: host -> radek web_sites (jazyk, mena, stav) a nahled zamestnance (?jazyk=en|it -> cookie web_jazyk, jen pro prihlaseneho zamestnance). Host, ktery v web_sites neni, = cestina, nic se nemeni.
  2. GET /api/i18n/ui.js?l=en - slovnik textu stranek ("window.__I18N = {...}") pro webapp/js/i18n.js; zdroj tabulka web_i18n (klic ui:..., stav nezastarale).
  3. after_request pro HTML: na jazykovem hostu (nebo v nahledu) nastavi <html lang>, vlozi slovnik + i18n.js na zacatek <head> a schova stranku do prvniho prekladu (html.i18n-pending),
     a drzi stranku mimo indexaci (noindex), dokud web_sites.status != live nebo indexable = 0.
  4. after_request pro verejne JSON endpointy (kategorie, produkty, bocni bloky, doprava/platba): doplni preklady z web_i18n (klic kod:pk:pole podle sesitu bot7), odkazy @cat:ID v HTML poli
     nahradi cestou, na jazykovem hostu skryje dodavatele (manufacturer) a CENY V KC (cena v EUR = faze 3, bot5; do te doby "napiste nam pro cenu") a vypne kosik.
  5. pomocne funkce pro SSR (storefront_pages): jazyk(), prelozit_radky().
FALLBACK: chybi-li preklad nebo je zastaraly (web_i18n.zastarale = 1), vrati se cestina; nic nepadne (kazda chyba modulu = puvodni odpoved).
CESTINA NIC NEPLATI: na hostu bez radku v web_sites a bez nahledu modul jen vrati puvodni odpoved (jedno hledani v cache slovniku hostu).
Tabulky web_sites a web_i18n: sql/2026-10-08_web_jazyky.sql, plni scripts/web_jazyk_import.py ze sesitu docs/web_jazyky/*.json.
"""
import hashlib
import json
import os
import re
import threading
import time
from decimal import Decimal, ROUND_HALF_UP

from flask import g, request, make_response

from app import app, get_conn
from products import _is_staff_request

JAZYKY = ("en", "it")
COOKIE = "web_jazyk"
CACHE_S = 60
WEBAPP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "webapp")

_lock = threading.Lock()
_SITES = {"t": 0.0, "rows": {}}
_SLUGY = {"t": 0.0, "rows": {}}
_UI = {}                 # lang -> {"t": cas, "data": dict, "hash": str}
_JS_VERZE = {"mtime": 0, "hash": ""}


# ---------------------------------------------------------------------------------------------------------------------------------------------
# jazyk pozadavku
# ---------------------------------------------------------------------------------------------------------------------------------------------
def _host():
    return (request.host or "").split(":")[0].strip().lower()


def sites(obnov=False):
    """{host: radek web_sites} (cache 60 s). Chybi-li tabulka nebo je DB nedostupna, {} = cestina vsude."""
    t = time.time()
    with _lock:
        if not obnov and t - _SITES["t"] < CACHE_S:
            return _SITES["rows"]
    rows = {}
    try:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT host, canonical_host, lang, locale, currency, price_mode, eur_rate, margin_pct, status, indexable, x_default FROM web_sites")
                for r in cur.fetchall():
                    rows[(r["host"] or "").lower()] = r
        finally:
            conn.close()
    except Exception as e:      # tabulka jeste neni / DB vypadek: cestina
        app.logger.warning("web_i18n: web_sites se nepodarilo nacist (%s)", e)
    with _lock:
        _SITES.update(t=t, rows=rows)
    return rows


def site():
    """Radek web_sites pro aktualni host, nebo None."""
    return sites().get(_host())


def _je_zamestnanec():
    try:
        return bool(_is_staff_request())
    except Exception:
        return False


def jazyk():
    """'cs' | 'en' | 'it' pro aktualni pozadavek (jednou za pozadavek)."""
    if hasattr(g, "web_jazyk"):
        return g.web_jazyk
    lang, zdroj = "cs", "host"
    s = site()
    p = (request.args.get("jazyk") or "").strip().lower()
    c = (request.cookies.get(COOKIE) or "").strip().lower()
    kandidat = p if p in ("cs",) + JAZYKY else (c if c in ("cs",) + JAZYKY else None)
    zam = None
    if kandidat is not None or (s and s["status"] != "live"):
        zam = _je_zamestnanec()
    if kandidat is not None and zam:
        lang, zdroj = kandidat, "nahled"
        if p in ("cs",) + JAZYKY:
            g.web_jazyk_cookie = p
    elif s and s["lang"] in JAZYKY and (s["status"] == "live" or zam):
        lang, zdroj = s["lang"], "host"
    g.web_jazyk, g.web_jazyk_zdroj = lang, zdroj
    # jazykovy host, ktery jeste neni zive pro verejnost: cesky obsah, ale NIKDY do indexu
    g.web_nezive_host = bool(s and s["status"] != "live" and lang == "cs")
    return lang


def mena_site():
    """{'locale', 'currency'} pro jazyk pozadavku (z hostu, nebo vychozi pro nahled)."""
    lang = jazyk()
    s = site()
    if s and s["lang"] == lang:
        return {"locale": s["locale"], "currency": s["currency"]}
    return {"locale": {"en": "en-GB", "it": "it-IT"}.get(lang, "cs-CZ"), "currency": "EUR" if lang in JAZYKY else "CZK"}


def je_indexovatelny():
    s = site()
    return bool(s and s["status"] == "live" and s["indexable"] and jazyk() == s["lang"] and g.get("web_jazyk_zdroj") == "host")


def site_pro_jazyk(lang=None):
    """Radek web_sites pro pocitani cen: radek aktualniho hostu, a v nahledu zamestnance na jinem hostu prvni radek stejneho jazyka (hlavni host drive nez alias)."""
    lang = lang or jazyk()
    s = site()
    if s and s["lang"] == lang:
        return s
    kandidati = sorted((r for r in sites().values() if r["lang"] == lang), key=lambda r: (r["canonical_host"] is not None, r["host"]))
    return kandidati[0] if kandidati else None


def cfg_cen(lang=None):
    """{'currency', 'rate', 'margin_pct'} (miniweb_cena.nastaveni: kurz = ruce zadany nebo zivy Fio, marze z web_sites) nebo None = ZADNA cena (pravidlo 9: bez marze / kurzu se Kc nikdy neprevadi odhadem)."""
    s = site_pro_jazyk(lang)
    if not s or s.get("price_mode") != "excl_vat":
        return None
    try:
        import miniweb_cena
        return miniweb_cena.nastaveni({"price_mode": "shown", "currency": s["currency"], "margin_pct": s["margin_pct"], "eur_rate": s["eur_rate"]})
    except Exception as e:
        app.logger.warning("web_i18n: cena EUR neni k dispozici (%s)", e)
        return None


def cena_eur(czk, cfg):
    """Kc bez DPH -> EUR bez DPH na 2 desetinna mista (pulky nahoru); None bez nastaveni / neplatna hodnota. (Mini-shopy zaokrouhluji na cele EUR - u celeho katalogu by drobny material vysel 0 EUR.)"""
    if czk is None or cfg is None or isinstance(czk, bool):
        return None
    try:
        d = Decimal(str(czk))
    except Exception:
        return None
    if not d.is_finite():
        return None
    return float((d / cfg["rate"] * (1 + cfg["margin_pct"] / 100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


_RE_CZK = re.compile(r"(^|_)czk(_|$)")          # price_czk, price_czk_placeholder, effective_price_czk, unit_price_per_m_czk ...
STAFF_POLE = ("dealer_discount_percent", "price_source_url", "dogus_price_coefficient", "min_stock", "max_stock", "supplier_id")


def preved_ceny(obj, cfg):
    """Rekurzivne: vsechna cisla v polich *_czk -> EUR (cena zakaznika; nazvy poli zustavaji, dokumentovano v docs/web_jazyky/README.md), bez nastaveni None. Staff pole pryc."""
    if isinstance(obj, dict):
        for k in list(obj.keys()):
            v = obj[k]
            if k in STAFF_POLE:
                obj[k] = None
            elif _RE_CZK.search(k) and not isinstance(v, (dict, list)):
                obj[k] = cena_eur(v, cfg)
            elif isinstance(v, (dict, list)):
                preved_ceny(v, cfg)
    elif isinstance(obj, list):
        for x in obj:
            preved_ceny(x, cfg)
    return obj


# ---------------------------------------------------------------------------------------------------------------------------------------------
# preklady z web_i18n
# ---------------------------------------------------------------------------------------------------------------------------------------------
def nacti_preklady(lang, klice):
    """{klic: text} jen pro nezastarale preklady daneho jazyka."""
    klice = list(dict.fromkeys(klice))
    out = {}
    if not klice or lang not in JAZYKY:
        return out
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for i in range(0, len(klice), 800):
                davka = klice[i:i + 800]
                cur.execute("SELECT klic, `text` FROM web_i18n WHERE lang=%s AND zastarale=0 AND klic IN (" + ",".join(["%s"] * len(davka)) + ")", [lang] + davka)
                for r in cur.fetchall():
                    out[r["klic"]] = r["text"]
    finally:
        conn.close()
    return out


def _slugy():
    t = time.time()
    with _lock:
        if t - _SLUGY["t"] < 300 and _SLUGY["rows"]:
            return _SLUGY["rows"]
    rows = {}
    try:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, slug FROM content_categories")
                rows = {int(r["id"]): r["slug"] for r in cur.fetchall()}
        finally:
            conn.close()
    except Exception as e:
        app.logger.warning("web_i18n: slugy kategorii se nepodarilo nacist (%s)", e)
    with _lock:
        _SLUGY.update(t=t, rows=rows)
    return rows


_RE_CAT = re.compile(r'href="@cat:(\d+)"')


def odkazy_html(html):
    """href="@cat:ID" (preklad od bot7) -> href="/<slug>" (zatim cesky slug; prelozene slugy = 08_slugy.json, dalsi faze)."""
    if not isinstance(html, str) or "@cat:" not in html:
        return html
    slugy = _slugy()

    def r(m):
        s = slugy.get(int(m.group(1)))
        return 'href="/%s"' % s if s else 'href="#"'
    return _RE_CAT.sub(r, html)


class Davka:
    """Sbira pole k prekladu v jednom pruchodu a vyridi je JEDNIM dotazem (zadne N+1)."""

    def __init__(self):
        self.polozky = []                          # (dict, json_klic, web_i18n_klic)
        self.slozene = []                          # (dict, json_klic, [klice], slozit(preklady) -> text)

    def pridej_slozene(self, d, json_klic, klice, slozit):
        """Pole slozene z vice prelozitelnych casti (napr. nazev sestavy z fragmentu): slozit({klic: preklad}) vrati novy text, nebo None (nic se nezmeni)."""
        if isinstance(d, dict) and isinstance(d.get(json_klic), str) and klice:
            self.slozene.append((d, json_klic, list(klice), slozit))

    def pridej(self, d, json_klic, klic):
        if isinstance(d, dict) and isinstance(d.get(json_klic), str) and d.get(json_klic).strip():
            self.polozky.append((d, json_klic, klic))

    def proved(self, lang):
        if not self.polozky and not self.slozene:
            return 0
        pr = nacti_preklady(lang, [k for _, _, k in self.polozky] + [k for _, _, ks, _ in self.slozene for k in ks])
        n = 0
        for d, jk, k in self.polozky:
            t = pr.get(k)
            if t:
                d[jk] = odkazy_html(t)
                n += 1
        for d, jk, ks, slozit in self.slozene:
            t = slozit({k: pr[k] for k in ks if k in pr})
            if t:
                d[jk] = t
                n += 1
        return n


def lokalizuj_strom(uzly, lang=None):
    """Pro SSR: strom kategorii (list uzlu s 'children') -> preklady name / nav_label / menu_group_label. Vraci pocet prelozenych poli."""
    lang = lang or jazyk()
    if lang not in JAZYKY or not uzly:
        return 0
    b = Davka()
    _kat_strom(b, uzly)
    return b.proved(lang)


def prelozit_nastaveni(klic, hodnota, pole="html", lang=None):
    """Pro SSR: jednoducha textova / html hodnota z app_settings -> preklad z nast:<klic>:<pole> (jinak puvodni hodnota)."""
    lang = lang or jazyk()
    if lang not in JAZYKY or not isinstance(hodnota, str) or not hodnota.strip():
        return hodnota
    t = nacti_preklady(lang, ["nast:%s:%s" % (klic, pole)]).get("nast:%s:%s" % (klic, pole))
    return odkazy_html(t) if t else hodnota


def prelozit_dict(kod_pk, d, pole, lang=None):
    """Pro SSR: jeden dict (radek / obsah stranky) -> preklady poli `pole` z klice <kod_pk>:<pole> (napr. kod_pk = 'str:12'). Vraci pocet prelozenych poli."""
    lang = lang or jazyk()
    if lang not in JAZYKY or not isinstance(d, dict):
        return 0
    b = Davka()
    for p in pole:
        b.pridej(d, p, "%s:%s" % (kod_pk, p))
    return b.proved(lang)


_GLOSAR = {"mtime": 0, "data": {}}


def nazev_webu(lang=None):
    """Nazev webu (pripona title, hlavicka) v jazyce pozadavku z docs/web_jazyky/glosar.json (bot7); jinak cesky text."""
    lang = lang or jazyk()
    cs = "Hliníkový konstrukční stavebnicový systém s drážkami"
    if lang not in JAZYKY:
        return cs
    cesta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "web_jazyky", "glosar.json")
    try:
        mt = os.path.getmtime(cesta)
        if mt != _GLOSAR["mtime"]:
            with open(cesta, encoding="utf-8") as f:
                _GLOSAR.update(mtime=mt, data=json.load(f))
        nw = _GLOSAR["data"].get("nazev_webu") or {}
        return nw.get(lang) or cs
    except Exception:
        return cs


def prelozit_radky(kod, radky, pole, lang=None, pk="id", predpona_pk=""):
    """Pro SSR: radky (list dictu z DB) -> doplni preklady poli `pole` (nazvy sloupcu) z klice <kod>:<predpona_pk><id>:<pole>. Vraci pocet prelozenych poli."""
    lang = lang or jazyk()
    if lang not in JAZYKY or not radky:
        return 0
    d = Davka()
    for r in radky:
        for p in pole:
            d.pridej(r, p, "%s:%s%s:%s" % (kod, predpona_pk, r.get(pk), p))
    return d.proved(lang)


# ---------------------------------------------------------------------------------------------------------------------------------------------
# JSON endpointy (verejne): mapovani na klice sesitu
# ---------------------------------------------------------------------------------------------------------------------------------------------
KAT_POLE = ("name", "nav_label", "menu_group_label", "meta_title", "meta_description", "focus_keyword")
STR_POLE = ("title", "intro_html", "body_html", "bottom_body_html")
KAR_POLE = ("name", "short_description", "description", "meta_title", "meta_description", "availability_text")
DODAVATEL_OK = ("vandrawee",)
# bloky homepage, ktere se na jazykovych webech NErenderuji: dom:blok7 jmenuje dodavatele (Dogus Kalip) i v obrazku - ceka na rozhodnuti Roberta (bot7, 2026-10-08)
SKRYTE_BLOKY = frozenset({7})


def _kat(b, d):
    if isinstance(d, dict) and d.get("id") is not None:
        for p in KAT_POLE:
            b.pridej(d, p, "kat:%s:%s" % (d["id"], p))


def _kat_strom(b, uzly):
    for u in uzly or []:
        _kat(b, u)
        _kat_strom(b, u.get("children"))


def _produkt(b, d):
    if not isinstance(d, dict) or d.get("id") is None:
        return
    for p in KAR_POLE:
        b.pridej(d, p, "kar:%s:%s" % (d["id"], p))
    if isinstance(d.get("unit"), str) and d["unit"].strip():
        b.pridej(d, "unit", "obch:jednotka:unit:%s" % d["unit"])
    um = d.get("umisteni_nazev")
    if isinstance(um, str) and um.strip():              # odznak umisteni regalu na karte: text z katalogu regal_umisteni
        klice = _katalog_klice().get(um)
        if klice:
            b.pridej_slozene(d, "umisteni_nazev", klice, lambda pr, klice=klice: next((pr[x] for x in klice if x in pr), None))
    # dodavatel / vyrobce se na jazykovych webech nezobrazuje (TEXT_FILTR; vyjimka: znacka vanDrawee, na ni stoji logika karet)
    d.pop("manufacturer", None)
    if isinstance(d.get("supplier_name"), str) and d["supplier_name"].strip().lower() not in DODAVATEL_OK:
        d["supplier_name"] = None


def _json_kategorie(b, data):
    if isinstance(data, dict):
        if "cart_enabled" in data:
            data["cart_enabled"] = False          # kosik a objednavky v EUR = faze 3 (bot5, docs/web_jazyky/README.md)
        if "discount_codes_enabled" in data:
            data["discount_codes_enabled"] = False
        _kat_strom(b, data.get("tree"))


def _json_obsah_kategorie(b, data):
    if not isinstance(data, dict):
        return
    cat = data.get("category")
    _kat(b, cat)
    if isinstance(cat, dict) and isinstance(data.get("page"), dict):
        for p in STR_POLE:
            b.pridej(data["page"], p, "str:%s:%s" % (cat.get("id"), p))
    for pr in data.get("products") or []:
        _produkt(b, pr)
    for pr in data.get("compatible_accessories") or []:
        _produkt(b, pr)
    for gi in data.get("gallery") or []:
        if isinstance(gi, dict) and gi.get("id") is not None:
            b.pridej(gi, "caption", "gal:%s:caption" % gi["id"])


def _json_hledani_kategorii(b, data):
    for c in (data.get("categories") if isinstance(data, dict) else None) or []:
        if isinstance(c, dict) and c.get("id") is not None:
            b.pridej(c, "name", "kat:%s:name" % c["id"])
            c["snippet"] = ""         # vyrez z ceskeho textu; preklad vyrezu = dalsi faze


def _json_produkty(b, data):
    for p in (data.get("products") if isinstance(data, dict) else None) or []:
        _produkt(b, p)


_CZ_PISMENA = re.compile(r"[ěščřžýůťďňĚŠČŘŽÝŮŤĎŇáíú]")


def _popisky_obrazku(b, data, cs_nazev):
    """usage_images[].caption, ktery je cesky nazev karty (nebo ma ceska pismena a nema vlastni preklad), se nahradi prekladem nazvu karty (alt obrazku nesmi byt cesky)."""
    prod = data.get("product") if isinstance(data, dict) else None
    if not isinstance(prod, dict) or prod.get("id") is None:
        return
    klic = "kar:%s:name" % prod["id"]
    for ui in data.get("usage_images") or []:
        if isinstance(ui, dict) and isinstance(ui.get("caption"), str) and (ui["caption"].strip() == cs_nazev or _CZ_PISMENA.search(ui["caption"])):
            b.pridej_slozene(ui, "caption", [klic], lambda pr, klic=klic: pr.get(klic))


def _json_produkt(b, data):
    if not isinstance(data, dict):
        return
    cs_nazev = ((data.get("product") or {}).get("name") or "").strip()
    _popisky_obrazku(b, data, cs_nazev)
    _produkt(b, data.get("product"))
    for p in data.get("related_products") or []:
        _produkt(b, p)
    for p in data.get("compatible_accessories") or []:
        _produkt(b, p)
    for gi in data.get("gallery") or []:
        if isinstance(gi, dict) and gi.get("id") is not None and "caption" in gi:
            b.pridej(gi, "caption", "gal:%s:caption" % gi["id"])


def _json_bocni_bloky(b, data):
    for blk in (data.get("blocks") if isinstance(data, dict) else None) or []:
        if isinstance(blk, dict) and blk.get("id") is not None:
            for p in ("title", "meta_description", "body_html"):
                b.pridej(blk, p, "dom:bocni%s:%s" % (blk["id"], p))


_KATALOG = {"t": 0.0, "map": {}}


def _katalog_klice():
    """{cesky text: [klice web_i18n]} pro katalogove texty sestav (horni_blok_varianty, regal_umisteni) - texty z JSONu sestav se v katalogu najdou podle cestiny (cache 5 min);
    stejny text muze mit vic radku (napr. kotveni shodne u vice umisteni), proto seznam klicu - pouzije se prvni, ke ktere existuje preklad."""
    t = time.time()
    with _lock:
        if t - _KATALOG["t"] < 300 and _KATALOG["map"]:
            return _KATALOG["map"]
    m = {}
    try:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, nazev, popis_zakaznicky FROM horni_blok_varianty")
                for r in cur.fetchall():
                    for p in ("nazev", "popis_zakaznicky"):
                        if (r[p] or "").strip():
                            m.setdefault(r[p], []).append("hbv:%s:%s" % (r["id"], p))
                cur.execute("SELECT id, nazev, montaz_zakaznicky, kotveni_zakaznicky FROM regal_umisteni")
                for r in cur.fetchall():
                    for p in ("nazev", "montaz_zakaznicky", "kotveni_zakaznicky"):
                        if (r[p] or "").strip():
                            m.setdefault(r[p], []).append("rum:%s:%s" % (r["id"], p))
        finally:
            conn.close()
    except Exception as e:
        app.logger.warning("web_i18n: katalog sestav se nepodarilo nacist (%s)", e)
    with _lock:
        _KATALOG.update(t=t, map=m)
    return m


_RE_NAZEV_SESTAVY = re.compile(r"^(.*?)\s+-\s+(.+)$")


def _hash12(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


def _json_sestavy(b, data):
    kat = _katalog_klice()
    for a in (data.get("assemblies") if isinstance(data, dict) else None) or []:
        if not isinstance(a, dict):
            continue
        for k in ("horni_blok_nazev", "popis_varianty", "kotveni_varianty", "montaz_varianty"):
            v = a.get(k)
            if isinstance(v, str) and v in kat:
                b.pridej_slozene(a, k, kat[v], lambda pr, klice=kat[v]: next((pr[x] for x in klice if x in pr), None))
        m = _RE_NAZEV_SESTAVY.match(a.get("name") or "")
        if m:
            casti = [x.strip() for x in m.group(2).split(",")]
            klice = {c: "sest:%s:fragment" % _hash12(c) for c in casti if c and not re.match(r"^boxy\d", c)}

            def slozit(pr, prefix=m.group(1), casti=casti, klice=klice):
                if not pr:
                    return None
                return prefix + " - " + ", ".join(pr.get(klice.get(c), c) for c in casti)
            b.pridej_slozene(a, "name", list(klice.values()), slozit)


def _json_doprava(b, data):
    for m in (data.get("methods") if isinstance(data, dict) else None) or []:
        if isinstance(m, dict) and m.get("id") is not None:
            b.pridej(m, "name", "obch:doprava%s:name" % m["id"])
            for k in ("price_czk",):
                if k in m:
                    m[k] = None


def _json_platba(b, data):
    for m in (data.get("methods") if isinstance(data, dict) else None) or []:
        if isinstance(m, dict) and m.get("id") is not None:
            b.pridej(m, "name", "obch:platba%s:name" % m["id"])
            if "price_czk" in m:
                m["price_czk"] = None


_JSON_CESTY = [
    (re.compile(r"^/api/categories$"), _json_kategorie),
    (re.compile(r"^/api/categories/\d+/content$"), _json_obsah_kategorie),
    (re.compile(r"^/api/categories/search$"), _json_hledani_kategorii),
    (re.compile(r"^/api/shop/products$"), _json_produkty),
    (re.compile(r"^/api/shop/products/\d+$"), _json_produkt),
    (re.compile(r"^/api/shop/products/\d+/assemblies$"), _json_sestavy),
    (re.compile(r"^/api/sidebar-blocks$"), _json_bocni_bloky),
    (re.compile(r"^/api/shipping-methods$"), _json_doprava),
    (re.compile(r"^/api/payment-methods$"), _json_platba),
]


def _zpracuj_json(resp, lang):
    handler = None
    for rx, fn in _JSON_CESTY:
        if rx.match(request.path):
            handler = fn
            break
    if handler is None or resp.status_code != 200 or resp.direct_passthrough:
        return resp
    data = json.loads(resp.get_data(as_text=True))
    b = Davka()
    handler(b, data)
    b.proved(lang)
    preved_ceny(data, cfg_cen(lang))
    resp.set_data(json.dumps(data, ensure_ascii=False))
    resp.headers["Content-Length"] = str(len(resp.get_data()))
    resp.headers.pop("ETag", None)
    resp.headers["Vary"] = ", ".join(sorted(set([x.strip() for x in resp.headers.get("Vary", "").split(",") if x.strip()] + ["Cookie", "Host"])))
    if g.get("web_jazyk_zdroj") == "nahled":
        resp.headers["Cache-Control"] = "private, no-store"
    return resp


# ---------------------------------------------------------------------------------------------------------------------------------------------
# slovnik textu stranek
# ---------------------------------------------------------------------------------------------------------------------------------------------
def slovnik(lang, obnov=False):
    """{'lang', 'locale', 'currency', 'exact': {cs: preklad}, 'patterns': [[cs, preklad], ...]} + hash (cache 60 s)."""
    t = time.time()
    c = _UI.get(lang)
    if c and not obnov and t - c["t"] < CACHE_S:
        return c
    exact, patterns = {}, []
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT cs, `text` FROM web_i18n WHERE lang=%s AND klic LIKE 'ui:%%' AND zastarale=0 AND cs IS NOT NULL ORDER BY klic", (lang,))
            for r in cur.fetchall():
                if re.search(r"\{\d+\}", r["cs"]):
                    patterns.append([r["cs"], r["text"]])
                else:
                    exact[r["cs"]] = r["text"]
    finally:
        conn.close()
    m = {"locale": {"en": "en-GB", "it": "it-IT"}.get(lang, lang), "currency": "EUR"}
    for s in sites().values():
        if s["lang"] == lang:
            m = {"locale": s["locale"], "currency": s["currency"]}
            break
    data = {"lang": lang, "locale": m["locale"], "currency": m["currency"], "exact": exact, "patterns": patterns}
    h = hashlib.sha1(json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:10]
    c = {"t": t, "data": data, "hash": h}
    _UI[lang] = c
    return c


@app.get("/api/i18n/ui.js")
def web_i18n_ui_js():
    lang = (request.args.get("l") or "").strip().lower()
    if lang not in JAZYKY:
        body = "window.__I18N=null;"
    else:
        body = "window.__I18N=" + json.dumps(slovnik(lang)["data"], ensure_ascii=False, separators=(",", ":")) + ";"
    resp = make_response(body)
    resp.headers["Content-Type"] = "application/javascript; charset=utf-8"
    resp.headers["Cache-Control"] = "public, max-age=300"
    return resp


def _i18n_js_verze():
    cesta = os.path.join(WEBAPP, "js", "i18n.js")
    try:
        mt = os.path.getmtime(cesta)
        if mt != _JS_VERZE["mtime"]:
            with open(cesta, "rb") as f:
                _JS_VERZE.update(mtime=mt, hash=hashlib.sha256(f.read()).hexdigest()[:10])
    except OSError:
        pass
    return _JS_VERZE["hash"]


# ---------------------------------------------------------------------------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------------------------------------------------------------------------
_HTML_VYLOUCENO = ("/admin", "/scene", "/nabidka", "/embed/", "/capture", "/kontrola", "/miniweb", "/storefront", "/glb-vyber", "/preview", "/stul-konfigurator", "/api/")
_RE_HTML_TAG = re.compile(r"<html\b([^>]*)>", re.I)
_RE_HEAD = re.compile(r"<head\b[^>]*>", re.I)
_RE_ROBOTS = re.compile(r'<meta\s+name=["\']robots["\'][^>]*>\s*', re.I)


def _html_tag(m, lang):
    attrs = m.group(1)
    attrs = re.sub(r'\blang=["\'][^"\']*["\']', "", attrs).strip()
    cls = re.search(r'\bclass=["\']([^"\']*)["\']', attrs)
    if cls:
        attrs = attrs.replace(cls.group(0), 'class="%s i18n-pending"' % cls.group(1).strip())
    else:
        attrs += ' class="i18n-pending"'
    return '<html lang="%s" %s>' % (lang, attrs.strip())


def _zpracuj_html(resp, lang, nezive_host):
    if resp.direct_passthrough or resp.status_code != 200 or (lang not in JAZYKY and not nezive_host):
        return resp
    if any(request.path.startswith(p) for p in _HTML_VYLOUCENO):
        return resp
    html = resp.get_data(as_text=True)
    if "<html" not in html.lower() or "</head>" not in html.lower():
        return resp
    noindex = not je_indexovatelny()
    vlozit = ""
    if lang in JAZYKY:
        sl = slovnik(lang)
        html = _RE_HTML_TAG.sub(lambda m: _html_tag(m, lang), html, count=1)
        # stranka je schovana jen do prvniho prekladu; POJISTKY nezavisle na i18n.js (404, blokovany skript, vypnuty JS): inline casovac 3 s a <noscript> pravidlo - stranka nikdy nezustane prazdna
        vlozit += ('<style>html.i18n-pending body{visibility:hidden}</style>'
                   '<noscript><style>html.i18n-pending body{visibility:visible!important}</style></noscript>'
                   '<script>setTimeout(function(){document.documentElement.classList.remove("i18n-pending")},3000)</script>'
                   '<script src="/api/i18n/ui.js?l=%s&amp;v=%s"></script><script src="/js/i18n.js?v=%s"></script>' % (lang, sl["hash"], _i18n_js_verze()))
    if noindex:
        html = _RE_ROBOTS.sub("", html)
        vlozit = '<meta name="robots" content="noindex, nofollow">' + vlozit
        resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    if vlozit:
        html = _RE_HEAD.sub(lambda m: m.group(0) + vlozit, html, count=1)
    resp.set_data(html)
    resp.headers.pop("ETag", None)
    resp.headers.pop("Last-Modified", None)
    resp.headers["Content-Length"] = str(len(resp.get_data()))
    resp.headers["Vary"] = ", ".join(sorted(set([x.strip() for x in resp.headers.get("Vary", "").split(",") if x.strip()] + ["Cookie", "Host"])))
    if g.get("web_jazyk_zdroj") == "nahled":
        resp.headers["Cache-Control"] = "private, no-store"
    return resp


SERVER_TEXTY = {       # texty, ktere server vraci primo (ne pres sablonu): presne cesky retezec -> preklad
    "Kategorie nenalezena.": {"en": "Category not found.", "it": "Categoria non trovata."},
}


def _server_text(resp, lang):
    """Jednoduche textove odpovedi (napr. 404 kategorie) na jazykovem webu: znamy cesky retezec -> preklad."""
    if lang in JAZYKY and "text/plain" in (resp.headers.get("Content-Type") or "").lower() and not resp.direct_passthrough:
        t = (resp.get_data(as_text=True) or "").strip()
        if t in SERVER_TEXTY and SERVER_TEXTY[t].get(lang):
            resp.set_data(SERVER_TEXTY[t][lang])
    return resp


def _robots_sitemap(resp):
    """Jazykovy host bez zelene brany: robots.txt = Disallow vse, sitemap.xml prazdna (kdyz je host v web_sites a neni indexovatelny)."""
    if request.path not in ("/robots.txt", "/sitemap.xml") or not site() or je_indexovatelny():
        return resp
    if request.path == "/robots.txt":
        r = make_response("User-agent: *\nDisallow: /\n")
        r.headers["Content-Type"] = "text/plain; charset=utf-8"
    else:
        r = make_response('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>\n')
        r.headers["Content-Type"] = "application/xml; charset=utf-8"
    r.headers["X-Robots-Tag"] = "noindex, nofollow"
    r.headers["Cache-Control"] = "no-cache"
    return r


@app.after_request
def _web_jazyk_after(resp):
    try:
        if request.path.startswith("/api/i18n/"):
            return resp
        resp = _robots_sitemap(resp)
        lang = jazyk()
        ctype = (resp.headers.get("Content-Type") or "").lower()
        nezive = bool(g.get("web_nezive_host"))
        if lang in JAZYKY or nezive or g.get("web_jazyk_cookie"):
            if "text/plain" in ctype:
                resp = _server_text(resp, lang)
            elif "text/html" in ctype:
                resp = _zpracuj_html(resp, lang, nezive)
            elif "application/json" in ctype and lang in JAZYKY and request.path.startswith("/api/"):
                resp = _zpracuj_json(resp, lang)
        pc = g.get("web_jazyk_cookie")
        if pc:
            if pc == "cs":
                resp.delete_cookie(COOKIE, path="/")
            else:
                resp.set_cookie(COOKIE, pc, max_age=12 * 3600, path="/", samesite="Lax", secure=request.headers.get("X-Forwarded-Proto") == "https", httponly=True)
    except Exception:
        app.logger.exception("web_i18n: zpracovani odpovedi selhalo, vracim puvodni")
    return resp
