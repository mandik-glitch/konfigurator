#!/usr/bin/env python3
"""Zaplata dokumentace (bot8, 2026-10-08): docs/OVLADANI_3D.md - pole `vodici.ovladani.razitka` a chovani razitek pri zivem tazeni. Pouziti: patch_docs.py <koren repa>"""
import io
import os
import sys

koren = sys.argv[1] if len(sys.argv) > 1 else "/opt/konfigurator"
p = os.path.join(koren, "docs/OVLADANI_3D.md")
s = io.open(p, encoding="utf-8").read()
if "`vodici.ovladani.razitka`" in s:
    print("docs: uz je aplikovano (commit e45888a3), nic se nemeni")
    sys.exit(0)
a = "- tah `zive` = seznam operací `{op: \"posun\"|\"natahni\"|\"roztahni\", ix: [indexy dílů], k, strana?}`;"
assert s.count(a) == 1, s.count(a)
nove = ("- `vodici.ovladani.razitka` = `[{dil, uzel, vypln: [uzel, od, počet]}]` (od 2026-10-08, jen když je výchozí model S razítky – WORKFLOW pravidlo 61; Robert: „razítka na generátoru při tažení zůstávají na místě“): na kterém dílu "
        "(`dil` = index dílu) razítko sedí, který uzel `n<uzel>` je jeho logo a kde jsou vrcholy výplně drážky v uzlu hliník. Prohlížeč (`v3d-ovladani.js` 1.2.0) při živém tažení hýbe razítka jako tuhá tělesa: `posun` stejně jako díl, "
        "`natahni` / `roztahni` podle polohy STŘEDU razítka vůči STŘEDU dílu podél osy (stejné pravidlo jako pro vrcholy dílu; logo se nedeformuje); zrušení tažení (Esc) je vrátí, razítka na dílech, které se nehýbou, stojí; po puštění "
        "přijde přesný model s razítky (na novém hashi jsou umístěná znovu). Starší klient pole ignoruje (razítka by za tažením zůstala do puštění). Test: `scripts/2026-10-08_razitka_tazeni/` (emulace pravidla nad skutečným GLB + prohlížeč).\n")
io.open(p, "w", encoding="utf-8").write(s.replace(a, nove + a))
print("OK docs/OVLADANI_3D.md")
