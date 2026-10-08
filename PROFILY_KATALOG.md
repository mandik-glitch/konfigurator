# Katalog profilů — rozměry, drážky, kompatibilita

Fakta specifická pro konkrétní typy profilů (ne obecná geometrie spojů — ta je v `PRAVIDLA_SPOJU.md`): řezání/max délka, tabulka drážek a kompatibility, přestavba tvaru na jiný profil se zachováním rozměrů, a zatím prázdné placeholder sekce (orientace, nosnost, povrch, otvory/hardware). Vydělené z `VLASTNOSTI_PROFILU.md` 2026-08-31.

## 1. Řezání a délka
- **Každý profil je definovaný svým průřezem (např. 40×40 mm) — délka je libovolná.** Katalogový GLB model (aktuálně standardizovaný na 1000 mm) je jen referenční vzorek, ne fixní rozměr dílu.
- **Maximální délka: 3000 mm.** Minimum a tolerance řezu zatím nejsou určené *(čeká na doplnění, není blokující)*.

> **Dopad na appku (poznámka pro mě):** katalog v DB teď má u všech profilů standardizovaný 1000mm vzorek + spočítaný průřez. Appka zatím vkládá díly ve vzorové délce beze změny. Přidání "zadej si délku (max 3000mm)" při vkládání je další krok, zatím neimplementováno.

## 2b. Tabulka: drážky a kompatibilita profilů

⚠️ **OPRAVENO (audit bot9, 2026-09-12): sloupec "ID v katalogu" byl zastaralý.** Katalog dnes (`SELECT id,name FROM cfg_dily WHERE layer='alu' AND dim_y_mm=1000`) má **26 alu profilů / 11 unikátních průřezů** (ne 11/15) - přibyly nové varianty (radius, uzavřený, light, zkosený) a některá `Object_N` ID byla přejmenována/nahrazena. Drážka/kompatibilita (Robertem potvrzené) zůstávají beze změny, jen ID sloupec aktualizován na skutečně existující id:

| Průřez (mm) | ID v katalogu (ověřeno živě 2026-09-12) | Drážka | Potvrzený produkt |
|---|---|---|---|
| 10x40 | **v katalogu dnes NEEXISTUJE** (`Object_6` smazán/přejmenován, žádný `dim_x=10,dim_z=40` řádek nenalezen) | **6 mm** | [Profil 10×40 (deskový)](https://www.logiman.cz/deskove-hlinikove-profily/hlinikovy-stavebnicovy-profil-10-x-40-x-3000-mm/) — kód 1.1.06.010040.07, materiál 6063 T5, 0.55 kg/m. Technický výkres průřezu od Roberta: šířka 40 / výška 10 / rozteč drážek 20 mm, hrdlo drážky 6,4 mm, stěna 1,4 mm, otvor Ø3,2 mm. |
| 20x20 | `profil_20x20` (+ `profil_20x20_radius`) | **6 mm** | [Profil 20×20](https://www.logiman.cz/hlinikove-profily-s-drazkou-6mm/hlinikovy-stavebnicovy-profil-20x20/) |
| 20x40 | `profil_20x40` | **6 mm** | [Profil 20×40](https://www.logiman.cz/hlinikove-profily-s-drazkou-6mm/hlinikovy-stavebnicovy-profil-20x40/) |
| 20x80 | `profil_20x80` | **6 mm** | [Profil 20×80](https://www.logiman.cz/hlinikove-profily-s-drazkou-6mm/hlinikovy-stavebnicovy-profil-20x80/) |
| 30x30 | `Object_7` (+ `profil_30x30_radius`, `profil_30x30_uzavreny`) | **8 mm (Light)** | [Profil 30×30 Light](https://www.logiman.cz/hlinikove-profily-s-drazkou-8mm/hlinikovy-stavebnicovy-profil-30x30-light/) |
| 30x60 | `Object_1` | **8 mm** | [Profil 30×60](https://www.logiman.cz/hlinikove-profily-s-drazkou-8mm/hlinikovy-stavebnicovy-profil-30x60/) |
| 35x35 | `profil_35x35` | **8 mm** | [Profil 35×35](https://www.logiman.cz/hlinikove-profily-s-drazkou-8mm/hlinikovy-stavebnicovy-profil-35-x-35-x-3000-mm/) |
| 40x40 | `Object_11` (+ `profil_40x40_light_s10`, `_uzavreny_s10`, `_zkoseny_s10`) | **10 mm (SuperLight S10)** | [Profil 40×40 SuperLight S10](https://www.logiman.cz/hlinikove-profily-s-drazkou-10mm/hlinikovy-stavebnicovy-profil-40x40-superlight-s10/) |
| 40x80 | `Object_14` (+ `profil_40x80_light_s10`) | **10 mm (SuperLight S10)** | [Profil 40×80 SuperLight S10](https://www.logiman.cz/hlinikove-profily-s-drazkou-10mm/hlinikovy-stavebnicovy-profil-40-x-80-x-3000-mm-superlight-s10/) |
| 45x45 | `Object_2` (+ `profil_45x45_light_s10`, `_radius`, `_uzavreny_s10`) | **10 mm** | [Profil 45×45](https://www.logiman.cz/hlinikove-profily-s-drazkou-10mm/hlinikovy-stavebnicovy-profil-45x45-superlight-s10/) |
| 45x90 | `profil_45x90_light_s10` (+ `_superlight_s10`) | **10 mm** | [Profil 45×90](https://www.logiman.cz/hlinikove-profily-s-drazkou-10mm/hlinikovy-stavebnicovy-profil-45x90-superlight-s10/) |

Navíc přibyl **`profil_25x25`** (25×25mm) - drážka/kompatibilita s ním zatím Robertem nepotvrzená, není v tabulce kompatibility níže.

**Kompatibilita spojů** — potvrzeno Robertem. ✓ = lze spojit kolmo, ✗ = nelze. Vzor: každý profil jde spojit sám se sebou, a čtvercové profily navíc se svým "dvojnásobným" protějškem ve stejné drážkové rodině (20x20+20x40, 30x30+30x60, 40x40+40x80, 45x45+45x90 — sloupek + příčka/rám). Toto pravidlo je od teď **závazné** a je vynucené jak v promptu pro 3Dbota (AI modul), tak tvrdě na serveru (viz kód `/api/ai/generate`) — nekompatibilní spoj se automaticky zahodí/rozpojí, i kdyby ho AI navrhla:

| profil | 10x40 | 20x20 | 20x40 | 20x80 | 30x30 | 30x60 | 35x35 | 40x40 | 40x80 | 45x45 | 45x90 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **10x40** | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| **20x20** | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| **20x40** | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| **20x80** | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| **30x30** | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| **30x60** | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| **35x35** | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ |
| **40x40** | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ | ✗ | ✗ |
| **40x80** | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ | ✗ | ✗ |
| **45x45** | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |
| **45x90** | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |

**OPRAVENO (audit bot9, 2026-09-12): tvrzení o vrstvách "black"/"zinc" neplatí.** `cfg_dily` dnes (`SELECT layer, COUNT(*) FROM cfg_dily GROUP BY layer`) má jen `layer='alu'` (26 řádků) a prázdný `layer=''` (5 řádků) - žádný `black` ani `zinc` řádek v `cfg_dily` neexistuje (materiálové vrstvy `black`/`zinc` zmíněné jinde v projektu se týkají `shop_products.color_hex`/materiálového panelu ve scéně, ne téhle katalogové tabulky profilů). Ověřit živě před dalším zápisem.

## 2c. Kanonické SKU pro řez/schéma (jednoznačnost `shop_products` ↔ `cfg_dily`)

**Robert, 2026-09-26** (po nálezu bot7: galerie produktu ukazovala technické schéma s **drážkou 8 mm místo skutečně použité 10 mm** u 40×40 — `fcda1a9d`, kontext v `AGENTS_LOG.md` heslo "Kanonický profil pro řez/schéma"). Příčina: k jednomu nominálnímu průřezu existuje v `shop_products` **víc SKU** (různé drážkové rodiny `groove_family` i víc variant ve stejné rodině — Light/Heavy/uzavřený/radius/zkosený), a řazení podle SKU je nespolehlivé (`"1.1.08..."` < `"1.1.10..."` lexikálně vyhraje vždy, i když se ve scéně reálně používá drážka 10). `shop_products.cfg_dily_id` → `cfg_dily.visible_in_scene=1` sice ukazuje na skutečně použitý díl, ale u 30×30 samo o sobě nestačí (dva kandidáti s `visible_in_scene=1`: `.03` plain Light a `.05` uzavřený).

Robert proto **napevno diktoval** kanonické SKU (bez výjimky) — použít je všude, kde se z průřezu dohledává KONKRÉTNÍ produktová karta pro technické schéma/řez (typicky galerie karty, `api/products.py`):

| průřez | kanonické SKU | `cfg_dily_id` | `groove_family` |
|---|---|---|---|
| 30×30 | `1.1.08.030030.03` | `Object_7` | 8 (Light — správně, 30×30 tuhle rodinu jinou nemá, viz tabulka výše) |
| 40×40 | `1.1.10.040040.03` | `Object_11` | 10 (SuperLight S10 — **ne** `1.1.08.040040.03`, ta SKU na drážku 8 existuje jako úplně jiný, do scény nenapojený produkt, `cfg_dily_id IS NULL`) |
| 45×45 | `1.1.10.045045.03` | `Object_2` | 10 (SuperLight S10) |

Ověřeno živě (bot8, 2026-09-26): všechny tři SKU sedí přesně na `cfg_dily_id`/`visible_in_scene=1`/`groove_family` výše, žádný rozpor. **Není to obecné pravidlo "drážka 10 > drážka 8"** — je to fixace KONKRÉTNÍ SKU per průřez, protože jde o disambiguaci, ne o preferenci drážky (u 30×30 kanonická SKU sama drážku 8 má, protože to je jediná reálně používaná 30×30 rodina).

## 3. Orientace a natočení
- Má profil symetrický průřez (jedno rotace stačí), nebo záleží na natočení (např. drážka musí směřovat určitým směrem)?
- Jaké natočení dává smysl (0/90/180/270°, nebo libovolné)?

## 4. Nosnost a zatížení
- Max. zatížení / rozpětí bez podpory?
- Existují kombinace (délka × průřez), které jsou konstrukčně nevhodné?

## 5. Povrchová úprava a materiály
- Jaké povrchové úpravy/barvy jsou u alu profilů dostupné?
- Které materiály (alu/black/zinc) se smí kombinovat v jedné sestavě a které ne?

## 6. Otvory, drážky, upevnění hardwaru
- Standardní rozteč drážek/otvorů pro uchycení konzol a krytek?
- Kam přesně na profil smí konzola/krytka sednout (jen konce, nebo kdekoli podél délky)?

## 7. Ostatní limity
- Cokoli dalšího, co appka musí hlídat, aby nenavrhla nesmysl.

---
*Založeno automaticky, čeká na vyplnění od Roberta.*

## Pravidlo profilů - PŘESTAVBA TVARU NA JINÝ PROFIL, se zachováním vnějších rozměrů (Robert, 2026-08-30, po noze Jumpy z profilu 30x30)

Zapsáno do DB jako nová tabulka `shape_geometry_methods` (stejný vzor jako `car_body_placement_methods`, ale pro jinou třídu úloh) - `name='prevod-profilu-zachovanim-rozmeru'`, `id=1`, `version=1`, `verified_by='robert'`. Úkol: existující tvar poskládaný z profilu (např. noha z 40x40) přestavět na JINÝ profil (30x30) se zachováním zadaných vnějších rozměrů (u nohy Jumpy: výška 1180mm, hloubka 349mm). **Není to výměna reference na jiný katalogový model** - spoje (T-styl, cap-styl) závisí na tloušťce profilu, pozice každého segmentu se musí přepočítat.

**5 kroků:**
1. ZMĚŘ (neodhaduj) přesný box KAŽDÉHO segmentu původního tvaru na skutečné GLB geometrii (`THREE.Box3().setFromObject`, ne z hrubých position/scale čísel) - z boxů urči topologii (které segmenty jsou svislé plné/zkrácené, které jsou vodorovné příčníky, jaké existují speciální detaily jako "cap" díl nebo náhradní zkrácený sloupek).
2. ROZDĚL každý rozměr na dva druhy: (a) FYZIKÁLNĚ/DESIGNOVĚ PEVNÉ rozměry - nezávisí na tloušťce profilu T (zadaná celková šířka/výška, reálná světlá výška zářezu pro podběh, reálná hranice úskoku sloupku před překážkou) - ZŮSTÁVAJÍ při změně T beze změny; (b) NA TLOUŠŤCE ZÁVISLÉ rozměry - odvozené přímo z T (délka vodorovného příčníku mezi dvěma svislicemi = CELKOVÁ_ŠÍŘKA − 2×T).
3. PŘEPOČTI pozice všech segmentů pro nové T - u KAŽDÉHO segmentu dotýkajícího se VNĚJŠÍ hrany tvaru (podlaha, strop, okraj šířky) OVĚŘ, že jeho střed je T_NOVÉ/2 od té hrany (polovina tloušťky, ne celá).
4. OVĚŘ `touchReport()` (gap/overlap na všech 3 osách) pro KAŽDÝ spoj na SKUTEČNÉ geometrii nového profilu - platný plochý spoj = přesně JEDNA osa gap=0/overlap=0, zbývající DVĚ osy PLNÝ přesah. Žádný tvar se neukládá, dokud tohle neprojde na všech spojích.
5. Ulož jako NOVÝ `custom_shapes` záznam (název = původní + prurez, např. "...349.30x30"), NE přepsat původní - obě varianty zůstávají vedle sebe.

**Skutečná chyba nalezená Robertem vizuálně (2026-08-30, ne self-review):** u DOLNÍHO vodorovného příčníku (ležícího přímo na podlaze, Y=0) byl kód napsán s chybným středem Y=T (celá tloušťka) místo správného Y=T/2 (polovina tloušťky) - příčník zůstal moc vysoko nad podlahou. HORNÍ příčník (u vrcholu) měl správný vzorec (`H − CAP_H − T/2`) už od začátku - nekonzistence mezi dvěma analogickými segmenty ve STEJNÉM skriptu byla přesně ten signál, že jde o chybu v kódu, ne o nejednoznačnost designu. **Poučení: každý segment dotýkající se vnější hrany (podlaha, strop, boční kraj) má svůj střed VŽDY přesně T/2 od té hrany - ověřuj to explicitně na vypočteném `Box3` (min.y by mělo vyjít 0.000, ne T/2), ne jen na vzorci v kódu.**

**Příklad (noha Jumpy, 2026-08-30):** `custom_shapes` 503/504 (40x40, `Object_11.glb`) → 526/527 (30x30, `Object_7.glb`). Zachované pevné rozměry: výška H=1180, šířka W=349, výška cap dílu=260, světlá výška zářezu=395, odsazení cap dílu od kraje příčníku=30 ~~(OPRAVENO, viz níže)~~, hranice úskoku sloupku=225. Na tloušťce závislé vzorce: délka příčníku = W−2T, střed při podlaze/stropu = T/2 od té hrany. Odsazení cap dílu (30mm) a hranice úskoku (225mm) u PŮVODNÍ 40x40 verze pravděpodobně vycházely z referenční fotky, kterou bot neměl k dispozici - převzato jako FIXNÍ (neškálované s T), geometricky konzistentní a bezkolizní, ale NEOVĚŘENO proti fotce.

**OPRAVA (2026-08-30, druhá chyba - nalezena AŽ přesným srovnávacím testem, ne self-review):** "odsazení cap dílu od kraje příčníku = 30mm" bylo ve skutečnosti kotvené k VNITŘNÍ hraně horního příčníku (`rungHi = W−T`), což je TLOUŠŤCE-ZÁVISLÁ souřadnice - u různých T tak cap vycházel na jiném absolutním místě. Robertovo pravidlo pro srovnávání profilů ("2D srovnávání je k tomu abychom doladili tvůj výpočet polohy pozice délek atd, takže finální přepočítaná noha z jiného profilu musí sedět na milimetr podle těchto testů") odhalilo důsledek: při kolizním krokování směrem ke stěně 40x40 a 30x30 kolidovaly RŮZNÝMI fyzickými částmi (40x40 zadní svislicí, 30x30 capem) → rozdílná finální pozice X i na identickém Z (2-3mm rozdíl). **Správná kotva: FIXNÍ vzdálenost 70mm PŘÍMO OD VNĚJŠÍ HRANY W** (T-nezávislá) - stejný princip, jaký už byl od začátku správně použitý u hranice úskoku sloupku (124mm od W). Po opravě: kolizní krokování na identickém Z dává PŘESNĚ STEJNÉ X u obou profilů (402mm/401mm, rozdíl 0.0mm, ověřeno `scripts/tmp_2026-08-30_precise_match_test.js`). `custom_shapes` 526/527 přepsány s opravenou geometrií, `product_assemblies.id=32` (srovnání 40x40 vs 30x30, sestava mezitím smazána 2026-08-31 "vymaž vsechno z auta" - OPRAVENO audit bot9 2026-09-12) přestaven, `shape_geometry_methods.id=1` → dnes `version=4` (`verified_by='bot16'`). **Obecné poučení:** každý vnitřní prvek reprezentující fyzickou/funkční vůli VŮČI VNĚJŠÍ HRANĚ (stěna, strop, kraj) musí být kotven vzdáleností OD TÉ VNĚJŠÍ HRANY PŘÍMO, nikdy od jiného vnitřního prvku, jehož vlastní pozice je už sama T-závislá - jinak se T-závislost "prosákne" přes řetězec odvozených pozic a projeví se až na fyzickém kolizním testu, ne na `touchReport()` (ten kontroluje jen spoje MEZI segmenty stejného tvaru, ne absolutní pozici vůči vnějšímu okolí).


## Pravidlo profilů - VÝPLNĚ DO DRÁŽEK: co dnes chybí (bot8, 2026-09-05, zjištěno měřením)

Robert 2026-09-05 zadal další verzi regálu: *„přidat stěny z plastové desky
8mm nebo mdf 8mm"* + *„do drážek profilů"*. Zadání je systémově správné —
regál na euroboxy stojí z profilu **30×30 Light, který má drážku 8 mm** (viz
tabulka výše), takže 8mm deska do něj patří. Realizaci ale dnes brání tři
věci, všechny ověřené, ne odhadnuté:

**1. Deska 8 mm v katalogu už EXISTUJE (OPRAVENO audit bot9, 2026-09-12).** Deskové materiály jsou v katalogu
tři: `PR10` (`shop_products.id=3539`, 10 mm, arch 1250×2500),
`Laminovaná deska šedá 25mm` (`id=3671`, 25 mm, arch 2070×2800) a od
2026-09-05 **`MDF deska Steel Grey 8mm`** (`id=3939`, `cfg_dily_id='deska_mdf_seda_8'`, `visible_in_scene=1`). Bod 1 a 2 (viz níže) jsou tím vyřešené, zbývá jen bod 3 (svislé panely a `GROOVE_INSERT_DEPTH_MM` pro 8mm rodinu).

**2. Stávající deska patří k JINÉ drážkové rodině.** `PR10` je 10 mm, tedy
pro profily s drážkou 10 mm (40×40, 40×80, 45×45, 45×90). Do drážky 8 mm
u 30×30 / 30×60 / 35×35 se nehodí. Robertových „8 mm" je pro tenhle regál
správně — jen ten materiál v katalogu není.

**3. Svislé panely (stěny) zatím NEJDOU vložit.** `webapp/js/scene/auto-deska.js`
(tlačítka „🪵 Deska do drážky" / „🪵 Deska na profily") umí **jen vodorovné**
vsazení; svislé je explicitně odmítnuté hláškou na řádcích 100 a 141:
*„Tahle verze podporuje jen vodorovné vsazení (deska rovnoběžná se zemí) -
svislé panely zatím ne."* Pro stěny je tedy potřeba tuhle funkci rozšířit,
ne ji jen zavolat.

**Doplněk: profily NEMAJÍ drážku v modelu.** `Object_7` je v GLB obyčejný
kvádr 30×30×1000 (100 vrcholů / 50 trojúhelníků), stejně `Object_11`
(40×40, 48 trojúhelníků). Drážka je na skutečném výrobku, v 3D modelu ne.
**Důsledek:** hloubku zásunu desky do drážky NELZE změřit z geometrie —
je to parametr. Pro rodinu 10 mm je to `GROOVE_INSERT_DEPTH_MM = 10`
(auto-deska.js, potvrzeno Robertem). **Pro rodinu 8 mm hodnota potvrzená
není a musí ji dát Robert** — nepřebírat mlčky 10 mm z jiné rodiny.
