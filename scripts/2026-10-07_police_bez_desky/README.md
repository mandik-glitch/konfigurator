# Spodní police BEZ DESKY – generátory stolu (bot8, 2026-10-07)

Robert: *„úpravy generátorů stolů: spodní police ať má volbu být bez desky, jen profily / rám“*.

## Co to dělá
Nový parametr generátoru **`police_deska`** (bool, výchozí `True`) a nový veřejný slot **`shelfboard`** (toggle, skupina Konstrukce hned za `shelf`; bez polic ho `options.shelfboard.hidden` skryje – `depends_on` nelze, nadřazený `shelf` je posuvník a kontrakt zná jen toggle). Vypnuto = každá spodní police je jen
**rám z profilů**: odpadne laminodeska police, její dělení u střední opory / rámu, zkrácení při hloubce > 900 mm a **podpěry pod ní**. Rohové spojky, které dosud vynechala deska police (kolize),
se vrátí (generátor vynechává spojky podle skutečných dílů). Počet a výška polic, `police_h…` a všechny ostatní díly beze změny. Police pod výřezem má vlastní přepínač/desku – neovlivněna.
SSE (systém 41) volbu ignoruje. Bez spodních polic je volba bezpředmětná (účinný parametr `True`, stejný hash).
**Výchozí = s deskou: hash, kód, cena, model, výrobní výpis a 3D ovládání (kromě nové položky nabídky) všech dosavadních konfigurací zůstávají beze změny** (zlatý otisk).

## Soubory (nové, vše v téhle složce; živý strom se nemění, dokud se neaplikuje `apply.sh`)
| soubor | k čemu |
|---|---|
| `patches/patch_konfigurator.py` | `api/stul_konfigurator.py`: parametr, normalizace, `_aktivni`, dotaz staff API, `_patro_ramu_police`, 3D ovládání (část police z rámu, nabídka Odebrat/Vrátit desku), montážní texty |
| `patches/patch_glb.py` | `api/stul_glb.py`: `kanonicky_hash` nese `police_deska` jen při `False` (a aspoň jedné polici, ne v SSE) |
| `patches/patch_sse.py` | `api/stul_sse.py`: SSE `police_deska` ignoruje |
| `patches/patch_koty.py` | `api/stul_koty.py`: kóty polic bez desky (horní hrana rámu) |
| `patches/patch_vyrobni_list.py` | `api/stul_vyrobni_list.py`: poznámka o dělení desek bez zmínky o policích |
| `patches/patch_shop.py` | `api/stul_shop.py`: slot `shelfboard` (PREPINACE, VYCHOZI_VYBER, schéma, texty cs/en/sk, `options.hidden`, normalizace, token klíč `B`, shrnutí, odkaz na výrobní list) |
| `patches/patch_ovladani_verejne.py` | `api/stul_ovladani_verejne.py`: `police_deska` → `shelfboard`, překlady 4 nových položek nabídky |
| `patches/patch_docs.py` | `docs/KONTRAKT_KONFIGURATOR_UI.md`, `docs/OVLADANI_3D.md` |
| `patches/patch_test_stul_shop.py` | EXISTUJÍCÍ test `scripts/2026-10-02_stul_testy/test_stul_shop.py`: kontrola „zapnutí každé volby má kladný příplatek“ vynechá `shelfboard` (bez polic nic nemění) |
| `apply.sh [kořen]` | aplikuje VŠECHNY záplaty na živý strom (kotvy se ověří předem do tmp, pak se soubory vymění; volat uvnitř zámku) |
| `prepare_cand.sh [adresář]` | postaví kandidátní strom (symlinky + upravené kopie) pro testy bez zásahu do živého stromu |
| `_spolecne.py`, `golden_head.py`, `golden_head.json` | mřížka konfigurací (1263 + 8 GLB) a zlatý otisk vyrobený nad stavem PŘED změnou |
| `test_police_bez_desky.py` | jádro (hermeticky, bez DB): parametr, hash, vyběr z mřížky bez desky vs. s deskou, 3D ovládání, kóty, výpis, GLB, živé tažení, veřejné 3D ovládání |
| `test_police_bez_desky_zlato.py` | zlatý otisk – celá mřížka, výchozí i výslovné `True` |
| `test_police_bez_desky_shop.py` | veřejné API (schéma, resolve, cena, token, shrnutí, výrobní list, SSE; DB jen čte) |
| `test_police_bez_desky_stranka.js` | stránka Generátor stolu 01 v Chromiu přes most `_most_stul.py` (přepínač v panelu, vypnutí, nabídka ve 3D, #hash, skrytí bez polic, „Výchozí hodnoty“) |
| `mutace.py` | mutační kontrola (každá chyba v 7 souborech api/ musí shodit test) |
| `run_regrese.sh` | nové + existující sady generátoru nad zvoleným stromem; části 1 = jádro stolu, 2 = police / desky / kóty, 3 = těžké sady jen nad generátorem, 4 = shop a SSE, 5 = nové testy (vč. zlatého otisku); `BEZ_NOVYCH=1` pro běh nad živým stromem |

## Postup nasazení (pod zámkem bot8)
1. `scripts/lock.sh acquire bot8 "…"` (guardované `api/*.py`), ověřit `lock.sh require bot8`.
2. `scripts/2026-10-07_police_bez_desky/apply.sh` – kotvy se ověří proti ŽIVÉMU souboru; selže-li kotva (někdo mezitím upravil stejné místo), nezapíše se nic.
3. `git diff --stat` – musí být jen 7× `api/*.py` + test_stul_shop.py + 2× docs; `api/venv/bin/python3 scripts/2026-10-07_police_bez_desky/test_police_bez_desky.py` (+ `_zlato`, `_shop` přes `systemd-run --property=EnvironmentFile=api/.env`).
4. Commit s explicitním pathspec (`api/stul_konfigurator.py api/stul_glb.py api/stul_sse.py api/stul_koty.py api/stul_vyrobni_list.py api/stul_shop.py api/stul_ovladani_verejne.py docs/KONTRAKT_KONFIGURATOR_UI.md docs/OVLADANI_3D.md scripts/2026-10-02_stul_testy/test_stul_shop.py scripts/2026-10-07_police_bez_desky`); commit-msg hook: nic se nemaže (bez `[remove-fn]`).
4b. Prohlížečový test: `systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-02_stul_testy/_most_stul.py scripts/2026-10-07_police_bez_desky/test_police_bez_desky_stranka.js 4934`.
5. API se nasadí plánovaně (0:00 / 12:30 HUP); statika (stul-host.js apod.) se NEMĚNÍ – UI se kreslí ze schématu.

## Výsledky ověření (2026-10-08; kandidát = živé soubory + záplaty; živé soubory beze změny od startu, žádný nový commit do nich)
| co | výsledek |
|---|---|
| Nové testy nad kandidátem | jádro `test_police_bez_desky.py` **69/69**, veřejné API `…_shop.py` **156/156**, zlatý otisk `…_zlato.py` **11/11** (1263 konfigurací + 8 GLB bit po bitu jako před změnou), prohlížeč `…_stranka.js` **14/14** (Chromium přes `_most_stul.py`) |
| Totéž nad ZÁKLADNÍM stavem (před změnou) | selhává (`KeyError: police_deska` / `shelfboard` – volba neexistuje) = reprodukce |
| Existující sady `run_regrese.sh` (části 1, 2, 4 = 29 sad), živý strom vs kandidát | 27 sad s IDENTICKÝM počtem kontrol, 2 mají u kandidáta víc kontrol (rc=0 obojí): `test_stul_shop` 1318 → 1336, `test_stul_ovladani` 2109 → 2131 (cykly přes sloty / položky nabídky projdou i nový slot); žádná sada neselhala |
| Část 3 (těžké sady jen nad generátorem: panely, navlek, regrese_*, luxy, zaslepky, razítka, délky panelů) | běžela na předchozí verzi kandidátu (generátorové soubory se od té doby nezměnily, jen komentář a ekvivalentní přepis kotvy v `stul_sse.py`): vše OK kromě `test_regrese_system30.py` (567/992) a `test_regrese_35_40_navlek.py` (1909/2048), které selhávají STEJNĚ i nad živým stavem (už existující selhání, s touto změnou nesouvisí) |
| Mutace (`mutace.py`, 39 mutací v 7 souborech `api/`) | **38 chyceno**, 1 zdůvodněně ekvivalentní (g04: redundantní podmínka SSE v hashi – SSE má `police_deska` po normalizaci vždy `True`; normalizaci hlídá mutace e01 a kontrola A7) |
| Kombinace se záplatami „horní police mezi stojkami“ (`scripts/2026-10-07_police_stojky`) | kotvy se aplikují v obou pořadích; jádrový test nad kombinací 68/69 – jediný rozdíl proti zlatému otisku je text montážního kroku 7 (`vypis`) z JEJICH záplaty, dily / klíče / spoje / ceny / kóty / 3D ovládání / hash shodné |
| `apply.sh` proti aktuálním živým souborům (kopie ve scratchpadu) | projde, výstup = kandidát (7/7 souborů shodných); druhé spuštění selže na kotvách a nic nezapíše |

## Co zůstává
* de / hu: chybí překlady `shelfboard`, `help_shelfboard`, DUVODY `shelfboard` a 4 položek 3D nabídky – záloha z angličtiny + varování v logu při startu (tok `docs/jazyky/README.md`, bot7 / bot16; `scripts/miniweb_jazyk_parita.py` je ohlásí).
* Prohlížeč: funkčnost ověřena (14/14), ale vzhled přepínače a 3D nabídky jsem očima neposuzoval (modul voleb vykreslí generický toggle, žádné nové CSS).
