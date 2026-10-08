# Generátor válečkových dopravníků – návrh a rozdělení práce

Zadání: Robert 2026-10-07 („začneme řešit vlastní 3D modely dopravníků, chceme nyní generátor dopravníků, ať je můžeme ukazovat ve 3D online nabídce jako ostatní produkty“).
Vedení: bot5 (bot9 určil 2026-10-07). Stránka s obrázky voleb, kterou Robert viděl: https://claude.ai/artifact/9PJu66oijj9qFsZ68pnD9s

## 1. Co Robert rozhodl (kliky 2026-10-07)

| Otázka | Odpověď |
|---|---|
| Rozsah první verze | Rovný válečkový dopravník + boční vodítka (zatáčky a kuličkové stoly až potom) |
| Délky | 1 až 6 m po 100 mm |
| Co volí zákazník | délka, hustota válečků, typ válečku a šířka, počet noh (4/6/8), spodní rám, výška |
| Kdo ho uvidí | Hned veřejně (generátor na kartě; aktivace karty = Robertův pokyn, pravidlo 54) |

## 2. Výběr zákazníka (`selection`, klíče krátce anglicky jako u stolu)

| klíč | typ | hodnoty | výchozí | poznámka |
|---|---|---|---|---|
| `rtype` | select | `alu` (hliník Ø50 hladký), `knurl` (hliník Ø50 vroubkovaný), `steel` (ocel Ø51) | `alu` | určuje profil: Ø50 → 23×75, Ø51 → 23×127 |
| `width` | select | délka válečku mm: alu a knurl 290/440/590/790, steel 290/440/590/790/990 | 590 | skutečné délky válečků; po přepnutí typu se neplatná šířka posune na nejbližší platnou s upozorněním |
| `len` | slider | 1000–6000, krok 100 | 2000 | délka dopravníku (délka bočního profilu) |
| `pitch` | slider | rozteč válečků mm, 75–300 po 25 | 150 | Robert 2026-10-07: plynule 75 až 300 mm po 25 mm |
| `h` | slider | výška mm, 570–870 po 10 | 800 | Robert 2026-10-07: celý rozsah noh. Nohy jsou teleskopické: 23×75 noha 530–875 mm, 23×127 noha 570–870 mm (karty #5297, #5298); „výška“ = horní hrana válečků nad podlahou |
| `legs` | select | `auto`, `4`, `6`, `8` | `auto` | auto = 4 noh do 3 m, 6 noh do 6 m (potvrzený recept); nejméně nohou podle rozpětí max. 3 m (dvojic ≥ 2, nad 3 m ≥ 3); méně než minimum se zvedne na minimum s upozorněním |
| `frame` | select | `full` (příčka na každý pár + 1 podélná), `cross` (jen příčky), `none` | `full` | spodní H-rám z profilu 40×40 |
| `guide` | select | `none`, `left`, `right`, `both` | `none` | boční vodítka |
| `guidetype` | select | `40`, `60` | `40` | profil vodítka 1.2.00.017040.00 / 1.2.00.016060.00 (+ plastová lišta, krytky); **Robert 2026-10-07: nejdřív zjistit u dodavatele, jak se vodítko drží na rámu** (v katalogu žádný držák není); vodítka se do generátoru zapnou až s jasným dílem, první verze je bez nich |

## 3. Kusovník a cena (hotová logika)

Recept: `docs/dopravniky_recept.json` (verze v1-potvrzeno-2026-10-07), výpočet `scripts/dopravniky_cena_z_komponent.py` (`kusovnik`, `cena_czk`).
Váleček: počet = `len // pitch`; 2 boční profily (2 × len); nohy + patky; H-rám: příček = dvojic noh × šířka, podélná = len − 0,2 m, 4 úchyty na dvojici.
Cena = ceil(součet(USD dílu × množství) × kurz × koeficient kategorie 1,2 × (1 + přirážka 10 %)); USD, kurz z karet dílů (`dogus_list_price_usd`, `dogus_price_rate_used`), takže generátor a karty hotových dopravníků dávají stejnou cenu. Cena bez DPH, celé Kč.
Kontrola: generátor pro (steel, 590, 2000 mm, pitch 150, auto, full) = 16 828 Kč (karta #5228).
Vodítka v ceně: profil délky `len` + plastová lišta délky `len` + 2 krytky na vodítko (doladí se po vyjasnění držáků).

## 4. Moduly a kdo je dělá (řez jako u stolu: konfigurátor → shop → GLB)

| Co | Soubor | Kdo |
|---|---|---|
| Čistá funkce parametry → normalizace, limity (nohy, výšky, šířky podle typu), seznam dílů s množstvím a polohami, upozornění | `api/dopravnik_konfigurator.py`: `sestav_dopravnik(**p)` → `{"parametry": efektivní, "dily": [{sku, nazev, mnozstvi, jednotka ("ks"/"m"), poloha...}], "upozorneni": [{id, ...}]}`, konstanty `ROZSAH`, `TYPY`, `SIRKY_PODLE_TYPU` (jako `stul_konfigurator`) | bot8 |
| GLB: katalogové GLB dílů usadit podle poloh, spojit, hash, razítka | `api/dopravnik_glb.py`: `model_pro_parametry(parametry, razitka=True) -> (hash, glb_bytes)` (razítka loga jsou VÝCHOZÍ na všech modelech generátorů – WORKFLOW pravidlo 61, Robert 2026-10-08; GLB nese razítka od prvního náhledu, `razitka=False` jen vyslovně), `RULES_VERSION` | bot10 |
| Shop: schéma (texty cs/en/sk), `resolve`, cena a kusovník z `dily`, `pro_objednavku`, `glb_bytes`, `konfigurovatelny` | `api/dopravnik_shop.py` (stejné rozhraní jako `stul_shop`) | bot5 |
| Rozcestník „který modul patří produktu“ pro trasy, košík a nabídku | `api/konfigurator_registr.py`, delegace v trasách `stul_shop.py` (bot8 souhlasil 2026-10-07, stolová větev beze změny) | bot5 |
| Nabídka z konfigurace, košík, objednávka | `nabidka_z_konfigurace.py`, `konfigurace_kosik.py` přes rozcestník | bot5 |
| UI, interní stránka, tlačítko Do online nabídky, texty SK/DE/HU | schématem řízené `product-configurator.js` + stránka generátoru | bot16 (texty bot7) |

Cena v `dopravnik_shop` se bere z `dily` podle SKU (USD, kurz a koeficient z karet dílů). Referenční výpočet množství, který `dily` musí dát pro hotové dopravníky: `scripts/dopravniky_cena_z_komponent.py` (`kusovnik`); test: generátor pro parametry odvozené z SKU hotové karty = cena karty (78 karet).
`parametry` pro GLB = efektivní hodnoty po normalizaci: `{rtype, width, len, pitch, h, legs (4|6|8), frame, guide, guidetype}`; jednotky mm, osa podél délky odpovídá `len`. Díly modelu: boční profily 23×75 / 23×127, válečky v roztečích `pitch`, teleskopické nohy s patkami, H-rám z profilu 40×40 s úchyty, vodítka.
Dogus STEP/CAD existuje u dílů (válečky, nohy, spojovací desky, kola, kuličkové jednotky), u hotových dopravníků ne.

## 5. Otevřené

1. Držák bočního vodítka: zjistit u dodavatele (na to čeká zapnutí vodítek, ne zbytek generátoru).
2. Minimální počet noh podle délky (rozpětí max. 3 m) a rozsah výšky 570–870 mm jsou odvozeny z receptu a z karet noh, ne od Roberta; při změně napsat do tohoto souboru.
