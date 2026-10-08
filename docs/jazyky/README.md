# Jazykové sady serveru: jak přidat další jazyk (de, hu, pl …)

Robert 2026-10-07: dokončit mini-shop anglicky 1:1 se slovenským a vytvořit kopie v němčině a maďarštině. Tenhle dokument popisuje **serverovou část**
(texty, které zákazníkovi vydává API, ne statické stránky mini-shopu). Doména, nginx, shop v DB a spuštění: `docs/MINISHOP_NOVY_JAZYK.md`.
Postup je pro každý jazyk **stejný**; dnes jsou připravené **de** a **hu**, další jazyk (pl, ro, hr, sl, it, fr, es, nl) potřebuje jen řádek v tabulce abeced (viz níže).

## Co jsou jazykové sady
Zákaznické texty, které vydává server – štítky a nápověda voleb konfigurátoru stolu, důvody „proč to nejde“, informační věty s počtem kusů, popisky ovládání
ve 3D, štítky dopravy v košíku – jsou pro **cs / en / sk natvrdo v kódu** (`api/stul_shop.py`, `stul_shop_sse.py`, `stul_ovladani_verejne.py`,
`miniweb_objednavky.py`, `miniweb.py`) a tam **zůstávají beze změny** (pro tyhle tři jazyky se sada nikdy nečte).
Každý další jazyk je **jeden datový soubor** `api/jazyky/<jazyk>.json`; kód ho na startu aplikace přidá do stejných slovníků. Bez zásahu do kódu.

| Jazyk | Kód | Stav | Plurál | Povolená písmena (nad ASCII) |
|---|---|---|---|---|
| čeština, slovenština, angličtina | cs sk en | v kódu | cs/sk: one, few, other · en: one, other | cs `áčďéěíňóřšťúůýž`, sk `áäčďéíĺľňóôŕšťúýž`, en žádná |
| němčina | de | soubory pro bot7 v `docs/jazyky/de/` | one, other | `äöüÄÖÜß` |
| maďarština | hu | soubory pro bot7 v `docs/jazyky/hu/` | jen **other** (`one` volitelné) | `áéíóöőúüűÁÉÍÓÖŐÚÜŰ` |
| polština, rumunština, chorvatština, slovinština, italština, francouzština, španělština, nizozemština | pl ro hr sl it fr es nl | abeceda a plurál předdefinované | podle jazyka | viz `ABECEDY` v `api/jazyky.py` |

**Tabulka abeced, pravidel plurálu a názvů jazyků je na JEDNOM místě: `api/jazyky.py` (`ABECEDY`, `PLURAL_PRO_JAZYK`, `NAZVY_JAZYKU`).** Nový jazyk mimo tabulku = tři řádky tam
(nástroje bez řádku odmítnou jazyk s hláškou „doplňte řádek do ABECEDY“). Každý jazyk smí navíc ASCII a obecnou typografii (`× – — − … „ “ ° € ·`).

## Postup (stejný pro každý jazyk; příkazy z kořene repa)
1. **Zdroj** – nástroj vytáhne z kódu všechny řetězce a vytvoří soubory k vyplnění (čte jen kód, do DB nic nezapisuje; potřebuje `api/.env`):
   ```
   api/venv/bin/python3 scripts/miniweb_jazyk_zdroj.py --lang de        # → docs/jazyky/de/01_… 05_*.json
   api/venv/bin/python3 scripts/miniweb_jazyk_zdroj.py --lang hu        # → docs/jazyky/hu/
   ```
   Když `.env` nejde přečíst: `systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator /opt/konfigurator/api/venv/bin/python3 scripts/miniweb_jazyk_zdroj.py --lang de`.
   Opakované spuštění je bezpečné: vyplněné hodnoty zůstanou, přidají se jen nové řetězce z kódu (prázdné); id, která už v kódu nejsou, se vypíšou jako zastaralá.
2. **Vyplnění (bot7)** – v každé položce `polozky` vyplnit pole `<jazyk>` (prostý JSON; pravidla níže). Zdroj je `cs` / `en` / `sk` v téže položce.
3. **Kontrola a sestavení** – bez `--apply` je to jen kontrola (nic se nezapíše), s `--apply` a bez chyb vznikne `api/jazyky/<jazyk>.json`:
   ```
   api/venv/bin/python3 scripts/miniweb_jazyk_sestav.py --lang de
   api/venv/bin/python3 scripts/miniweb_jazyk_sestav.py --lang de --apply
   ```
   Exit 0 = v pořádku, 1 = chyby (vypsané s id položky), 2 = špatné použití. `--json` dá strojový výstup.
4. **Commit** souborů `docs/jazyky/<jazyk>/` a `api/jazyky/<jazyk>.json` (JSON není guardovaný soubor, zámek nepotřebuje).
5. **Nasazení**: sada se načte při startu API (plánovaný HUP 0:00 / 12:30, ručně se nerestartuje). ⚠ Viz past 1 – samotný commit JSON plánované nasazení zatím nespustí.
6. **Úplnost napříč vrstvami** (jen čtení, DB jen SELECT):
   ```
   api/venv/bin/python3 scripts/miniweb_jazyk_parita.py --lang de --ref sk
   ```
   Tabulka `vrstva / stav / kontrola`; stav `MEZERA` = něco chybí (exit 1), `INFO` = jen poznámka. Vrstvy: **server** (sada vs. kód), **i18n** (`webapp/miniweb/i18n/<jazyk>.json` vs. `<ref>.json`: klíče, `{placeholdery}`, prázdné texty, abeceda, značka),
   **seo** (sekce v `api/miniweb_seo_sablony.json` rekurzivně, `PATHS`), **db** (schválené texty kategorií a produktů, povinná pole vč. `url_slug`, právní dokumenty, storefront a řádek shopu), **pripni** (`webapp/pripni-cokoli/texty.json`: klíče, `_aktivni`).
   `--bez-db` vrstvu DB přeskočí, `--json` dá strojový výstup.
7. **Spuštění shopu**: `scripts/miniweb_shop.py --slug packstations-<jazyk> --go-live` (kontroluje, že soubor `api/jazyky/<jazyk>.json` existuje; **úplnost** ověř krokem 6).

## Soubory pro bot7 (`docs/jazyky/<jazyk>/`)
| Soubor | Položek | Co to je |
|---|---|---|
| `01_stul_texty.json` | 106 | štítky a nápověda voleb konfigurátoru stolu (99) + texty SSE stolu (7) |
| `02_stul_zpravy.json` | 65 | důvody „proč volba nejde“ (28), hlášky (14), názvy dílů ve větách (15), texty tlačítek (5), důvod šuplíků SSE (1), ano / ne (2) |
| `03_stul_info_sablony.json` | 10 | informační věty s počtem kusů jako ŠABLONY (3 s tvary podle počtu) |
| `04_ovladani.json` | 140 | popisky ovládání ve 3D náhledu („Výška desky“, „Přidat výřez sem“ …); klíč je česká šablona |
| `05_objednavky.json` | 5 | štítky dopravy v košíku (3) + volitelné potvrzení poptávky (2) |
| **celkem** | **326** | z toho 3 plurálové, 34 s placeholdery |

Položka:
```json
{"id": "stul_shop.TEXTY_AKCI.roztahnout_h", "poznamka": "text tlačítka / předpona nabídky", "typ": "text",
 "placeholdery": ["{v}"], "cs": "Zvýšit zadní stojky na {v} mm a zapnout", "en": "Raise the rear uprights to {v} mm and switch on",
 "sk": "Zvýšiť zadné stojky na {v} mm a zapnúť", "de": ""}
```
Plurálová položka (`"typ": "plural"`) má pole jazyka jako **objekt s tvary** – podle jazyka `one`, `other` (de), jen `other` (hu), `one`, `few`, `many`, `other` (pl):
```json
{"id": "stul_shop.info.podpery.s_u1", "typ": "plural", "placeholdery": ["{n}"], "en": {"one": " and {n} supporting profile is added under it.", "other": "…"}, "de": {"one": "", "other": ""}}
```
Server si tvar vybere podle počtu (1 → `one`, jinak `other`; hu vždy `other`). Položky s `"volitelne": true` (potvrzení poptávky, zatím vypnuté) smí zůstat prázdné, předmět a tělo se ale vyplňují **společně**.

## Pravidla textů (kontroluje `miniweb_jazyk_sestav.py`; chyba = sada se nezapíše)
1. **Vyplněno** (žádná prázdná položka mimo volitelných), žádné `TODO` / `???`, žádné HTML.
2. **Placeholdery** `{n} {d} {w} {h} {u} {k} {v} {t1} {t2} {prah} {mezera} {name} {site}` přesně jako v poli `placeholdery` (pořadí ve větě lze změnit). V tvaru `one` smí chybět jen `{n}` („ein Profil“). Text musí být **platná šablona**: žádná osamocená `{` nebo `}`, ani `{{n}}`, `{n:05d}`, `{0}` – server by za běhu spadl na `.format()`.
3. **Abeceda jazyka**: každý znak mimo ASCII, obecnou typografii a písmena jazyka je chyba – např. česká a slovenská písmena `ě š č ř ž ý ů ť ď ň ľ ĺ ŕ ô` v němčině a maďarštině, v němčině i `á í é ú`; legitimní maďarská `á é í ó ö ő ú ü ű` projdou.
4. **Žádná značka ani interní slova**: Logiman, konfigurátor / **Konfigurator (i německy)**, vandrawee (stejná pravidla jako `BRAND_RE` v `scripts/miniweb_domena.py`).
5. **Mezery, středník a tečka na začátku a na konci** stejně jako v angličtině – informační šablony navazují na `zaklad`.
6. Rozumná délka (do 3× anglický text + 60 znaků). **Varování** (nezastaví): shodné s angličtinou / češtinou u delšího textu, dvojitá mezera.
7. Terminologie jednotně v celém shopu (i18n, SEO, katalog); drážka profilu = v angličtině „slot“, ekvivalent v jazyce určuje bot7. Prodej jen firmám (B2B), bez značky.

## Jak server sadu používá a co dělá, když něco chybí
- **Chybějící položka v sadě** → anglický text + jednorázové varování do logu API (`jazyky: …`), nikdy 500 ani KeyError. Je to jen pojistka: úplnost hlídají `sestav` (neúplnou sadu nevydá) a `parita`.
- **Vadná sada** (neplatný JSON, jiné `lang` než název souboru, špatné typy, sada pro cs/en/sk) → sada se ignoruje + varování; aplikace naběhne. **Vadná šablona** v jedné hodnotě (osamocená `{ }`, neznámé pole `{x}`, `{n:05d}`) → jen ta hodnota se nahradí anglickou zálohou (+ varování). Jazyk se připojuje atomicky; neočekávaná chyba jednoho jazyka ho v daném modulu vynechá, nikdy neshodí aplikaci ani cs / en / sk.
- **Jazyk bez sady**: API ho nezná; `_lang()` vezme hlavičku `Accept-Language` nebo **češtinu**. Zákazník by u německého shopu viděl česká tlačítka – proto jazykové kontroly před spuštěním shopu.
- Sada se čte **při startu** (import modulů). Přepsání souboru bez reloadu se neprojeví. Adresář lze přepsat env `JAZYKY_DIR` (testy).

## Testy
`api/venv/bin/python3 scripts/2026-10-07_jazyky_testy/test_jazyky.py` (~4 min, 97 kontrol, žádné zápisy do DB; čte jen `app_settings`). Pokrývá: pravidla plurálu, abecedy (de / hu / syntetický jazyk s diakritikou; **mutace: české písmeno v de a hu spadne, maďarské ő ű v hu projde**),
nástroje zdroj / sestav / parita (mutace polí), syntetickou sadu `xx` v kódu (schémata všech systémů, `resolve`, informační věty, ovládání, SSE, košík, skutečné trasy), neúplnou a vadnou sadu a **neměnnost cs / en / sk** (otisk výstupů s prázdným adresářem sad a se sadou se musí rovnat).

## Kdo co dělá
| Krok | Kdo |
|---|---|
| Vyplnění souborů `docs/jazyky/<jazyk>/` (a všechny ostatní zákaznické texty jazyka) | **bot7** |
| Nástroje, kód, testy, cesty URL, doména, nginx, kontrola úplnosti | **bot16** |
| Řádek shopu v DB, import katalogu a dokumentů (drafty), `orders_enabled` | **bot5** |
| Schválení textů (`/miniweb-schvaleni.html`) a root příkazy | **Robert** (koordinuje bot9) |

## Pasti
1. **Samotný commit `api/jazyky/<jazyk>.json` plánované nasazení nespustí**: `scripts/nasazeni.py` sleduje jen commity do `api/*.py` (`PATHSPEC_API = ":(glob)api/*.py"`) a „od startu workerů žádný commit“ = „nic nasazovat“. Řešení = rozšířit `PATHSPEC_API` o `:(glob)api/jazyky/*.json` (dva řádky v `nasazeni.py`, řeší bot16); do té doby sada naběhne až s nejbližším nasazením nějaké změny v `api/*.py` (`scripts/nasazeni.py --stav` ukáže, co čeká). Ručně se nerestartuje (WORKFLOW).
2. **Změna české šablony v kódu** (např. přejmenování popisku ovládání) udělá z odpovídající položky sady zastaralou – `zdroj` ji vypíše, `parita` ukáže „položky mimo kód“ a v sadě chybí nová → anglická záloha. Po změně textů v kódu vždy znovu `zdroj` + doplnit.
3. `miniweb_shop.py --go-live` u sady ověřuje jen **existenci souboru**; kompletnost je věc `parita` (vrstva server).
4. U slovenštiny je hodnota ano / ne v souhrnu voleb dnes `yes` / `no` (stav kódu, neměnit); nové jazyky mají vlastní slova (`ano_ne.ano`, `ano_ne.ne`).
5. Nový jazyk ve frontendu (`webapp/miniweb/i18n/<jazyk>.json`, SEO šablony, `PATHS`) je samostatná práce – serverová sada ji nenahrazuje; stav ukáže `miniweb_jazyk_parita.py`.
