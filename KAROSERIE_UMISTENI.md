# Umístění do karoserie vozidla

Výběr karoserie/modelu podle oficiální kóty dveří, kolizní krokování (1mm kroky, NE bisekce), pravidlo o nezávislosti pozic noh na prohnutí stěny (a jeho rozšíření na tuze spojené sestavy), poloha `.vyrez` nohy podle podběhu kola, otočení karoserie CI14 o 180°. Vydělené z `VLASTNOSTI_PROFILU.md` 2026-08-31. Viz taky `KOMPONENTY_EUROBOXY.md`.

## Pravidlo profilů - členitá/`.vyrez` noha se řídí POLOHOU PODBĚHU KOLA, ne pořadím/koncem sestavy (OPRAVENO Robertem 2026-08-23, viz historie chyby níže)

**Aktuální, správné pravidlo:** která noha v sestavě regálu je
členitá/`.vyrez` (přerušená spodní svislice, náhradní snížený sloupek)
se řídí VÝHRADNĚ tím, jestli se ta konkrétní noha nachází NAD PODBĚHEM
KOLA konkrétní karoserie - ne tím, jestli je to "poslední" noha, "zadní"
noha, nebo konec dál od přepážky B. Robert: **"členitá noha je skrze
podběhy (kola auta)"** + **"a členitá nemusí být poslední, ale ta která
je prostě nad podběhem."**

**Proč na tom záleží (2 vs 3-4 nohy):** u regálu jen se 2 nohama (jedna
na každém konci, viz `product_assemblies.id=11` "Regál 40A01 Doblo",
sestava mezitím smazána - audit bot9 2026-09-12, historický odkaz)
vždy VYPADÁ, jako by platilo "členitá = konec dál od B" - ale je to jen
DŮSLEDEK toho, že podběh kola tam zrovna vychází, ne skutečné pravidlo.
U delší karoserie se 3-4 nohama (Robert: "někdy jsou ale v autě i 3
nebo 4 nohy") je podběh kola typicky u NĚKTERÉ VNITŘNÍ nohy, ne u
krajní - tam by "vždy poslední konec" dalo ŠPATNÝ výsledek. **Před
umístěním jakéhokoli regálu/sestavy noh vždy zjisti skutečnou POLOHU
podběhu kola v cílové karoserii (geometrie karoserie, ne odhad) a
členitou/`.vyrez` nohu dej TAM, ne mechanicky na krajní pozici.**

Souvisí s pravidlem pro samostatnou "Noha" výše (`.vyrez` = má
přerušenou spodní konstrukci) - to zůstává v platnosti pro TVAR dílu,
mění se jen kritérium PRO KTEROU POZICI v sestavě se použije.

## Pravidlo profilů - KANONICKÝ POSTUP umístění regálu/sestavy do karoserie: kolizní krokování, ne modelování tvaru stěny (Robert 2026-08-23, ověřeno na FI22 s přesností ~12mm proti jeho ruční referenci)

Robert popsal svůj vlastní ruční postup slovo od slova: **"1) postavit
uprostřed auta 2) posunout 1 mm nad podlahu 3) posunout k přepážce,
resp 1mm zabořit, zčervená, 2mm zpátky, čekám jestli stále červená,
pokud ne pokracuju dalším bodem 4) posunuju ke stěně, stejným stylem
dokud nezčervená, 2mm zpátky, čekám jestli stále červená, pokud ne je
hotovo."** Bot to implementoval 1:1 v Node.js
(`robert_algorithm.js` vzor, kolizní test = hranový raycasting proti
skutečné GLB geometrii stěn, stejný jako produkční
`checkCarBodyCollisions()`) a na regálu 524 + karoserii FI22 se trefil
na Robertovo ruční umístění s rozdílem [12.2, 0.4, 8.0]mm - v rámci
tolerance jeho "2mm zpátky" ruční práce.

**Proč to funguje líp než "změřit rovinu stěny a přiložit":** stěny
karoserií NEJSOU ploché desky (L mesh FI22 = stěna+podlaha+náběhy v
jednom kuse, "rovina stěny" reálně neexistuje - medián X střední
výškové vrstvy kolísá 0-712mm podle Z). Kolizní test proti skutečné
geometrii je jediný spolehlivý "smysl" - stejně jako Robert "to prostě
vidí", bot to prostě testuje.

**KRITICKÉ implementační detaily (oba nalezeny vlastními chybami):**
1. **Krokovat po 1mm, NIKDY bisekce s velkým rozsahem** - bisekce
   "protuneluje" skrz tenkou stěnu (oba testované konce bez kolize,
   střed se nikdy netestuje) a vrátí nesmysl/Infinity. Kroky menší než
   tloušťka stěny tunelovat nemohou.
2. **Start "uprostřed auta" = uprostřed NÁKLADOVÉHO PROSTORU** (zadní
   hrana až líc přepážky B), ne uprostřed bboxu boční stěny - ten
   zahrnuje i kabinu PŘED přepážkou a sestava by se "narodila" už
   zabořená do předku. A počítat s tím, že lokální počátek sestavy
   NENÍ její střed (offset volit přes bbox sestavy).
3. Pořadí os přesně podle Roberta: podlaha → přepážka B → stěna.
   Po každém "zčervenání" 2mm zpět a ZNOVU ověřit, že už není červená.

**Předpoklad metody (Robert):** "pro tuto metodu jsou ale zapotřebí
nohy už vytvarované, to je to členění zadní nohy, nohy můžu na začátku
nachystat, některé karoserie už nohy mají, případně se upraví" -
tzn. metoda umísťuje HOTOVOU sestavu s nohami už vytvarovanými pro
danou karoserii (členění podle podběhu, viz pravidlo výše); tvarování
noh je SAMOSTATNÝ krok před umístěním, ne součást téhle metody.
Testovací běh 2026-08-23 používal nohy ne zcela ideální pro FI22
("pro test to nevadí" - Robert).

**Poznámka k metodě (Robert 2026-08-23, po potvrzení nohou T6):** "po
směru jízdy je pozice nohy odvislá od toho co chce klient, jak dlouhý
chce regál a kolik místa chce nechat směrem k přepážce a vzadu za
podběhem. to je individuální, ale pozice nohy vůči stěně je daná." -
tzn. **podélná (Z) pozice = VSTUP OD KLIENTA/konfigurace** (kroky
"podél auta" v metodě jsou jen výchozí/testovací umístění, ne pevné
pravidlo), zatímco **pozice vůči stěně (kolmo) je vždy DANÁ metodou**
(kolizní dojetí ke stěně, zářez přes podběh). Zapsáno i do DB záznamu
metody (`car_body_placement_methods.name='kolizni-krokovani'`, klíč
`poznamka_robert_2026_08_23`, version 2).

**Maximální rozpon nohou (Robert 2026-08-23):** "pokud se umístí nohy
dle metody kolizni-krokovani, tam přední noha je na konci, dál jít
nemůže. Zadní noha může jít až do místa kolize se stěnou (v rohu
auta), vrátit se 20mm, ověřit kolizi a pokud není kolize jsme na
maximálním rozponu nohou, tj. prostor mezi nohama je největší jaký
může být pro dané auto/model." - Přední noha = koncová pozice u
přepážky B dle metody. Zadní noha = kolizní krokování DOZADU podél
stěny až do rohu auta, **zpět 20mm (ne standardních 2mm!)**, ověřit.
Výsledek = horní mez pro klientovu volbu délky regálu (podélná pozice
je jinak individuální, viz poznámka výše). V DB jako klíč
`max_rozpon_nohou` (version 3).

## Pravidlo profilů - VÝBĚR KAROSERIE/modelu podle oficiální kóty zadního otvoru dveří (Robert, 2026-08-29, formulováno po umístění noh Jumpy)

Jiný krok než kolizní krokování výše — TOHLE rozhoduje, KTEROU karoserii/model vůbec použít, PŘEDTÍM než se cokoli umísťuje. Zapsáno do DB jako samostatná metoda (`car_body_placement_methods.name='vyber-karoserie'`, `id=2`, `version=1`, `verified_by='robert'`) - `kolizni-krokovani` (`id=1`) na ni navazuje, ne nahrazuje.

**5 kroků:**
1. Ověř dostupnost délkové/výškové varianty modelové řady v AKTUÁLNÍM oficiálním ceníku výrobce - chybějící varianta (Jumpy L1 = CI13/CI24) se VYŘAZUJE i když GLB existuje.
2. Zjisti oficiální kótu zadního otvoru dveří z oficiálního zdroje (ceník/technický list PDF), NE z GLB - dveře/rám dveří často nejsou v GLB modelovány vůbec nebo přesně.
3. **Modelová řada může mít VÍC typů zadních dveří s RŮZNOU výškou** (Jumpy furgon: dvoukřídlé 1282×1220mm vs. výklopné 1212×1181mm - výklopné jsou NIŽŠÍ, tedy přísnější limit) - použij vždy nejmenší/nejpřísnější napříč všemi nabízenými typy, ne jen ten, co je zrovna v DB.
4. Porovnej výšku/šířku HOTOVÉ sestavy proti nejpřísnější kótě z kroku 3, vyber karoserii kde nepřesahuje - rezerva může být reálně velmi malá (Jumpy noha H1 1180mm vs. výklopné dveře 1181mm = 1mm rezerva, NENÍ to chyba měření, přijmi to jako platné, pokud kóta sedí z oficiálního zdroje).
5. Zapiš použitou kótu + zdroj do `karoserie_model_reference` u KAŽDÉ relevantní `legacy_vendor_code` varianty (i když mají stejnou hodnotu napříč variantami modelové řady - všech 6 variant Jumpy CI14/15/18/19/25/26 má identickou `official_door_opening_height_mm=1220mm`, protože sdílí stejné dveře/tooling, liší se jen délkou karoserie).

**Otevřená mezera v DB schématu (zapsáno 2026-08-29):** `karoserie_model_reference.official_door_opening_height_mm` dnes zachycuje jen JEDEN typ dveří (u Jumpy furgonu vychází na 1220mm = dvoukřídlé). Kóta VÝKLOPNÝCH dveří (1181mm), která byla u nohy H1 1180mm SKUTEČNÝM limitujícím faktorem, v DB schématu chybí (žádný sloupec typu `official_tailgate_opening_height_mm`). Dokud sloupec nepřibude, musí se tahle druhá kóta ověřovat RUČNĚ z oficiálního zdroje při každém výběru karoserie blízko stropní výšky - nespoléhat jen na to, co už je v DB.

## Karoserie CI14 (car_bodies 114/115/116) otočena o 180° kolem svislé osy Y (Robert, 2026-08-30)

Robert po zhlédnutí regálu na euroboxy ve scéně: "celé to přetoč o 180 stupňů, otevre se mi to zadkem auta opačně že nevidím do auta", upřesnění na dotaz - otočit VŠECHNO včetně karoserie, a "ty karoserie ulož otočené ať se vkládají správně" - tedy OPRAVIT ZDROJOVÝ GLB SOUBOR karoserie, ne jen jednorázově otočit tuhle jednu sestavu.

**Provedeno:** `webapp/katalog/car_bodies/Citroën_Jumpy_CI14_2016-_{L,R_D,B}.glb` (odpovídají `car_bodies.id=114/115/116`) FYZICKY přepsány - binární patch POSITION i NORMAL accessorů, transformace `(x,y,z) → (-x,y,-z)` (180° rotace kolem světové osy Y, střed v počátku 0,0,0 - beze změny velikosti souboru, jen přepsané hodnoty). Zálohy originálů: `backups/2026-08-30_car_body_ci14_pre_180_flip/`. Skript: `scripts/tmp_2026-08-30_flip_car_body_180.js`.

**Důsledek pro VŠECHNY existující i budoucí `product_assemblies` používající tyhle `car_body_*` reference s identity quaternionem:** stěna "L" (dřív na +X straně, `x∈[0,807]`) je teď na −X straně (`x∈[-807,0]`) a naopak "R_D" na +X. Osa Z je zrcadlená stejně (`z∈[-147,2265]` → `z∈[-2265,147]`). **V okamžiku provedení této změny na projektu EXISTOVALY JEN 3 sestavy** používající tuhle karoserii (`product_assemblies.id=43/44/45`, regál na euroboxy - všechny 3 řádky mezitím smazány, audit bot9 2026-09-12, historický odkaz) - ty byly přepočítány stejnou 180° transformací (nohy, nosníky, spojnice, euroboxy), takže jejich fyzický vztah ke (nyní otočené) karoserii zůstal zachovaný. **Pro budoucí session:** pokud se najde JINÁ, dřív vytvořená sestava s touhle karoserií (např. ve staré záloze/archivu), její pozice budou vůči NOVÉ orientaci karoserie zrcadlové/špatné - je potřeba je přepočítat stejnou transformací, ne jen znovu vložit se starými souřadnicemi.


## Upozornění: konkrétní čísla z kolizního krokování NEJSOU univerzální mezi modely aut (Robert, 2026-08-31)

Po dokončení regálu ukotveného k přepážce vozidla Jumpy CI14 (viz `KOMPONENTY_EUROBOXY.md`, `product_assemblies.id=47`, sestava mezitím smazána - audit bot9 2026-09-12, historický odkaz) Robert: "ok nevím jestli tento typ výpočtu bude správný i v dalších autech, ale zde je ok."

**Generalizuje METODA** (viz `car_body_placement_methods.id=1` `kolizni-krokovani` - verze se průběžně mění, ověř živě `SELECT version FROM car_body_placement_methods WHERE id=1`, nepamatovat si číslo, OPRAVENO audit bot9 2026-09-12): identifikace přepážky podle tvaru bboxu stěny (celá šířka/výška, úzký plát v ose délky vozu, na krajní pozici - ne boční stěna táhnoucí se po celé délce) + kolizní krokování 1mm/2mm zpět pro nalezení bezpečné pozice.

**NEGENERALIZUJE konkrétní číslo:** Z-pozice přepážky Jumpy CI14 (~2007/2037mm), tvar/rozměry podběhu, přesná geometrie stěny B - to vše je SPECIFICKÉ pro tenhle model karoserie. U jiného modelu (jiný `car_bodies` záznam) je nutné znovu spustit celý postup (identifikace stěny + kolizní krokování) na jeho REÁLNÉ GLB geometrii - nikdy nepřebírat čísla zjištěná u Jumpy CI14 jako výchozí/hardcoded hodnotu pro jiné auto.

## Protažení limitujícího svislého profilu členité nohy proti reálnému podběhu - OBECNÝ postup (Robert, 2026-08-31)

Zapsáno detailně v `KOMPONENTY_EUROBOXY.md` (sekce "Protažení zadní svislice výřezové nohy") a v DB `shape_geometry_methods.id=6` (`protazeni-zadni-svislice-vyrezove-nohy`, `version=3`, `verified_by='robert'`) - odkaz sem přidán, protože Robert postup výslovně prohlásil za OBECNÝ, ne jen pro eurobox regály: "tato uprava clenite nohy lze aplikovat obecne pro libovolne komponenty i karoserie protoze se prizpusobuje podbehu v danem libovolnem miste."

**Princip:** u členité ("výřezové") nohy, kde svislý profil blíž stěně nedosahuje k podlaze kvůli podběhu kola, lze reálným 1mm kolizním krokováním (proti SKUTEČNÉ GLB geometrii karoserie na dané Z-pozici, ne proti odhadnuté konstantě) zjistit, jak daleko dolů ten profil skutečně může sahat - kolize + 20mm odskok (ne standardních 2mm). Sousední kratší svislý profil (ten, co obchází podběh dál od stěny) se zkrátí o stejnou délku, o kterou se ten limitující profil protáhl, a spojovací příčka mezi nimi se jen posune na nový styk.

**Co generalizuje / co ne:** METODA (kolizní krokování konkrétního limitujícího profilu proti reálné geometrii) platí pro libovolnou karoserii i typ komponenty. KONKRÉTNÍ ČÍSLO (u Jumpy CI14 vyšlo Y_new=199mm/ΔY=196mm) je specifické pro tenhle model a pozici - u jiné karoserie/komponenty nutno kolizní krokování zopakovat, stejné pravidlo jako u "kolizni-krokovani" (`car_body_placement_methods.id=1`) výše.

## Audit orientace VŠECH karoserií v katalogu (bot16, 2026-08-31)

Robert po zhlédnutí regálu na Jumpy L2 (CI25) ve scéně: "je to jakési otočené celé", pak: "možná je to tím, že se karoserie neotočili a chce to zkontrolovat vsechny auta". Zadání: najít SKUTEČNÉ kritérium "je tahle karoserie otočená správně", ne jen odhad, a aplikovat ho na CELÝ katalog `car_bodies` (304 modelů, 912 GLB souborů).

### Skutečné kritérium správnosti (Robert, přesná citace): "kdyz se vloží do sceny, musím se dívat do zadních dveří auta"

Tj. při vložení karoserie do scény s VÝCHOZÍ kamerou (identity quaternion dílu, žádná rotace při vložení - `car_bodies` nemá žádný sloupec pro rotaci/transform, viz `DESCRIBE car_bodies`) musí uživatel hledět OTEVŘENÝM koncem (zadní dveře) DOVNITŘ, směrem k přepážce B - ne na vnějšek/zadek přepážky.

**Výchozí kamera** (OPRAVENO audit bot9 2026-09-12, kód přesunut refaktoringem `61c0ede1` 2026-09-03: `webapp/js/scene/catalog-panels.js`, ne `scene.html`): `camera.position.set(1800, 1500, 2400)`, `controls.target = VIEW_DEFAULT_TARGET = (0, 50, 0)` - kamera stojí na straně KLADNÉHO Z (a kladného X), dívá se směrem k počátku (klesající Z, klesající X). Karoserie se vkládá do scény BEZ rotace (`car_bodies` v DB nemá žádné pole pro rotaci) - tedy surové lokální souřadnice GLB = světové souřadnice.

**Z toho plyne přímo měřitelný test, beze změny:**
- Spočti bounding box POSITION accessoru stěny „B" (přepážka) z jejího GLB - `zMidB = (minZ+maxZ)/2`.
- **`zMidB < 0` (přepážka na straně ZÁPORNÉHO Z, daleko od kamery)** → karoserie je OTOČENÁ SPRÁVNĚ (uživatel se dívá otevřeným koncem od kamery/blízko počátku směrem dozadu k přepážce v dálce - přesně "dívám se do zadních dveří auta").
- **`zMidB > 0` (přepážka na straně KLADNÉHO Z, blízko/před kamerou)** → karoserie je OTOČENÁ ŠPATNĚ (uživatel hledí na vnějšek přepážky/zadek auta, otevřený konec je v dálce za počátkem - přesně Robertova stížnost "otevre se mi to zadkem auta opačně že nevidím do auta").

Test NEPOTŘEBUJE žádnou druhou podmínku (např. na které straně X leží stěna "L") - ověřeno na celém katalogu (viz níže), že znaménko X strany "L" koreluje 1:1 se znaménkem `zMidB` (obě jsou příznakem TÉŽE chybějící/přebývající 180° rotace kolem Y) - je tedy REDUNDANTNÍ, ne nezávislý faktor. Jediné a postačující kritérium je `sign(zMidB)`.

### Ověření testu na obou známých případech

| Karoserie | Stav | B_minZ | B_maxZ | zMidB | Test řekne | Souhlasí s Robertem? |
|---|---|---|---|---|---|---|
| CI14 SOUČASNÁ (`webapp/katalog/car_bodies/Citroën_Jumpy_CI14_2016-_B.glb`) | opravená, Robert potvrdil OK | -2561.97 | -2024.44 | **-2293.20** | OK (správně) | ANO - tohle je stav PO opravě, kterou si Robert vyžádal a potvrdil |
| CI14 PŮVODNÍ (`backups/2026-08-30_car_body_ci14_pre_180_flip/..._B.glb`) | před opravou, Robert řekl "nevidím do auta" | 2024.44 | 2561.97 | **+2293.20** | NEEDS_FLIP (špatně) | ANO - přesně tohle Robert reklamoval |
| CI25 PŘED touhle opravou (`backups/2026-08-31_car_body_ci25_180_flip/`, = běžela ve scéně, kdy Robert řekl "je to jakési otočené celé") | před opravou | 2024.44 | 2561.97 | **+2293.20** | NEEDS_FLIP (špatně) | ANO - byte-identické s CI14 PŘED opravou, stejná vada |

Test 100% souhlasí s oběma známými Robertovými reakcemi (CI14 OK až po opravě, CI25/CI14-pred-flip špatně) - použit jako jediné kritérium pro zbytek katalogu.

**Poznámka k dřívější (chybné) domněnce z tohoto zadání:** dřívější odhad "CI24 nepotřebuje otočit" byl založen jen na strukturální kontrole (existuje stěna B na kladné straně Z, sedí tvarem), NE na skutečném kritériu "kam se dívá výchozí kamera". CI24 má `zMidB = +1943.2` (stejné znaménko jako CI25 před opravou) - podle SKUTEČNÉHO kritéria tedy CI24 **POTŘEBUJE otočit stejně jako CI25** (viz tabulka níže) - dřívější závěr byl mylný, ne že by existoval nějaký další rozlišující faktor (X-handedness stěny "L" byl prověřen a je jen redundantní/korelovaný příznak, ne nezávislá výjimka).

### Metoda auditu (reprodukovatelné)

1. `SELECT id, name, glb_file FROM car_bodies WHERE glb_file IS NOT NULL ORDER BY glb_file` → 912 řádků / 304 modelů (`_L`/`_R_D`/`_B`, jeden model má `_B_wall` misto `_B`) - uloženo `scripts/2026-08-31_car_bodies_dump.tsv`.
2. Pro každý model načíst POSITION bounding box GLB souboru role "B" (binární GLB parser čte `accessors[].min/max` přímo z hlavičky, bez nutnosti dekódovat celý bin chunk) - `scripts/2026-08-31_glb_position_bbox.js`.
3. `zMidB = (minZ+maxZ)/2`; `zMidB < -50` → OK, `zMidB > +50` → NEEDS_FLIP (±50mm práh jen jako pojistka proti hraničním případům - reálně vyšlo VŠECH 304 modelů s `|zMidB| > 250mm`, žádný nejednoznačný/hraniční případ).
4. Celý skript: `scripts/2026-08-31_car_body_orientation_audit.js` (čte dump z kroku 1, počítá bbox jako v kroku 2, vypisuje verdikt na model). Výstup: `scripts/2026-08-31_car_body_orientation_audit_results.jsonl` (304 řádků, 1 JSON objekt na model - `base`, `ids`, `B_minZ/maxZ/midZ`, `L_minZ/maxZ`, `RD_minZ/maxZ`, `verdict`).

### Výsledek: 273 modelů z 304 (90%) potřebuje otočení, jen 31 je v pořádku

**AKTUALIZACE 2026-09-05 (audit bot9 doplnil 2026-09-12): hromadná oprava PROVEDENA.** Robert spustil `scripts/2026-09-05_orientace_vse.sh` (commity `c5a43647` + `9220e97e`, dokončeno včetně 36 souborů s diakritikou v názvu). Ověřeno `scripts/2026-09-05_kontrola_orientace.py`: **304/304 modelů OK.** Tabulka a seznam níže popisují stav PŘED opravou (2026-08-31), jako dokumentaci metody/rozsahu problému, ne aktuální stav.

```
CELKEM: 304 modelů (912 car_bodies řádků)
NEEDS_FLIP: 273
OK:         31   (z toho CI14 a CI25 - obě opravené touhle/předchozí session)
UNCERTAIN:   0   (žádný hraniční/nejasný případ)
```

**Rozpad podle výrobce (NEEDS_FLIP / OK):**

| Výrobce | NEEDS_FLIP | OK |
|---|---|---|
| BYD | 1 | 0 |
| Citroën/Citro_n | 20 | 1 (CI14 i CI25 už opraveny) |
| Dacia | 1 | 0 |
| Fiat | 22 | 0 |
| Flexis | 2 | 0 |
| Ford | 35 | 10 |
| Hyundai | 0 | 3 |
| Ineos | 1 | 0 |
| Isuzu | 2 | 0 |
| Iveco | 11 | 0 |
| Kia | 1 | 0 |
| MAN | 12 | 0 |
| Maxus | 15 | 2 |
| Mercedes | 32 | 2 |
| Nissan | 12 | 3 |
| Opel/Vauxhall | 23 | 1 |
| Peugeot | 23 | 0 |
| Renault | 16 | 2 |
| Toyota | 19 | 1 |
| Volkswagen | 25 | 5 |
| FO30 (testovací/demo karoserie, id 3/4/5) | 1 | 0 |

**Úplný seznam 31 modelů, které jsou OK (nepotřebují otočit)** - všechny ostatní (273) v `scripts/2026-08-31_car_body_orientation_audit_results.jsonl` NEEDS_FLIP:

- Citroën_Jumpy_CI14_2016- (114/115/116) - opraveno bot 2026-08-30
- Citroën_Jumpy_CI25_2021- (129/130/131) - opraveno TOUHLE session, viz níže
- Ford_Connect_FO45_2024- (240/241/242)
- Ford_Connect_FO46_2024- (243/244/245)
- Ford_Custom_FO11_2012-2023 (255/256/257)
- Ford_Custom_FO29_2012-2023 (267/268/269)
- Ford_Custom_FO55_2023- (285/286/287)
- Ford_Custom_FO56_2023- (288/289/290)
- Ford_Ranger_FO32_2023- (294/295/296)
- Ford_Ranger_FO54_2024- (297/298/299)
- Ford_Transit_FO19_2014- (312/313/314)
- Ford_Transit_FO20_2014- (315/316/317)
- Hyundai_H1_HY05_2008-2017 (21/22/23)
- Hyundai_H350_HY06_2014- (75/76/77)
- Hyundai_H350_HY07_2014- (363/364/365)
- Maxus_Deliver7_ME20_2024- (426/427/428)
- Maxus_e-Deliver7_ME14_2024- (459/460/461)
- Mercedes_Citan_MB15_2012-2021 (42/43/44)
- Mercedes_Citan_MB16_2012-2021 (90/91/92)
- Nissan_NV250_NI20_2019-2021 (582/583/584)
- Nissan_NV250_NI21_2019-2021 (585/586/587)
- Nissan_NV300_NI19_2016- (588/589/590)
- Opel_Vivaro_OP21_2014-2019 (651/652/653)
- Renault_Kangoo_RE07_2007-2021 (735/736/737)
- Renault_Kangoo_RE08_2007-2021 (738/739/740)
- Toyota_Hilux_TO03_2015- (57/58/59)
- Volkswagen_Amarok_VW24_2023- (108/109/110)
- Volkswagen_Caddy_VW31_2021- (846/847/848)
- Volkswagen_Caddy_VW32_2021- (849/850/851)
- Volkswagen_Transporter_VW42_2024- (909/910/911)
- Volkswagen_Transporter_VW43_2024- (912/913/914)

**Zajímavost/možné vysvětlení rozsahu:** 90% katalogu má stejnou vadu → nejde o náhodnou chybu jednotlivých modelů, ale o systematickou vlastnost dávky/konverzního pipeline, kterou byla většina GLB souborů vyrobena (STP→GLB konverze, viz `backups/2026-08-10_product_stp_to_glb_batch*`) - pravděpodobně chyběla jedna otočka o 180° kolem Y v konverzním kroku pro většinu vozů, zatímco menšina (31 modelů, různí výrobci bez zjevného společného vzoru) byla dodána/zkonvertována už ve správné orientaci. **Kvůli velkému rozsahu (273 souborů) je tahle oprava ZÁMĚRNĚ NEPROVEDENÁ na nic než CI25 (viz níže)** - čeká na Robertovo rozhodnutí, jak s tak velkou dávkou naložit (bulk skript s tímhle otočením je triviální - `scripts/2026-08-31_flip_car_body_ci25_180.js` zobecnělý na seznam souborů - ale hromadná binární úprava 273 produkčních souborů bez výslovného svolení by byla přesně ten druh kroku, co `WORKFLOW.md` bod 23 varuje neudělat bez zeptání).

### Provedená oprava: CI25 (car_bodies 129/130/131)

CI25 byla jediná v tomhle auditu FYZICKY opravena (zbytek jen nahlášen) - byla to ta konkrétní karoserie, na kterou si Robert ve scéně stěžoval ("je to jakési otočené celé" u Jumpy L2/CI25 regálu), takže je nejnaléhavější a Robertovo zadání ji výslovně povolilo opravit rovnou.

**Provedeno stejně jako CI14 (2026-08-30):**
1. Zálohy originálů (před opravou): `backups/2026-08-31_car_body_ci25_180_flip/Citroën_Jumpy_CI25_2021-_{L,R_D,B}.glb` (md5 ověřeno identické s produkčními soubory před patchem).
2. Binární patch POSITION i NORMAL accessorů, `(x,y,z) → (-x,y,-z)` (180° rotace kolem světové osy Y), beze změny velikosti souboru. Skript: `scripts/2026-08-31_flip_car_body_ci25_180.js` (zobecněná verze `tmp_2026-08-30_flip_car_body_180.js` - projde všechny meshe/primitivy souboru, ne jen `meshes[0].primitives[0]`, i když u CI25 to vyšlo nastejno, protože každý soubor má jen 1 mesh/1 primitivu).
3. Ověřeno: nová geometrie CI25 (`webapp/katalog/car_bodies/Citroën_Jumpy_CI25_2021-_{L,R_D,B}.glb`) je teď md5-identická se SOUČASNOU (opravenou) CI14 - očekávané, protože CI25 byla už předtím byte-identická s CI14 PŘED opravou (sdílí stejný zdrojový model/tooling, jen jiná délka karoserie by se čekala - to, že jsou geometricky úplně identické i v délce, je samostatný, nevyřešený nález mimo rozsah tohohle úkolu, viz "Otevřený nález" níže).
4. `sign(zMidB)` po opravě: B wall `Z∈[-2561.97, -2024.44]`, `zMidB=-2293.2` → OK, odpovídá kritériu.

**DŮSLEDEK PRO `product_assemblies.id=51` (regál na CI25, zmíněný v `KOMPONENTY_EUROBOXY.md` sekce "Regál na euroboxy — Jumpy L2 (CI25)") - NEPROVEDENO, tabulka je prázdná:** podle zadání měl být `id=51` přepočítán stejnou `[x,y,z]→[-x,y,-z]` transformací (nohy, nosníky, spojnice, euroboxy) jako u CI14 (`id=43/44/45`), ověřen bez kolize a artefakt na `https://claude.ai/code/artifact/95adc5f4-b8e3-4e63-9483-b929e5edbc75` republikován s novou geometrií. **Při pokusu o to zjištěno: tabulka `product_assemblies` byla v okamžiku téhle session opakovaně PRÁZDNÁ (`SELECT COUNT(*) FROM product_assemblies` → 0), přestože `KOMPONENTY_EUROBOXY.md` popisuje `id=43/44/45/47/49/50/51` jako existující, vytvořené/upravované ještě DNES (2026-08-31).** Vysvětlení nalezeno v průběhu session (viz další odstavec) - tabulka je zjevně souběžně živě upravovaná jiným botem (pravděpodobně bot8, vlastník 3D scény dle `WORKFLOW.md`), NE jednorázově smazaná/poškozená.

**Potvrzeno za běhu téhle session - živý race s jiným botem, PŘESNÁ příčina Robertova nového hlášení "regály plavou mimo karoserii":** Robert mezitím nahlásil, že 3 nově vložené varianty CI25 regálu (`product_assemblies.id=53/54/55`, `shop_products.id=3802/3803/3804` "Jumpy L2 CI25 - boxy43-...") se ve scéně vykreslují CELÉ MIMO tělo karoserie. Krátké dotazování DB v tomhle okně skutečně zachytilo `id=53/54/55` živé (`created_at 2026-08-31 19:45:07`, 82 dílů každá: 3× `car_body_129/130/131` na identitě `position=[0,0,0]`, `quaternion=[0,0,0,1]` + 55× `Object_7` (nohy/nosníky/spojnice) + 24× `product_3071`/`product_3788` (euroboxy/záslepky)) - `data._note` pole u nich doslova říká: *"Zatim NEOVERENA orientace karoserie CI25 (probiha samostatny audit vsech karoserii) - pokud audit potvrdi potrebu 180 flipu, tahle geometrie se bude muset prepocitat."* O pár vteřin/desítek vteřin později byly řádky `53/54/55` už zase pryč (tabulka znovu prázdná při opakovaném dotazu) - druhý bot je zjevně průběžně staví/maže/přestavuje v reálném čase souběžně s touhle session, `shop_products` 3802-3804 zůstaly (`active=0`, osiřelé, stejný vzorec jako u dřívějších 3799/3800).

**PŘÍČINA symptomu (potvrzeno, NENÍ to jiný druh chyby než orientace - je to přesně týž 180°-flip problém, jen v jiné podobě):** `car_body_129/130/131` díly byly v `id=53/54/55` uloženy s `position=[0,0,0]`/identity quaternionem - tzn. sestava předpokládala vykreslení karoserie PŘÍMO v jejím syrovém GLB rámci. Zbylých 79 dílů (nohy/nosníky/euroboxy) bylo postaveno kolizním krokováním proti PŮVODNÍ (před-flip, `zMidB=+2293`) geometrii karoserie. Jakmile tahle session fyzicky přepsala `webapp/katalog/car_bodies/Citroën_Jumpy_CI25_2021-_*.glb` (baked 180° flip, viz výše) - identický `part_id="car_body_129"` s IDENTICKOU identitní transformací teď vykresluje MESH V NOVÉ (zrcadlené) POLOZE, zatímco zbylých 79 dílů zůstalo na starých souřadnicích ze STARÉ polohy karoserie → karoserie "odjela" pryč a regál zůstal viset ve vzduchu tam, kde dřív byla stěna. **Přesně to je "renders entirely outside the vehicle body shell" - NE jiný druh souřadnicového nesouladu (špatný offset/osa), jak avizovalo varovné hlášení koordinátora - je to ten samý, jediný chybějící 180°/Y flip, potvrzeno i numericky (car_body díly na identitě = surové GLB souřadnice jsou přímo světové, takže flip GLB souboru = flip world pozice karoserie beze změny world pozice ostatních dílů).**

**Recept na opravu (pro kohokoli, kdo `id=53/54/55` znovu vytvoří/najde je znovu živé) - PROVEDENO ANALYTICKY a připraveno jako skript, ALE NEAPLIKOVÁNO na živou DB** (řádky byly v okamžiku pokusu o zápis už zase smazané - psát do prázdna/měnícího se cíle za běhu souběžné práce jiného bota by bylo riskantní přepsání, ne oprava): `scripts/2026-08-31_flip_product_assembly_parts_180.js <in.json> <out.json>` - vezme `product_assemblies.data` JSON, transformuje VŠECHNY díly KROMĚ `car_body_*` (`position: [x,y,z]→[-x,y,-z]`, `quaternion: q180Y·q` stejně jako `scripts/tmp_2026-08-30_flip_assembly_180.js` u CI14), `car_body_*` díly nechá being na identitě BEZE ZMĚNY (mesh je už fyzicky přepsaný/baked, další transformace by ho otočila podruhé zpátky do špatné orientace). Po přepočtu nutné znovu ověřit kolizním testem proti NOVÉ (opravené) geometrii karoserie, teprve pak uložit a republikovat 2D artefakt.

**Pro Roberta/další bota - shrnutí stavu:** `product_assemblies` je momentálně (konec téhle session) prázdná tabulka - nic k opravě live neexistuje. Jakmile bot8 (nebo kdokoli) znovu uloží CI25 regál/y proti UŽ OPRAVENÉ karoserii (současný stav `webapp/katalog/car_bodies/Citroën_Jumpy_CI25_2021-_*.glb`, `zMidB=-2293.2`, OK), stačí stavět přímo v NOVÉM (opraveném) rámci od nuly - kolizní krokování zopakované proti aktuální geometrii dá rovnou správný výsledek, ŽÁDNÝ dodatečný přepočet není potřeba. Skript `2026-08-31_flip_product_assembly_parts_180.js` je pro případ, že by se našla/obnovila stará geometrie postavená PŘED opravou (např. ze zálohy/historie), kterou by bylo levnější přepočítat než stavět znovu od nuly.

### Co NENÍ v tomhle auditu provedeno (záměrně)

- **Žádný z 273 nahlášených modelů (kromě CI25) nebyl fyzicky upraven** - podle zadání jde jen o report kvůli rozsahu (velká dávka souborů, dopad na případné existující `product_assemblies` používající tyhle karoserie by musel být zkontrolován/přepočítán stejně jako u CI14, což je práce navíc na model).
- Audit se soustředí VÝHRADNĚ na orientaci (rotaci) kolem Y - NEKONTROLUJE jiné potenciální problémy modelů (např. zjištěný "CI25 je identická s CI14 i v délce/rozměru, ne jen v orientaci" - to je nález o možná nesprávně přiřazeném/zdvojeném zdrojovém souboru, ne o rotaci, mimo rozsah tohohle úkolu, ale stojí za prošetření zvlášť).
- Reprodukovat/rozšířit audit o nově přidané karoserie: spustit `scripts/2026-08-31_car_body_orientation_audit.js` po obnovení `scripts/2026-08-31_car_bodies_dump.tsv` čerstvým dotazem (příkaz v komentáři na začátku skriptu).

## PŘEKONÁNO/OPRAVENO NÍŽE (bot16, 2026-08-31): CI25 BYLA dodatečně otočena o 180°

Sekce hned pod tímhle odstavcem ("Karoserie CI25 ... NENÍ otočena") popisuje stav PŘED opravou - ponechána beze změny jako historický záznam (rozestupy z kolizního krokování v ní zůstávají použitelné jako VZDÁLENOSTI, ale souřadnicová soustava, ve které vznikly, už neplatí - CI25 je od 2026-08-31 fyzicky otočená stejně jako CI14). Úplný, ověřený test "je karoserie otočená správně" + audit VŠECH karoserií v katalogu na stejný problém + detaily téhle opravy: sekce **"Audit orientace VŠECH karoserií v katalogu (bot16, 2026-08-31)"** na konci souboru.

## Karoserie CI25 (car_bodies 129/130/131) NENÍ otočena — GLB identické s CI14 pred-flip (bot, 2026-08-31) [STAV PŘED OPRAVOU, viz poznámka výše]

Při stavbě regálu na euroboxy pro levou stěnu Jumpy L2 CI25 (`product_assemblies.id=51`) zjištěno: GLB soubory `car_bodies/Citroën_Jumpy_CI25_2021-_{L,R_D,B}.glb` jsou **byte-for-byte identické** (md5 shoda) se zálohou `backups/2026-08-30_car_body_ci14_pre_180_flip/` (tedy s CI14 PŘED jeho 180° flipem). CI25 GLB **nebyla fyzicky rotována** — sestava `id=51` je proto postavena PŘÍMO v této nativní (as-shipped) souřadnicové soustavě, ŽÁDNÝ 180°/MIRROR_C transform. V nativním rámci: přepážka B na Z∈[2024.4, 2562.0] (vysoký konec), otevřený konec vozu u Z≈−147 (nízký konec) — tedy směr "pryč od přepážky" = KLESAJÍCÍ Z (opačná konvence než u CI14's POST-flip souřadnic, kde tomu bylo naopak - nezaměňovat mezi sestavami).

**Fresh kolizní krokování (car_body_placement_methods.id=1) na CI25, i když je geometrie shodná s CI14 pred-flip — čísla NEBYLA převzata, jen ověřením vyšla kompatibilní:** offsetX=425 (hloubka od středu k levé stěně), offsetY=2 (nad podlahou), přední (plná) noha anchorZ=1993 (Z-slab [1993,2023], ~1.4mm rezerva k přepážce). Max. rozpon noh (20mm zpět): REAR_ANCHOR_Z=25 (kolize nalezena na anchorZ=5).

**DALŠÍ NÁLEZ (rozšíření metody `protazeni-zadni-svislice-vyrezove-nohy`, shape_geometry_methods.id=6, viz i KOMPONENTY_EUROBOXY.md):** samotné `Y_new` jedné nohy (zjištěné kolizním krokováním JEN na Z pozici té nohy) nestačí jako podlaha lůžka pro CELÝ sloupec — nosník+spojnice sloupce SPANUJÍ celou Z-délku mezi dvěma nohami a mohou kolidovat s podběhem NĚKDE UPROSTŘED rozpětí víc, než u kterékoli z obou krajních noh. Nalezeno na sloupci mezi nohou1 (Y_new=214) a nohou2 (Y_new=279) Jumpy CI25: leg-based odhad floor=max(214,279)=279 PŘI TOMTO floor nosník+spojnice KOLIDOVALY s karoserií. Oprava: DALŠÍ fresh kolizní krokování (1mm nahoru, +20mm rezerva) přímo na CELÉM nosníku+spojnicích daného sloupce (ne jen v bodech noh) — skutečný floor sloupce vyšel 318mm (o 39mm víc). **Obecné poučení pro budoucí stavby vícepatrových sloupcových regálů:** po zjištění Y_new KAŽDÉ nohy vždy ještě ověřit kolizním krokováním i samotný nosník/spojnice PŘES CELÉ rozpětí sloupce — leg-based floor je nutná, ale NENÍ VŽDY DOSTAČUJÍCÍ podmínka. Zapsáno i do `shape_geometry_methods.id=6` (`version` 4→5).

## Auditní test potvrzen živě na sporném případu VW11/T6 (Robert, 2026-08-31)

Robert zpochybnil rozsah auditu ("Já si pamatuju že naopak byla správně těch karoserií") s odkazem na `Transporter T6 VW11`, kterou 2026-08-23 označil jako "výborně" ve scéně s nohama 512/513. Audit ale VW11 označil jako `NEEDS_FLIP`. Kontrolní vložení SAMOTNÉ karoserie VW11 (bez regálu, `product_assemblies.id=56`) do scény a živé vizuální potvrzení: **"je otočená předkem auta ke mně takže obráceně"** - audit měl pravdu, VW11 skutečně potřebovala flip. Robertovo dřívější "výborně" z 2026-08-23 se týkalo SPRÁVNÉHO umístění nohou vůči podběhu (jiná otázka), ne orientace karoserie při vložení - dvě nezávislé věci, snadno zaměnitelné.

**VW11 opravena** stejným postupem jako CI14/CI25 (180° flip POSITION+NORMAL, záloha `backups/2026-08-31_car_body_vw11_180_flip/`), ověřeno `zMidB=-2121.5` (správně) po opravě.

**Závěr pro další práci:** auditní test (`zMidB` znaménko stěny B vůči defaultní kameře) je DŮVĚRYHODNÝ, potvrzeno na 3 nezávislých případech (CI14, CI25, VW11). Rozsah nálezu (273/304 karoserií potřebuje flip) se považuje za platný, dokud se nenajde konkrétní protipříklad se skutečně čerstvým vizuálním ověřením (ne staré potvrzení, které se mohlo týkat něčeho jiného).

## Berlingo/Partner/Trafic (14 karoserií) — flip potvrzen, RE29 zvláštní nález u MIRROR_X (bot16, 2026-08-31)

Živé ověření `zMid` formule na 3 vzorcích (CI16, PE18, RE28 - B stěna) PŘED hromadnou aplikací potvrdilo shodu s `2026-08-31_car_body_orientation_audit_results.jsonl` (všech 14 „B (" řádků `NEEDS_FLIP`) - flip proveden na všech 42 GLB (`scripts/tmp_2026-08-31_flip_bpt_180.js`), znovu ověřeno `zMid<0` po patchi na všech 14. MIRROR_X (`worldX=offsetX-localX`) aplikován rovnou od začátku (dle nálezu z Vivaro pilotní session, `car_body_placement_methods.id=1`).

**Nález u Renault Trafic RE29 (L2), NENÍ chyba MIRROR_X:** kolizní krokování "stěna" (krok 1c) u RE29 skončilo na `offsetX=+805` (kladná strana X), zatímco RE28 (L1, stejná rodina) skončilo na `offsetX=-325` (záporná strana) - na první pohled vypadá jako obrácené znaménko/stranovost. Přímá kontrola (`collidesWithWalls` na kandidátních `offsetX` od -325 do +800 na Z blízko přepážky) potvrdila: prostor je VOLNÝ (bez kolize) na celém intervalu od -325 do +600, kolize začíná až kolem +700. Krokovací algoritmus (1mm dolů od bezpečného seedu, zastaví na PRVNÍ kolizi) narazil nejdřív na tuhle izolovanou překážku (offsetX≈700), ne na skutečnou vnější boční stěnu (ta je dál, blíž k -970 dle `boxL0.min.x`). Příčina: GLB mesh "L" u RE29 (na rozdíl od RE28) obsahuje geometrii (pravděpodobně B-sloupek/kolejnice posuvných dveří specifickou pro delší L2 karosérii) zasahující neobvykle blízko ke středu vozu těsně u přepážky. Výsledná noha je fyzicky validní (bezkolizní), jen posazená blíž ke středu než by šlo teoreticky dosáhnout. **Poučení pro příští práci s podobnou karoserií:** jednoduché monotónní 1mm krokování se nechá "nachytat" izolovanou překážkou (sloupek/nosník) mezi seedem a skutečnou vnější stěnou - pokud výsledný `offsetX` vychází nečekaně (např. jiné znaménko než u sesterské varianty), stojí za to explicitně proskenovat celý interval (ne jen věřit prvnímu nalezenému kolizi) a rozlišit "skutečná vnější stěna" od "izolovaná vnitřní překážka".

## Ford Custom/Transit Custom + VW Transporter T6/T7 (22 karoserií) — flip + MIRROR_X živě změřeno per model (bot16, 2026-08-31)

Živě přeměřeno `zMidB` na všech 22 zadaných modelů (13 Custom + 9 Transporter) - 15/22 `NEEDS_FLIP` (flip proveden, zálohy `backups/2026-08-31_car_body_custom_transporter_180_flip/`), VW11 potvrzen jako už flipnutý z dřívější session (`zMidB=-2121.5`), zbytek (FO11/FO29/FO55/FO56/VW42/VW43) nativně OK.

**MIRROR_X měřeno NEZÁVISLE na flip-verdiktu pro každý model** (`scripts/tmp_2026-08-31_check_L_wall_x_sign.js`, živé `sign` středu stěny L) - 18/22 potřebuje `worldX=offsetX-localX`. Důležitý nález: **FO11 a FO29 NEpotřebovaly flip, ale PŘESTO potřebují mirror-X** (stěna L na nich vyšla na záporné X i bez fyzického otočení karoserie) - potvrzuje, že mirror-konvence a flip-potřeba jsou dvě NEZÁVISLÉ vlastnosti GLB geometrie, jedna se nedá odvodit z druhé, obě je nutné měřit zvlášť na KAŽDÉM modelu.

**Nová oprava metody `max_rozpon_nohou` (car_body_placement_methods.id=1) — podběh jako izolovaný ostrov UPROSTŘED korby:** na Ford Custom FO11 (cargo 2921mm) prosté krokování-do-první-kolize dalo `REAR_ANCHOR_Z` jen 1400mm (mylně vzalo ~950mm hluboký podběh uprostřed korby za konec vozu). Oprava: při první kolizi zkusit lookahead (do 2500mm po 50mm) a POTVRDIT, že za bodem uvolnění existuje DALŠÍ skutečná kolize (ne jen prázdný prostor za koncem modelu) - pokud ano, pokračovat odtud. Po opravě FO11 vyšel `REAR_ANCHOR_Z=83` (maxSpan=2478mm), realisticky odpovídající 2921mm cargo_length.

**Nová oprava — fyzický konec MODELOVANÉ geometrie jako fallback pro krátké/otevřené korby:** na VW15 (T6 Kombi Crew Van) sonda nenašla ŽÁDNOU kolizi (rovnoběžné stěny až k plně otevřenému konci, žádný "roh"). Přidán fallback: pokud sonda dojede až na hranu modelované geometrie stěny L bez kolize, použije se tahle hrana (s 20mm rezervou) jako `REAR_ANCHOR_Z`.

Detail (přesná čísla, 17/22 postavených sestav, 5/22 legitimních "nesedí" vč. Ford/VW T7 sdílené platformy Multicab/L-Partition) v `KOMPONENTY_EUROBOXY.md` a `AGENTS_LOG.md`, bot16 2026-08-31.

## Chyba: regál Trafic L2 (RE29) postaven mimo levou stěnu — vadná GLB data (Robert, 2026-09-01)

Robert: "nektery trafic mel regal uplne mimo levé strany." Zjištěno: `product_assemblies.id=104` (Trafic L2 RE29) měl nohy na X∈[471.6, 790.6], zatímco `id=103` (Trafic L1 RE28, stejná šířka/výška vozidla, jen jiná délka) měl správně ověřené nohy na X∈[-659.8, -340.8] — stejné vnitřní rozestupy (159.5mm), jen úplně jiný absolutní offset (přesně o 1131.4mm).

**Root cause:** GLB soubor `Renault_Trafic_RE29_2026-_L.glb` (stěna "L") obsahuje 13 odlehlých vrcholů u X≈426.6mm, zatímco naprostá většina (16000+ vrcholů) leží v pásmu X∈[-970,-600] - reálný tvar stěny. Tenhle drobný datový artefakt (vadná/přebytečná geometrie v souboru) rozšířil `Box3` bounding box stěny L nesmyslně daleko do kladného X, což zmátlo výpočet offsetu při stavbě regálu u RE29 (na rozdíl od RE28, jehož GLB tenhle artefakt nemá).

**Oprava:** posunuto o -1131.4mm v ose X (přeneseno z už ověřeného RE28, stejný příčný profil vozidla - jen jiná délka, X-profil identický). Nohy teď sedí na stejném X jako RE28. **Nebyl proveden nezávislý plný re-run kolizního krokování** (jen přenos ověřené hodnoty ze sourozeneckého vozidla) - pokud by se v budoucnu chtělo nezávisle přepočítat, potřeba nejdřív vyčistit/ignorovat odlehlé vrcholy v `Box3` výpočtu stěny.

## Doplnění chybějících `official_door_opening_height_mm` pro modely s postaveným eurobox regálem (bot16, 2026-09-01)

Robert: "kde chybí oficiální výška dveří, musíme dohledat na webu (u ofic dealerů) ČR" - navazuje na `shape_geometry_methods.id=8` (výška nohy podle výšky dveří), který 41 řádků z nočního auditu přeskočil právě kvůli chybějící kótě (viz `AGENTS_LOG.md`, bot16 2026-09-02 zápis o aplikaci id=8).

**Rozsah:** ze 161 `legacy_vendor_code` s `official_door_opening_height_mm IS NULL` v celém katalogu (300+ karoserií) vytipováno 23 kódů, které SKUTEČNĚ mají postavený eurobox regál (cross-referencováno `product_assemblies.data` - extrakce `car_body_<id>` odkazů → `karoserie_model_reference.legacy_vendor_code`). Pouze na těchto 23 se soustředila práce, ve shodě se zadáním "prioritizovat těch ~30 kódů, co mají postavený regál, než širší katalog".

**Nalezeno a zapsáno do DB (17 kódů), vždy stejný typ dveří jako u sourozeneckých variant ve stejné modelové řadě (zadní dvoukřídlé/výklopné dveře, ne boční posuvné - konvence zavedená u Jumpy/Expert/Custom):**

- **OP18 (Vivaro L3H1 19-) = 1220mm** - stejný oficiální zdroj (`opel.cz CZ_Vivaro_Van.pdf`) jako sourozenci OP19/OP20 (stejná H1 střecha, jen jiný rozvor), nezávisle potvrzeno druhým oficiálním dealerským ceníkem Opel (`autodobrovolny.opeldealer.cz`, vydání 1/2026) - identická hodnota 1220mm napříč všemi zobrazenými délkami karoserie u H1 střechy.
- **TO22 (Proace Long Electric 20-), TO23 (Proace Compact Electric 20-) = 1220mm** - oficiální CZ katalog Toyota (`pdf.sites.toyota.cz/proace-katalog.pdf`) potvrzuje 1220mm shodně napříč L1/L2 diesel; kombinace se sourozenci TO07-09/12/17 (diesel, všechny délky) i TO21 (Medium Electric, ze samostatného UK tech-spec PDF) potvrzuje, že kóta je neměnná napříč délkou karoserie I pohonem (diesel vs. elektro) u tohoto vozidla.
- **PE02, PE03 (Partner L1/L2 -18) = 1148mm** - oficiální Peugeot "Prices, Equipment and Technical Specifications" (listopad 2015, `charterspeugeot.com` - autorizovaný dealerský mirror originálního výrobcova dokumentu, ověřeno metadaty PDF), řádek "Load height of rear opening", shodné pro L1 i L2.
- **PE18, PE19 (Partner L1/L2 19-), PE23, PE24 (e-Partner L1/L2 21-) = 1196mm** - oficiální Peugeot "Prices, Equipment and Technical Specifications" MY20.5 (únor 2020, CDN `d1amhj1m505d5v.cloudfront.net`), řádek "Maximum load height of rear opening", Panel Van & Crew Van, shodné pro L1/L2. e-Partner nemá vlastní samostatný zdroj - použita stejná generace/karoserie jako diesel Partner 19- (elektro varianta nemění karoserii/dveře, stejný vzor jako Toyota Proace/Proace Electric výše).
- **VW11, VW12 (Transporter T6 L1/L2 -23) = 1299mm** - `volkswagenprestavby.cz` (oficiální zdroj rozměrů VW Užitkové vozy pro karosářské nástavby), Transporter 6.1 rozměry, "Výklopné dveře nákladového prostoru" 1473×1299mm shodně pro L1 i L2 se základní (nízkou) střechou.
- **VW13, VW14 (Caddy/Caddy Maxi -20, 4. generace) = 1134mm** - `volkswagenprestavby.cz`, Caddy 4. generace skříňový vůz rozměry, "Zadní výklopné dveře" 1183×1134mm shodně pro Caddy i Caddy Maxi.
- **VW21, VW22 (Caddy Cargo/Cargo Maxi 21-, 5. generace) = 1122mm** - `volkswagenprestavby.cz`, Caddy Cargo 5. generace rozměry, "Zadní dveře, křídlové" 1234×1122mm (druhá nabízená varianta "výklopné" = 1130mm, zvolena křídlová jako přísnější/nižší); nezávisle potvrzeno shodou s Ford Transit Connect 24- (FO36/37/45/46, `ford.cz`, 1122mm), sdílená platforma Ford/VW.
- **VW31, VW32 (Caddy Cargo/Cargo Maxi PHEV 24-) = 1122mm** - PHEV nemá vlastní zdroj, sdílí identickou karoserii/dveře s diesel Caddy Cargo 21- (stejný vzor jako e-Partner/Proace Electric výše).

**Nenalezeno, ponecháno `NULL` k 2026-08-31 (6 kódů, žádné hádání/nízko-důvěryhodné zdroje) - VŠECH 6 DODATEČNĚ DOHLEDÁNO A ZAPSÁNO (audit bot9 2026-09-12 ověřil `AGENTS_LOG.md` ř. 19800, zápis 2026-09-03):**

- **FO21, FO27 (Transit Custom L2H2/L1H2 12-, vysoká střecha H2)** a **FO28, FO29 (Transit Custom L2/L1 DCiV 12-, crew van)** - starší generace Ford Transit Custom (2012-2018). Oficiální ford.cz ceník (`PL-new_transit_custom_van.pdf`, stejný zdroj jako sourozenci FO10/FO11 = 1314mm pro H1 střechu) je nedostupný z tohoto prostředí (timeout/blokace, opakovaně i přes `archive.org` - rate-limit 429), žádný jiný oficiální zdroj (ford.co.uk brožury, media.ford.com) pro TUHLE konkrétní starou generaci/H2 varianty/DCiV nebyl dohledán - jen nespolehlivé agregátory (parkers.co.uk, vanguide.co.uk, swissvans.com) s VZÁJEMNĚ ROZPORNÝMI čísly (1706mm vs. 1814mm pro H2), proto NEPOUŽITO K 2026-08-31. **DOPLNĚNO 2026-09-03: FO21/FO27=1706mm, FO28/FO29=1347mm** (dobové Ford UK brožury, ověřeno křížově), zapsáno do `karoserie_model_reference.official_door_opening_height_mm`.
- **RE28, RE29 (Trafic Van E-Tech Electric L1/L2 26-)** - zbrusu nový model (2026), oficiální ceník nalezen a stažen (`cdn.group.renault.com/ren/cz/pdf/pricelists/trafic-van-e-tech-elektricky-cenik.pdf`, platnost od 26.1.2026) a úspěšně přečten (`pdftotext`), ale obsahoval K 2026-08-31 POUZE výšku bočních posuvných dveří (1284mm), NE výšku zadních křídlových dveří, kterou používá konvence zavedená u sourozeneckého diesel Trafic (RE14/RE15 = 1320mm "výška křídlových dveří", ne bočních 1284mm ze stejného zdroje). Použití bočního rozměru místo zadního by porušilo konzistenci typu dveří napříč modelovou řadou - ponecháno NULL K 2026-08-31. **DOPLNĚNO 2026-09-03: RE28/RE29=1320mm** (oficiální švýcarský ceník Renault, PDF), zapsáno. Poznámka z téhož zápisu: existující postavená noha má H≈1250mm, tedy 70mm nevyužité rezervy - neaplikováno na existující veřejné sestavy, samostatné posouzení.

**Poznámka k dalšímu kroku (NEPROVEDENO zde, záměrně):** aplikace `shape_geometry_methods.id=8` (přizpůsobení výšky nohy nově doplněným kótám) je samostatný navazující krok, který koordinátor spustí odděleně (vyžaduje pečlivou kolizní kontrolu per noha, riziko kolize při souběžném běhu s touhle datovou opravou) - viz `AGENTS_LOG.md`.

Skript: `/tmp/.../scratchpad/apply_door_heights.py` (dočasný, DB update přes `api/venv/bin/python3` + `pymysql` + `api/.env`, stejný vzor jako ostatní noční skripty).

**Obecné poučení:** `Box3().setFromObject()` na reálné GLB geometrii může být zkreslený i pár desítkami odlehlých vrcholů (byť jde o zlomek z tisíců) - u nových/neprověřených GLB souborů je vhodné kontrolovat histogram vrcholů (ne jen min/max), podobně jako se to dělalo u detekce podběhu dřív v projektu.

## Pravidlo profilů - ORIENTACE REGÁLU: přední vs. zadní strana (Robert, 2026-09-06, po vzorku turntable renderu "zezadu")

Robert doslovně: **"výřez v noze je zadní část, svislý nejdelší profil
nohy je přední část, horní výsek tzn. zúžený horní blok je vykrojen
dozadu... ulož si to do pravidel pro další sessions, aby nerenderovali
zezadu."**

- **Zadní strana (u stěny karoserie)** = noha s výřezem (`.vyrez`,
  přerušená spodní svislice, `cap`/`zadni-svislice*`).
- **Přední strana (otevřená, odkud se vytahují boxy)** = nejdelší
  svislý profil nohy (`predni-svislice`).
- **Zúžený horní regálový blok** je vykrojený DOZADU (sleduje zúžení
  stěny karoserie), ne dopředu.

**Důsledek pro rendery/kamery/turntable (`scene.html` `paRenderTurntable`,
`api/turntable.py`):** hero/výchozí pohled i střed azimutové výseče MUSÍ
být z přední strany. Nikdy neurčovat přední stranu pevným úhlem ani ze
znaménka X v `product_assemblies.data` - u Jumpy sestav (id=187/188) má
`predni-svislice` x=−440 > `cap` x=−666, přesto v render rigu vychází
přední strana na **azimut 270°** (kamera `x = cx + d·cos(el)·sin(az)`), a
původní hero (el 20 / az 60) byl pohled ze strany stěny. Přední normálu
spočítat z vyrenderovaných dílů podle rolí (`shape.parts[i].role` má
stejné pořadí jako `newEntries[i]` z `insertCustomShape`): směr od
`cap`/`zadni-svislice` k `predni-svislice` ve world souřadnicích rigu.
Výseč 270° (Robert 2026-09-06: "nepotřebujeme vidět regál zezadu") =
vynechat 90° kolem zadní strany. `CANONICAL_VIEWS` měl tenhle problém
("zezadu" napevno az=240, u Jumpy ve skutečnosti zezadu není) jen DO
2026-09-06 - OPRAVENO (audit bot9 2026-09-12 ověřil `api/turntable.py`):
`_canonical_views_for_front(FRONT_AZIMUTH_DEG)` počítá azimut dynamicky
podle přední strany dané sestavy, ne napevno.

## ⭐ ZÁVAZNÉ pravidlo (Robert 2026-09-08): NIKDY nerenderovat karoserii

**"pravidlo: NIKDY nerenderujeme karoserii !!!!!!!!"** — žádný render
(turntable, náhled, demo screenshot, obrázek posílaný Robertovi nebo
kamkoli ven) NESMÍ obsahovat geometrii karoserie vozidla — ani jako
plnou plochu, ani průhlednou/wireframe pro "kontext". Reálně chyceno
2026-09-08 (bot8): render sestavy "Doblo K-075 A" s logem LOGIMAN.CZ
zahrnoval karoserii jako průhlednou siluetu "pro kontext" — přesně
tohle je zakázané.

**Platí pro VŠECHNY renderovací nástroje v tomhle projektu** (vlastní
`scripts/*_render*.html`/`scripts/2026-08-20_section_cut.js`/
`scripts/2026-08-20_live_section_cut.js`, i budoucí) — ne jen pro
oficiální e-shopovou otočku (`api/turntable.py`). Do renderu smí jít
JEN sestava/regál samotný (profily, boxy, MDF výplně, doplňky) — u
technických řezů/kolizních kontrol se karoserie samozřejmě dál MĚŘÍ
(raycast, `collidesWithWalls`) a její rozměry se PROMÍTAJÍ do pozic
dílů, ale sama geometrie karoserie se nikdy nekreslí/nezobrazuje ve
výsledném obrázku.
