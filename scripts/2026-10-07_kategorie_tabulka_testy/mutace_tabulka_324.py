#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mutacni kontrola testu nahledu tabulky kategorie #324 (bot16, 2026-10-07): zamerne chyby ve KOPII stranky, kazda musi test shodit (exit != 0).
Spusteni: python3 mutace_tabulka_324.py [cesta/dopravniky-324.html]   (vychozi webapp/nahled-tabulka/dopravniky-324.html)"""
import os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "..", "webapp", "nahled-tabulka", "dopravniky-324.html")
html = open(SRC, encoding="utf-8").read()
MUT = [
 ("OR mezi skupinami misto AND", 'return GROUPS.every(function (g) {\n      if (g.key === skipKey) return true;', 'return GROUPS.some(function (g) {\n      if (g.key === skipKey) return true;'),
 ("pocty u stitku ignoruji ostatni filtry", "all.filter(function (p) { return p[g.key] === v && passes(p, g.key); }).length", "all.filter(function (p) { return p[g.key] === v; }).length"),
 ("obracene razeni (sestupne/vzestupne)", 'var arr = list.slice(), d = state.dir === "desc" ? -1 : 1', 'var arr = list.slice(), d = state.dir === "desc" ? 1 : -1'),
 ("DPH 15 % misto 21 %", "var VAT = 21;", "var VAT = 15;"),
 ("vychozi zobrazeni Karty", 'sort: "vychozi", dir: "asc", view: "tabulka" }', 'sort: "vychozi", dir: "asc", view: "karty" }'),
 ("spatny odkaz Detail", '"/produkt/" + encodeURIComponent(p.slug)', '"/product/" + encodeURIComponent(p.slug)'),
 ("Zrusit filtry nemaze typ", "function resetAll() { GROUPS.forEach(function (g) { state[g.key] = {}; }); update(); }", 'function resetAll() { GROUPS.forEach(function (g) { if (g.key !== "typ") state[g.key] = {}; }); update(); }'),
 ("stranka nenacita dalsi strany API", "if (pr.length && rows.length < (d.total || 0) && page < 20) { page++; return next(); }", "if (false) { page++; return next(); }"),
 ("adresa se nezapisuje", 'history.replaceState(null, "", location.pathname + (s ? "?" + s : ""))', "0"),
 ("ztlumeny stitek jde zmacknout", 'if (b.getAttribute("aria-disabled") === "true") return; ', ""),
 ("vychozi razeni neodpovida katalogu", "else { return a.idx - b.idx; }", "else { return b.idx - a.idx; }"),
 ("prepnuti motivu zapisuje na server", 'try { localStorage.setItem("shopTheme", nxt); } catch (e) {}', 'try { localStorage.setItem("shopTheme", nxt); } catch (e) {} fetch("/api/auth/theme", { method: "PUT", body: "{}" });'),
 ("pocet u stitku vzdy 'variant' (bez sklonovani)", '(n === 1 ? "varianta" : (n >= 2 && n <= 4 ? "varianty" : "variant"))', '"variant"'),
 ("typ valecku bez zobrazovaneho nazvu", "function typLabel(v) { return TYP_LABEL[v] || v; }", "function typLabel(v) { return v; }"),
 ("poznamka pod tabulkou jina", "Šířka odpovídá délce válečku, délka je délka dopravníku.", "Rozměry jsou orientační."),
 ("zahlavi Sirka bez jednotky", '["sirka", "Šířka (mm)", true, "sirka"]', '["sirka", "Šířka", true, "sirka"]'),
 ("skupina Sirka bez slova dopravniku", 'label: "Šířka dopravníku (délka válečku)"', 'label: "Šířka (délka válečku)"'),
 ("aria-label Detail puvodni", '"Detail produktu: "', '"Detail: "'),
 ("jednotka v bunkach i na pocitaci", "td .u { display: none; }", "td .u { display: inline; }"),
 ("tabulka bez ceny s DPH (stejna jako bez)", 'cell("num cena-vat", "s DPH", hasP ? fmtKc(withVat(net)) : "–");', 'cell("num cena-vat", "s DPH", hasP ? fmtKc(net) : "–");'),
]
FILTR = sys.argv[2] if len(sys.argv) > 2 else ""          # volitelne: jen mutace, jejichz nazev obsahuje retezec
selhalo = 0
for nazev, stare, nove in MUT:
    if FILTR and FILTR not in nazev: continue
    if html.count(stare) != 1:
        print("PRESKOCENO (vzor v strance neni 1x): " + nazev); selhalo += 1; continue
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html.replace(stare, nove)); cesta = f.name
    env = dict(os.environ, NAHLED_HTML=cesta, STOP_NA_PRVNI_CHYBE="1")
    r = subprocess.run(["node", os.path.join(HERE, "test_tabulka_324.js")], env=env, capture_output=True, text=True, timeout=300)
    os.unlink(cesta)
    ok = r.returncode != 0
    prvni = next((l for l in r.stdout.splitlines() if l.startswith("FAIL")), "")[:110]
    print(("OK  mutace shozena: " if ok else "CHYBA mutace PRESLA testem: ") + nazev + ("  [" + prvni + "]" if prvni else ""))
    if not ok: selhalo += 1
print("\nVYSLEDEK mutaci: %d/%d shozeno" % (len([m for m in MUT if not FILTR or FILTR in m[0]]) - selhalo, len([m for m in MUT if not FILTR or FILTR in m[0]])))
sys.exit(1 if selhalo else 0)
