#!/usr/bin/env python3
"""Ergonomicky stul SSE se VIDITELNE nejmenuje „system 41“ (Robert 2026-10-08, pres bot9: „tak mu nerikej 41 kdyz je to SSE“). Vnitrni klic 41 (selection.system, hash, SKU, RULES_VERSION, app_settings
stul_pravidla) zustava. Hermeticky (bez DB, bez prohlizece): proleze texty, ktere vidi clovek (zdroje stranek a skriptu v webapp/, preklady mini-shopu, retezce v api/stul_vyrobni_list.py) a hleda
„system 41“ / „systém 41“ (bez komentaru; Python pres ast = jen retezcove konstanty mimo docstringy). Dynamicke skladani textu („systém “ + cislo) hlida prohlizecovy test_sse_stranka.js
(1h2 + 3d) a test_stul_pravidla_stranka.js (F4) a tenhle test hlida pritomnost pomocne funkce `sysNazev` ve stul-host.js a vyjimky v kartach / nabidce / Scene.
Spusteni: api/venv/bin/python3 scripts/2026-10-08_sse_nazev/test_sse_nazev_texty.py"""
import ast
import glob
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VZOR = re.compile(r"syst[eé]m\s*41", re.I)
OK, FAILS = 0, []


def check(cond, msg):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print(f"  CHYBA: {msg}")


def bez_komentaru_js(s):
    """JS / HTML text bez komentaru (// do konce radku mimo retezce, /* ... */, <!-- ... -->)."""
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    out, i, n, q = [], 0, len(s), None
    while i < n:
        c = s[i]
        if q:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(s[i + 1])
                i += 1
            elif c == q:
                q = None
        elif c in "\"'`":
            q = c
            out.append(c)
        elif c == "/" and i + 1 < n and s[i + 1] == "/" and not (i > 0 and s[i - 1] == ":"):
            while i < n and s[i] != "\n":
                i += 1
            continue
        elif c == "/" and i + 1 < n and s[i + 1] == "*":
            j = s.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        else:
            out.append(c)
        i += 1
    return "".join(out)


def retezce_python(zdroj):
    """Retezcove konstanty ze zdroje Pythonu mimo docstringy (vcetne casti f-retezcu)."""
    strom = ast.parse(zdroj)
    docstringy = set()
    for uzel in ast.walk(strom):
        if isinstance(uzel, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and uzel.body and isinstance(uzel.body[0], ast.Expr) \
                and isinstance(uzel.body[0].value, ast.Constant) and isinstance(uzel.body[0].value.value, str):
            docstringy.add(id(uzel.body[0].value))
    return [u.value for u in ast.walk(strom) if isinstance(u, ast.Constant) and isinstance(u.value, str) and id(u) not in docstringy]


def soubory(vzory):
    out = []
    for v in vzory:
        out += sorted(glob.glob(os.path.join(REPO, v), recursive=True))
    return [f for f in out if "/nahled" not in f and "/node_modules/" not in f and os.path.isfile(f)]


# ---- front-end: stranky a skripty (bez komentaru)
fe = soubory(["webapp/*.html", "webapp/js/**/*.js", "webapp/miniweb/*.js", "webapp/miniweb/*.html"])
check(len(fe) > 60, f"prohledano dost souboru front-endu ({len(fe)})")
spatne = {}
for f in fe:
    txt = bez_komentaru_js(open(f, encoding="utf-8", errors="replace").read())
    nalez = [m.group(0) for m in re.finditer(r".{0,50}" + VZOR.pattern + r".{0,30}", txt, re.I)]
    if nalez:
        spatne[os.path.relpath(f, REPO)] = nalez[:2]
check(not spatne, f"front-end: nikde viditelne 'system 41' ({spatne})")

# ---- preklady mini-shopu (viditelne retezce)
spatne = {}
for f in soubory(["webapp/miniweb/i18n/*.json"]):
    txt = open(f, encoding="utf-8").read()
    if VZOR.search(txt):
        spatne[os.path.relpath(f, REPO)] = VZOR.findall(txt)[:3]
check(not spatne, f"preklady mini-shopu: nikde 'system 41' ({spatne})")
for jazyk in ("cs", "en", "sk", "de", "hu"):
    t = open(os.path.join(REPO, "webapp/miniweb/i18n", f"{jazyk}.json"), encoding="utf-8").read()
    check(re.search(r'"pdc\.sys41":\s*"[^"]*SSE[^"]*"', t) is not None, f"mini-shop {jazyk}: prepinac systemu nazyva 41 'SSE' (pdc.sys41)")

# ---- api: vyrobni list (retezce, ne docstringy)
vl = open(os.path.join(REPO, "api/stul_vyrobni_list.py"), encoding="utf-8").read()
retezce = retezce_python(vl)
check(not [r for r in retezce if VZOR.search(r)], "api/stul_vyrobni_list.py: v retezcich neni 'system 41'")
check(any("ergonomický stůl SSE" in r for r in retezce), "api/stul_vyrobni_list.py: nazev SSE pro hlavicku vyrobniho listu")

# ---- pomocna funkce a vyjimky pro SSE
host = open(os.path.join(REPO, "webapp/js/stul-host.js"), encoding="utf-8").read()
check(host.count("function sysNazev(n)") == 1 and host.count("sysNazev(") >= 4, f"stul-host.js: pomocna funkce sysNazev a jeji pouziti ({host.count('sysNazev(')}x)")
check("Přepnout na ergonomický stůl SSE" in host, "stul-host.js: odkaz 'Přepnout na ergonomický stůl SSE'")
for f, kus in (("webapp/js/stul-karta.js", 'Number(pl.system) === 41 ? "SSE"'), ("webapp/js/stul-nabidka.js", 'Number(pl.system) === 41 ? "SSE"'),
               ("webapp/js/scene/stul-konfigurator.js", 'sy === 41 ? "SSE"')):
    check(kus in open(os.path.join(REPO, f), encoding="utf-8").read(), f"{f}: vyjimka pro SSE ({kus})")
h41 = open(os.path.join(REPO, "webapp/stul-konfigurator-41.html"), encoding="utf-8").read()
check(h41.count("Generátor stolu 04 – ergonomický stůl SSE") == 3, f"stul-konfigurator-41.html: titulek, znacka a nadpis ({h41.count('Generátor stolu 04 – ergonomický stůl SSE')}x)")
check('data-system="41"' in h41, "stul-konfigurator-41.html: vnitrni klic data-system=\"41\" zustava")

# ---- vnitrni klic 41 zustava
sys.path.insert(0, os.path.join(REPO, "api"))
src = open(os.path.join(REPO, "api/stul_konfigurator.py"), encoding="utf-8").read()
check("SYSTEM_SSE = 41" in src, "stul_konfigurator.SYSTEM_SSE = 41 (vnitrni klic beze zmeny)")
check('RECEPT_SSE = "stul_system41"' in open(os.path.join(REPO, "api/stul_shop.py"), encoding="utf-8").read(), 'recept "stul_system41" beze zmeny')
check('STUL-S{system}-' in open(os.path.join(REPO, "api/stul_karta.py"), encoding="utf-8").read(), "SKU karty STUL-S<system>-<hash8> beze zmeny")

print(f"\nvysledek: {OK} OK, {len(FAILS)} chyb")
sys.exit(1 if FAILS else 0)
