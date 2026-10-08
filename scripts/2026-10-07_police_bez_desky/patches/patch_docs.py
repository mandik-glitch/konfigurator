#!/usr/bin/env python3
"""Zaplata dokumentace: docs/KONTRAKT_KONFIGURATOR_UI.md (tabulka zavislosti + sekce 'Spodni police BEZ DESKY') a docs/OVLADANI_3D.md (cast police bez desky). Kotvene nahrady.
Pouziti: patch_docs.py <koren repa>   (zapise primo do docs/ - docs nejsou v kandidatnim stromu; apply.sh ji vola s kontrolou kotev predem)"""
import os
import sys

root = sys.argv[1]
KONTRAKT = os.path.join(root, "docs", "KONTRAKT_KONFIGURATOR_UI.md")
OVLADANI = os.path.join(root, "docs", "OVLADANI_3D.md")


def nahrad(s, a, b, label):
    assert s.count(a) == 1, "kotva %s: %d vyskytu" % (label, s.count(a))
    return s.replace(a, b)


k = open(KONTRAKT, encoding="utf-8").read()
k = nahrad(k, "\n## Výchozí konfigurace generátoru – admin tlačítko „Uložit jako výchozí“", '''
## Spodní police BEZ DESKY – slot `shelfboard` (bot8 2026-10-07, Robert: „spodní police nech má volbu být bez desky, jen profily / rám“)
Generátory 01–03 a 05 (systémy 30 / 35 / 40 / 45; stůl SSE ne – jeho police leží přímo na spojnicích nohou) mají za `shelf` přepínač, zda mají spodní police laminodesku. **Výchozí je s deskou, takže hash / kód / cena / model všech dosavadních konfigurací zůstávají beze změny** (zlatý otisk 1263 konfigurací: `scripts/2026-10-07_police_bez_desky/test_police_bez_desky_zlato.py`).
- **Generátor:** parametr `police_deska` (bool, výchozí `True`; `?police_deska=0` v dotazu staff API). `False` = každá spodní police je jen **rám z profilů** (obě boční příčky police, přední a zadní příčka, u široké police střední příčka): odpadne deska police, její dělení u střední opory / rámu, zkrácení desky při hloubce > 900 mm **a podpěry pod ní** (bez desky nemají co nést); rohové spojky, které dosud vynechávala deska police (kolize), se vrátí. Počet, výška polic (`police_h1…`) a všechny ostatní díly beze změny: výška se dál měří k rovině horní plochy desky (= horní hrana rámu + 18 mm), takže přepnutí desky nic nehýbe. Police pod výřezem má vlastní přepínač a vlastní desku – volba ji neovlivní. Bez spodních polic (`police` = 0) a v SSE se volba nepoužívá (účinný parametr `True`, stejný hash).
- **Hash a token modelu:** `police_deska` je v `kanonicky_hash` JEN při `False` a aspoň jedné polici; podepsaný token modelu (`_zabal`) nese klíč `B` = 0 jen bez desky (starší tokeny a výchozí = s deskou).
- **Veřejné API:** slot **`shelfboard`** (toggle, skupina Konstrukce, hned za `shelf`, výchozí `true`; bez `depends_on` – nadřazený `shelf` je posuvník, kontrakt zná jen toggle –, bez polic ho `options.shelfboard.hidden: true` skryje; texty cs / en / sk + `help_shelfboard`, de / hu zatím záloha z angličtiny – viz `docs/jazyky/README.md`). Bez polic server hodnotu ignoruje (výběr se vrátí s `true`, stejný hash). `options.shelfboard.on.price_delta` = přesný rozdíl ceny po vrácení desky. Shrnutí výběru (`souhrn`) ukáže „Desky na spodních policích: ne“ jen bez desky; odkaz na výrobní list / sestavu pro zaměstnance nese `police_deska=0` jen bez desky. Kusovník a cena: bez laminodesky police, bez podpěr, s případnými novými rohovými spojkami.
- **3D ovládání:** část police (`shelf1…`) je bez desky tvořena rámem (obě boční příčky police), `param` obsahuje `shelf` i `shelfboard`; v nabídce „Odebrat desku police“ / „Vrátit desku police“ (u více polic „…desky všech polic“; platí pro všechny spodní police). Tahy výšek polic a jejich živé tažení beze změny.
- **Kóty:** bez desky kóta výšky horní hrany rámu police a mezery nad ním (jinak horní plocha desky).
- **Výrobní výpis / list:** bez položky „spodní police“ mezi deskami, montážní kroky 2 a 3 bez zmínky o deskách a podpěrách polic, poznámka o dělení desek jen pro pracovní desku.
- **Testy:** `scripts/2026-10-07_police_bez_desky/` – `test_police_bez_desky.py` (jádro: parametr, hash, mřížka konfigurací bez desky proti vlastní s deskou, 3D ovládání, kóty, výpis, GLB, živé tažení, veřejné překlady), `…_zlato.py` (zlatý otisk), `…_shop.py` (veřejné API), `mutace.py`, `run_regrese.sh`.

## Výchozí konfigurace generátoru – admin tlačítko „Uložit jako výchozí“''', "sekce")

o = open(OVLADANI, encoding="utf-8").read()
o = nahrad(o, "\n## Části `podpery_<N>` (bot8 2026-10-03)\n", '''
## Police BEZ DESKY (bot8 2026-10-07)
Je-li parametr `police_deska` vypnutý (slot `shelfboard`), část `shelf<N>` tvoří rám police (obě boční příčky) místo desky; `param` je `["shelf","shelfboard"]`, nabídka má navíc „Odebrat desku police“ / „Vrátit desku police“ (u více polic „…desky všech polic“; mění všechny spodní police). Části `supports<N>` (podpěry pod deskou) bez desky nevznikají. Tahy `sh<K>` a jejich `zive` operace se chovají jako s deskou (výška se měří k rovině horní plochy desky = horní hrana rámu + 18 mm).

## Části `podpery_<N>` (bot8 2026-10-03)
''', "ovladani")
open(KONTRAKT, "w", encoding="utf-8").write(k)             # zapis az po overeni vsech kotev (zadna dokumentace napul)
open(OVLADANI, "w", encoding="utf-8").write(o)
print("OK docs")
