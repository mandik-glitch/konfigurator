#!/usr/bin/env python3
"""Zaplata dokumentace 'svitidla LED rucne' (bot8, 2026-10-08): docs/KONTRAKT_KONFIGURATOR_UI.md (radek tabulky zavislosti slotu, uprava odrazek sekce 'Delka LED svitidla' + nova sekce), docs/OVLADANI_3D.md (svitidla v ovladani ve 3D) a
MAPA_3D_A_GENERATORU.md (uprava radku LED + novy radek). Kotvene nahrady (assert count == 1) proti ZIVYM souborum. Pouziti: patch_docs.py <koren_repa> (zapisuje SOUBORY V KORENI - volat uvnitr zamku bot8,
nebo s koren_repa = kopie)"""
import os
import sys

root = sys.argv[1]


def uprav(rel, a, b, label):
    p = os.path.join(root, rel)
    s = open(p, encoding="utf-8").read()
    assert s.count(a) == 1, "kotva %s: %d vyskytu" % (label, s.count(a))
    open(p, "w", encoding="utf-8").write(s.replace(a, b))


KONTRAKT = "docs/KONTRAKT_KONFIGURATOR_UI.md"
uprav(KONTRAKT, '''| `ledlen` | `posts`, `led`, `ledlight` |
''', '''| `ledlen` | `posts`, `led`, `ledlight` |
| `ledcount`, `ledpos1` … `ledpos4` | `posts`, `led`, `ledlight` |
''', "tabulka")
uprav(KONTRAKT, '''**všechna svítidla stolu jsou stejně dlouhá** a řadí se vedle sebe (rozteč = délka tělesa z GLB: 1247 / 647 mm, `led_telo_dilu`), počet `max(1, floor((šířka + 47) / těleso))`, skupina vycentrovaná jako dosud, přesah ≤ 47 mm (`LED_PREVIS`).''',
       '''**všechna svítidla stolu jsou stejně dlouhá**; kolik jich je a kde leží, je od 2026-10-08 RUČNÍ volba (sekce „Svítidla LED ručně“ níže; rozteč = délka tělesa z GLB: 1247 / 647 mm, `led_telo_dilu`; nejvíc `max(1, floor((šířka + 47) / těleso))`, přesah ≤ 47 mm (`LED_PREVIS`)).''', "odrazka generator")
uprav(KONTRAKT, '''`led_info` = `{delka, typy: [{delka, telo, pocet, min_sirka, vejde}]}` (jen když je svítidlo na stole).''',
       '''`led_info` = `{delka, typy: [{delka, telo, pocet, min_sirka, vejde}], pocet, max, telo, osa, okraj, stred, polohy, auto, meze, pridat, odebrat}` (jen když je svítidlo na stole; nové klíče viz „Svítidla LED ručně“).''', "odrazka led_info")
uprav(KONTRAKT, '''## Horní police mezi zadními stojkami (bot8 fork 3, 2026-10-07''', '''## Svítidla LED ručně: počet a poloha podél profilu (bot8 2026-10-08, Robert: „svítidla v generátoru se přidávají automaticky za sebe podle délky, ale chceme aby se přidávala jen ručně a mohla se posouvat podél profilu“)
Generátory 01–03 a 05 (stůl SSE LED nemá). **Svítidla se už nepřidávají sama podle šířky stolu: výchozí je JEDNO svítidlo** (dosud se na stolu od šířky 2447 mm s LED 1200, resp. 1247 mm s LED 600 řadila automaticky 2–4 vedle sebe; tyhle výchozí konfigurace se záměrně mění – 217 ze 873 stolů zlaté mřížky; `led_pocet` = dřívější počet dá PŘESNĚ dřívější model). Zákazník svítidla přidává, odebírá a posouvá podél příčného profilu nad LED.
- **Generátor:** `led_pocet` (celé 1–4, výchozí 1; vyšší, než se vejde, se ořízne na `led_info.max`) a `led_z1` … `led_z4` (poloha STŘEDU svítidla v mm od osy stolu, + doprava, `None` = automaticky: svítidla těsně vedle sebe, skupina vystředěná jako dosud; na 0,1 mm; `?led_pocet=&led_z1=` v dotazu staff API, `null` / `auto` / prázdné = automaticky). Pravidla: pořadí zleva doprava se nemění, svítidla se nepřekrývají (kdo by se překryl, je odsunut doprava), aspoň 90 % délky každého leží nad příčným profilem (přesah ≤ 10 %) a rozpětí celé skupiny je ≤ šířka + 47 mm (`LED_PREVIS`). Efektivní `parametry` nesou skutečný počet a polohy; poloha shodná s automatickou je `None` (jedna konfigurace = jeden model = jeden hash). Bez svítidla (LED / stojky / svítidlo vypnuto, nebo odebráno) je `led_pocet` 1 a polohy `None`. SSE parametry ignoruje.
- **`led_info`:** `pocet`, `max`, `telo` (délka tělesa), `osa` (osa stolu v souřadnicích generátoru), `okraj` (vnější okraje stolu vůči ose), `stred` (CELÝ rozsah středu svítidla nad profilem), `polohy` / `auto` (skutečné a automatické polohy vůči ose), `meze[k]` (rozsah posunu k-tého svítidla mezi sousedy / okrajem), `pridat` (parametry po přidání dalšího svítidla: vedle posledního, jinak vedle prvního, jinak do mezery, jinak všechna znovu vystředěná; `None` = už se nevejde), `odebrat[k]` (parametry po odebrání k-tého, ostatní zůstanou na místě).
- **Veřejné API:** slider **`ledcount`** (1–4 ks) a **`ledpos1` … `ledpos4`** (mm, −1500…1500, krok 1, `null` = automaticky) hned za `ledlen`, `depends_on: [posts, led, ledlight]`, výchozí výběr `ledcount: 1`, `ledpos*: null`. `options.ledcount = {min: 1, max, value}`; `options.ledpos<k> = {min, max, value, auto, fits}` pro existující svítidla – `min` / `max` je CELÝ rozsah středu svítidla nad profilem, stejný pro všechna svítidla a nezávislý na počtu (nabídka ve 3D přidat / odebrat mění počet i čísla poloh jedním krokem a modul voleb ořezává hodnoty podle STARÝCH mezí `options`; nepřípustné polohy generátor upraví a vrátí skutečné) – a `{hidden: true}` pro neexistující; bez svítidla `ledcount {min: 1, max: 1}` a `ledpos* {hidden: true}`. Požadovaný počet vyšší, než se vejde, = `notices[]` `{slot: "ledcount", action: "info"}` („Počet svítidel LED snížen na N …“, cs/en/sk, další jazyky anglická záloha). Shrnutí voleb ukazuje počet jen když není 1 a polohu jen u svítidla s výslovně zadanou polohou. Token modelu: klíč `J` = `[počet, poloha 1.., null = auto]` (bez klíče = 1 svítidlo, auto); odkaz na výrobní list nese `led_pocet` / `led_z<k>`.
- **Hash:** `led_pocet` 1 se u stolu, kam se vejde jen jedno svítidlo, do hashe nenese (hashe úzkých stolů a stolů bez svítidla zůstávají); u širšího stolu se nese (dřív tam byl počet automaticky 2–4, hash i kód takových stolů se tedy změnil). Polohy `None` / pro neexistující svítidlo se nenesou. `rules_version` se nemění.
- **3D ovládání:** část `led` má v nabídce „Přidat svítidlo LED“ (na maximu zakázáno s důvodem), každé svítidlo je vlastní část `ledlamp<k>` s nabídkou „Odebrat toto svítidlo“ / „Vrátit svítidlo na výchozí místo“ a TAH `ledpos<k>` podél příčného profilu (osa Z; meze = sousední svítidla / okraj, `mereni` „od levého / pravého okraje stolu“ a „od levého / pravého svítidla“; živé tažení = PŘESNÁ operace `posun` svítidla, ostatní díly stojí). EN/SK texty v `stul_ovladani_verejne.py`.
- **Testy:** `scripts/2026-10-08_led_rucne/` – `test_led_rucne.py` (generátor: vstup, počty, polohy MĚŘENÉ z vrcholů meshe, náhodný pokus na invarianty a idempotenci, kanonická podoba, `led_info`, 3D ovládání, živé tažení, hash, SSE, GLB, lux; zlatý otisk 873 konfigurací), `test_led_rucne_shop.py` (veřejné API včetně simulace ořezu hodnot starými mezemi), `mutace.py`, `golden_head.py` (otisk PŘED změnou).

## Horní police mezi zadními stojkami (bot8 fork 3, 2026-10-07''', "sekce")

OVL = "docs/OVLADANI_3D.md"
uprav(OVL, '''- Přesně: `stredni_noha`, `led_rameno`, `suplik_posun`. NÁHLED''', '''- **Svítidla LED (bot8 2026-10-08):** každé svítidlo je vlastní část `led_<k>` (veřejně `ledlamp<k>`, `priorita` 3) s nabídkou „Odebrat toto svítidlo“ / „Vrátit svítidlo na výchozí místo“ a TAH `led_z<k>` (veřejně `ledpos<k>`; osa Z podél příčného profilu, `faktor` 1, `min`/`max` = sousední svítidla / okraj, `mereni` „od levého / pravého okraje stolu“ a „od levého / pravého svítidla“ jako `add + mul × hodnota`); jeho `zive` je jediná PŘESNÁ operace `posun` svítidla (ostatní díly stojí; globální vycentrování modelu klient nedělá, jako u ramene LED). Část `led` (celé osvětlení) má navíc nabídku „Přidat svítidlo LED“. Viz `docs/KONTRAKT_KONFIGURATOR_UI.md`, sekce „Svítidla LED ručně“.
- Přesně: `stredni_noha`, `led_rameno`, `suplik_posun`, `led_z<k>`. NÁHLED''', "ovladani")

MAPA = "MAPA_3D_A_GENERATORU.md"
uprav(MAPA, '''všechna svítidla stolu stejně dlouhá, řadí se vedle sebe po šířce stolu;''', '''všechna svítidla stolu stejně dlouhá (počet a polohu volí zákazník ručně, viz další řádek);''', "mapa led")
uprav(MAPA, '''| **Formáty tabulí laminodesky, dělení desek u střední opory**''', '''| **Svítidla LED ručně: počet a poloha podél profilu** (Robert 2026-10-08: „svítidla se mají přidávat jen ručně a mohla se posouvat podél profilu“; generátory 01–03 a 05) | parametry `led_pocet` (1–4, výchozí 1 – svítidla se už nepřidávají sama podle šířky stolu) a `led_z1` … `led_z4` (střed svítidla v mm od osy stolu, `None` = automaticky); pořadí se nemění, svítidla se nepřekrývají, aspoň 90 % délky nad profilem; `led_info` (`pridat`, `odebrat`, `meze`); veřejné sloty `ledcount` + `ledpos1` … `ledpos4`; 3D: nabídka „Přidat svítidlo LED“, části `ledlamp<k>`, tah `ledpos<k>`; širokým stolům se výchozí konfigurace mění (1 svítidlo místo 2–4), `led_pocet` = dřívější počet dá přesně dřívější model | `api/stul_konfigurator.py` (`LED_MAX`, `led_polohy`, `led_meze`, `led_pridat`, `led_odebrat`, blok 2a), `api/stul_shop.py`, `api/stul_ovladani_verejne.py`, `api/stul_glb.py` (hash), `docs/KONTRAKT_KONFIGURATOR_UI.md`, testy `scripts/2026-10-08_led_rucne/` |
| **Formáty tabulí laminodesky, dělení desek u střední opory**''', "mapa novy radek")
print("OK docs ->", root)
