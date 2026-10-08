"""Spolecne pomucky pro preklad hlavniho webu (scripts/web_jazyk_*.py). bot7, 2026-10-08."""
import hashlib
import json
import os
import re
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLOZKA = os.path.join(ROOT, "docs", "web_jazyky")
SADY = ["01_kategorie", "02_stranky", "03_karty", "04_homepage", "05_typologie", "06_galerie", "07_obchod", "09_nastaveni", "10_ui", "11_sestavy", "12_sablony"]
JAZYKY = ("en", "it")

CESKA_PISMENA = re.compile("[ěščřžýůťďňĚŠČŘŽÝŮŤĎŇáíúóÁÍÚÓ]")
# vlastni jmena (mesta, znacky), ktera se pisou s diakritikou i v EN/IT textu
VLASTNI_JMENA = ("Zlín", "Slavičín", "Škoda", "Praha", "ČSN", "Husinecká")
ZAKAZANA = re.compile(r"dogus|vandr|unity|konfigur|configurator|configuratore|ponk\b", re.I)
KOD_V_ID = re.compile(r"^(?P<tbl>[a-z]+):(?P<pk>[^:]+):(?P<pole>.+)$")


def pole_z_id(i):
    m = KOD_V_ID.match(i)
    return m.group("pole") if m else ""


def klic(pole, cs):
    """Klic prekladove jednotky: stejny text ve stejnem poli se preklada jednou."""
    return hashlib.sha1((pole + "|" + cs).encode("utf-8")).hexdigest()[:10]


def hsh(cs):
    return hashlib.sha1(cs.encode("utf-8")).hexdigest()[:10]


def nacti_sadu(nazev):
    with open(os.path.join(SLOZKA, nazev + ".json"), encoding="utf-8") as f:
        return json.load(f)


def uloz_sadu(nazev, polozky):
    with open(os.path.join(SLOZKA, nazev + ".json"), "w", encoding="utf-8") as f:
        json.dump(polozky, f, ensure_ascii=False, indent=1)
        f.write("\n")


TAG_RE = re.compile(r"<(/?)([a-zA-Z0-9]+)([^>]*)>")


def znacky(html):
    """Posloupnost znacek (jmeno + atributy bez textu alt/title) - musi byt v prekladu shodna."""
    out = []
    for m in TAG_RE.finditer(html):
        attrs = m.group(3).strip()
        attrs = re.sub(r'\s(alt|title)="[^"]*"', "", " " + attrs).strip()
        out.append((m.group(1), m.group(2).lower(), attrs))
    return out


def cisla(text):
    """Multimnozina ciselnych skupin (oddelovace tisicu a desetin sjednoceny)."""
    t = re.sub(r"\b[23]D\b", " ", re.sub(r"<[^>]+>", " ", text)).replace("\u00b2", "2").replace("\u00b3", "3")
    t = re.sub(r"(?<=\d)[ .,  ](?=\d{3}\b)", "", t)   # 1 000 / 1,000 / 1.000 -> 1000
    t = re.sub(r"(?<=\d)[.,](?=\d)", "", t)                    # 1,5 / 1.5 -> 15
    return Counter(re.findall(r"\d+", t))


def text_bez_html(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


def zkontroluj(pole, typ, cs, cil, jazyk):
    """Vrati (chyby, varovani) pro jeden preklad."""
    chyby, var = [], []
    if not cil or not cil.strip():
        return ["prazdny preklad"], var
    if cil != cil.strip() and cs == cs.strip():
        chyby.append("mezery na okrajich")
    holy = text_bez_html(cil)
    for jm in VLASTNI_JMENA:
        holy = holy.replace(jm, " ")
    m = CESKA_PISMENA.search(holy)
    if m:
        chyby.append("ceske/necilove pismeno %r" % m.group(0))
    m = ZAKAZANA.search(text_bez_html(cil))
    if m:
        chyby.append("zakazane slovo %r" % m.group(0))
    if re.search(r"\bgroove", cil, re.I) and jazyk == "en":
        chyby.append("EN: 'groove' -> 'slot'")
    if "**" in cil or "```" in cil:
        chyby.append("markdown ve vystupu")
    if re.search(r"\bKč\b|\bCZK\b", cil):
        var.append("mena Kc/CZK")
    if typ == "html":
        if znacky(cs) != znacky(cil):
            chyby.append("HTML znacky se lisi od zdroje")
    elif "<" in cil and "<" not in cs:
        chyby.append("HTML ve vystupu textoveho pole")
    zs, zc = Counter(re.findall(r"\{[A-Za-z0-9_]+\}|%[sd]", cs)), Counter(re.findall(r"\{[A-Za-z0-9_]+\}|%[sd]", cil))
    if zs != zc:
        chyby.append("zastupky se lisi: zdroj %s, preklad %s" % (dict(zs), dict(zc)))
    cc, cl = cisla(cs), cisla(cil)
    if pole in ("meta_title", "meta_description", "focus_keyword"):
        if cl - cc:
            chyby.append("cisla navic oproti zdroji: %s" % dict(cl - cc))
    elif cc != cl and not re.search(r"\bKč\b", cs):
        chyby.append("cisla se lisi: zdroj %s, preklad %s" % (dict(cc - cl), dict(cl - cc)))
    n = len(text_bez_html(cil))
    if pole == "meta_title" and n > 65:
        chyby.append("meta_title %d znaku (max 65)" % n)
    if pole == "meta_description":
        if n > 170:
            chyby.append("meta_description %d znaku (max 170)" % n)
        elif n < 90:
            var.append("meta_description jen %d znaku" % n)
    if pole not in ("meta_title", "meta_description") and n > 3 * max(len(text_bez_html(cs)), 1) + 60:
        chyby.append("preklad je moc dlouhy (%d vs %d)" % (n, len(text_bez_html(cs))))
    if cil.strip() == cs.strip() and re.search(r"[a-zěščřžýáíé]{4,}", cs, re.I) and len(cs) > 25:
        chyby.append("preklad je shodny se zdrojem")
    return chyby, var
