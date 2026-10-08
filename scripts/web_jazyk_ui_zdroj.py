#!/usr/bin/env python3
"""Zdroj UI vet hlavniho webu k prekladu do dalsich jazyku (en = vandrawee.eu, it = vandrawee.it) - bot16, Robert 2026-10-08.

Z kodu zakaznickych stranek (HTML + JS, cestina se v kodu NEMENI) vytahne texty, ktere uzivatel vidi, a zapise je jako sesit docs/web_jazyky/10_ui.json
ve STEJNEM tvaru jako sesity bot7 (README_ZDROJ.md):  {id, typ (text|html), cs, en, it, h, [zmena]}
  id   = ui:<sha1(cs)[:12]>:<kontext>   kontext = tlacitko | nadpis | text | odkaz | placeholder | title | alt | aria | hlaska
  cs   = NORMALIZOVANY zdroj = klic slovniku v prohlizeci (stejna funkce norm() v webapp/js/i18n.js):
         mezery slozene na jednu, ciselne skupiny -> {n} ("Celkem 12 ks" -> "Celkem {n} ks"), promenne z JS sablon -> {0} {1} ...,
         inline znacky uvnitr vety (<a>, <b>, <span> ...) -> cislovane znacky <1>..</1> (poradi vyskytu, atributy se v textu neprekladaji; <br> -> <1/>)
  h    = sha1(cs)[:10] v okamziku prekladu (vyplni nastroj bot7), zmena = true kdyz se cs zmenilo
Jeden zaznam na jednu normalizovanou vetu; kde a v jakem kontextu se veta pouziva je v docs/web_jazyky/10_ui_kontext.json ({id: {zdroj: [soubor:radek], kontexty: [...], priznaky: [...]}}).
Opakovane spusteni je BEZPECNE: hotove preklady (en, it, h, zmena) zustanou, pridaji se nove vety, zmizele s prekladem dostanou "zastarale": true, zmizele bez prekladu se zahodi.

Pouziti (z korene repa; potrebuje beautifulsoup4 z venv API, nic se nezapisuje mimo docs/web_jazyky/10_ui*.json):
  api/venv/bin/python3 scripts/web_jazyk_ui_zdroj.py [--stav] [--soubor product.html ...]
"""
import argparse
import hashlib
import html as htmlmod
import json
import os
import re
import sys

from bs4 import BeautifulSoup, NavigableString, Comment

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBAPP = os.path.join(ROOT, "webapp")
VYSTUP = os.environ.get("UI_VYSTUP") or os.path.join(ROOT, "docs", "web_jazyky", "10_ui.json")                  # UI_VYSTUP jen pro zkousky (nezapisovat do docs)
KONTEXT = os.environ.get("UI_KONTEXT") or os.path.join(ROOT, "docs", "web_jazyky", "10_ui_kontext.json")

# zakaznicke stranky hlavniho e-shopu (nabidka-online.html, scene.html, admin.html a storefronty jsou mimo prvni vlnu)
STRANKY = ["index.html", "category.html", "product.html", "moje-objednavky.html", "login.html", "register.html", "forgot-password.html",
           "reset-password.html", "verify-email.html", "kontakt.html", "realizace.html", "poptavka-stul.html", "404.html", "blok.html"]
# JS nacitane temito strankami, ktere maji vlastni zakaznicke texty (ostatni <script src> se projdou automaticky, tady jen vylouceni)
JS_VYLOUCIT = {"three-mesh-bvh.js", "client-errors.js"}

MARKER_OD, MARKER_DO = "\ue000", "\ue001"        # nahrada ${vyraz} v sablonach pri parsovani HTML
ZN_OD, ZN_KONEC, ZN_SAM, ZN_X = "\ue002", "\ue004", "\ue005", "\ue003"     # inline znacky uvnitr vety (na <N> .. </N> .. <N/> se prevedou az po norm(), aby cislo znacky neprevzala {n})

INLINE = {"a", "abbr", "b", "strong", "i", "em", "small", "span", "sup", "sub", "br", "code", "mark", "u", "kbd", "s", "del", "ins", "label", "font", "img", "wbr"}
VOID = {"br", "img", "wbr", "input", "hr", "meta", "link", "area", "base", "col", "embed", "source", "track"}
PRESKOC_TAG = {"script", "style", "noscript", "svg", "path", "defs", "textarea_ignore"}
TL_TRIDY = re.compile(r"(^|[\s_-])(btn|button|tlacitko)([\s_-]|$)", re.I)

# --------------------------------------------------------------------------------------------------------------------------------------
# normalizace (MUSI byt shodna s norm() v webapp/js/i18n.js)
# --------------------------------------------------------------------------------------------------------------------------------------
WS = re.compile(r"[\s   ]+")
CISLO = re.compile(r"(?<![\w{])\d+(?:[  ]\d{3})*(?:[.,]\d+)?(?![\w}])")


def norm(s):
    s = WS.sub(" ", s).strip()
    return CISLO.sub("{n}", s)


def sha(s, n):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:n]


# --------------------------------------------------------------------------------------------------------------------------------------
# slovnik cestiny (pro JS retezce bez diakritiky)
# --------------------------------------------------------------------------------------------------------------------------------------
DIAK = re.compile(r"[ěščřžýáíéúůďťňĚŠČŘŽÝÁÍÉÚŮĎŤŇ]")
RUCNI_SLOVA = set("""cena ceny celkem doprava platba adresa telefon heslo email jmeno prijmeni odeslat hledat zpet dalsi ano ne kosik objednavka objednavky doklad doklady faktura
produkt produkty kategorie kategorii vyber vyberte zavrit zrusit ulozit smazat upravit pridat odebrat potvrdit pokracovat prihlasit prihlaseni registrace odhlasit uzivatel
firma ico dic mesto psc zeme stat poznamka mnozstvi jednotka sleva zdarma dodani termin sklad skladem dostupnost zaruka popis parametry obrazek nacitam chyba nepodarilo
nenalezeno zadne vsechny vse zobrazit skryt filtr razeni nejlevnejsi nejdrazsi novinky akce nabidka poptavka dotaz zprava kontakt kontakty prodej montaz sestava""".split())


def nacti_slovnik():
    slova = set(RUCNI_SLOVA)
    d = os.path.join(ROOT, "docs", "web_jazyky")
    for f in ("01_kategorie.json", "02_stranky.json", "04_homepage.json", "07_obchod.json"):
        p = os.path.join(d, f)
        if not os.path.exists(p):
            continue
        try:
            for it in json.load(open(p, encoding="utf-8")):
                for w in re.findall(r"[A-Za-zÀ-ž]{4,}", it.get("cs", "")):
                    slova.add(w.lower())
        except Exception:
            pass
    return slova


SLOVNIK = None

# vnitrni (zamestnanecke) texty, ktere zakaznik nikdy nevidi a ktere obsahuji slova zakazana ve verejnych textech (dodavatel, interni cena, kurz): do prekladu nepatri
INTERNI_RE = re.compile(r"Dogus|🔒|\b[Ii]nterní|\bFio\b|[Vv]andr|[Uu]nity|Shoptet|\bTitle:|\bDescription:")

KOD_RE = [
    re.compile(r"^(?:https?:)?//"), re.compile(r"^[/.#\[]"), re.compile(r"^[\w.$-]+(?:/[\w.$%:{}-]*)+/?$"), re.compile(r"^[\w.$@:-]+$"),
    re.compile(r"=>|&&|\|\||function\b|\breturn\b|\bconst\b|\blet\b"), re.compile(r"^[#.][\w-]"), re.compile(r"^\d[\d\s.,:/-]*$"),
    re.compile(r"^(?:[a-z-]+\s*:\s*[^;]+;?\s*)+$"),      # css deklarace
]


def je_regex(t):
    """Retezec bez mezer, ktery vypada jako regularni vyraz (trida znaku [aá], \\b, (?:, ^...$) - napr. kontrola uniku znacky v realizace-foto.js, ne text pro cloveka."""
    return " " not in t and bool(re.search(r"\[[^\]]{2,}\]|\\[bdwsBDWS.]|\(\?|^\^|\$$", t))


def vypada_cesky(s):
    """Je retezec z JS (mimo HTML sablony) lidsky text cesky? vraci None / 'diak' / 'slovnik'."""
    global SLOVNIK
    t = s.strip()
    if len(t) < 2 or not re.search(r"[A-Za-zÀ-ž]", t) or je_regex(t):
        return None
    if DIAK.search(t):
        if re.search(r"=>|&&|\|\||function\b", t):
            return None
        return "diak"
    for r in KOD_RE:
        if r.search(t):
            return None
    if SLOVNIK is None:
        SLOVNIK = nacti_slovnik()
    slova = re.findall(r"[A-Za-zÀ-ž]{3,}", t)
    if slova and any(w.lower() in SLOVNIK for w in slova) and (" " in t or t[0].isupper()):
        return "slovnik"
    return None


# --------------------------------------------------------------------------------------------------------------------------------------
# JS: lexer retezcu a sablon
# --------------------------------------------------------------------------------------------------------------------------------------
REGEX_PRED = set("(,=:[!&|?{};~^%*+-<>") | {None}
REGEX_KLICOVA = {"return", "typeof", "case", "in", "of", "delete", "void", "throw", "new", "else", "do", "yield", "await"}
ESC = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}


def odescapuj(s):
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c != "\\" or i + 1 >= len(s):
            out.append(c)
            i += 1
            continue
        n = s[i + 1]
        if n == "u" and i + 5 < len(s) + 1 and re.match(r"[0-9a-fA-F]{4}", s[i + 2:i + 6]):
            out.append(chr(int(s[i + 2:i + 6], 16)))
            i += 6
        elif n == "u" and s[i + 2:i + 3] == "{":
            j = s.find("}", i)
            out.append(chr(int(s[i + 3:j], 16)))
            i = j + 1
        elif n == "x" and re.match(r"[0-9a-fA-F]{2}", s[i + 2:i + 4]):
            out.append(chr(int(s[i + 2:i + 4], 16)))
            i += 4
        elif n == "\n":
            i += 2
        else:
            out.append(ESC.get(n, n))
            i += 2
    return "".join(out)


def js_literaly(src, base=0, out=None, toks=None):
    """Vraci seznam {'druh': 'str'|'tpl', 'hodnota': str | 'casti': [str|('expr', int)], 'pos': int} pro retezce a sablony v JS zdroji (mimo komentare a regexy).
    toks (volitelny seznam) dostane proud tokenu (druh, hodnota/index literalu, pos) pro hledani zretezeni retezcu s promennymi."""
    if out is None:
        out = []
    i, n = 0, len(src)
    posl = None           # posledni vyznamny znak / klicove slovo
    while i < n:
        c = src[i]
        if c in " \t\r\n":
            i += 1
            continue
        if c == "/" and src[i + 1:i + 2] == "/":
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and src[i + 1:i + 2] == "*":
            j = src.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if c in "'\"":
            j = i + 1
            while j < n and src[j] != c:
                j += 2 if src[j] == "\\" else 1
            out.append({"druh": "str", "hodnota": odescapuj(src[i + 1:j]), "pos": base + i})
            if toks is not None:
                toks.append(("lit", len(out) - 1, base + i))
            i = j + 1
            posl = "x"
            continue
        if c == "`":
            casti, buf, j, k = [], [], i + 1, 0
            while j < n and src[j] != "`":
                if src[j] == "\\":
                    buf.append(src[j:j + 2])
                    j += 2
                elif src[j] == "$" and src[j + 1:j + 2] == "{":
                    casti.append(odescapuj("".join(buf)))
                    buf = []
                    # najdi odpovidajici }
                    depth, m = 1, j + 2
                    while m < n and depth:
                        ch = src[m]
                        if ch in "'\"":
                            m += 1
                            while m < n and src[m] != ch:
                                m += 2 if src[m] == "\\" else 1
                        elif ch == "`":
                            # vnorena sablona: preskoc ji cele (rekurzivne pres vlastni lexer na zbytku)
                            m += 1
                            dd = 0
                            while m < n and not (src[m] == "`" and dd == 0):
                                if src[m] == "\\":
                                    m += 1
                                elif src[m] == "$" and src[m + 1:m + 2] == "{":
                                    dd += 1
                                    m += 1
                                elif src[m] == "}" and dd:
                                    dd -= 1
                                m += 1
                        elif ch == "{":
                            depth += 1
                        elif ch == "}":
                            depth -= 1
                        m += 1
                    vyraz = src[j + 2:m - 1]
                    js_literaly(vyraz, base + j + 2, out)         # retezce uvnitr ${...} jsou samostatne
                    casti.append(("expr", k))
                    k += 1
                    j = m
                else:
                    buf.append(src[j])
                    j += 1
            casti.append(odescapuj("".join(buf)))
            out.append({"druh": "tpl", "casti": casti, "pos": base + i})
            if toks is not None:
                toks.append(("tpl", len(out) - 1, base + i))
            i = j + 1
            posl = "x"
            continue
        if c == "/":
            if posl in REGEX_PRED or posl in REGEX_KLICOVA:
                j, tr = i + 1, False
                while j < n and (src[j] != "/" or tr) and src[j] != "\n":
                    if src[j] == "\\":
                        j += 1
                    elif src[j] == "[":
                        tr = True
                    elif src[j] == "]":
                        tr = False
                    j += 1
                i = j + 1
                while i < n and src[i].isalpha():
                    i += 1
                posl = "x"
                if toks is not None:
                    toks.append(("w", "regex", base + i))
                continue
            if toks is not None:
                toks.append(("p", "/", base + i))
            i += 1
            posl = "/"
            continue
        if c.isalnum() or c in "_$":
            j = i
            while j < n and (src[j].isalnum() or src[j] in "_$"):
                j += 1
            slovo = src[i:j]
            posl = slovo if slovo in REGEX_KLICOVA else "x"
            if toks is not None:
                toks.append(("w", slovo, base + i))
            i = j
            continue
        posl = c
        if toks is not None:
            toks.append(("p", c, base + i))
        i += 1
    return out


# --------------------------------------------------------------------------------------------------------------------------------------
# HTML: jednotky prekladu
# --------------------------------------------------------------------------------------------------------------------------------------
def je_inline(el):
    return el.name in INLINE


def jednotka_inline(el):
    """Obsah elementu jako veta se znackami <1>..</1>; vraci (text, ma_znacky). Text uzlu uz s MARKER_OD..MARKER_DO."""
    cnt = [0]

    def rek(uzly):
        out = []
        for u in uzly:
            if isinstance(u, Comment):
                continue
            if isinstance(u, NavigableString):
                out.append(str(u))
            elif u.name in VOID or not list(u.children):
                cnt[0] += 1
                out.append("%s%s%s" % (ZN_SAM, chr(0xE100 + cnt[0]), ZN_X))
            else:
                cnt[0] += 1
                k = cnt[0]
                out.append("%s%s%s%s%s%s%s" % (ZN_OD, chr(0xE100 + k), ZN_X, rek(u.children), ZN_KONEC, chr(0xE100 + k), ZN_X))
        return "".join(out)
    t = rek(el.children)
    return t, cnt[0] > 0


def vsechno_inline(el):
    for u in el.children:
        if isinstance(u, Comment):
            continue
        if isinstance(u, NavigableString):
            continue
        if not je_inline(u):
            return False
        if not vsechno_inline(u):
            return False
    return True


def ma_text(el):
    return any(isinstance(u, NavigableString) and not isinstance(u, Comment) and u.strip() for u in el.children)


def kontext_prvku(el, atribut=None):
    if atribut:
        return {"placeholder": "placeholder", "title": "title", "alt": "alt", "aria-label": "aria", "value": "tlacitko"}.get(atribut, "text")
    p = el
    while p is not None and getattr(p, "name", None):
        if p.name in ("button", "summary") or (p.name == "input" and (p.get("type") or "").lower() in ("button", "submit", "reset")):
            return "tlacitko"
        if p.name in ("h1", "h2", "h3", "h4", "h5", "h6", "legend", "th", "caption"):
            return "nadpis"
        if p.name == "a":
            return "tlacitko" if TL_TRIDY.search(" ".join(p.get("class") or [])) else "odkaz"
        if p.name in ("div", "p", "li", "td", "section", "article", "body"):
            break
        p = p.parent
    return "text"


def projdi_html(html_text, pridej, radek_od=1, preskoc_expr=True):
    """Projde HTML (cele stranky nebo fragment ze sablony) a vola pridej(text, typ, kontext, radek_nebo_None)."""
    soup = BeautifulSoup(html_text, "html.parser")

    def radek(el):
        return radek_od + (el.sourceline - 1 if getattr(el, "sourceline", None) else 0)

    def atributy(el):
        if el.name == "meta" and isinstance(el.get("content"), str) and el.get("content").strip() and (
                (el.get("name") or "").lower() in ("description", "twitter:title", "twitter:description") or (el.get("property") or "").lower() in ("og:title", "og:description", "og:site_name")):
            pridej(el.get("content"), "text", "meta", radek(el))
        for a in ("placeholder", "title", "alt", "aria-label"):
            v = el.get(a)
            if isinstance(v, str) and v.strip():
                pridej(v, "text", kontext_prvku(el, a), radek(el))
        if el.name == "input" and (el.get("type") or "").lower() in ("button", "submit", "reset") and el.get("value"):
            pridej(el.get("value"), "text", "tlacitko", radek(el))

    def rek(el):
        if getattr(el, "name", None) in PRESKOC_TAG:
            return
        if getattr(el, "name", None) == "title" and el.string and el.string.strip():
            pridej(str(el.string), "text", "meta", radek(el))
            return
        if getattr(el, "name", None):
            atributy(el)
        # jednotka = cely element s vetou (text + inline znacky)
        if getattr(el, "name", None) and el.name not in VOID and ma_text(el) and vsechno_inline(el) and el.name not in ("html", "body"):
            t, znacky = jednotka_inline(el)
            pridej(t, "html" if znacky else "text", kontext_prvku(el), radek(el))
            # atributy vnorenych inline prvku (title, alt) zvlast
            for pod in el.find_all(True):
                atributy(pod)
            return
        for u in list(getattr(el, "children", [])):
            if isinstance(u, Comment):
                continue
            if isinstance(u, NavigableString):
                if u.strip():
                    pridej(str(u), "text", kontext_prvku(el), radek(el))
            else:
                rek(u)

    rek(soup)


# --------------------------------------------------------------------------------------------------------------------------------------
# sber
# --------------------------------------------------------------------------------------------------------------------------------------
class Sbirka:
    def __init__(self):
        self.polozky = {}      # normalizovany cs -> {"typ", "kontexty": set, "zdroj": [..], "priznaky": set}

    def pridej(self, text, typ, kontext, soubor, radek, priznak=None):
        t = text
        # promenne ze sablon
        def ph(m):
            return "{%s}" % m.group(1)
        t = re.sub(MARKER_OD + r"(\d+)" + MARKER_DO, ph, t)
        t = norm(t)
        # cislo znacky je zakodovane jako znak U+E100+k (aby ho norm() nezamenil za {n})
        t = re.sub(ZN_OD + "([\ue100-\ue1ff])" + ZN_X, lambda m: "<%d>" % (ord(m.group(1)) - 0xE100), t)
        t = re.sub(ZN_KONEC + "([\ue100-\ue1ff])" + ZN_X, lambda m: "</%d>" % (ord(m.group(1)) - 0xE100), t)
        t = re.sub(ZN_SAM + "([\ue100-\ue1ff])" + ZN_X, lambda m: "<%d/>" % (ord(m.group(1)) - 0xE100), t)
        if INTERNI_RE.search(t):
            return
        # prazdne / bez pismen / jen promenne
        bez = re.sub(r"<\d+/?>|</\d+>|\{[n\d]+\}", "", t)
        if not re.search(r"[A-Za-zÀ-ž]", bez) or len(bez.strip()) < 2:
            return
        p = self.polozky.setdefault(t, {"typ": typ, "kontexty": [], "zdroj": [], "priznaky": set()})
        if typ == "html":
            p["typ"] = "html"
        if kontext not in p["kontexty"]:
            p["kontexty"].append(kontext)
        zr = "%s:%s" % (soubor, radek)
        if zr not in p["zdroj"] and len(p["zdroj"]) < 6:
            p["zdroj"].append(zr)
        if re.search(r"\bKč\b|\bCZK\b", t):
            p["priznaky"].add("mena")
        if priznak:
            p["priznaky"].add(priznak)


def radek_z_pos(src, pos):
    return src.count("\n", 0, pos) + 1


OTEV, ZAV = "([{", ")]}"
DELIM = set(",;:?=!&|<>-*%^~{")            # operatory/oddelovace, ktere ukoncuji retez zretezeni (odcitani, ternar, porovnani ...)


def retezeni(toks, lits=None):
    """Najde zretezeni "text " + promenna + " dalsi text" (jen operator +, operandy = retezec | jednoduchy vyraz); vraci seznam retezcu, kazdy = seznam
    (druh, index_literalu|None, pos). Zavorky ( [ { se prochazeji rekurzivne (uvnitr funkce / objektu / zavorky jsou dalsi retezce) a nadrazena uroven je vidi jako jeden operand."""
    vysledek = []

    def skupina(i):                       # index zaviraci zavorky k oteviraci na i
        d, j = 0, i
        while j < len(toks):
            if toks[j][0] == "p" and toks[j][1] in OTEV:
                d += 1
            elif toks[j][0] == "p" and toks[j][1] in ZAV:
                d -= 1
                if d == 0:
                    return j
            j += 1
        return len(toks) - 1

    def scan(od, do):
        items, i = [], od
        while i < do:
            k, v, pos = toks[i]
            if k in ("lit", "tpl"):
                items.append((k, v, pos))
            elif k == "p" and v == "+":
                items.append(("+", None, pos))
            elif k == "p" and v in OTEV:
                j = skupina(i)
                scan(i + 1, j)                            # vnitrek zavorky samostatne
                items.append(("w", None, pos))
                i = j
            elif k == "p" and (v in DELIM or v in ZAV):
                items.append(("d", None, pos))
            elif k == "p" and v == ".":
                items.append((".", None, pos))
            else:
                items.append(("w", None, pos))
            i += 1
        sl = []
        for it in items:
            if sl and sl[-1][0] == "w" and it[0] in ("w", "."):
                continue
            if sl and sl[-1][0] == "." and it[0] == "w":
                sl[-1] = ("w", None, sl[-1][2])
                continue
            sl.append(it)
        i = 0
        while i < len(sl):
            if sl[i][0] in ("lit", "tpl", "w"):
                j, kus = i, []
                while j < len(sl) and sl[j][0] in ("lit", "tpl", "w"):
                    kus.append(sl[j])
                    if j + 2 < len(sl) and sl[j + 1][0] == "+" and sl[j + 2][0] in ("lit", "tpl", "w"):
                        j += 2
                    else:
                        break
                if len(kus) >= 2 and any(x[0] == "lit" for x in kus) and any(x[0] == "w" for x in kus):
                    vysledek.append(kus)
                i = j + 1
            else:
                i += 1
    scan(0, len(toks))
    return vysledek


def zpracuj_js(src, soubor, sb, radek0=1):
    toks = []
    literaly = js_literaly(src, toks=toks)
    spotrebovane = set()
    for kus in retezeni(toks, literaly):
        casti, indexy, mk = [], [], 0
        for k, v, pos in kus:
            if k == "w":
                casti.append("%s%d%s" % (MARKER_OD, mk, MARKER_DO))
                mk += 1
            else:
                l = literaly[v]
                indexy.append(v)
                casti.append(l["hodnota"] if l["druh"] == "str" else "".join(c if isinstance(c, str) else "%s%d%s" % (MARKER_OD, 90 + c[1], MARKER_DO) for c in l["casti"]))
        slozeno = "".join(casti)
        radek = radek0 + src.count("\n", 0, kus[0][2])
        if re.search(r"</?[a-zA-Z]", slozeno):
            projdi_html(slozeno, lambda tx, ty, kk, r, radek=radek: sb.pridej(tx, ty, kk, soubor, radek, "html-zretezeni"), radek)
            spotrebovane.update(indexy)
        else:
            holy = re.sub(MARKER_OD + r"\d+" + MARKER_DO, " ", slozeno)
            j = vypada_cesky(holy)
            if j:
                sb.pridej(slozeno, "text", "hlaska", soubor, radek, "zretezeni" if j == "diak" else "zretezeni-slovnik")
                spotrebovane.update(indexy)
    for idx, lit in enumerate(literaly):
        if idx in spotrebovane:
            continue
        radek = radek0 + src.count("\n", 0, lit["pos"])
        if lit["druh"] == "str":
            v = lit["hodnota"]
            if "<" in v and re.search(r"</?[a-zA-Z]", v):
                projdi_html(v, lambda t, ty, k, r: sb.pridej(t, ty, k, soubor, radek, "html-v-retezci"), radek)
            else:
                if "&" in v and re.search(r"&#?\w+;", v):
                    v = htmlmod.unescape(v)
                j = vypada_cesky(v)
                if j:
                    sb.pridej(v, "text", "hlaska", soubor, radek, None if j == "diak" else "slovnik")
        else:
            casti = lit["casti"]
            slozeno = ""
            for c in casti:
                slozeno += c if isinstance(c, str) else "%s%d%s" % (MARKER_OD, c[1], MARKER_DO)
            if re.search(r"</?[a-zA-Z]", slozeno):
                projdi_html(slozeno, lambda t, ty, k, r: sb.pridej(t, ty, k, soubor, radek, "html-v-sablone"), radek)
            else:
                holy = re.sub(MARKER_OD + r"\d+" + MARKER_DO, " ", slozeno)
                j = vypada_cesky(holy)
                if j:
                    sb.pridej(slozeno, "text", "hlaska", soubor, radek, None if j == "diak" else "slovnik")


def zpracuj_stranku(nazev, sb):
    cesta = os.path.join(WEBAPP, nazev)
    if not os.path.exists(cesta):
        return []
    html_text = open(cesta, encoding="utf-8").read()
    soup_js = []
    # inline <script> bloky -> JS (s radkem), zbytek -> HTML
    def vyrad(m):
        if re.search(r"\bsrc\s*=", m.group(1) or ""):
            return m.group(0)
        pos = m.start(2)
        soup_js.append((pos, m.group(2)))
        return m.group(0)[:m.start(2) - m.start(0)] + re.sub(r"[^\n]", " ", m.group(2)) + m.group(0)[m.end(2) - m.start(0):]
    bez_skriptu = re.sub(r"<script([^>]*)>(.*?)</script>", vyrad, html_text, flags=re.S | re.I)
    # <style> nepatri do textu
    bez_skriptu = re.sub(r"<style[^>]*>.*?</style>", lambda m: re.sub(r"[^\n]", " ", m.group(0)), bez_skriptu, flags=re.S | re.I)
    # HTML komentare pryc (zachovat radky)
    bez_skriptu = re.sub(r"<!--.*?-->", lambda m: re.sub(r"[^\n]", " ", m.group(0)), bez_skriptu, flags=re.S)
    projdi_html(bez_skriptu, lambda t, ty, k, r: sb.pridej(t, ty, k, nazev, r))
    for pos, js in soup_js:
        zpracuj_js(js, nazev, sb, radek0=html_text.count("\n", 0, pos) + 1)
    jsy = re.findall(r"<script[^>]+src=[\"']([^\"'?#]+)", html_text, flags=re.I)
    jsy += re.findall(r"[\"'`](/js/[\w.-]+\.js)", html_text)                  # nacitane az za behu (document.createElement('script'), import())
    return jsy


def hlavni():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stav", action="store_true", help="jen vypis, nic nezapisovat")
    ap.add_argument("--soubor", action="append", help="jen tyto stranky (default vsechny zakaznicke)")
    a = ap.parse_args()
    sb = Sbirka()
    js_soubory = []
    for s in (a.soubor or STRANKY):
        for src in zpracuj_stranku(s, sb):
            nazev = os.path.basename(src)
            if src.startswith("/js/") or src.startswith("js/"):
                if nazev not in JS_VYLOUCIT and os.path.exists(os.path.join(WEBAPP, "js", nazev)) and nazev not in js_soubory:
                    js_soubory.append(nazev)
    for j in js_soubory:
        zpracuj_js(open(os.path.join(WEBAPP, "js", j), encoding="utf-8").read(), "js/" + j, sb)
    # ulozeni (slouceni s existujicim sesitem)
    stare = {}
    if os.path.exists(VYSTUP):
        for it in json.load(open(VYSTUP, encoding="utf-8")):
            stare[it["cs"]] = it
    polozky, kontext = [], {}
    PRIORITA = ["tlacitko", "nadpis", "placeholder", "title", "alt", "aria", "meta", "odkaz", "text", "hlaska"]
    for cs, p in sorted(sb.polozky.items(), key=lambda kv: kv[0].lower()):
        kont = sorted(p["kontexty"], key=lambda k: PRIORITA.index(k) if k in PRIORITA else 99)[0]
        id_ = "ui:%s:%s" % (sha(cs, 12), kont)
        st = stare.pop(cs, None)
        it = {"id": id_, "typ": p["typ"], "cs": cs, "en": (st or {}).get("en", ""), "it": (st or {}).get("it", ""), "h": (st or {}).get("h", "")}
        if st and st.get("zmena"):
            it["zmena"] = True
        polozky.append(it)
        kontext[id_] = {"zdroj": p["zdroj"], "kontexty": p["kontexty"], "priznaky": sorted(p["priznaky"])}
    zastarale = [it for it in stare.values() if not je_regex(it["cs"])]          # regex z kodu (drive omylem exportovany) se zahodi i s prekladem
    for it in zastarale:
        if it.get("en") or it.get("it"):
            it["zastarale"] = True
            polozky.append(it)
    if a.stav:
        print("polozek: %d, zastaralych: %d (s prekladem %d), js souboru: %s" % (len(polozky), len(zastarale), sum(1 for i in zastarale if i.get("en") or i.get("it")), ", ".join(js_soubory)))
        return
    json.dump(polozky, open(VYSTUP, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(kontext, open(KONTEXT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    kont_poc = {}
    for it in polozky:
        k = it["id"].rsplit(":", 1)[1]
        kont_poc[k] = kont_poc.get(k, 0) + 1
    print("zapsano %d vet do %s (kontexty: %s); zastaralych s prekladem: %d, zahozenych bez prekladu: %d; JS: %s" % (
        len(polozky), os.path.relpath(VYSTUP, ROOT), ", ".join("%s %d" % kv for kv in sorted(kont_poc.items())),
        sum(1 for i in zastarale if i.get("en") or i.get("it")), sum(1 for i in zastarale if not (i.get("en") or i.get("it"))), ", ".join(js_soubory)))


if __name__ == "__main__":
    hlavni()
