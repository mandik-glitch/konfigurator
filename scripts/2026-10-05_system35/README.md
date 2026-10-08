# Generátor stolu 03 – systém 35 (profil 35×35)

Zadání (Robert 2026-10-05): „Postav další generátor stolu systém 35, samozřejmě kompatibilní s předešlými 30/40.“ Na dotaz, čím nahradit díly, které pro 35×35 v katalogu nejsou
(rohová spojka, patka, šikmá spojka): **„Používají se spojky systému 30, vystředit vždy na střed drážky.“** Stejná konfigurace (rozměry, volby) jde přepnout mezi systémy 30 / 35 / 40
(systém je vlastnost produktu, `schema.systems` nese 3 karty, přepínač zákazníka dělá modul voleb – bot16 – sám pro všechny aktivní systémy).

## Díly systému 35
| role | díl | poznámka |
|---|---|---|
| profil | `profil_35x35` (cfg_dily, GLB `profil_35x35.glb`, produkt 3469, SKU 1.1.08.035035.02) | drážka 8, 35×35 |
| rohová spojka | `product_3158` (ze systému 30) | desky spojky leží na lících profilu (±17,5 mm od uzlu), šířka 27 mm vystředěná na osu = střed drážky |
| záslepka | `product_3090` (35×35, příruba 3,3 mm) | |
| patka | `product_3251` (M8, ze systému 30) | odhad: M8 v profilu 35 (jinak M10 = 3283) – ověřit |
| šikmá spojka (vzpěry) | `product_3254` (ze systému 30) | vystředěná na střed drážky, konstanty `VZPERA_*` jako ve 30 |
| spojovací materiál | M6×12 (2.1.21.0612) + otočná matice drážka 8 (2.1.001.08.06) | jako ve 30 |

## Konstanty `SYSTEMY[35]` (`api/stul_konfigurator.py`)
`deska_zkraceni` 5 mm (2 × D, D = (35 − 30) / 2 = 2,5), `police_min_od_podlahy` 132,5 (spodní líc rámu police jako ve 30), `vyrez_x` 105 (závěsy police o 5 mm širší),
`odstup_od_nohou` 30 (spojka 3158 sahá u střední nohy 27 + 17,5 = 44,5 mm od osy, box 47,5 mm), `zaslepka_vyska` 3,3, `patka_delka` 75 / `patka_zasun` 30 (jako 30). Pravidla posunu `R`
jsou ve všech systémech stejná; liší se šablona a konstanty závislé na šířce profilu. Minimální šířka stolu s panelem 1262 mm (`S.panel_limity(35)`).

## Odvození šablony
`odvod_sablony_35.py` (z `odvod_sablony_40.py`): vnější plochy noh zůstávají, osy noh a příček se posunou dovnitř o D = 2,5 mm, nosné plochy (horní plocha rámu pod deskou a rámu police, horní konce
zadních noh) zůstávají, konce profilů dosedají na líce sousedů (±17,5), příslušenství drží svůj dotykový povrch, rohové spojky 3158: `W = uzel + sgn · 17,5` (dvě osy, třetí osa 0 = vystředěno),
`pozice = W − R · Q30`. Výstup `vystup/stul_sablona_system35.json` (→ `api/stul_sablona_system35.json`) a `vystup/zmeny_30_na_35.json` (tabulka změn).

## Patche
`patch_konfigurator_35.py` (SYSTEMY[35], `SABLONA_PATH_35`, názvy dílů, deduplikace `SPOJKY_PARTS` / `KONCE_PARTS` / `VZPERY_SPOJKY` – sdílené 3158, 3251, 3254 se jinak v testech počítají dvakrát, text
spojovacího materiálu pro všechny systémy kromě 40) a `patch_shop_glb_35.py` (`RECEPT_35` v `stul_shop.py`, materiály `profil_35x35` a 3090 v `stul_glb.py`); oba idempotentní.
Karta: `zaloz_kartu_system35.py` (náhled; `--apply` přes systemd-run; neaktivní karta `STUL.SYSTEM35.KONF` + záznam v `configurator_products`; pravidlo 54 – aktivuje Robert).

## Testy (výsledky 2026-10-05, nad HEAD po commitu bot8 7220a163)
- `test_prejimka_system35.py`: sirka 1200 bez panelů = odvozená šablona (0,003 mm), výchozí stůl 35 (1280, 1 panel) bez problémů; zlatý test 30 beze změny.
- `test_regrese_system30.py 7220a163`: systém 30 bit po bitu stejný (1016/1016), tj. zavedení systému 35 ho nezměnilo.
- Obecné sady `spust_v_systemu.py 35 …`: vyroba, podpery (15382), suplik_meze, loz, police_vysky, strany_pet, pet_umisteni, ovladani, zive, zive_vyska, vyrez_police, led_svetlo, panely – vše OK jako u 40.
- `test_shop_system35.py` (veřejné API 30/35/40, přenositelnost výběru, token `y`, výrobní list 03, staff trasa) a `test_stul_host_35.js` (stránky, přepínání 35 → 40 → 30 → 35, vzpěry), nad fiktivními kartami.
- `test_stul_glb.py` má pevná čísla pro 30 (obrys desky s výřezem); u 35 stejně jako u 40 selhávají jen tyhle zlaté hodnoty.

## Kategorie „Ergonomický balicí stůl system 35“ (Robert 2026-10-05: „pro generátor stolu systém 35 založ na každém webu novou kategorii“)
Hlavní e-shop: kategorie **#312** `/ergonomicky-balici-stul-system-35` pod 182 (sourozenci 206, 311), `sort_order` 1 → v seznamu hned za 183 „Ergonomické balicí stoly SSE“; kostra bez textu `zaloz_kategorii_system35.py`
(nahled / `--apply` přes systemd-run, idempotentní). Texty píše bot7, generátor do kategorie dává bot16 (`CATEGORY_GENERATORS[312]`, `card: 4955`). Mini-shop (SK baliace-stoly.top živý, EN packing-tables.top není live):
kategorie `ergonomic-packing-table-system-35` + produkt PWB-003 (karta 4955) jako drafty podle postupu v paměti (texty bot7 → `miniweb_import.py` → schvaluje Robert, jen přes `--items`); obrázek karty `webapp/miniweb/img/produkt-4955.jpg`
(`scripts/2026-10-03_snimek_konfigurace.sh 4955 …`, výchozí konfigurace 1280 × 800 + panel).

## Návlek nohou (jekl 40×40×2) – Robert 2026-10-05
Zadání: „Navlek/jekl nastavitelné délky od 200 do 400 mm se nasadí namísto koleček, záslepek nebo patek jako další volba resp. jako výchozí volba, tak aby alespoň 70 mm nohou stolu zajelo do jeklu, na jehož spodním konci bude jeklová záslepka“;
„návlek půjde do kolize se spodními policemi, takže v úrovni návleku nemůže být jiný komponent, žádný“; „cena návleku 200 mm 370 Kč, délky 400 mm 550 Kč“. (Na stole SSE jsou nohy z jeklu 40×40 o délce ~675 mm s profilem 35×35 uvnitř; v generátoru 35 je to jinak: jekl je dole, profil nohy do něj zajíždí.)
Jen systém 35. Změny: `api/stul_konfigurator.py` (parametry `navlek`, `navlek_delka`, konstanty `NAVLEK_*`, geometrie, kontroly, automatické odebrání, 3D ovládání, výrobní výpis), `api/stul_glb.py` (procedurální tvar jeklu a jeho záslepky), `api/stul_api.py` (cena),
`api/stul_shop.py` (veřejné sloty `sleeve` / `sleevelen`, výchozí výběr, token), `api/stul_ovladani_verejne.py` (překlady 3D menu), `api/stul_vyrobni_list.py`, `webapp/js/stul-host.js` (pole cen v Pravidlech stolu), `webapp/js/scene/stul-konfigurator.js` (Scéna).
- **Geometrie:** pod KAŽDOU nohou (i středními) jekl 40×40, stěna 2 mm, délka 200–400 mm po 10 (výchozí 300), střed v ose nohy; spodek jeklu 3 mm nad podlahou (příruba jeklové záslepky leží na podlaze, zátka 12 mm míří do jeklu); profil nohy v jeklu končí **přesně 70 mm** pod horním koncem jeklu (nejvyšší poloha stolu),
  takže je profil nohy kratší o (délka − 70 + 3) mm a výška desky se nemění. Návlek vytlačí kolečka i patky (zapnutý navlek = `kolecka` a `patky` vypnuté).
- **Provedení (Robert 2026-10-05 po skice):** vnější rohy jeklu **sražené 45° o 2 mm jako na jeklu nohy stolu SSE** (osmiúhelníkový obrys 40 s rohy ±20 / ±18, přesně podle `sse_full.glb`; příruba záslepky má stejný obrys, vnitřní dutina zůstává čtverec 36×36), **barva tmavá šedočerná RAL 7016, lesk** (GLB materiál `ral7016` = antracit sRGB 41 / 49 / 51, kovovost 0, drsnost 0,18; záslepka zůstává černý plast; **past:** `baseColorFactor` je pro viewer LINEÁRNÍ (0,0222 / 0,0307 / 0,0331), starší materiály „v gamma hodnotách“ jsou vyšší – se sRGB číslicemi 0,161 / 0,192 / 0,200 vyšel jekl středně šedý); barva je i v názvu řádku (kusovník, objednávka) a ve výrobním výpisu / listu.
- **V úrovni návleku žádný jiný komponent:** do výšky horního konce jeklu + 3 mm (Robert po skice: minimum 3 mm) nesmí sahat žádný jiný díl než nohy, jekly a záslepky. Nejnižší police (osa rámu) leží ≥ horní konec + 3 mm + ½ profilu (do délky 304 mm, tedy u výchozích 300 mm, drží polohu ze šablony 327,7 mm, u 400 mm se zvedá na 423,5 mm; ručně zadaná výška police pod touto mezí je problém `police_vyska` a návlek se kvůli ní NEODEBERE – chyba zůstane vidět; zanoření dílu do jeklu u moc nízkého stolu bez ručních výšek polic návlek dál odebere),
  police pod výřezem se do té úrovně nevejde (nabídka odebrat), držák PET a šuplíky v úrovni návleku se samy odeberou, ručně posunutý držák PET dá `navlek_kolize` + nabídku odebrat (a `pet_meze` končí nad návlekem).
- **Nízký stůl:** délka se ořízne na největší možnou (`navlek_meze.max`, horní konec jeklu + 3 mm pod spodkem rámu desky / pod nejnižší policí; ve veřejné odpovědi `options.sleevelen.max` a oznámení `info`); nevejde-li se ani 200 mm, návlek se odebere (`navlek_vyska`, kolečka se nevracejí, zůstanou záslepky profilu).
- **Cena:** extra práce „Návlek nohy – jekl 40×40×2, délka N mm, RAL 7016 lesk (vč. záslepky)“ × počet noh; 200 mm = 370 Kč, 400 mm = 550 Kč, mezi tím lineárně (0,9 Kč/mm; **předpoklad: Kč bez DPH za 1 návlek vč. záslepky**), pravidla `cena_navlek_200` / `cena_navlek_400` v Pravidlech stolu (staff stránka). Hmotnost: ocel 2,32 kg/m (průřez 296 mm² se sraženými rohy) + záslepka 12 g.
- **Veřejné API:** sloty `sleeve` (přepínač, skupina Konstrukce) a `sleevelen` (200–400 po 10 mm, závisí na `sleeve`) JEN v systému 35; výchozí výběr 35: `sleeve: true, sleevelen: 300, wheels: false`; systémy 30 a 40 beze změny (žádné klíče návleku ve schématu, výběru ani options); token modelu: bit 9 v `t` + klíč `a` (délka); kolečka a patky mají při návleku `options.<slot>.on.disabled` s důvodem; texty cs/en/sk (ke kontrole bot7).
- **Scéna („Vložit do Scény“):** návlek a jeho záslepka nejsou v katalogu Scény (`insertCustomShape` by při neznámém dílu vkládání přerušil), modul scény je před vložením odfiltruje a přepočítá indexy; souhrn to uvede.
- **Testy (zelené):** `test_navlek.py` (3735 kontrol: nezávislé měření z AABB a z vrcholů GLB, obrys jeklu proti jeklu SSE, mřížka 990 sestav, mutace), `test_shop_navlek.py` (119; DB jen čtení), `test_navlek_scena.js` (9), `test_navlek_stranka.js` (skutečný prohlížeč přes most),
  regrese `test_regrese_system30.py <rev>` (systém 30 bit po bitu stejný) a `test_regrese_35_40_navlek.py <rev>` (systémy 35 a 40 BEZ návleku beze změny; mění se jen nabídky 3D ovládání), sady 1–22 nad 30 / 35 / 40; `spust_s_navlekem.py <test.py>` pouští sady nad systémem 35 s návlekem jako výchozím stavem
  (sady s pevným očekáváním koleček – `test_stul_loz` zlatý test, `test_stul_led_svetlo`, `test_stul_panely`, `test_stul_pet_umisteni`, `test_stul_police_vysky` (hash výchozího stolu), `test_stul_strany_pet` – tam oprávněně nesedí).
**Otevřené:** způsob zajištění výšky (aretace, šrouby) a SKU/karta jeklu určí Robert (zatím jen řádek práce s pravidly cen); návlek ve Scéně vyžaduje `cfg_dily` řádek + GLB; fyzické ověření.

## Otevřené
Mini-shop drafty a texty (bot7/bot16/Robert), aretace a SKU návleku (Robert), návlek ve Scéně (cfg_dily + GLB), fyzické ověření spojky/patky/šroubu na profilu 35, animace „Připni cokoli“ pro 35 (není).
