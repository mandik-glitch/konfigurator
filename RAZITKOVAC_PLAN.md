# Razítkovač profilů 3D logem — plán

Zadání: Robert 2026-09-09 — *„připrav plán na razítkovač profilů 3D logem"*
a hned nato *„3D logo nech má pod sebou i vyplněnou drážku"*.

Cíl: **automaticky** posadit ochranné 3D logo na profily produktových sestav
místo dnešního ručního umístění u jediné sestavy z 263.

Souvislosti: `PRODUKTOVE_RENDERY.md` (sekce o logu a ochraně modelu, 3 stupně
důvěry), předávka `scripts/handover.py show 101`.

Podklady tohoto plánu vznikly měřením nad reálnou GLB geometrií a živými daty
(2026-09-09), ne odhadem. Kde je něco domněnka, je to označené.

---

## 1. Co se změřilo (a co z toho plyne)

### 1.1 Umístění je popsatelné jedním vzorcem

Všechny 4 ručně umístěné instance u sestavy `id=134` sedí **bezezbytku** na
jednom předpisu. Označ `T` = jednotkový vektor podél dlouhé osy hostitelského
profilu, `N` = vnější normála zvolené stěny:

```
quaternion = makeBasis(T, N×T, N)      // lokální +X = řádek textu → T
                                       // lokální +Y = výška písmen → N×T
                                       // lokální +Z = tloušťka     → N
position   = pivot hostitele + N × (polovina průřezu + polovina tloušťky loga)
           = pivot + N × 15,695 mm     (pro profil 30×30 a logo tl. 1,392 mm)
```

Rekonstruované kvaterniony se od uložených liší o **0,000°** u všech čtyř.
Logo je podél délky i napříč šířkou **přesně vycentrované** (odchylka 0,0000 mm)
a jeho zadní plocha leží 0,001 mm pod rovinou stěny — tedy prakticky lícuje,
ven vystupuje 1,391 z 1,392 mm.

> **Oprava dokumentace:** `PRODUKTOVE_RENDERY.md` dosud tvrdila „otočí se o 90°
> kolem Z". To neplatí pro **žádnou** ze 4 uložených instancí — je to jen
> speciální případ z dema (profil podél Y, stěna +Z). Obecné pravidlo je
> `makeBasis(T, N×T, N)` výše.

### 1.2 Novou geometrii psát netřeba

Stávající rig pro příslušenství tu pózu umí přesně:
`findAccessoryToProfileCandidatesAllSpins()` → konektor rodiče typu `face` →
`childFaceConnIdx = 6` (tenká −Z plocha loga) → `spinIndex = 2` →
`applyFaceToFaceCandidate()`. Tímhle **konstantním** receptem se reprodukovala
všechna 4 loga s odchylkou 0,0010 mm a 0,0000°, a to pro profily ve třech
různých světových osách a dvě různé stěny.

Node.js základ: `scripts/2026-09-01_uhelniky_leg_joints_lib.js` (1:1 port
aktuální `scene.html` **včetně** kanonizace spinu) + `webapp/js/scene-geometry-shared.js`
+ `scripts/2026-08-19_glb_real_geometry.js`.

### 1.3 Knihovna je jednodušší, než se čekalo

Napříč 263 sestavami je **22 091 dílů**, ale **jediný profil**: `Object_7`
(30×30), 11 230 kusů = 50,8 % všech dílů, ve všech 263 sestavách. Žádný jiný
profil z `cfg_dily` se nepoužívá.

Profily se škálují výhradně na lokální ose Y (délka = 1000 × `scale[1]`) a
všech 6 vyskytujících se kvaternionů jsou násobky 90° → **každý profil je
osově zarovnaný se světem**. Délky: medián 289 mm, p90 1232 mm, max 1692 mm.
**96,3 % profilů je delších než logo** (223,2 mm); sestava bez jediného
dost dlouhého profilu neexistuje.

### 1.4 Kolik log stačí — a proč je vzor 134 špatná předloha

Jedna plocha pokryje nejvýš **29 z 81** směrů otočného náhledu (27 azimutů ×
3 elevace), při kritériu „kamera do 60° od normály".

| log | pokrytí |
|---|---|
| 1 | 29/81 (36 %) |
| 2 | 55/81 (68 %) |
| 3 | **81/81 u 259 z 263 sestav** |
| 4 | 81/81 u všech |

Vítězný recept je pokaždé stejný: **přední rovina +X + oba konce regálu +Z a −Z.**
Lícující čitelný slot ve všech třech rovinách má 254 z 263 sestav; po zmírnění
na „nezakrytá, ale ne zcela lícující plocha" všech 263.

> ⚠️ **Vzor 134 se nesmí kopírovat.** Změřeno: `logo-0` a `logo-3` sedí **obě**
> na přední rovině +X (vzájemně redundantní, 29/81 každé) a `logo-1` je na
> zadní rovině −X, kterou 270° výseč otočného náhledu skoro vynechává — kryje
> jen **4 z 81** směrů. Jediný existující ruční vzor je tedy dobrý na odvození
> *orientace*, ale ne *výběru ploch*.

Kandidátských ploch je dost: typická sestava má 84 slotů, kam se logo vejde,
75 čitelných aspoň z jednoho směru, 24 lícujících s obálkou a 12 „prvotřídních".
Minimum přes všech 263 sestav jsou **4 prvotřídní sloty** — žádná není na hraně.

### 1.5 Drážka pod logem — Robertova podmínka, změřeno

Vnější stěna profilu 30×30 **není plochých 30 mm**: materiál je jen 2 × 9,57 mm,
mezi tím je otevřená drážka. Z 28mm výšky loga tedy **8,20 mm přemosťuje
prázdno** — logo tam visí ve vzduchu.

`Box3` to hlásí jako lícující dotyk, takže žádný stávající test na to
neupozorní. Robertova podmínka *„nech má pod sebou i vyplněnou drážku"* je
proto oprava skutečné vady, ne kosmetika.

Výplň **jako díl neexistuje** — v `cfg_dily` není krytka ani lišta do drážky a
v `webapp/katalog/` k tomu není GLB. Musí se generovat. Drážka navíc není jeden
rozměr (6 / 8 / 10 mm podle profilu, viz `PROFILY_KATALOG.md`), i když v praxi
dnes rozhoduje jediná: 30×30 Light = **8 mm**.

---

## 2. Co plán musí vyřešit, protože to jinak tiše selže

Tohle jsou nálezy, které by se při implementaci naslepo neprojevily jako chyba.

1. **Zápis přes API zahazuje `role`.** `_validate_custom_shape_parts`
   (`api/app.py`) nemá `role` ve whitelistu, takže `POST /api/product-assemblies`
   vrátí **200 OK** a přitom smaže `predni-svislice`/`cap`/… — a otočný náhled
   se pak začne renderovat **zezadu** (přední azimut se počítá z rolí).
   Razítkovač proto musí zapisovat mimo tenhle endpoint, nebo se whitelist
   musí nejdřív opravit.
2. **Bookkeeping validátor bude každé logo počítat jako spoj.** Změřeno: každá
   ze 4 instancí tvoří pár, který `isFlush()` uzná (překryv 0,0010 mm ≤ eps
   0,05, plný překryv na zbylých dvou osách) → spustí invarianty I2 i I3.
   **Neexistuje kombinace dat, která validátor uspokojí, aniž by se do sestavy
   započetl fiktivní spoj za 110 Kč.** Buď se validátor naučí logo ignorovat,
   nebo se logu přizná zvláštní status.
3. **Regresní sada o razítkování nic nedokazuje.**
   `scripts/2026-08-19_regression_scene/run_all.js` na sestavy vůbec nesahá —
   staví si vlastní syntetickou geometrii. Zelený běh není důkaz.
4. **`isProfilePart(logo) === true`** — appka logo považuje za profil, ne za
   příslušenství. To má důsledky pro kusovník, cenu i pro accessory rig.
5. **`attach_pose` použít nelze** (tři nezávislé blokátory) — naučená póza jako
   u koleček tudy nevede.
6. **Volba stěny v `runWallAut` závisí na `camera.position`** → headless
   nepoužitelná, razítkovač si musí stěnu vybrat sám.
7. **Souběh s úkolem bot9** (`TASKS.md`, pravidlo 25): chystá úklid **téhož**
   pole `data.parts` u všech 263 sestav a přesun rozpisu boxů z názvu do
   atributu. Razítkovač se **nesmí opírat o názvy sestav** a neměl by přepisovat
   `data.parts` současně s ním.

---

## 3. Kde razítko vlastně musí být

Průzkum našel **dva různé zdroje geometrie**, a v tom je jádro problému:

| zdroj | kam vede | propíše se razítko z dat? |
|---|---|---|
| `product_assemblies.data.parts` | obě větve otočného náhledu | **ano**, samo |
| `placed[]` živé scény → `exportSceneAsGlb()` | nabídka, render sestavy | **jen** když sestava přišla do scény přes `insertCustomShape()` |

A teď to podstatné. Jediné místo v celém systému, kde **skutečná geometrie
odchází neautentizovanému příjemci**, je:

```
GET /api/public/offers/<token>/model
```

Dnes tam leží **3 živé nabídky a všechny tři jsou neorazítkované** (ověřeno
rozborem meshů v GLB, ne hledáním řetězce „logo" — názvy uzlů jsou zploštěné
na `bomgrp_N`). To je jediné místo, kde razítko skutečně plní svůj účel:
forenzní stopa a značka původu.

Ostatní cesty: otočný náhled posílá ven jen JPEG; Blender/GPU větev posílá
kompletní geometrii, ale na Robertovu stanici (token, důvěryhodný cíl);
render sestavy je staff-gated.

> **Samostatný nález, který razítko neřeší:** veřejný turntable payload
> (`/api/shop/products/<id>/turntable`) vrací `camera.bbox_min`/`bbox_max`/
> `bounding_radius` — tedy **přesné vnější rozměry sestavy v mm**, bez
> přihlášení. Proti Robertovu cíli „aby nešly odečíst rozměry" je to díra,
> na kterou razítkování nemá vliv. Řešit zvlášť.

---

## 4. Návrh postupu

Rozdělené tak, aby se dalo zastavit po kterémkoli kroku a mělo to smysl.

### Krok 1 — Výplň drážky jako generovaný díl

Bez ní razítko nesplňuje zadání, takže jde první.

* Změřit průřez drážky profilu 30×30 z reálné GLB (ne z katalogového listu) —
  šířku hrdla, hloubku, rozteč.
* Vygenerovat GLB výplně: kvádr na míru drážky, délka = 223,2 mm (stopa loga)
  + malý přesah, materiál `layer='alu'`.
* Založit ho jako katalogový díl (`cfg_dily` + GLB v `webapp/katalog/`) —
  **pozor**, samotné GLB nestačí, viz past zapsaná v `AGENTS_LOG.md`
  2026-09-08. A **nedávat mu délku 1000 mm**, jinak vysvítí v ceníku profilů
  (viz oprava `admin_profily.py` z 2026-09-09).
* Ověřit řezem, že výplň lícuje s vnější stěnou a logo na ní dosedá celou
  plochou.

### Krok 2 — Umísťovač jedné dvojice (logo + výplň)

Node.js funkce: vstup = sestava + hostitelský profil + volba stěny; výstup =
dvě položky do `data.parts`.

* Použít accessory rig s konstantním receptem z 1.2 — nepsat vlastní matematiku.
* Výplň se sází stejným předpisem, jen s `N × (polovina průřezu − hloubka drážky/2)`.
* Ověření: řez ze **živého stavu scény** (`scripts/2026-08-20_live_section_cut.js`,
  ne vlastní rig — viz past s kolečkem 3404) + kontrola překryvu na **všech
  třech osách**.

### Krok 3 — Výběr ploch

Podle 1.4, ne podle vzoru 134: **přední rovina +X + oba konce +Z a −Z**, tři
loga. Kandidáti se řadí podle (lícuje s obálkou) → (počet čitelných směrů) →
(volný běh ≥ 300 mm).

Výstup kroku: pro každou sestavu seznam tří slotů, **zatím bez zápisu**.

### Krok 4 — Robertovo schválení nad řezy

Kanonický postup (`VLASTNOSTI_PROFILU.md`, pravidlo o učení dílů): očíslovaná
tabulka variant jako technické řezy ze živého stavu → Robert vybere číslo →
teprve pak se zapisuje. Na jedné sestavě, ne na 263.

### Krok 5 — Hromadné nasazení

* Zápis **přímo do DB**, ne přes `POST /api/product-assemblies` (bod 2.1).
* Napřed dump do `backups/`, pak dry-run s výpisem, teprve pak `--zapsat` —
  stejný vzor jako `scripts/2026-09-09_zrcadlo_sestav_backfill.py`.
* Až **po** doběhnutí úkolu bot9, ne souběžně (bod 2.7).

### Krok 6 — Zacelit únikovou cestu

Razítkovat i geometrii, která odchází přes `GET /api/public/offers/<token>/model`
— to je jediné místo, kde na razítku doopravdy záleží. Tři existující živé
nabídky jsou dnes bez razítka.

---

## 5. Co potřebuje rozhodnout Robert

1. **Kolik log na sestavu.** Tři pokryjí všech 81 směrů u 259 z 263 sestav,
   čtyři u všech. Čtvrté logo je pojistka za cenu dalšího prvku v každé sestavě.
2. **Co s bookkeeping validátorem** (bod 2.2) — má logo přestat být počítáno
   jako spoj, nebo se smířit s fiktivním spojem v kusovníku?
3. **Má razítko být i na snímcích prstenců**, nebo jen na veřejných kanonických
   obrázcích? (Dnes je v geometrii, takže na všech.)
4. **Pořadí vůči úkolu bot9** — počkat na dokončení nového číslování, nebo
   razítkovat dřív a počítat s tím, že se `data.parts` budou přepisovat dvakrát.
5. **Ta díra s rozměry** (konec sekce 3) — řešit hned, nebo zvlášť později?

---

*Zapsal bot8, 2026-09-09. Podklady: workflow „razitkovac-profilu-3d-logem"
(5 průzkumných agentů, měření nad reálnou geometrií a živými daty).*
