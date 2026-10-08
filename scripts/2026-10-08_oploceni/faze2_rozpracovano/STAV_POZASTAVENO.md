# Fáze 2 generátoru „ochranný kryt a oplocení“ – POZASTAVENO (bot8 fork, 2026-10-08 ~11:15)

Důvod: koordinátor – Robert oplocení zatím NESCHVÁLIL a musí dodat informace / požadavky. Po jeho informacích koordinátor fork znovu rozjede zprávou.
Všechno je jen v mé kopii `$SP/oploceni/f2/` (`export SP=/tmp/claude-0/-opt-konfigurator/5fc47cb9-8166-4280-8938-fb90e89ba54c/scratchpad`). Do /opt/konfigurator nic z fáze 2 zapsáno není.

## 0) Ověřeno při pozastavení (11:10–11:15)
* `/opt/konfigurator`: neexistuje `api/oploceni_*.py`, `webapp/oploceni-konfigurator.html`, `webapp/js/oploceni-host.js`, `docs/KONTRAKT_OPLOCENI.md`; v `api/konfigurator_registr.py`, `stul_shop.py`, `konfigurace_kosik.py`, `nabidka_z_konfigurace.py`, `MAPA_3D_A_GENERATORU.md`, `docs/KONTRAKT_KONFIGURATOR_UI.md` nejsou žádné moje značky (`modul_pro`, `recepty/<recept>`, `rozmery_text`, `mimo_stul`, `KONTRAKT_OPLOCENI` = 0 výskytů); `git status` složky `scripts/2026-10-08_oploceni` je čistý (= commit 01a0b56b, fáze 1); `DEPLOY_LOCK.json` volný, `lock.sh` jsem nevolal. Jediný zbytek z fáze 2 v živém stromu: 4 osiřelé soubory bytecode `api/__pycache__/oploceni_*.cpython-312.pyc` (vznikly `py_compile` přes symlinkovaný `__pycache__` kandidáta; gitignore) – **SMAZÁNY**, `prepare_cand_f2.sh` / `apply_f2.sh` / `mutace_oploceni.py` opraveny, aby `__pycache__` do farmy symlinků nebrali.
* DB: jen SELECT a SHOW COLUMNS (testy, dry-run skriptů karet), žádný zápis; falešná DB v `test_oploceni_karty.py` je v paměti.
* Procesy: mutační běh (systemd jednotka `run-u21644.service`, hlavní PID 2592862 + 4 testovací potomci) zastaven `systemctl stop` té jedné jednotky (žádný pkill), dočasné `/tmp/mut_oploceni_*` smazány; žádný Chromium ani test neběží.

## 1) Co je hotovo (zdroje ve `$SP/oploceni/f2/skripty/`, kandidát ve `$SP/oploceni/f2/cand`)
| oblast | soubory | stav |
|---|---|---|
| jádro + 3D + cena | `novy_api/oploceni_{konfigurator,glb,cena}.py` | hotovo (původně fáze 1, přesun do api/, nové helpery pro dveře / hmotnost, zjednodušení patky a zámku, karty výplní) |
| shop vrstva | `novy_api/oploceni_shop.py` | hotovo: schéma cs/en/sk (20 slotů), úprava výběru + `notices`, `price_delta`, staff blok, `pro_objednavku`, `glb_bytes`, token `opl.`, strop 600 dílů, meze 4000×4000×3000 |
| kotvené záplaty | `apply_patches_f2.py` | hotovo: `konfigurator_registr.py` (MODULY), `stul_shop.py` (delegace + staff routa `GET /api/shop/configurator/recepty/<recept>`), `konfigurace_kosik.py`, `nabidka_z_konfigurace.py` |
| stránka | `novy_webapp/oploceni-konfigurator.html`, `novy_webapp/js/oploceni-host.js`, `oploceni_verze.py` | hotovo (staff + `?public=1&id=`), layout opraven (okno „Výplň po stranách“ ve 3. sloupci, titulek okna, podnadpisy se schovávají se skupinou) |
| karty | `zaloz_kartu_oploceni.py`, `zaloz_karty_vyplni.py` (oba dry-run + implementovaný `--apply`, funkce `nacti_*` / `zapis` / `over_zapis`) | hotovo; dry-run ověřen nad živou DB (jen čtení); `--apply` ověřen jen proti falešné DB |
| dokumentace | `novy_docs/KONTRAKT_OPLOCENI.md`, `patch_docs_f2.py` (řádek do MAPA_3D, věta do KONTRAKT_UI, idempotentní) | hotovo (zkušebně aplikováno na kopii) |
| testy | `test_oploceni.py` (jádro + karty výplní v ceně, sekce L), `test_oploceni_shop.py` (A–M), `test_oploceni_karty.py` (falešná DB), `test_oploceni_stranka.js` + `_most_oploceni.py` (Chromium), `run_regrese.py` | hotovo |
| mutace | `mutace_oploceni.py` (367 mutací: jádro, GLB, cena, shop, záplaty, skripty karet; staví na `OPLOCENI_STOP_PRVNI`) | kotvy 367/367 v pořádku; běh PŘERUŠEN |
| obrázky | `img/stranka_{staff,verejna,mobil}.png` (po opravě layoutu, očima zatím nezkontrolované), `img/zj_*.png` (zjednodušení patky/zámku, zkontrolováno), `img2/*.png` (4 konfigurace z `render_oploceni.py`, nezkontrolované) | částečně |

Poslední výsledky nad kandidátem (živé soubory + moje záplaty): `test_oploceni.py` 625/625, `test_oploceni_shop.py` 151/151 (~70 s), `test_oploceni_karty.py` 42/42 hermeticky (44 kontrol s DB_* a porovnáním se živým schématem shop_products), stránka v Chromiu 49/49 (~6 min), registr 20/20 a dopravník 33/33 shodně s živým stromem (dřívější běh). Mutace: kotvy 367/367, přerušený běh 65 z 65 zachyceno, 0 přeživších (`mutace_vse_preruseno.log`; šlo o začátek seznamu – jádro n*/r*/d*).

## 2) Co zbývá
1. Regrese kandidát vs živý strom: `run_regrese.py` (kosik, nabidka, nabidka_backend, stul_shop, stul_api; registr + dopravník už byly shodné) – zatím NEPUŠTĚNO.
2. Celý běh mutací (≈302 zbývá; po prvním selhání testu se mutace zastaví, při zátěži serveru 1–2 h; přeživší mutace = doplnit test, ne kód).
3. `README_FAZE2.md` (nasazení, pořadí kroků), přepsat `README.md` (je ještě text fáze 1), `commit_f2.txt` (pathspec + zpráva) – **neexistují**; `apply_f2.sh` je vyžaduje v seznamu `SOUBORY_SCRIPTU` a bez nich skončí „ve zdrojích chybí“.
4. Vyzkoušet `apply_f2.sh` na scratch kořeni (kopie stromu s reálnými adresáři pro `api/`, `webapp/js`, `docs`, `scripts/2026-10-08_oploceni`; NE symlinkované adresáře – `cp --remove-destination` nesmí zapisovat do živých) a nejdřív `--jen-vypocet`; zatím NEVYZKOUŠENO.
5. Finální obrázky (stránka staff + veřejná s konfigurací jako na fotce) po schválení zadání a závěrečná zpráva.

## 3) Jak navázat (příkazy; vše bez zápisu do /opt/konfigurator)
```
export SP=/tmp/claude-0/-opt-konfigurator/5fc47cb9-8166-4280-8938-fb90e89ba54c/scratchpad
cd /opt/konfigurator
bash $SP/oploceni/f2/skripty/prepare_cand_f2.sh $SP/oploceni/f2/cand          # kandidat = zive api/webapp (symlinky) + moje zaplaty a nove soubory
C=$SP/oploceni/f2/cand/repo; PY=/opt/konfigurator/api/venv/bin/python3
SR="systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --setenv=PYTHONDONTWRITEBYTECODE=1 --working-directory=$C"
(cd $C && PYTHONDONTWRITEBYTECODE=1 $PY scripts/2026-10-08_oploceni/test_oploceni.py | tail -3)         # jadro, hermeticky ~15 s
(cd $C && PYTHONDONTWRITEBYTECODE=1 $PY scripts/2026-10-08_oploceni/test_oploceni_karty.py | tail -3)   # skripty karet, falesna DB
$SR $PY $C/scripts/2026-10-08_oploceni/test_oploceni_shop.py | tail -5                                  # shop vrstva, DB jen cte ~70 s
$SR --setenv=SNIMKY=$SP/oploceni/f2/img $PY $C/scripts/2026-10-08_oploceni/_most_oploceni.py $C/scripts/2026-10-08_oploceni/test_oploceni_stranka.js 9990   # Chromium ~6 min, internet pro three.js
$SR --setenv=OPLOCENI_API=$SP/oploceni/f2/cand/api $PY $C/scripts/2026-10-08_oploceni/mutace_oploceni.py [--jadro|--shop] [nazev ...]            # mutace
$SR $PY $C/scripts/2026-10-08_oploceni/run_regrese.py                                                  # regrese (viz hlavicka souboru; kandidat vs zivy)
```
Dlouhý běh se spouští jako pozadí (`run_in_background`) a zastavuje se JEN jeho jednotkou: `for p in $(pgrep -f "oploceni/mutace_oploceni.py"); do cat /proc/$p/cgroup; done` → `systemctl stop run-uNNNN.service` (nikdy pkill). Dočasné `/tmp/mut_oploceni_*` smazat přes python `shutil.rmtree`.

## 4) Co po změně zadání znovu pustit
| změna | upravit | znovu pustit |
|---|---|---|
| geometrie / pravidla jádra (pole, dveře, spojky, patky, výplň v drážce) | `novy_api/oploceni_konfigurator.py`; zvednout `VERZE_PRAVIDEL` + `RULES_VERSION` (shop) | `prepare_cand_f2.sh`; `test_oploceni.py` (přepsat zlaté `OTISKY` v sekci J), shop test, stránka, mutace (K, G), `render_oploceni.py` pro obrázky; doc `KONTRAKT_OPLOCENI.md` §2–3 |
| veřejné volby / meze / výchozí hodnoty / texty | `novy_api/oploceni_shop.py` (`VEREJNE_MEZE`, `VYCHOZI_VYBER`, `TEXTY`, `UPRAVA`, `INFO`) | shop test (A–D, L), stránka (A4 = počet slotů), mutace S; doc §2 |
| ceny, výplně, karty | `oploceni_konfigurator.VYPLNE` / `TESNENI_KARTY`, `novy_api/oploceni_cena.py`, `zaloz_karty_vyplni.py` (`KARTY`) | core test L, shop test M, `test_oploceni_karty.py`, mutace C a karty |
| stránka | `novy_webapp/oploceni-konfigurator.html`, `js/oploceni-host.js` | stránka v Chromiu; piny `?v=` se při apply spočítají sami (`oploceni_verze.py`) |
| produktová karta (SKU, název, popis) | konstanty v `zaloz_kartu_oploceni.py` | `test_oploceni_karty.py` |
| dotčené sdílené soubory (registr, košík, nabídka, routy) | `apply_patches_f2.py` (kotvy: každá právě 1×) | `prepare_cand_f2.sh` (kotvy selžou, když se živý soubor mezitím změnil), registr + dopravník + regrese |
| cokoli | – | před předáním `apply_f2.sh --jen-vypocet <scratch kořen>`, pak teprve ostrý `apply_f2.sh` pod zámkem koordinátora |

## 5) Výchozí rozhodnutí, která jsem zvolil jako NÁVRH (Robert je může změnit podle živé stránky)
Výplň v drážce s výřezy v rozích; dveře ven se 3 závěsy; meze polí 1200 / 1100 mm; 5 typů výplní (karty neaktivní); mezilehlé sloupky končí pod souvislou horní příčkou; patky volitelné (výchozí ne); veřejné meze 4000 × 4000 × 3000 mm (jádro umí 6000 × 6000), strop 600 dílů veřejného modelu; montáž se nenabízí; výplně do ceny jako virtuální desky s orientační cenou za m², dokud nevzniknou karty; karty výplní `visible_in_scene=1` + GLB (kvůli cenovému kontextu) = po zápisu se objeví i v katalogu Scény (stejně jako laminodesky) – rozhodnutí pro Roberta; kategorie karet výplní neurčena (návrh pod 149 / 150); norma ISO 14120 / 13857 jako upozornění „posuzuje projektant stroje“.
Poznámky: v katalogu chybí hmotnost dílu Pant 40×40 (pravý) → hmotnost v kusovníku „neúplná“; `pdc-layout.js` (sdílený, bot16) nechává viset podnadpis skupiny v okně `adv`, když je skupina prázdná – v hostu to řeší vlastní rozdělovač skupin, sdílený soubor jsem neměnil.
