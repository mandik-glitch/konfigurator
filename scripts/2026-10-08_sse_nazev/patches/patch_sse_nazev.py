#!/usr/bin/env python3
"""Zaplata (bot8, 2026-10-08): ergonomicky stul SSE se VIDITELNE nejmenuje „system 41“ (Robert pres bot9: „tak mu nerikej 41 kdyz je to SSE“). Vnitrni klic 41 (selection.system, hash, SKU, RULES_VERSION,
app_settings stul_pravidla) se NEMENI. Meni jen texty, ktere vidi clovek: stranka generatoru 04 (titulek, znacka, nadpis), odkaz na prepnuti na SSE, hlasky okna Pravidla stolu, info o konfiguraci v kartach a nabidkach,
nazev dilu / popis ve Scene, vyrobni list; v dokumentaci nazvy sekci.
Pouziti: patch_sse_nazev.py <koren repa>   (soubory se prepisuji na miste; kazda kotva musi byt v souboru prave jednou)"""
import io
import os
import sys

koren = sys.argv[1] if len(sys.argv) > 1 else "/opt/konfigurator"


def uprav(soubor, zmeny):
    p = os.path.join(koren, soubor)
    s = io.open(p, encoding="utf-8").read()
    for a, b in zmeny:
        if s.count(a) == 0 and s.count(b) >= 1:                      # uz aplikovano (commit 3f68f82a)
            continue
        assert s.count(a) == 1, (soubor, s.count(a), a[:80])
        s = s.replace(a, b)
    io.open(p, "w", encoding="utf-8").write(s)
    print("OK", soubor)


NAZEV = "Generátor stolu 04 – ergonomický stůl SSE"
uprav("webapp/stul-konfigurator-41.html", [
    ("<title>Generátor stolu 04 systém 41 (SSE)</title>", f"<title>{NAZEV}</title>"),
    ("<span>Generátor stolu 04 systém 41 (SSE)</span></a>", f"<span>{NAZEV}</span></a>"),
    ("<h1>Generátor stolu 04 systém 41 (ergonomický stůl SSE)</h1>", f"<h1>{NAZEV}</h1>"),
])

uprav("webapp/js/stul-host.js", [
    ("  var PRODUCT_ID_30 = 4934;",
     "  function sysNazev(n) { return Number(n) === 41 ? \"SSE\" : \"systém \" + n; }          // SSE se viditelne nejmenuje „systém 41“ (Robert 2026-10-08); 41 je jen vnitrni klic (selection.system, hash, SKU)\n"
     "  var PRODUCT_ID_30 = 4934;"),
    ('"Přepnout na stůl SSE (systém 41, nohy SSE; přenesou se rozměry)"', '"Přepnout na ergonomický stůl SSE (nohy SSE; přenesou se rozměry)"'),
    ('$("pravVychozi").textContent = "Výchozí pro systém " + sys + " ("', '$("pravVychozi").textContent = "Výchozí pro " + sysNazev(sys) + " ("'),
    ('stav("Uloženo (systém " + sys + "), přepočítávám stůl…", false);', 'stav("Uloženo (" + sysNazev(sys) + "), přepočítávám stůl…", false);'),
    ('"Generátor stolu " + GEN[SYSTEM].no + " (systém " + SYSTEM + ") zatím není zapnutý."', '"Generátor stolu " + GEN[SYSTEM].no + " (" + sysNazev(SYSTEM) + ") zatím není zapnutý."'),
])

for f in ("webapp/js/stul-karta.js", "webapp/js/stul-nabidka.js"):
    uprav(f, [('(pl.system ? " · systém " + pl.system : "")', '(pl.system ? " · " + (Number(pl.system) === 41 ? "SSE" : "systém " + pl.system) : "")')])

uprav("webapp/js/scene/stul-konfigurator.js", [
    ('name: "Generátor stolu " + GENERATORY[sy].no + " systém " + sy,', 'name: "Generátor stolu " + GENERATORY[sy].no + " " + (sy === 41 ? "SSE" : "systém " + sy),'),
    ('(sy !== 30 ? "Systém " + sy + " (profil "', '(sy !== 30 ? (sy === 41 ? "SSE" : "Systém " + sy) + " (profil "'),
])

uprav("api/stul_vyrobni_list.py", [
    ('_CISLO_GENERATORU = {30: "01", 40: "02", 35: "03", 41: "04", 45: "05"}          # cislo generatoru stolu podle systemu profilu (poradi vzniku)\n',
     '_CISLO_GENERATORU = {30: "01", 40: "02", 35: "03", 41: "04", 45: "05"}          # cislo generatoru stolu podle systemu profilu (poradi vzniku)\n'
     '_JMENO_SYSTEMU = {41: "– ergonomický stůl SSE"}                                  # SSE se viditelne nejmenuje „system 41“ (Robert 2026-10-08); 41 je jen vnitrni klic\n'),
    ('Generátor stolu {_CISLO_GENERATORU.get(system, "01")} systém {system} · {_e(s["kod"])}</h1>', 'Generátor stolu {_CISLO_GENERATORU.get(system, "01")} {_JMENO_SYSTEMU.get(system, f"systém {system}")} · {_e(s["kod"])}</h1>'),
])

uprav("MAPA_3D_A_GENERATORU.md", [
    ("| **Generátor stolu 04 systém 41 – ergonomický stůl SSE** (Robert 2026-10-05, bot8) |", "| **Generátor stolu 04 – ergonomický stůl SSE** (vnitřní klíč systému 41, viditelně se tak nejmenuje – Robert 2026-10-08; zadal Robert 2026-10-05, bot8) |"),
    ("**Čtvrtý generátor = stůl SSE (systém 41, bot8 2026-10-05):**", "**Čtvrtý generátor = stůl SSE (vnitřní klíč systému 41, viditelně jen „SSE“; bot8 2026-10-05):**"),
])
uprav("docs/KONTRAKT_KONFIGURATOR_UI.md", [
    ("## Ergonomický stůl SSE = systém 41, čtvrtý generátor (bot8 2026-10-05, Robert:", "## Ergonomický stůl SSE (vnitřní klíč systému 41 – viditelně se nejmenuje „systém 41“, Robert 2026-10-08), čtvrtý generátor (bot8 2026-10-05, Robert:"),
])
uprav("docs/OVLADANI_3D.md", [
    ("## Stůl SSE (systém 41): ovládání ve 3D (bot8 2026-10-05)", "## Stůl SSE (vnitřní klíč systému 41): ovládání ve 3D (bot8 2026-10-05)"),
])
