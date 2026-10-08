# Systém 40 (profil SuperLight 40×40): druhý generátor stolu

bot10, 2026-10-04. Zadání Roberta: druhý generátor stolů s profily 40×40 vedle systému 30; **vnější rozměry stejné**, nohy dovnitř o 5 mm, konce/okraje/rohy přepočítat z 30 na 40;
tatáž konfigurace (stejné rozměry a volby) jde přepnout mezi systémy – jen základní konstrukce z profilů, co druhý systém nemá, se odebere; přepínat v maximální možné míře.

## STAV (2026-10-04): parametr `system` (30 | 40) je v generátoru, API i stránkách
**Generátor** (`api/stul_konfigurator.py`): parametr `system` (výchozí 30). Tabulka `SYSTEMY` drží profil (`Object_7` / `Object_11`), rohovou spojku (3158 / 3176), šablonu (`stul_sablona_577.json` /
`stul_sablona_system40.json`), záslepku a patku konců noh (3071, 3251 / 3091 „Záslepka 40x40 S10“, 3283 „patka M10“), zkrácení desek (0 / 10 mm), nejnižší polici nad podlahou (130 / 135),
výchozí polohu výřezu od přední hrany (100 / 110: závěsy police pod výřezem jsou ve 40 o 10 mm širší), odstup šuplíkového boxu od líce nohy (30 / 40: rohové spojky 3176 u středních noh sahají 57 mm
od osy nohy) a příznak `vzpery`. Aktivní systém drží kontext `_v_systemu(...)` (contextvars; nastavuje ho vstup – `sestav_stul`, `_sestav_jadro` – nebo `r["parametry"]["system"]` u funkcí nad výsledkem),
cenové a kusovníkové funkce poznají systém podle `part_id` (`PROFIL_PARTS`, `SPOJKY_PARTS`). Pravidla posunu `R` jsou v obou systémech STEJNÁ (lineární v hloubce, šířce, výšce), liší se šablona a konstanty
závislé na šířce profilu (polovina profilu `_H()`, rozteč polic, zkrácení desky police o P+1 z každé strany, nejkratší noha 2·P, mezera rámu police od pracovního rámu P+30).
**Systém 30 je beze změny**: `test_regrese_system30.py` (992 porovnání se starou verzí z gitu: díly, problémy, rozměry, meze, ovládání 3D, výrobní výpis, ceny položek, `odpoved()`) = bit po bitu stejné, hash konfigurace
30 se nemění (klíč `system` se z hashe 30 vynechává), token modelu 30 nemá klíč `y`.
**Šikmé vzpěry jsou i ve 40** (spojka 3220, SKU 2.2.006.4040.08): geometrie z vlastního tvaru č. 178 „Šikmá spojka 40 na profilu 40“ (Robert) a z meshe `product_3220.glb` (úhlová plocha y + z = 31,96, počátek spojky ve středu čelního čtverce, boční osa nativní Z, 0,1656 mm za koncem profilu, odstup středu konce od stěny 22,744 mm); `overeni_vzpery_40.py` porovnává generátor s tvary #580 (30) a #178 (40): shoda do 0,02 mm. Příznak `vzpery` v `SYSTEMY` zůstává pro případný další systém bez vzpěr (zapnutý `vzpery` se pak sám odebere s důvodem).
**Veřejné API** (`api/stul_shop.py`): systém je VLASTNOST PRODUKTU: `app_settings.configurator_products` = `{"4934": "stul_system30", "<id>": "stul_system40"}`; `system_pro_produkt(product_id)`; výběr zákazníka (rozměry,
volby) je v obou systémech stejný a přenositelný (neobsahuje pole `system`; pole `sys`/`system` ve výběru se ignoruje), schéma nese `system`, `profile` (`30x30` / `40x40`), `profile_mm` a `systems`
(`[{system, card_id, active}]`, karty obou systémů pro přepnutí téhož výběru, `active` = karta je v obchodě aktivní); token modelu nese `y: 40`; `pro_objednavku(selection, rules_version, lang, product_id=None, system=None)`
(košík předává `product_id`, takže systém určí karta, na kterou se kupuje). Staff trasa `/api/stul/konfigurace?system=40`.
**Stránky**: `webapp/stul-konfigurator.html` (Generátor stolu 01 systém 30) a `webapp/stul-konfigurator-40.html` (Generátor stolu 02 systém 40), obě nad `js/stul-host.js` (atribut `data-system` na `<html>`); karta 40
se najde ve `schema.systems`, takže stránka nemá pevné ID. Odkaz „Přepnout na systém …“ v záhlaví nese tentýž hash (tatáž konfigurace).
**Kategorie 311 „Robustní balicí stůl system 40“** (Robert 2026-10-04: „Bude nová kategorie…“): pod 182 vedle 206, adresa `/robustni-balici-stul-system-40`, kostru založil `zaloz_kategorii_system40.py` (náhled bez zápisu, `--apply` přes systemd-run,
idempotentní, adresa přes `_unique_category_slug(_slugify(název))` jako admin „Nová kategorie“), texty zapsal bot7 (`docs/kategorie_system40_texty_navrh.md`), generátor v kategorii připojuje `CATEGORY_GENERATORS[311]` v `webapp/category.html` (`{src, title, card}`; `card` = karta systému pro přepínač 30 ↔ 40)
(`/embed/stul.html?p=4954`). Test: `node scripts/2026-10-04_system40/test_kategorie_generator.js` (živé stránky 311, 206 a 183, jen čtení; 21 kontrol).
**Karta 40**: `zaloz_kartu_system40.py` (nahled bez zápisu; `--apply` přes systemd-run založí NEAKTIVNÍ kartu `STUL.SYSTEM40.KONF` a doplní `configurator_products`; zapíše se jen po Robertově pokynu, API pro recept 40 naběhne
až po nasazení kódu ve 12:30 / 3:30).

## Testy
- Sady `scripts/2026-10-02_stul_testy/` (bot8) jsou obecné pro oba systémy (profil, spojky, zkrácení podle `S.SYSTEMY`); nad systémem 40 se pouští `api/venv/bin/python scripts/2026-10-04_system40/spust_v_systemu.py 40 <test.py>`
  (nastaví výchozí systém a kontext). Zelené pro 40: zive, zive_vyska, ovladani, vyroba, podpery, suplik_meze, vyrez_police, loz, police_vysky, strany_pet, pet_umisteni; pro 30 všech 19 sad (`run_all.sh`).
  Sady s čísly šablony #577 (zlatý test, `test_stul_konfigurator.py` od části „3) pravidla“; první část = nezávislé ověření napojení 378×3 konfigurací je zelená i pro 40) a obálky v `test_stul_glb.py` jsou jen pro 30.
- `test_regrese_system30.py [git-revize]`: systém 30 proti verzi před zavedením systému.
- `test_prejimka_system40.py`: `sestav_stul(system=40)` = odvozená šablona, bez problémů.
- `test_shop_system40.py` (přes systemd-run, viz hlavička): veřejné API, košík `pro_objednavku`, token, GLB, výrobní sestava a list, staff trasy, 3D ovládání, vzpěry; 83 kontrol.
- `overeni_vzpery_40.py`: geometrie šikmých spojek vs vlastní tvary #580 / #178 v DB (jen čtení).
- `test_stul_host_40.js` (přes most `_most_stul.py` s `PID40`): stránky 01 a 02, přepínání téhož výběru (vzpěry zůstanou), starší odkaz se střední nohou.

## Otevřené (rozhodnutí / ověření mimo mě)
- Šroub ke šikmé spojce 3220: zápustný imbus M6, délku a SKU určí Robert (řádek v kusovníku bez karty a ceny, jako u 3254), matice do drážky 10 (2.1.001.10.06).
- Šroub ke spojce 3176: návrh M6×16 (4945, 2.1.21.0616); ověřit u karty spojky. Otočná matice do drážky 10 (3582, 2.1.001.10.06).
- Uchycení držáku PET, LED, elektrožlabu a panelů do drážky 10, kolečka na spodku nohy 40×40: geometrie jsou odvozené, fyzické uchycení ne (v kusovníku jen spojky).
- Patka M10 (3283): zasunutí závitu do nohy 30 mm je odhad (jako u M8); záslepka 3091 má přírubu 3,3 mm (změřeno v GLB).
- Texty šuplíků ve veřejném API: pro 30 zůstávají staré (620 / 700 mm; skutečně dnes 650 / 690), pro 40 počítá prahy generátor (`_prahy_suplik`).
- Zákaznický přepínač 30 ↔ 40 je HOTOVÝ a živý (bot16, Robert 2026-10-05 „přepínač dáme klientovi“, commit e5d5a493): modul voleb `ctx.systemSwitch` (jen když `schema.systems` má 2+ aktivní karty), hash `#v=`, vložený generátor, karta mini-shopu (jen když má obchod veřejně oba produkty) a kategorie 206/311 (`CATEGORY_GENERATORS[id].card`, zpráva `stul-embed-switch-system`, vybere se bere s sebou); nová kategorie systému = přidat `card` v `webapp/category.html`. Popis a testy: `docs/EMBED_STUL.md`, sekce „Přepínač systému 30 ↔ 40“.

---
# Podklady (původní zadání pro bot8)

bot10, 2026-10-04. Zadání Roberta: druhý generátor stolů s profily 40×40 vedle systému 30; **vnější rozměry stejné**, nohy dovnitř o 5 mm, konce/okraje/rohy přepočítat z 30 na 40;
přepnutí mezi generátory jen pro základní konstrukci z profilů (další prvky nebudou vždy kompatibilní); přepínat v maximální možné míře.

## Soubory
- `odvod_sablony_40.py` → `vystup/stul_sablona_system40.json` (stejný formát jako `api/stul_sablona_577.json`, 50 dílů, stejné `lic_peers`/`attached_to`) a `vystup/zmeny_30_na_40.json` (tabulka změn po dílech).
- `overeni_sablony_40.py`: nezávislé ověření (obálka, kontakty, zanoření spojek do materiálu profilu, topologie), **VSE OK**; negativní kontrola citlivosti testu zanoření prošla (posun spojky o 4 mm = zanoření 4 mm).
- `sestav_glb_sablony.py 30|40 out.glb`: složí šablonu do GLB pro náhled (snímek přes `scripts/2026-10-03_snimek_modelu.js`).
- `_spolecne.py`: načítání GLB a šablony.

## 1) Odvozená šablona (P = 40, P/2 = 20, D = 5)
Čísla jsou odvozená z měřených souřadnic šablony 30, ne od oka:
- Vnější plochy noh zůstávají (X −141,5 / 658,5, Z −422,4 / 777,6, spodek 101,5 / vrch zadních noh 1894,5): osy noh a příček v rovinách noh se posunou dovnitř o **5 mm** (přední X −126,48 → −121,48; zadní 643,52 → 638,52; Z −407,37 → −402,37 a 762,63 → 757,63).
- Nosné plochy zůstávají: horní plocha horního rámu (821,5) a rámu police (345,2); osa horního rámu y 806,54 → **801,54** (−5), rámu police 330,2 → **325,2** (−5); ramena a příčka LED leží na koncích zadních noh (1894,5): osa 1909,5 → **1914,5** (+5), celková výška +10 (horní plocha ramen LED).
- Délky: příčky 740 → **720** (rozteč os − 40), 1140 → **1120**, nohy beze změny (720 a 1793), příčka LED 1200 (mezi vnějšími plochami) beze změny, ramena LED 560 beze změny (přední konec zůstává, příčka LED se posune dopředu o 5: osa x 83,5 → 78,5).
- Příslušenství drží svůj dotykový povrch: pracovní deska a deska police se zkrátí o **10 mm** (zadní hrana na líci zadních noh 618,5; přední hrana a šířka stejné), šuplíkový box −10 mm ve výšce (visí na spodku rámu), perfopanely a elektrožlab −10 mm v X (líc zadních noh), LED −5 mm v X (visí pod příčkou LED), PET držák +5 X a +10 Z (vnitřní líc přední levé nohy), kolečka drží osy noh. Podrobnosti po dílech: `vystup/zmeny_30_na_40.json`.

## 2) Rohová spojka 3176 vůči uzlu spoje
Obě spojky jsou L-profily z plechu: vnější plochy ramen leží na plochách dvou profilů (rohová hrana = průsečík dvou lícních rovin), šířka je vystředěná na osy, jazýčky jsou v hrdle drážky. 3158: plechy 4 mm, rameno 27, šířka 27, rohová hrana v místních (0; 0,86; šířka/2 = 13,5), počátek modelu u rohu. 3176: plechy 7,25 mm, rameno 37, šířka 37, rohová hrana v místních (0; −37; 18,5), počátek modelu na konci ramene A. Otočení (quaternion) beze změny proti 3158.
**Odsazení pivotu od uzlu (průsečík os), |složky| v mm, znaménka stejná jako u 3158:** systém 30 = (15, 14,14, 13,5) v pořadí podle spoje, systém 40 = **(20, 57,0, 18,5)**: 20 = P/2 (líc profilu), 18,5 = polovina šířky spojky, 57,0 = 20 + 37 (počátek 3176 leží u konce ramene, ne u rohu). U každé spojky jsou obě odsazení (30 i 40) v `vystup/zmeny_30_na_40.json` (`spojky[].offset_pivotu_od_uzlu_30/_40`). Ověřeno na všech 20 spojkách: odsazení rohové hrany od uzlu je vždy (±15, ±15, 0) v osách spoje.

## 3) Šikmá spojka 3220 (vzpěry): ZATÍM NEDODÁNO
Vzpěry jsou volitelný prvek, ne základní konstrukce (Robert: přepnutí jen pro základní konstrukci). Analýzu 3220 podle 3254 (stejná metoda jako u 3176) udělám, až to bude potřeba; do té doby v systému 40 vzpěry vypnout/nepodporovat.

## 4) Mapování katalogových karet 30 → 40
| díl | systém 30 | systém 40 |
|---|---|---|
| profil ve scéně | `Object_7` (30×30, SKU 1.1.08.030030.03, produkt 3457) | `Object_11` (SuperLight S10, SKU 1.1.10.040040.03, produkt 3468; 40×40, délka 1000 v ose Y) |
| rohová spojka | 3158 (2.2.001.08.3030.33) | 3176 (2.2.001.10.4040.33) |
| šikmá spojka | 3254 (2.2.001.08.3030.06) | 3220 (2.2.006.4040.08), zatím nepodporováno |
| otočná matice ke spojce | 3579 (2.1.001.08.06, drážka 8) | 3582 (2.1.001.10.06, drážka 10) |
| šroub ke spojce | 4944 (2.1.21.0612, imbus válcová M6×12) | **návrh M6×16 = 4945 (2.1.21.0616)**: plech 7,25 místo 4 mm = o 3,25 mm víc; délku ověřit u karty spojky |
Beze změny: kolečko 4916, laminodeska 4933, panel 4931, šuplíkový box 4930, LED 4929, elektrožlab 4932, PET držák 4928.

## 5) Co ve 40 potřebuje jinou geometrii nebo ověření (nevyřešeno, ne moje data)
Nevyřešeno a k ověření (Robert / karty): držák PET 4928 (klip na 30 mm profil, jak se chová na 40), uchycení LED, elektrožlabu a panelů do drážky (matice a šrouby do drážky 10 místo 8, v kusovníku zatím jen spojky), upevnění koleček na spodek nohy 40×40. `attached_to` (`child_conn`/`parent_conn`) a `used_conn` jsem u spojek opsal ze šablony 30: indexy spojovacích bodů pro 3176 a Object_11 ve Scéně nejsou ověřené (polohy dílů jsou explicitní, takže vložení do Scény je správné, jen případné další „přichycení“ ve Scéně).
