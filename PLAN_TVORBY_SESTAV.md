# Plán tvorby sestav

Cesta **od receptu až po hotovou prodejní položku v e-shopu** — s
rendery a s ekvalizérem na konfiguraci sestav. Obecný postup pro
**libovolnou nezařazenou sestavu**: vozidlo, typologie regálu, velikost
profilu a skladba jsou PARAMETRY postupu, ne jeho obsah. Robert
2026-09-11: *„jen se bude menit skladba a typ regálu."*

**Tohle není jednorázový úkol, je to výrobní linka.** Robert 2026-09-11:
*„tento nástroj/plán na tvorbu sestav od receptu po hotový eshopový
produkt s rendery a equalizerem na konfiguraci sestav budeme pouzivat do
budoucnu velmi často, zakládáme tím prodejní položky v eshopu."*
Prakticky z toho plyne: každý krok musí jít **zopakovat bez přemýšlení**
a každá past se sem musí zapsat hned, jak se zaplatí — příště přes ni
projde další vozidlo, ne totéž.

## ⭐ Pravidla tohoto dokumentu (Robert 2026-09-11)

1. **Zapisuje do něj pouze bot3.** Ostatní boti poznatky, nálezy a hotové
   kroky POSÍLAJÍ bot3 zprávou, nezapisují sem sami. Důvod: plán je
   jediné místo, kde se drží pořadí práce napříč flotilou; kdyby do něj
   psal každý, rozpadne se na sbírku nesouvisejících poznámek a přestane
   být rozhodovatelný.
2. **Každý bot čeká na práci od bot3 a nahlíží sem, jen když si není
   jistý.** Plán NENÍ povinné čtení při startu session a není to fronta
   úkolů, ze které si někdo bere práci sám. Je to záchranná síť pro
   chvíli, kdy bot neví, co jeho kus znamená v celku — jak navazuje, co
   ho blokuje, jaká past na něj čeká. Práci rozdává bot3.
3. **Tenhle plán je SPECIFIKACE přehledové tabulky na dashboardu.**
   Robert 2026-09-11: *„náš plán ‚výroby sestav' musime dál uderžovat a
   doplňovat jako detailní popis toho co vlastně bude v přehledové
   tabulce workflow na dasboardu."* Dělba je tedy jasná: **tabulka drží
   STAV** (kde která sestava je), **plán popisuje VÝZNAM** (co ten krok
   obnáší, čím je hotový, jaká past na něm čeká). Každý krok v tabulce
   má odpovídající popis tady — a naopak, nový krok se nejdřív dopíše
   sem, teprve pak přibude do číselníku. Kroky mají stabilní klíče, viz
   sekci **Kroky výrobní linky** níže.
4. **Artifact je jen POHLED, ne zdroj pravdy.** Republikuje se z tohoto
   souboru, nikdy naopak:
   https://claude.ai/code/artifact/aa527d06-6532-4ad8-a09d-705971971d92
5. **Zapisuje se jen vyřčené pravidlo a kvalitní výstup diskuze, ne
   každá věta** (Robert, 2026-09-14, viz `WORKFLOW.md` bod 37 pro plné
   znění a zdůvodnění - platí plošně pro všechny projekty). Otevřené
   varianty/možnosti BEZ rozhodnutí ("možná A, možná B, probereme
   příště") sem nepatří vůbec, ani jako stručná poznámka. Naopak
   kvalitní ZÁVĚR/vysvětlení, ke kterému diskuze dospěla, se zapsat má,
   i bez formálního "pravidla" - jen ne surový průběh vyjednávání.
   Cesta k rozhodnutí (kdo co navrhoval, jak se debatovalo) zůstává v
   `AGENTS_LOG.md`, tenhle soubor ji neduplikuje ani zkráceně. Platí
   dopředu, ne zpětně - starší zápisy se kvůli tomu
   nemažou (viz ale úklid otevřených caveatů níže, proveden 2026-09-14
   ihned po zavedení pravidla).

### ⭐ Stará dokumentace se MAŽE, ne doplňuje

Robert 2026-09-11: *„stara dokumentace by se mela mazat."*

Vzniklo z živého výpadku: grafická stanice přestala odpovídat a
`PRODUKTOVE_RENDERY.md` pořád popisovala, že se agent spouští jako
naplánovaná úloha po přihlášení do Windows. Poslal jsem proto Roberta
hledat okno s konzolí a poklepat na `.bat` — jenže *„to jsme davno
zrusili a jede to jako sluzba"*. Zastaralý návod odvedl řešení výpadku
špatným směrem.

**Když se něco změní, starý popis zmizí.** Ne „dřív to bylo takhle, teď
je to jinak" — jen to, co platí. Historie žije v gitu, ne v dokumentu.
Dva návody vedle sebe znamenají, že si příště někdo vybere ten špatný.

**Výjimka: pasti.** Ty se zapisují i po opravě, protože popisují, čemu se
vyhnout. Rozdíl je jednoduchý — **návod, jak něco udělat, má být jen
jeden; varování může být víc.**

**A u všeho, co se děje na Robertově stanici, se píše, odkud to víme a
kdy se to naposledy ověřilo.** Na ta místa nevidíme a mění se, aniž
bychom o tom věděli — datum ověření je jediná obrana.

### Proč tenhle soubor vznikl

Plán existoval do 2026-09-11 **jen jako artifact**. Nedalo se do něj
připisovat, nešlo do něj grepovat, žádná nová session ho při startu
nenašla a byl napsaný na konkrétní případ (Doblo C, euroboxy) místo na
obecný postup. Důsledky byly měřitelné: razítkovač se v něm ztratil a
Robert v něm nacházel mezery dřív než my — mimo jiné to, že plán tvrdil
jako hotový článek z GPU do otočného náhledu, který ve skutečnosti
neexistoval (40 hotových sad snímků na disku, 0 řádků v DB).

---

## Přehled řetězu

```
  Recept  →  Scéna  →  Schválení  →  Skladová karta  →  Rendery  →  Web
   (R)       (0,1)       (2)             (3)             (4)        (5)
```

| Značka | Význam |
|---|---|
| ✅ | funguje a je ověřené |
| ⬜ | chybí, uděláme sami |
| ❓ | čeká na rozhodnutí Roberta |
| ⛔ | dvě části systému si odporují |

---

## Fáze R — Recept

**Vstup:** postup, který se osvědčil na jedné sestavě.
**Výstup:** řádek v `shape_geometry_methods` — pojmenovaný, verzovaný.
**Hotovo, když:** podle receptu postaví totéž i bot, který u vzniku nebyl.

Recept je **zapsaný postup skládání**, ne kus geometrie. Díky němu se
další vozidlo nestaví od nuly a nevymýšlí se pokaždé znovu, co už jednou
někdo změřil. Tady začíná celý řetěz — proto stojí před scénou, ne za ní.

| id | v. | Recept | K čemu |
|---|---|---|---|
| 1 | 4 | `prevod-profilu-zachovanim-rozmeru` | stejný design, jiná tloušťka profilu, zachované vnější rozměry |
| 2 | 2 | `zmena-hloubky-nohy` | |
| 3 | 14 | `ukladani-euroboxu-do-luzek` | nejvíc iterovaný recept |
| 4 | 2 | `dokonceni-nohy-zaslepky-a-uzavreni` | volná čela noh, patky, záslepky |
| 5 | 3 | `regal-sloupcova-struktura` | |
| 6 | 7 | `protazeni-zadni-svislice-vyrezove-nohy` | |
| 7 | 2 | `uhelniky-na-spoje-nohy` | **verze 3 se připravuje** — kolize je kolize bez ohledu na pozici |
| 8 | 6 | `prizpusobeni-vysky-nohy-vysce-dveri` | |
| 9 | 13 | `horni-blok-pro-dlouhe-predmety` | ⚠️ zastaralý, nepopisuje polici |
| 10 | 2 | `razitkovani-profilu-ochranne-logo` | razítkovač, viz fáze 4 |

**Recept se verzuje, nepřepisuje.** Když se pravidlo změní, zvedne se
`version` a do receptu se zapíše, co se změnilo a proč — jinak nejde
zpětně poznat, podle které verze která sestava vznikla.

> **Past: recept může zastarat, aniž by to bylo vidět.** `id=9`
> (`horni-blok-pro-dlouhe-predmety`, v. 13) nepopisuje polici, přestože
> provedení 4 a 6 ji mají. Kdo podle něj bude stavět, postaví neúplný
> blok a nic ho nevaruje. **Před použitím receptu se ověřuje, že popisuje
> to, co dnes stavíme** — zvlášť u těch s vysokým číslem verze, které se
> měnily mnohokrát.

> **Past: pozice dílu z jednoho vozidla neplatí pro jiné.** Robert
> 2026-09-11: *„Je jasné že různé auta mají různé tvary takže pokud se
> vyskytne kolizní úhelník tak nemusí mít stejnou pozici jako v doublu."*
> Recept popisuje **pravidlo**, ne souřadnice. Kritérium musí být
> geometrické (skutečný průnik reálné GLB geometrie), ne „sedí tam, kde
> ve vzoru".

---

## Fáze 0 — Kdo je co

Bez téhle identity je zbytek nejednoznačný.

| Pojem | Kde žije | Role |
|---|---|---|
| **Karoserie** | `car_bodies` → katalog scény | Nikdy součást PRODUKTU (kusovník/cena/hmotnost/render ji vždy vyřazují — sestava se neprodává s autem). Součástí DAT sestavy (`data.parts`, `car_body_<id>` díly) ale od 2026-09-17 BÝT MUSÍ, viz ⭐ pravidlo níž a WORKFLOW.md pravidlo 25. |
| **Sestava** | `product_assemblies` | Konkrétní postavený regál. Nese geometrii, kusovník a cenu. |
| **Základní sestava** | tatáž tabulka | **Nositel produktové karty.** Z ní vznikl produkt, z ní se vzal název i SKU. |
| **Varianta** | tatáž tabulka | Další sestava navázaná na *tutéž* kartu. Nemá vlastní produkt, vlastní cenu na webu ani vlastní SKU. |
| **Produktová karta** | `shop_products` | To, co se prodává. Jedna karta, N sestav. |

`product_assemblies.shop_product_id` ukazuje na kartu. Sloupec **nemá**
`UNIQUE`, takže na jedné kartě může viset libovolně mnoho sestav — a
právě to z ostatních dělá varianty. Přidání další varianty nevyžaduje
zásah do kódu.

**⭐ Auto je součástí dat sestavy vkládané botem (Robert, 2026-09-17,**
**ZMĚNA - do 2026-09-17 platil opak).** Doslova: *„vkládání sestav
botem musí obsahovat sestavu i s autem, podle toho právě probíhá oční/
vizuální kontrola."* Na dotaz upřesnil: karoserie se ukládá PŘÍMO do
`data.parts` sestavy (`car_body_<car_bodies.id>` díly, typicky
`_L`/`_R_D`/`_B`, na pozici vůči které byla sestava postavena - u botem
stavěných sestav syrové GLB: `position=[0,0,0]`, identity quaternion,
`scale=[1,1,1]`), ne jen jako oddělená položka scény. Důvod: Robertova
vizuální kontrola probíhá vždy vůči autu (fit, podběh, strop, proporce)
- bez auta v datech by si ho musel sám dohledávat v katalogu a vkládat
ručně. **Obchodní jádro pravidla se neposouvá:** karoserie se dál
neprodává, není položka kusovníku/ceny/hmotnosti (`isCarBodyPart` filtr
před výpočtem), nikdy se nerenderuje, a razítkovač loga ani kolizní
příznak úhelníků s ní nepracují. Plné znění a historie (do 2026-09-17
platil opak) viz `WORKFLOW.md` pravidlo 25.

> **❓ Slabina k rozhodnutí — „základní" dnes znamená nejnižší `id`.**
> Tedy náhodu pořadí vzniku. Když se základní sestava přestaví a uloží
> znovu, dostane vyšší `id` a **přestane být základní** — karta se tiše
> otevře na něčem jiném. Tohle tiché přehození už jednou nastalo.
> **HOTOVO (2026-09-11, OPRAVENO audit bot9 2026-09-12):** výslovný
> příznak `product_assemblies.is_master` (`sql/2026-09-11i_product_
> assemblies_is_master.sql` + `api/product_assemblies.py:689-702`,
> transakčně vynuceno) nahrazuje dřívější konvenci „nejstarší = základní".
> Nositele karty teď určuje `is_master`, ne pořadí zápisu.

> **Past: název se kopíruje jen jednou.** Název produktu vzniká z názvu
> sestavy při vzniku produktu a **nic ho potom nesynchronizuje**. Každé
> přejmenování sestavy tu dvojici rozejde, a protože se ze stejného
> názvu odvozuje SKU, rozejde se i to. Přejmenováváš sestavu →
> přejmenuj i kartu. Platí jen pro základní sestavu.

---

## Fáze 1 — Scéna

**Vstup:** prázdná scéna + karoserie z katalogu jako kulisa.
**Výstup:** řádek v `product_assemblies` ve složce *Nezařazená*.
**Hotovo, když:** sestava má geometrii, kusovník i cenu a jde otevřít.

1. Do scény se vloží **karoserie** jako kulisa. Do sestavy nepatří a při
   ukládání se vypouští.
2. Postaví se **regál** z profilů, příslušenství a desek.
3. Označí se díly a uloží se jako **produktová sestava**.
4. **Varianta = totéž znovu**, jen s jiným provedením, navázané na
   stejnou kartu.

Zapíše se: `parts[]` (`part_id`, `position`, `quaternion`, `scale`,
`role`) · `join_groups`, `frame_groups` (evidence spojů) · `bom` a
`price_summary` (kusovník a cena).

> **⛔ Past: kusovník počítá JEDINĚ prohlížeč.**
> `computeAssemblyBomAndPrice` (`scene.html`, OPRAVENO audit bot9
> 2026-09-12: aktuální řádek 4954, ne 4382 - hledej `grep -n "function
> computeAssemblyBomAndPrice" webapp/scene.html`, číslo se časem
> posouvá) běží **při uložení ze
> scény**. Sestava založená skriptem má `bom` i `price_summary` prázdné
> — a přesně to se stalo všem sedmi sestavám vzoru. Karta pak nemá co
> ukázat. Kdo zakládá sestavy skriptem, musí kusovník doplnit zvlášť,
> nebo sestavu jednou otevřít ve scéně a přeuložit.

> **Past: karoserie v `data.parts`.** Do renderu se `car_body_*` díly
> nedostanou — `resolve_parts()` (OPRAVENO audit bot9 2026-09-12:
> `scripts/2026-09-09_turntable_job.py:511`, ne `resolve_parts()` ve
> `scene.html` - ta funkce tam vůbec není) je přeskakuje stejně jako
> prohlížeč (filtr `entry.part.source === "car_body"` ve
> `webapp/scene.html:5691` a `:6177`). **Nemazat je ale ze sestav:** veřejný
> SEO popisek (`api/storefront_pages.py::_assembly_seo_sentence`)
> odvozuje vozidlo právě z `car_body_<id>` a jinam pro něj nesahá.
> `car_model_id` je u většiny sestav zatím NULL (OPRAVENO audit bot9
> 2026-09-12: k 2026-09-12 má 31 z 294 sestav `car_model_id` už
> vyplněný - ověř živě `SELECT COUNT(*) FROM product_assemblies WHERE
> car_model_id IS NOT NULL`), takže je ten díl zatím hlavním, ale už ne
> jediným nositelem vazby na vozidlo. Odstranit je lze až po dopočítání
> `car_model_id` u ZBÝVAJÍCÍCH sestav.

> **❓ Zákaznický název chybí.** Varianta potřebuje **dvě jména**:
> interní (`NÁHLED horní blok 2/6 jedno pásmo - rám + dna [ZÁKLAD]…`) a
> zákaznické, které dnes **neexistuje** — na web by šlo interní jméno
> včetně slova „NÁHLED". Zákaznické má být krátké a bez modelu vozidla
> (ten je už v názvu produktu): „Jedno pásmo, rám + dna". Kde bydlí —
> nové pole, nebo konvence v názvu — je otevřené.

---

## Fáze 1b — Číslování sestav

**Rozhodnuto (Robert 2026-09-11):** kód nese **všech šest složek**,
oddělených pomlčkami:

```
K-075-EB-30-A-0001-2-0
  │    │   │  │   │  │ └ dodatek (unikátnost, výchozí 0)
  │    │   │  │   │  └── horní blok (0 = bez, 1–6 provedení)
  │    │   │  │   └───── varianta typologie (u euroboxů rozpis boxů, 4 číslice)
  │    │   │  └───────── verze
  │    │   └──────────── hlavní profil (30 · 40 · 45, skutečná velikost)
  │    └──────────────── typologie (EB euroboxy · UN universal
  │                      · OS ocelové šuplíky · EV euroboxy na výsuvech
  │                      · UK ukládání kufrů)
  └───────────────────── karoserie z `car_models`
```

**⭐ Kód je identifikátor, ne popis.** Robert: *„kód nemusí říkat nic,
kód má být jednoznačný, v popisu karty potom může být popis"* a
*„dodatkové číslo zajistí, že se kód nemůže duplikovat."* Jedinou
povinností kódu je být **jednoznačný a stabilní**.

**Pravdou jsou pole, kód je jen zápis.** Každý rozměr má vlastní sloupec
na sestavě (s číselníkem tam, kde má smysl) a kód se z nich *generuje*.
Rozdíl je praktický: přidání dalšího typu regálu je pak **nový řádek
číselníku**, ne přeformátování všech dosavadních kódů. Význam čtvrté
složky určuje druhá — „varianta 3" znamená u euroboxů jiný rozpis než u
ocelových šuplíků, jsou to dva různé číselníky s cizím klíčem na
typologii.

**Stav:** zapracováno a aplikováno (commit `19d8104b`, migrace
`sql/2026-09-11b_kod_sestavy_format_roberta.sql`, skript
`scripts/2026-09-11_kod_sestavy_format.py`, záloha v `backups/`). Verze
doplněna u **292 z 294** sestav (OPRAVENO audit bot9 2026-09-12, počet
sestav roste - ověř živě `SELECT COUNT(*) FROM product_assemblies WHERE
verze IS NOT NULL` / `COUNT(*)`).

⬜ **Zadáno, zatím NEZAPSÁNO jako hotové (Robert 2026-09-13, přes
bot9):** *„Automatizovat generování kódu SKU zároveň, když se sestava
razítkuje 3D-logem."* Dosud `kod_sestavy` generuje výhradně bot ručním
spuštěním skriptu (`scripts/_kod_sestavy.py::sestavit_kod_sestavy()`,
commit `52b30b4b`) - žádný živý endpoint ho nezapisuje automaticky.
Napojit na `_orazitkuj_pri_zarazeni()` (`api/product_assemblies.py`,
volá se z `PUT /api/product-assemblies/<id>`, spouští
`razitkovac.prerazitkuj()` při zařazení sestavy do kategorie) - jakmile
razítkování REÁLNĚ proběhne (ne když je přeskočeno jako „už aktuální"),
na stejném místě dopočítat a zapsat i `kod_sestavy`. Implementace
(guardovaný soubor, `DEPLOY_LOCK`) předána bot5 a bot8.

### Číselník horních bloků

Robert 2026-09-11: *„kódy variant horního bloku budou čísla, postupně po
sobě."* `0` = bez horního bloku.

| Kód | Provedení |
|---|---|
| 1 | jedno pásmo – jen rám |
| 2 | jedno pásmo – rám + dna *(základ)* |
| 3 | dvě pásma – jen rám, bez police |
| 4 | dvě pásma – rám, police jen příčky, bez horních příček |
| 5 | dvě pásma – plné výplně, bez police, horní příčka jen u přepážky |
| 6 | dvě pásma – plné výplně, s policí, horní příčka jen u přepážky |

> **⛔ Past: „horní" v názvu role NEZNAMENÁ horní blok — znamená DRUHÉ
> PÁSMO.** Jednopásmový blok je celý z rolí `podelnik-*-spodni` a
> `pricka-spodni-*`, takže provedení „jedno pásmo – jen rám" vypadá jako
> „bez horního bloku" a dostalo by `0` místo `1`. **Spolehlivý test je
> role začínající na `podelnik`** — podélník se mimo horní blok
> nevyskytuje. Ověřeno nad všemi 269 sestavami dvakrát nezávisle
> (bot10 + bot3, 2026-09-11): **13 s blokem, 256 bez** — konkrétně
> sestavy 134, 135, 182, 189, 209, 219, 289, 332, 333, 334, 335, 336,
> 337. Dřív tu stálo 14; to číslo vzniklo započtením sestavy **279**,
> která žádnou roli `podelnik*` nemá — je to starý box-sloupcový layout
> bez horního bloku a maže se z jiného důvodu (kolizní úhelníky).

> **Past: `K-123e` je JINÉ VOZIDLO, ne varianta.** Přípona `e` znamená
> elektrickou verzi. `K-122` a `K-123e` jsou dva různé vozy, i kdyby
> vyšly geometricky identicky.

**⭐ NORMA (Robert, 2026-09-14, potvrzeno): geometrie horních bloků
01-04, jak je má Doblo K-075 A/B, je nová platná norma pro horní bloky
MALÝCH DODÁVEK, pro skladování dlouhého materiálu** (tyče, trubky,
profily). Není to jen jednorázový výsledek pro Doblo - stejné
provedení se má napříč malými dodávkami použít jako standard pro tenhle
konkrétní účel (malá dodávka + dlouhý materiál). Detail geometrie a
zápis do receptů (`shape_geometry_methods`, případně propojení s
obecnějším `id=9` "horni-blok-pro-dlouhe-predmety") je doména bota8,
zadáno mu přímo - včetně otevřené otázky, která vozidla pod „malé
dodávky" spadají.

> ⚠️ **Tabulka kódů výš (1-6) je ZASTARALÁ** - `horni_blok_varianty` má
> dnes (2026-09-14) 8 řádků (`00` až `07`, včetně nového `07` "s
> dorazovou deskou") a sestavy Doblo A/B pojmenované „A-01" až „A-04" v
> `product_assemblies.name` NEODPOVÍDAJÍ 1:1 kódům `01`-`04` v
> `horni_blok_varianty` (namátkou: „A-01" má `horni_blok_varianta_id`
> s kódem `07`, ne `01`) - název sestavy a kód číselníku jsou dnes DVĚ
> různá číslování. Přepis tabulky na aktuální stav nechávám bot8, ať se
> neplete se dvěma paralelními číslováními najednou.

### Dvě osy, jedna karta

Robert 2026-09-11: *„A, B, C nemohou být samostatné karty, chtěl jsem
měnit A, B, C dalším posuvníkem."* Karta je **jedna na vozidlo** a nese
dvě nezávislé osy:

| Posuvník | Co mění | Poloh |
|---|---|---|
| **Verze** | rozpis euroboxů (A / B / C…) | 3 |
| **Horní blok** | provedení nad boxy | 6 |

Varianta je tedy **dvojice souřadnic** („C + 4"), 3 × 6 = **18 sestav na
jedné kartě**. Osy proto musí být uložené **jako pole**, ne dolované z
názvu sestavy.

**⭐ Vazba verze → rozpis boxů se zapisuje výhradně do `karoserie_verze`**
(Robert 2026-09-13, přes bot9). "Verze" (A/B/C/D/E) je **nezávislý
komunikační štítek pro zákazníka**, ne geometricky odvozené pořadí -
vazba mezi verzí a konkrétním rozpisem boxů (`typologie_varianta_id`)
pro dané auto (`karoserie_kod`) žije VÝHRADNĚ v tabulce
`karoserie_verze` (sloupce `karoserie_kod`/`verze`/`typologie_varianta_id`,
UNIQUE na dvojici karoserie+verze) - **nikdy se neodvozuje z textu
názvu sestavy regexem**, jak se dělo dosud.
- **bot8** (zakládá novou verzi pro auto při stavbě nového rozpisu
  boxů) zapíše řádek do `karoserie_verze`.
- **bot5** (staví skladovou kartu s posuvníkem verze) čte z
  `karoserie_verze`, ne z názvu sestavy.
Tabulka postavena a zpětně naplněna (commit `7e394469`) - 236
existujících dvojic auto×verze, ověřeno 0 kolizí před zápisem. Beze
změny zůstává: verze i horní blok jsou dva posuvníky na JEDNÉ kartě
(potvrdil Robert znovu na příkladu „Doblo L1 do roku 2022").

**Velikost profilu není osa posuvníku.** Robert: *„velikost profilu je
jen pro orientaci, profil určuje admin."* Není to volba zákazníka ani
důvod pro samostatnou kartu.

### Kde začíná horní blok

Není to konstanta. Generátor ji počítá z konkrétní sestavy jako **vyšší
ze dvou podmínek**: 30 mm nad nejvyšším boxem, nebo 5 mm nad nejvyšším
úhelníkem. Různě vysoké boxy tedy vyjdou správně samy. Za pozornost
stojí, **která** z podmínek rozhodne — když vyhraje úhelník, rozdílné
výšky boxů se na výsledku vůbec neprojeví, a teprve podle toho se pozná,
jestli je horní blok mezi verzemi přenositelný.

### Nová osa: umístění (odděleně od typologie)

**Rozpracováno 2026-09-13** (Robert přímo s bot9, commit `2a449d35`,
`sql/2026-09-13_regal_umisteni.sql` + `scripts/2026-09-13_regal_umisteni_zapsat.py`,
idempotentní, `--apply` ověřeno živě). Nová, NEZÁVISLÁ osa vedle
`regal_typologie` (EB/UN/OS/EV = systém/obsah) - reálný produkt je
kombinace **jedné položky umístění × jedné položky typologie**. Nová
tabulka `regal_umisteni`:

| Kód | Umístění | Stav |
|---|---|---|
| RL | Regál levý (boční strana) | **jediná dnes rozpracovaná, × EB, vzor Doblo C** |
| RP | Regál pravý (boční strana) | rozpracovaná spolu s RL |
| RK | Regál - kabina (za přepážkou) | placeholder - **nemá horní blok**, u některých aut místo toho spodní blok |
| DP | Dvojitá podlaha | placeholder |
| VZ | Výsuvné bloky ze zadních dveří | placeholder |
| VB | Výsuvné bloky z bočních dveří | placeholder |
| VP | Výsuvná podlaha | placeholder |

> **Oprava 2026-09-14 (bot3):** tabulka dřív měla "RB" a chyběla jí RK
> - Robert "RB" výslovně zamítl (*„RB? co to je, uz jednou jsem to
> zamitl, máme u regalu RL, RP, RK"*). Opraveno podle živé DB
> (`regal_umisteni`, 7 řádků).

Přidán `product_assemblies.umisteni_id` (FK na `regal_umisteni`, zatím
`NULL` u všech). Zároveň upřesněn (jen popis, žádná nová položka) obsah
placeholderů `regal_typologie`: UN = upínací police/organizéry/vany/
sklopné dvířka, OS = šuplíková stěna/regál, EV = výsuvné euroboxy jako
šuplíky.

**Doplněno 2026-09-13 (Robert, commit `3459ef14`):** další položka osy
`regal_typologie` - **UK** (`ukladani_kufru`, "Ukládání kufrů"), zatím
jen pojmenovaná, obsah neurčen (stejný vzor jako UN/OS/EV výše).

**Beze změny zůstává SKU karty** = `K-<karoserie>-<typologie>-<profil>`
(dnes `K-075-EB-30`) - verze i horní blok zůstávají uvnitř karty přes
`kod_sestavy` jednotlivé sestavy, ne v SKU. Potvrdil Robert, nezávisle
ověřil i bot5.

❓ **Záměrně nedořešeno, čeká na Roberta** - nepovažovat za hotové: jak
přesně vstoupí do dat "levá/pravá strana" (orientace vs. vlastní kód),
spodní blok u přepážky (RP), a jestli/jak umístění vstoupí do formátu
`kod_sestavy`.

---

## Fáze 2 — Schválení

**⭐ Zatržítko schvaluje, složka zařazuje** (Robert 2026-09-11, mění
dřívější pravidlo).

Robert: *„já si cenu před schválením zkontroluju v přehledu ve scéně;
schválení zatržítkem znamená, že se může sestava propsat jako produkt a
zveřejnit."*

| | Zatržítko `technicky_ok` | Složka `category_id` |
|---|---|---|
| **Znamená** | sestava je v pořádku a smí ven | kam na webu patří |
| **Pouští k renderům** | ano | ne |
| **Pouští do produktu** | ano | ne |
| **Určuje kategorii** | ne | ano |

Schválená a nezařazená sestava tedy **existuje jako produkt**, jen není v
kategorii. Není to chyba, je to legitimní stav.

**Zařazení se dá dělat dávkou**, schválení ne — to zůstává na člověku.

Důsledky:
- Neschválená sestava **nepotřebuje obrázky**. Chybějící render u ní
  není nález k opravě, ani v QA, ani v auditu.
- Neschválená varianta se do posuvníku počítá, ale nemá co ukázat.

**⭐ `technicky_ok` je jediná pojistka - veřejné API ji nekontroluje.**
(bot5 nález, ověřeno bot9, 2026-09-16, `api/product_assemblies.py:1195`,
`product_assemblies_public()`.) Dotaz je `WHERE pa.shop_product_id=%s`,
BEZ filtru na `technicky_ok` i BEZ filtru na `shop_products.active`.
`shop_product_id` dostává KAŽDÁ sestava už při prvním uložení ze scény
(`product_assemblies_create`, karta vzniká rovnou, jen s `active=0`) -
nejde tedy o krok, který lze podmínit schválením. Ochrana je čistě v
kázni "neaktivovat/nesdílet kartu, dokud sestava(y) na ní nejsou
schválené" - stejný princip jako `shop_product_id=NULL` u varianty 04 s
mezerou <70mm výš v tomto souboru. Žádná druhá vrstva na straně čtení
neexistuje.

---

## Fáze 3 — Skladová karta

**⭐ Vizuální schválení karty se dělá jednou za typologii, ne za kartu
(Robert, 2026-09-17).** Doslova: *„každý typ regálu bude asi potřebovat
malinko jiný vizuál a to je to schválení adminem."* Odlišit od
`technicky_ok` (pravidlo 44, `WORKFLOW.md`) - to zůstává VŽDY ruční za
KAŽDOU sestavu bez výjimky. Tohle je jiná úroveň: `card_auto_link.py`
(bot5, commit `3934c85e`) u nového vozidla bez karty rovnou zakládá
kartu (název/popis/strukturu) - Robert vědomě přijal riziko automatizace
(„radši vrátím dodatečně akci zpět"), zmírněné tím, že auto-založená
karta zůstává `active=0`, dokud nedoběhne render. Jakmile Robert jednou
vizuálně potvrdí vzhled PRVNÍ auto-založené karty dané typologie
(`regal_typologie`, dnes EB = euroboxy), další karty STEJNÉ typologie
(jiná vozidla, stejná šablona) se dál zakládají automaticky BEZ dalšího
vizuálního schvalování - jen se plní jinými daty. Nová typologie
(UN/OS/EV/UK) potřebuje vlastní první vizuální schválení znovu, protože
jiný typ regálu = jiný vizuál. Souvisí s (zatím pozastavenou) diskuzí o
typologii jako primární ose kategorií u bota7 - „typ regálu" je tady
stejný pojem jako `regal_typologie`.

**⭐ Dělba práce (Robert 2026-09-13):** **bot8 chystá ceník sestav**
(kusovník/cena dopočtená z geometrie pro všechny varianty) **pro bot5**,
který z něj **staví konfigurace na e-shopu** - pomocí generátoru SKU
poskládá všechny varianty na kartě a přiřadí jim správné SKU.

**⭐ Vlastní SKU per varianta (Robert 2026-09-13, doslovně):** *„Každá
sestava a každá její varianta, která má svoji vyrenderovanou sadu
snímků, musí mít svůj vlastní SKU."* Spouštěč je **existence vlastní
vyrenderované sady** (`product_turntable_frames`), ne existence sestavy
samotné. **Netýká se a neruší SKU KARTY** (`shop_products.sku`, zůstává
sdílené, např. `K-075-EB-30`) ani dřívější rozhodnutí „A, B, C nemohou
být samostatné karty" (viz „Dvě osy, jedna karta" ve Fázi 1b) - jde o
SKU na úrovni JEDNOTLIVÉ SESTAVY/VARIANTY, ne karty. Ověřeno bot9
2026-09-13: `kod_sestavy` je už dnes jedinečný per sestava a všech 7
sestav Doblo C (341-347) MÁ vyrenderovanou sadu, tedy podle pravidla už
DNES kvalifikují pro vlastní SKU. Mechanika (použít `kod_sestavy`
přímo jako SKU varianty, nebo samostatné pole - napojení na
`shop_order_items`) se řeší mezi bot9 a bot5.

`webapp/admin/js/sklad-produkty.js`, záložka „3D model".

✅ `by-product` vrací `assembly` (základní) i `assemblies[]` (všechny
varianty). Ekvalizér přepíná **přímo mezi navázanými sestavami** a
přepnutí **přepočítá kusovník i cenu** dané varianty.

✅ **Cena se počítá z geometrie.** Žádný ceník kombinací se neudržuje —
osmnáct kombinací se ocení samo.

**⭐ Prodejní cena = náklad × marže, s možností přepsat.** Z geometrie
vychází náklad; prodejní cena se dopočte **jedním koeficientem**
(Admin → „Koeficienty cen" → Koeficient konfigurátoru). U konkrétní
kombinace jde cenu ručně přepsat. **Druhý koeficient se zavádět nesmí** —
tenhle se aplikuje na jediném místě, kde cena do konfigurátoru vstupuje
(`/api/katalog`), a další marže by se s ním násobila dvakrát.

> **Dvě opravy, ať se nevrátí:** (a) karta ukazovala jinou sestavu, než
> se schvalovalo — brala nejnovější navázanou, s příchodem variant se
> náhled přehodil; nově nejstarší = základní. (b) Posuvník ukazoval
> neschválené varianty — počítal si je sám skrýváním dílů podle rolí;
> nahrazeno skutečnými sestavami.

⬜ **Kusovník zůstává a bude následovat posuvník.** Sekce „Kusovník (ze
scény)" dnes ukazuje uložený snímek *základní* sestavy.
Druhá vada je hlubší: počítá `cena × počet kusů`, takže deska MDF
800×1200 stojí 1000 Kč místo 960 Kč a profily se neškálují délkou.

⬜ **Zadáno, zatím NEHOTOVO (Robert 2026-09-13, přes bot9, zapsáno i
jako pravidlo 14 v `TEXT_FILTR.md`).** Montáž sestavy z více profilů:
(a) montáž je nabízená **SLUŽBA s vlastní cenou přebíranou ze scény** -
`price_summary` ji dnes vůbec nepočítá, potřeba doplnit; (b) kotvení je
vlastní oddělená, dynamická část popisu (stejně jako montáž/pravidlo 12
a zbytek popisu/pravidlo 13 v `TEXT_FILTR.md`); (c) nabízení varianty
„včetně montáže" řídí nastavení v adminu, **per produkt/kategorie**.
Implementace: bot5 (obchod/cena), bot8 (scéna - cena montáže).

**⭐ Sestava si při opravě ponechává svoje ID (Robert, opakovaně
zdůrazněno 2026-09-17).** Drobná ruční korekce administrátorem (funkce
`resave_scene` v `api/product_assemblies.py`, bot8 2026-09-15) přepisuje
data na STEJNÉM řádku/ID - nikdy nezaložit nový řádek. Je to jediná
výjimka z obecného pravidla „uložení ze scény vždy zakládá nový řádek"
(ostatní cesty pořád platí beze změny - jde o NOVOU konfiguraci, ne
opravu existující). Viditelná stopa, že šlo o opravu: poslední segment
kódu sestavy [dodatek] se při resave zvýší o 1. Důvod: nové ID by
přetrhalo vazby na už existující renderované sady/kartu/nabídky - oprava
má být neviditelná změna KE STEJNÉ věci, ne vznik nové.

---

## Fáze 4 — Rendery

`scripts/2026-09-09_turntable_render.py` → GPU worker. Úzké hrdlo celého
řetězu; web bez obrázků nemá co přepínat.

**⭐ Geometrická podmínka pro variantu 04 (Robert, 2026-09-15):**
*„pokud vychází u sestavy a varianty 04, že mezera mezi příčkami/profily
horního bloku je menší než 70mm, tato varianta se nebude renderovat ani
zobrazovat na e-shopu, varianta 04 nebude ani v kartě, jen jako uložená
nepoužívaná geometrie."* Platí napříč celým katalogem, ne jen pro jedno
vozidlo - kontrola/měření je doména bota8. Bod je dnes 24 sestav
(`horni_blok_varianty` kód 06, „dvě pásma - plné výplně, s policí").
Prakticky: `shop_product_id` u takové sestavy zůstává/se nastaví na
`NULL` (nikdy nenavazovat na kartu) - sestava dál existuje v DB jako
geometrie, jen mimo prodejní řetěz úplně (přísnější než jen „nerenderovat").
Ověřeno 2026-09-15: všech 21 dnes vyřazených Jumpy sestav už
`shop_product_id=NULL` mělo, žádný dodatečný zásah nebyl potřeba.

**⭐ ZPŘÍSNĚNO 2026-09-17 (Robert):** *„nestavět geometrii vůbec, pokud
není splněna podmínka mezery 70mm."* Předchozí znění (výše) počítalo s
tím, že se geometrie u varianty 04 POSTAVÍ a jen se vyřadí z prodejního
řetězu („uložená nepoužívaná geometrie") - tohle už neplatí. Kontrola
podmínky (mezera <70mm) musí proběhnout PŘED zahájením stavby geometrie,
a pokud neprojde, geometrie se vůbec nevytváří - žádný nový uložený
nepoužitý záznam. Mechanika (kde přesně v pipeline kontrolu provést) je
na bot8. Nevztahuje se retroaktivně na už existujících 24 sestav (kód
06) - jejich případné smazání je samostatné rozhodnutí, dosud nezadané.

**⭐ Renderovací dávku zadává bot4 (PŘEKONÁNO 2026-09-12).** Původně
Robert 2026-09-11: *„rendery může zadávat jen bot3 který má přehled."*
Od 2026-09-12 je bot4 (GPU/render manager) tím, kdo rendery zadává a
řídí frontu - bot3 dál koordinuje/urguje, ale nezadává sám. Princip
zůstává stejný: žádný bot nespouští rendery z vlastní iniciativy - ani
zkušební, ani jednorázové, ani když má hotový kód a je si jistý. Kdo má
render připravený, **napíše bot4 a počká**.

**Zadání se nevyčerpá jedním spuštěním** (upřesněno 2026-09-11 poté, co
se to dalo číst dvojak). Když úlohu něco zabije, **znovuspuštění je NOVÉ
zadání** — i pro tentýž snímek, tutéž sestavu a tentýž důvod. Totéž platí
pro **změnu způsobu běhu**: mimo frontu, mimo službu, jiný stroj, jiné
parametry. Takovou změnu lze navrhnout, ne provést. Platí i pro
jednosnímkové běhy, `--test` a `--prstenec`.

Důvod je přehled na jednom místě: 11. 9. běžely kolem sestavy 333
**tři různé věci naráz** — zrušená dávka, kterou GPU stejně dojíždělo,
jeden snímek ve frontě, a odpojený Blender mimo službu. Přesně tomu
pravidlo předchází.
Důvod je provozní, ne hierarchický: jedna dávka je ~3 hodiny GPU na
jediné stanici, sestavy se mezitím mění, a bot vidící jen svůj kus
nevidí, že sestava jde za hodinu přestavět nebo že se z ní ještě má něco
smazat — tři hodiny GPU se pak vyhodí.

1. `scripts/2026-09-09_turntable_render.py <assembly_id>` zařadí úlohu
2. Agent na Robertově stanici (`Logiman2`, RTX 3060 / OptiX) si ji
   vyzvedne sám
3. Renderuje se podle Robertovy šablony `X30-1.blend` ze Sdíleného disku
4. Snímky se vrátí na server a **ingest je zapíše do DB**

Materiály bere render přímo ze šablony — `Sandblasted aluminium` na
profily, `Scratched grey plastic` na euroboxy. Naše GLB nemají UV
souřadnice, proto se textury promítají box-projekcí. Pozadí je gradient
šedá→černá, HDRI slouží jen pro odlesky.

### Kontrakt otočného náhledu

| Veličina | Hodnota |
|---|---|
| Dávka | **54 snímků** = 3 elevace × 9 azimutů (270° výseč po **30°**) × 2 velikosti |
| Z toho skutečných renderů | **27** (1024² se zmenšuje z 2048²) |
| Vzorky | **500** (šablona má 924, úloha ji přebíjí) |
| Jedna dávka | **≈ 30 minut** (naměřeno: 90 minut při kroku 10°) |

> **Krok byl 2026-09-11 zvětšen z 10° na 30°** na přímý pokyn Roberta
> („chci nastavit 30 stupnu na prstenec hned"). Dávka tím spadla z 81
> renderů na 27, tedy z hodiny a půl na půl hodiny — při 269 sestavách je
> to rozdíl mezi týdny a dny. Cenou je trhanější otáčení na webu.
> `ARC_DEG = 270` a tři prstence (−40/0/+40) zůstávají.
>
> **⛔ PAST, která to stála 90 minut GPU:** `STEP_DEG` je konstanta v
> `api/turntable.py`, kterou **běžící gunicorn drží v paměti od startu**,
> kdežto `scripts/2026-09-09_turntable_job.py` ji čte **ze souboru při
> každém spuštění**. Změna kroku se tedy projeví v nové úloze okamžitě,
> ale v ingestu až po restartu — a dávka postavená podle starého kroku
> pak při kontrole úplnosti **neprojde** („Neplatný azimut 10, 0..350 po
> 30"). Pořadí musí být: **dávka doběhne → ingest → teprve pak restart.**
> Dokud to tak je, musí se **zakázat restart celé flotile**, protože
> restartuje kdokoli.

Dávka se přijme **jen kompletní**; neúplnou odmítne chybou 409.

> **⭐ Žádné stills se nedělají** (`WORKFLOW.md` pravidlo 29). Obrázky pro
> e-shop se **přebírají z natáčecích snímků**. Robert: *„vypusť hero
> snímek, vymaž, zapomeň"*, *„převezmou se z otáčkových snímků, které
> určím"*. Zbývají čtyři pohledy (hero, bok, shora, hero 16×9) jako
> VÝSTUPY, ne jako samostatné rendery. **Pohled „zezadu" se ruší úplně** —
> prstenec je 270° výseč a zadních 90° záměrně vynechává.
> Potřebuje to tabulku „pohled → (elevace, azimut)", kterou nastavuje
> Robert, a ořez ze čtvercového snímku na potřebný poměr stran.

> **Past, která stála 40 sad snímků:** GPU cesta dlouho nevolala
> upload/commit — snímky ležely na disku (1,5 GB), v
> `product_turntable_frames` bylo nula řádků, a úloha přitom svítila
> zeleně. Opraveno commitem `3adf36f6` (`api/turntable_ingest.py`):
> přední azimut je POVINNÝ z manifestu (žádný fallback na 270), při
> neúspěchu `state="error"` a snímky se **nemažou**, `.frames/` se maže
> až po ÚSPĚŠNÉM commitu. **Po každé dávce se kontroluje počet řádků v
> DB, ne soubory na disku.**

> **Past při každé výměně šablony:** Robert soubor při úpravě smaže a
> nahraje nový, takže dostane nové `id` a ukazatel ukazuje do prázdna
> (během jednoho večera dvakrát: `1784 → 2058 → 2064`). Renderovalo by se
> s výchozími hodnotami, tiše. **Šablona se dohledává podle názvu v
> `shared_drive_files`, nikdy podle adresáře.**

### Razítkování profilů 3D logem

`scripts/razitkovac.py`, funkce `orazitkuj()`. Uloženo natrvalo v DB.

**Kdy se aplikuje — ZMĚNA 2026-09-11.** Robert: *„myslím že není jasné
kdy se pridávají razítka, melo by se stát hned poté co sestava opustí
stav ve scéně nezařazeno a přechází do konkretní složky stromu."*

Spouštěčem je tedy **zařazení do složky** — změna `category_id` z
„Nezařazená" na konkrétní složku stromu. Ne zatržítko `technicky_ok`; to
schvaluje, složka zařazuje, od 11. 9. jsou to dvě různé věci (viz fáze 2).
V tu chvíli se razítka **propíšou do dat sestavy** jako díly s rolí
`logo-ochrana*`.

Do 11. 9. se razítka počítala až při stavbě renderovací úlohy a byla
dočasná. **Bývalá výjimka (OPRAVENO audit bot9 2026-09-12, už vyřešená):**
sestava **134** (Doblo K-075 A) měla v datech 4× `logo-ochrana` **bez
výplní** — pozůstatek ručního dema z 2026-09-08. Dnes má 5 kompletních
párů logo+výplň (role `logo-ochrana-logo-0..4` + `logo-ochrana-vypln-0..4`,
ověřeno živě). Má `category_id=NULL`, takže se
při zařazení přerazítkuje podle otisku.

**Dva důsledky té změny stojí za to říct nahlas:**
- **Razítka budou nově vidět i ve 3D scéně.** Dřív tu stálo, že je tam
  nikdy neuvidíš a že je to záměr. Neplatí to — Robert je tam celý den
  hledal a nenacházel, a tohle je odpověď na to.
- **Zavírá to díru, kterou razítkování nepokrývalo.** Skutečná geometrie
  odchází nepřihlášenému příjemci přes `GET /api/public/offers/<token>/model`
  a razítka tam nebyla, protože vznikala jen v renderu. V datech sestavy
  půjde ven orazítkovaná.

Co musí platit: razítka **nesmí do kusovníku ani do ceny** (nejsou to díly
k výrobě) · **idempotence** — přeřazení mezi složkami ani druhé uložení
nesmí vyrobit druhou sadu · renderovací úloha je nesmí přidat podruhé
navrch · **přestavěná sestava potřebuje nová razítka**, protože stará
můžou sedět na profilech, které už neexistují.

**Pravidla razítka** (Robert, postupně 2026-09-09 až 11):

| Co | Jak |
|---|---|
| Rozsah | dnes **jen profily 30×30** |
| Strany | **všechny strany regálu, výslovně včetně SHORA a ZEZADU** (Robert 2026-09-11, podruhé a důrazně: *„psal jsem ze razitka 3D budou ze vsech stran regálů tzn i shora a zezadu !!!"*) |
| Hustota | **každý třetí** profil s viditelnou stěnou, na každé straně zvlášť. Umístění na profilu Robert potvrdil jako správné, mění se jen rozsah stran. |
| Zápis stran | orazítkované stěny se **ukládají** — do receptu, do tohohle postupu a do dat sestavy v DB (Robert 2026-09-11: *„zapsat razitkovane stěny do receptu, do postupu, do DB"*). Nesmí být jen dopočítané při běhu. |
| Logo | **LOGiMAN.CZ** (malé i), délka **222,204 mm** |
| Umístění | náhodně podélně, ale **deterministicky** (sha256) — má působit rovnoměrně rozmístěně |
| Minimální rozestup | **na jednom profilu se dvě loga nesmí potkat blíž než 500 mm od sebe** (Robert, 2026-09-17) — platí NAPŘÍČ stěnami, nezáleží na tom, jestli jsou na stejné nebo různé stěně profilu, pořád je to jeden profil |
| Sražení hran | horní hrany **1 mm**, **přímkou, ne obloukem** |
| Výplň drážky | pod logem, **nejvýš v délce loga**, lícuje se stěnou profilu |
| Průhlednost výplně | **50 %** |
| Materiál | OPRAVENO audit bot9 2026-09-12: platí už jen pro **výplň** ("hliník jako profily" - beze změny). **Logo** má od 2026-09-11 vlastní barvu odlišnou od hliníku (`LOGO_BARVA_HEX`, dnes `#D4863F`, navíc renderované jako barevné sklo - transmission/IOR), viz `PRODUKTOVE_RENDERY.md` "Barva loga". |

**Důsledky, které je potřeba říkat nahlas:**
- Razítka **nejsou v kusovníku a nic nestojí** — nejsou to díly k výrobě.
- Na nové varianty se použijí **samy**, není co nastavovat per sestavu.
- Výplň drážky **není kosmetika, je to oprava vady**: vnější stěna
  profilu 30×30 není plochých 30 mm, takže 8,20 mm z 28mm loga by
  přemosťovalo prázdno a `Box3` to hlásil jako lícující dotyk.

**⭐ Proč razítka do 11. 9. NEBYLA ze všech stran — a co se tím mění**

Nebyl to nedodělek v hustotě, ale **vazba výběru stěny na směr pohledu**.
`vyber_profily_k_razitkovani()` v `scripts/razitkovac.py` dělala dvě věci,
které razítka držely vepředu:

1. u každého profilu vybrala **jedinou** stěnu, a to `max(kandidati,
   key=lambda n: _dot(n, pohled))` — tedy tu nejvíc natočenou k **přední**
   kameře. Horní ani zadní stěna nemohla vyhrát nikdy;
2. profily, jejichž osa míří na kameru, **přeskočila úplně**
   (`MAX_SOUBEZNOST_S_POHLEDEM = 0.90`) s odůvodněním „vidíme jen čelo".
   To platí pro přední pohled; při pohledu shora je takový profil vidět
   celý.

**Pravidlo, které z toho plyne:** stěna k orazítkování se vybírá podle
**geometrie profilu**, nikdy podle `front_azimut_deg`. Dokud v tom
rozhodování figuruje směr pohledu, budou razítka vždycky jen z jedné
strany — a `MIN_NATOCENI_STENY` měřené vůči jedinému směru ztrácí smysl.

**Proč se orazítkované stěny musí ZAPSAT, ne dopočítávat**

Robert to zadal na tři místa naráz (recept, postup, DB) a důvod je
provozní: bez zápisu nejde po čase zjistit, **které stěny konkrétní
sestava opravdu má** — jen to, které by dostala, kdyby se razítkovala
teď. Rozdíl se projeví přesně tam, kde bolí: sestava orazítkovaná starší
verzí vypadá v datech stejně jako nová, `OTISK_VERZE` řekne jen *že* je
zastaralá, ne *čím*. Zapsané stěny navíc dovolí ověřit pokrytí bez
renderu — což je teď jediná cesta, protože rendery Robert zastavil až do
doby, než razítka budou i shora a zezadu.

**Dopad na počet:** dnešních 43 log na sestavě 333 je jedna stěna na
profil. Při všech použitelných stěnách to vychází kolem čtyřnásobku.
Číslo musí padnout **před** zápisem — může si vynutit zvednutí
`KAZDY_NTY`, a to je Robertovo rozhodnutí, ne naše.

**Kolize se musí přeměřit znovu.** Zadní stěna často dosedá ke stěně
karoserie a na horní leží police — obojí jsou místa, kde dosud žádné
razítko nebylo, takže dřívější „0 kolizí" o nich nic neříká. Na tohle
nestačí AABB; patří sem SAT s objemovým vzorkováním
(`scripts/2026-09-11_mesh_kolize_lib.js`).

**Ověřeno 2026-09-11 na (dnes smazané, nahrazené sestavou 344) sestavě 333:** úloha má **112 dílů proti 98 v
sestavě** — 7× `logo_logiman_cz.glb` + 7× `vypln_drazky_30.glb`.
Razítkovač do úlohy prokazatelně přidává; pokud razítka nejsou vidět,
příčina je až na snímcích (materiál hliník na hliníku, 50% výplň, nebo
razítko mimo 270° výseč prstence).

> **Díra, kterou razítkování nepokrývá:** chrání se tím **jen otočný
> náhled**. Skutečná geometrie odchází nepřihlášenému příjemci ještě
> jednou cestou — `GET /api/public/offers/<token>/model` — a tam razítka
> nejsou. Veřejný payload otočky navíc vrací přesné vnější rozměry
> sestavy v mm; to je samostatná díra, na kterou razítko nemá vliv.

---

### Pasti renderovací cesty — všechny zaplacené 2026-09-11

> **Podlaha se při pohledu zdola vykresluje jako plocha.** Šablona
> `X30-1.blend` nemá objekt `TT_FLOOR`, takže si kód pro každý render
> vyrobí vlastní rovinu jako zachytávač stínů. Při `film_transparent =
> False` a pohledu **zezdola** (elevace −40°) ta rovina sice nic
> nevykreslí, ale **fyzicky blokuje kameře výhled** — usekne spodek
> sestavy rovnou hranou a díly čnějící ven z jejího okraje vypadají jako
> odtržené a poletující. Řešeno v kódu: podlaha se skryje kameře pro
> záporné elevace. **Do šablony se nesahá, je Robertova.**
> Zdůvodnění, které rozhoduje: při pohledu zdola vzhůru **není co
> simulovat** — nikdo ve skutečné fotce z podhledu zem nevidí.

> **„Skrytý díl" znamenalo „nenačitelný".** `visible_in_scene = 0` se v
> prohlížeči filtrovalo **na vstupu do celého katalogu**, ne až v
> pickeru. Sestava, která takový díl nese (logo, výplň drážky), pak
> nešla vůbec vložit do scény — *„neznámý díl vypln_drazky_30 v
> katalogu"*. Filtr patří do funkce, která staví seznam „vlož nový díl",
> ne do plnění katalogu.

> **Zrušení renderu nic neruší.** Agent na stanici zrušení neumí přečíst,
> takže GPU dávku dopočítá do konce a server výsledek zahodí. „Zrušit"
> dnes znamená jen „zahodit výsledek" — plná cena GPU se zaplatí tak jako
> tak. Neopraveno.

> **Složka pro snímky vytvořená rootem zablokuje ingest.** Služba běží
> pod `www-data`; adresář založený skriptem pod rootem do ní nepustí a
> převzetí spadne na `Permission denied` — **až po doběhnutí celého
> renderu.** Každý skript, který sahá na cesty, které používá aplikace,
> se pouští `sudo -u www-data` / `systemd-run --uid=www-data`.

> **Archiv na Sdíleném disku patří do KOŘENE `otočky/`.** Robert se dívá
> do složky a čeká, až v ní přibudou obrázky — ne o úroveň níž do
> podsložky s hashem dávky. Aktuální dávka je v kořeni; při příchodu nové
> se stará **odsune** do podsložky (přeřazením, ne kopií). Rozlišuje se
> příznakem `live` v manifestu.

> **Tichá archivace = nedohledatelná archivace.** `archivuj_davku`
> nezanechávala v logu stopu ani při úspěchu, ani při neúspěchu — vlastní
> logger nenapojený na nic, a k tomu `app.logger` na úrovni WARNING,
> takže `info` zanikalo i po opravě první příčiny. Hledalo se kvůli tomu
> půl hodiny něco, co bylo v pořádku.

## Fáze 5 — Web

`webapp/product.html`

✅ `GET /api/shop/products/<id>/assemblies` — veřejné, jen `id`, `name`,
`has_turntable` ·
✅ `GET /api/shop/products/<id>/turntable?assembly=<id>` ·
✅ **posuvník hotový** (bot5, `aa050117`→`04ca8850`→`b9b24d82`→`c89a7a68`,
2026-09-12): svislý slider místo tlačítek, mění obrázek I cenu, klávesnice
+ ARIA `role="slider"`, neschválené provedení zůstává na rysce bez
posunu skrz — viz ⭐ blok níže.

⬜ **Zadáno bot8, zatím NEHOTOVO (Robert 2026-09-13, přes bot9):**
*„Když mám vybraný jakýkoli snímek, který nese info o úhlu, a
posuvníkem změním sestavu, musí se nová sestava načíst snímkem s
totožným náklonem/úhlem."* Týká se přepínače variant (`fd6c0392`,
bot8) - dnes po přepnutí sestavy naskočí výchozí/první snímek, ne
stejný úhel/elevace, který měl zákazník rozkoukaný před přepnutím.
Implementace na bot8 (jeho feature, guardované soubory).

**⭐ Posuvník mění provedení a s ním CENU** (Robert 2026-09-11, opravuje
dřívější zápis). Do té doby tu i v kódu stálo *„mění se JEN obrázek,
kusovník ani ceny na veřejnou stránku nepatří"* — **neplatí.** Sedm
provedení stojí 24 237 až 32 141 Kč, to nemůže být jedno číslo.

**Kusovník ven NEJDE.** Robert: *„Jen cena, kusovník zůstává vnitřní."*
Rozpis dílů prozrazuje konstrukci skoro stejně jako geometrie — počítá se
z něj cena, ale neposílá se.

**V přehledu produktů zastupuje kartu jedno provedení, které určí Robert**
— jeho obrázek a jeho cena. Drží to příznak `is_master` na sestavě, právě
jedna na kartu, vynuceno transakčně.

> **⛔ Cena, kterou vidí zákazník, se NEBERE ze sestavy.** Čte se z
> `shop_products.price_czk_placeholder` a to pole **nic neplní** — jediní
> dva zapisovatelé se týkají cen profilů, ne sestav. Zveřejnit kartu bez
> jeho vyplnění znamená, že zákazník neuvidí **žádnou** cenu, ne špatnou.
> Robert 2026-09-11 rozhodl **publikovat i bez ceny** a doplnit ji sám.

> **Objednávka neumí nést zvolenou variantu.** Proto má tlačítko do
> košíku jen zástupce karty; u ostatních provedení je místo něj
> poptávkový odkaz. Jinak by si zákazník koupil cenu zástupce, a viděl
> jinou.

✅ posuvník místo dnešních tlačítek (viz výše) ·
⬜ obrázky (viz fáze 4) ·
✅ **OPRAVENO bot5 2026-09-15 (`d72bedbc`): barevný puntík (osobní
značka Roberta ve scéně) unikal na kartu.** Robert: *„priznak u
nekterych sestav je jen pro muj prehled ve scene, nemá se prenášet dál
do systemu"* - barevný puntík 🟠 (U+1F7E0) na začátku
`product_assemblies.name`. Unikalo živě na kartu 3947 (Jumpy K-120,
nález bot3). Oprava na všech 3 výstupech (server `verejny_popisek_
sestavy()`+`obsahuje_interni_znaceni()` pro galerii, klient
`pdOcistiVerejnyPopisek()`/`pdAssemblyLabel()`) - široký Unicode rozsah
místo jednoho konkrétního emoji, odolné i vůči budoucím značkám. Ověřeno
živě bot3, `curl` na 392/396/400 čisté, běžný český text s diakritikou
beze změny.
✅ **OPRAVENO bot5 2026-09-12 (`e8e91a3d`): únik interního textu.**
`pdAssemblyLabel()` propouštěla `[10/30mm od kolize]` (hranatá závorka
se neořezávala, jen kulatá) a u Jumpy i samotný K-kód (K-118/K-119,
zakázáno pravidlem 25). Neuniklo živě (karty měly `active=0`), ale
blokovalo publikaci. Oprava: `pdOcistiVerejnyPopisek()` jako poslední
krok před vrácením (ořízne `[...]` i `K-XXX` včetně `K-123e`, prázdný
výsledek padá na neutrální „Provedení" — **nikdy** na původní text jako
fallback, i po vyřešení otázky níže tahle pojistka zůstává). Ověřeno na
13/13 reálných názvů + okrajové případy. QA `k_kod_v_zakaznickem_textu`
rozšířena o `product_assemblies.name` + nová kontrola na `[hranaté
závorky]` (K-kódová chytala jen půlku úniku) — obě dnes 0 nálezů. ·
✅ **OPRAVENO bot5 2026-09-12: nebezpečně mylný komentář o marži.**
`api/product_assemblies.py` tvrdil u veřejného endpointu „bez marže,
koeficient 1.0" — změřeno na datech, marže **1,400 je v `price_summary`
už zapečená** (aplikuje se jednou v `/api/katalog`), ceny jsou v pořádku.
Komentář ale hrozil, že příští bot marži přičte podruhé (zákazník by
zaplatil 1,96× náklad) — přepsán i s postupem měření. ·
✅ **bot8 dokončil kusovníky pro 341-351 (2026-09-12).** Všech 13 sestav
má `bom`+`price_summary`: Doblò 3943 11 822–17 250 Kč (7 provedení),
Jumpy L2 3944 7 713–9 144 Kč, Jumpy L3 3945 9 629–11 643 Kč; karta 3943
má 54 aktivních snímků otočky. **Asymetrie se potvrdila:** zástupce
(343) je jediné provedení BEZ ceny, protože ta se bere z
`shop_products.price_czk_placeholder`, které plní jen Robert ručně —
konkrétní chybějící hodnota je na kartě 3943. ·
❓ produkt `3942` není publikovaný (`active=0`, `is_archived=1`, veřejné
API vrací 404 - OPRAVENO audit bot9 2026-09-12: kategorie [`id=247`,
"Regály do auta"] i popis jsou dnes vyplněné, zbývá jen rozhodnutí o
publikaci; navíc jediná sestava 337 byla mezitím smazána, nástupce je
produkt 3943 se sestavami 341-347) ·
❓ zákaznické názvy variant (viz fáze 1)

✅ **AKTIVOVÁNO bot3 2026-09-12** (Robert: *„zapni to na eshopu rendery
se doplní az budou"*): `shop_products.active=1` pro 3943/3944/3945.

✅ **OPRAVENO bot5 2026-09-12: stejný únik i přes samotné API, ne jen
frontend.** `GET /api/shop/products/<id>/assemblies` vracelo
`product_assemblies.name` syrové - klientská `pdOcistiVerejnyPopisek()`
čistí jen to, co jde přes prohlížeč, kdokoli s přímým dotazem na
veřejné (bez auth) API dostal `[10/30mm od kolize]` i K-kód. Ověřeno
`curl` naživo bot3 2026-09-12, karty už byly aktivní. Opraveno na
serveru na dvou postižených endpointech - klientská pojistka zůstává
jako druhá vrstva, ne jediná.

✅ **OPRAVENO bot5 2026-09-12 (`df322a89`): třetí výstupní bod, popisek
galerie.** `GET /api/shop/products/<id>` vracel `gallery[0].caption`
sestavené z `assembly_name` syrové (peče se do DB při commitu otočky v
`_fill_gallery_and_thumbnail`, `api/turntable.py` - kořen zůstává na
bot4, tohle je čtecí pojistka nad tím, co už v DB leží). Oprava v
`shop_products_get` čistí jen popisky, kde je opravdu zakázaný obsah
(`[...]`/K-kód) - plošné čištění by u běžných fotek (např. „Profil
30x30 - detail drážky") uřezalo první slovo, proto se aplikuje
selektivně. Ověřeno naostro na 4 veřejných výstupech (varianty
3943/3944, galerie 3943, storefront Doblò) + bez regrese na `/`,
sitemap, kategorii, produktu i obou API (vše 200). Potvrzeno: jediná
další veřejná cesta pro caption (`app.py:3194`/`4517`,
`gallery_items.py:266`) vybírá jen `filename`, žádná další díra.

🔴 **NÁLEZ bot5 2026-09-12, předáno bot4: `api/turntable.py:1340`
deaktivuje otočky podle `shop_product_id` BEZ filtru na `assembly_id`.**
Důsledek: commit nové dávky zhasne otočky VŠECH OSTATNÍCH sestav téže
karty, karta nikdy nemůže mít víc než jedno `has_turntable=true`
zároveň. Na kartě 3943 se to stalo 4×, tři kompletní sady 54 snímků
(341/342/347) jsou dnes zhasnuté a `GRACE_HOURS=24` je fyzicky smaže
zítra večer, pokud se nezachrání dřív. **Robertův předpoklad „rendery
se doplní samy" tímhle padá** - posuvník se bez opravy nikdy neodemkne
na víc než jedno provedení na kartu, ať se vyrenderuje cokoli navíc.
Robert: *„Reš to s Botem 4 nebo 3"* - v gesci bot4 (spravuje
`turntable.py`), bot3 koordinuje/urguje.

**V řešení 2026-09-12 (bot4+bot16):** bot4 nález nezávisle ověřil (řádek
~1338), poslal bot16 opravu + seznam batch ID k reaktivaci
(341/347/342/343, plus 344/345/346 až dorendrují) i gallery caption
nález jako dodatek téže opravy. Bot3 neduplikuje, čeká na hlášení
hotovo. Restart gunicornu proveden bot3 2026-09-12 (bezpečnost ověřena
reálným importem, ne jen syntaxí) - nasadil zároveň i caption opravu
výše.

ℹ️ **Posuvník je dnes ZÁMĚRNĚ omezený jen na provedení s hotovou
otočkou** (bot5, po reaktivaci naskočí víc dosažitelných poloh, ale ne
všechny) - Robert: *„bude lepší počkat na ty rendery"*. Plné odemčení
(jezdec dosáhne i na provedení bez otočky) je hotové a otestované jako
patch v `backups/2026-09-12_bot5_posuvnik_odemceni/`, nasazení čeká na
Robertovo rozhodnutí, není to bot5ovo řešit samo.

**⭐ Pravidlo zveřejňování karty** (Robert 2026-09-15): *„preferuje se
zverejnit prestoze nemá karta kompletní data o vsech variantách"* · *„ke
zverejnení karty stací 1 kompletní varianta renderů"*. Karta tedy
NEČEKÁ s `active=1` na hotové rendery všech provedení - stačí, aby JEDNO
provedení (typicky `is_master`, viz zástupce výše) mělo kompletní
otočku, zbytek doplní render fronta postupně. Stejný princip jako už
dřívější „publikovat i bez ceny" (2026-09-11 výše) - zveřejnit dřív,
doplňovat průběžně, nečekat na stoprocentní úplnost.

---

## Co čeká na rozhodnutí Roberta

| Otázka | Proč to blokuje |
|---|---|
| **Kde bydlí zákaznický název?** | Bez něj jde na web „NÁHLED horní blok 1/6…". |
| **Publikovat produkt 3942?** | Do té doby web nemá co ukázat. |
| **MDF čte v renderu modře** | Odstín `#5c626a` vytáhne pod AgX modrou složku víc, než jak vypadá ve scéně. |
| **Jaké typologie existují** | Padly čtyři (EB/UN/OS/EV), seznam nebyl uzavřený. Každý pozdější přírůstek mění formát kódu. |
| **Výše marže** | Ovládání: Admin → Koeficienty cen. Koeficient scény (`app_settings.scene_price_coefficient`) je od 2026-09-25 **1,25** a od 2026-10-01 platí **jen pro profily a produkty z Dogusu** (Robert: „koeficient pro scénu se týká jen profilů a produktů které se načítají z dogusu“), ostatní díly jdou v základní ceně. Balné 3 % (Robert 2026-10-01). Všech 530 sestav + 12 karet přepočteno (bot8, commit `c77795b5`, záloha `backups/2026-10-01_prepocet_koef_profily_dogus/`). |
| **Cena za posuvníkem verze** | A, B a C mají různý obsah boxů, tedy různý náklad — na jedné kartě to znamená cenu per kombinaci, dnes karta umí cenu jedinou. |
| **Objednávka musí nést kombinaci** | Jedna karta = jedno SKU, ale tři verze boxů jsou fyzicky různé zboží k vychystání. |
| **Je umístění plošné napříč katalogem, nebo per skupina/vozidlo?** (nález bot9 2026-09-13, sweep AGENTS_LOG.md) | `profil_mm=30` zapsal bot5 plošně pro celý katalog (293/293) - otevřené, jestli totéž platí i pro **umístění** (dnes RB), nebo se musí určovat po skupinách/vozidlech zvlášť. |
| **⛔ Horní blok 06 má reálnou geometrickou kolizi, nikdy funkčně neověřen** (nález bot8, log #30866/#30882, sweep bot9 2026-09-13) | Provedení „dvě pásma, plné výplně, s policí, horní příčka jen u přepážky" - role `vypln-bok-prepazka` proniká do `pricka-spodni-0`/`pricka-police-0`. Ověřeno na OBOU vozidlech, kde se dnes zkoušelo (Doblo A i B) - kolize obou, ne jen jednoho. Bot8 to dvakrát nechal jako otevřený nález, dosud nezapsáno k rozhodnutí. |

**✅ Vyřešeno 2026-09-13: počítá se příslušenství do ceny spoje?** Robert
opakovaně a výslovně potvrdil pravidlo **profil-profil** (min. jedna
strana „čelo"; „bok profilu k boku není spoj") - příslušenství (úhelníky,
záslepky) se do ceny spoje NEPOČÍTÁ. Uzavřeno na 4 místech (viz
`AGENTS_LOG.md` 2026-09-13, „spor spojů #2" + „sjednocení jointCount"):
`scene.html` mělo 3 nezávislé kopie stejné logiky, sjednoceno do jedné
funkce `classifyJointPair`; k tomu nový Node.js backfill port
`detectRealJointCount` (profil-profil only, záměrně samostatný podle
Robertova rozhodnutí).

**Oprava vlastního zápisu (bot8 2026-09-13):** předchozí verze tady
mylně mluvila o "watchdog kroku, který ještě čeká na implementaci" -
ve skutečnosti šlo o DVĚ různé věci. Vyřazený `joint_count_backfill`
(`joint_count_batch.js`) zůstává vyřazený navždy - jeho úkol dnes plní
**JINÝ, už dřív povolený krok automatu, `bom_backfill`**
(`2026-09-06_backfill_bom_price.js`), do kterého bot8 `detectRealJointCount()`
přímo integroval. **Není to plán, už je to hotové a spuštěné:** bot8 ho
2026-09-13 ručně pustil na CELÝ katalog (303/303 sestav, 0 chyb, přímo
na Robertův pokyn v chatu "potřebujeme aktualizovat ceny sestav v DB,
podle scény, napříč systémem"), záloha stavu před zápisem
`backups/2026-09-06_bom_backfill/pred_zapisem.json`. **Výsledek, ověřeno
bot3 přímo v DB:** cena spojů napříč katalogem `0 → 21 944 ks / 2 413 840
Kč`. Živě dotčená je jen karta **3943** (jediná `technicky_ok=1`) -
`price_czk_placeholder` přepsán `15 247 → 26 682 Kč`, odsouhlaseno bot5.
Karty 3944/3945 nejsou `technicky_ok`, zákazník je neviděl. Starý
`joint_count_backfill` zápis ve `scripts/2026-09-11_watchdog_prace.py`
se má označit jako trvale obsoletní (úkol už plní `bom_backfill`), ne
"čeká na implementaci" - dva nezávislé zapisovače do stejných dat by
byl závod, ne přínos.

**Rozhodnuto 2026-09-11:** vzorky **500** · kusovník **zůstává** a
následuje posuvník · HDRI balit netřeba · kód nese **všech šest složek** ·
profil se píše **30/40/45** a určuje ho **admin** · bez horního bloku =
**0** · pohled **zezadu se ruší** · prodejní cena = **náklad × marže** ·
**vzor se dělá na Doblu C**, starší horní bloky neplatí · **0/6 nesmí mít
ani jeden díl horního bloku** · zatržítko **schvaluje**, složka
**zařazuje** · karta se jmenuje **po vozidle** · typologie dvouznakově
**EB / UN / OS / EV** · **SKU neobsahuje slovo SEST** · **rendery zadává
jen bot3** · **do tohoto plánu zapisuje jen bot3, čte ho každý bot**.

---

## Doporučené pořadí

1. **Dokončit vzor — šest provedení na Doblu C.** Je to předloha pro
   všechna ostatní vozidla; starší horní bloky neplatí a přestaví se
   podle něj. Dokud vzor není hotový, nemá smysl dělat nic dalšího.
2. **Vyčistit sestavy** — staré horní bloky a kolizní úhelníky
   (viz pracovní seznam).
3. **Schválit** zatržítkem. Tím se otevře zbytek řetězu.
4. **Doplnit kusovníky** a napojit sekci v kartě na posuvník.
5. **Jedna zkušební otočka** (Robert 2026-09-11: *„Jedna sestava jako
   zkouška"*) — teprve po jeho OK se pouští zbytek.
6. **Vyrenderovat kompletní otočky.** Dlouhé, ale bez dozoru.
7. **Publikovat produkt a nasadit posuvník na web.**

---

## Kroky výrobní linky (specifikace tabulky na dashboardu)

Tohle je obsah přehledové tabulky — panel **na dashboardu adminu**, první
shora, přes celou šířku; ostatní panely dostaly sbalování, aby se tam
vešel. Řádek = **karta** (vozidlo × typologie), rozbalitelná na jednotlivé
sestavy pod ní.

### A) Dopočítané — neodškrtávají se

Zaškrtnou se samy, jakmile jsou pravda. **Ručně je přepsat nejde a nesmí
jít** — to je celá pojistka proti tomu, aby se přehled rozešel se
skutečností, jak se to už jednou stalo (40 hotových sad snímků na disku,
0 řádků v DB, a plán přitom tvrdil, že je hotovo).

| Klíč | Fáze | Splněno, když |
|---|---|---|
| `scena_bom` | 1 | sestava má neprázdný `bom` a `price_summary` |
| `schvaleno` | 2 | `technicky_ok` |
| `razitka` | 3 | sestava má v `data.parts` díly s rolí `logo-ochrana*` **v aktuální podobě** (sedí otisk) |
| `karta` | 3 | `shop_product_id` není NULL |
| `rendery` | 4 | existují aktivní řádky v `product_turntable_frames` |
| `web` | 5 | produkt `active=1` a má kategorii |

### B) Odškrtávané ručně — dvoustavově

Kroky, na které se databáze zeptat neumí. **„hlášeno hotovo"** zapíše
bot, který práci dělal; **„ověřeno"** zapisuje **jedině bot4 (kontrolor)**
po nezávislém ověření, s krátkým verdiktem. Robert 2026-09-11:
*„kontrolor bot4 bude do prehledove tabulky odškrtávat zda je zadana
prace /ukol flotile skutečně dokončená."* Znovu-nahlášení téhož kroku
ověření ruší.

| Klíč | Úroveň | Fáze | Co znamená |
|---|---|---|---|
| `geometrie_zkontrolovana` | sestava | 1 | spoje prověřené podle metodiky — překryv na všech 3 osách, topologie rohu, reálná GLB geometrie |
| `vycisteno` | sestava | 1 | pryč staré horní bloky a kolizní úhelníky |
| `vzor_prestaven` | sestava | 1 | postaveno podle schváleného vzoru (Doblo C), ne podle starších provedení |
| `prvni_otocka_schvalena` | **karta** | 4 | první otočka vozidla proběhla a Robert ji viděl, teprve pak se pouští zbytek |
| `texty_hotove` | **karta** | 5 | zákaznický popis a texty produktu hotové |

Kroky žijí v číselníku (`production_step_defs`), ne natvrdo v kódu —
přidat krok je řádek, ne migrace. **Seznam poroste; neber ho jako
uzavřený.** Nový krok se nejdřív popíše v tomhle dokumentu, teprve pak
přibude do číselníku.

> **⭐ STAV se v tabulce neklikne. Jediná výjimka je blokace.**
> Fáze i kroky jsou ke čtení — nic se v nich nezaškrtává a nic se v nich
> nehledá. Zápis do kroků jde výhradně přes API s botím tokenem,
> „ověřeno" navíc jen kontrolorským. Vynuceno **v endpointu**, ne
> skrytím tlačítka; skryté tlačítko není zámek.
>
> **Volně psaná blokace (oddíl C) je výjimka a je to záměr** — je to
> jediné pole, které člověk vyplňuje, protože data neumí říct PROČ něco
> stojí. Netýká se jí to „bez výjimky", které platí na stav.
>
> **Meze toho vynucení, ať se nepřeceňuje:** oba tokeny leží v
> `api/.env` a boti běží jako `root`, takže si je kterýkoli bot přečte.
> Proti UI a proti omylu to drží, proti záměru ne — stejný strop jako u
> přístupu k databázi. Pojistkou je proto **stopa**: kdo volal se
> zaznamenává **ze serveru podle použitého tokenu**, nikdy z těla
> požadavku, a na nesoulad má být kontrola.
>
> Původně tu byl krok `robert_potvrdil_scena` a zaškrtávátka byla
> klikatelná pro staff. Obojí padlo 2026-09-11: Robert si omylem kliknul
> fajfku a řekl k tomu *„určitě nebudu klikat v tech vnitřních tabulkách
> a neco hledat, pokud jsem ve sceně udelal zatrzitko nebudu to prece
> potvrzovat znova."* **Jeho potvrzení JE zatržítko ve scéně** — tedy
> `technicky_ok`, které už je v tabulce jako dopočítaná fáze
> „2 Schváleno". Krok byl tedy žádost o totéž podruhé na jiném místě.
> A zaškrtávátko, které jde kliknout omylem, je ve výkazu stavu vada:
> přesně tím se přehled rozejde se skutečností.

> **Sloupec `razitka` je BRÁNA PŘED RENDEREM.** Robert 2026-09-11:
> *„v tabulce stavu sestav: chybi sloupec razitka (aby se mohlo
> renderovat)."* Neorazítkovaná sestava se nemá renderovat — vyrenderovala
> by se neochráněná. Proto stojí mezi schválením a rendery.
> **Nezaškrtává se ručně** — od chvíle, kdy se razítka propisují do dat
> sestavy při zařazení do složky, na to data umí odpovědět sama.
> Dvě pasti: existovala **stará razítka ve vadné podobě** (sestava 134
> nesla 4× `logo-ochrana` bez výplní, pozůstatek dema z 8. 9. - OPRAVENO
> audit bot9 2026-09-12, dnes má 5 kompletních párů logo+výplň) a rozhodovat se
> podle pouhé přítomnosti rolí by je počítalo jako hotové. Proto se čte
> **otisk** (`razitka_otisk`), ne jen přítomnost. Predikát je sdílený —
> `isStampPart()` ve `webapp/js/scene-geometry-shared.js`, Python
> protějšek `je_razitko()` v `scripts/razitkovac.py`; **nepsat si vlastní**.

### B2) Kdo s tabulkou pracuje a jak

Robert 2026-09-11: *„tabulka drží aktuální stav, o dodržování aktuálního
stavu v tabulce se stará bot4 kontrolor, bot3 koordinator vidí stav
práce, zná při rozdelování úkolů cokdo umí nejlépe resp jaký má kontext a
podle toho stavu se řídí jak rozdelovat nedokončené ukoly."*

| Kdo | Co v tabulce dělá |
|---|---|
| **Tabulka** | drží **aktuální stav**. Nic víc a nic míň — není to fronta úkolů ani archiv. |
| **bot4 kontrolor** | **ručí za to, že stav v tabulce odpovídá skutečnosti.** Odškrtává „ověřeno", a to až po nezávislém ověření. Když se do věci znovu sáhne, ověření padá. |
| **bot3 koordinace** | **čte z tabulky, co je nedokončené, a podle toho rozdává práci.** Nerozhoduje se podle toho, kdo je zrovna volný, ale podle toho, kdo danou věc umí nejlíp a kdo v ní už má kontext. |
| **ostatní boti** | hlásí „hotovo" u svých kroků. Práci si z tabulky **neberou sami** — čekají na zadání od bot3. |

Proč to takhle: koordinace, která rozdává podle volných rukou, posílá
práci tam, kde se musí celý kontext budovat znovu. Tabulka má proto vedle
stavu nést i **kdo na kroku naposledy dělal** — to je pro rozdělování
stejně důležité jako samotný stav.

A proč ověřuje někdo jiný než ten, kdo dělal: 11. 9. se třikrát stalo, že
hlášení „hotovo" bylo optimističtější než skutečnost, a pokaždé se to
našlo pozdě a náhodou. Sebehodnocení ten rozdíl nezachytí.

### B3) Kolize — červený název ve scéně

Robert 2026-09-11: *„označ mi ve scene ty sestavy resp jejich nazev
červenou barvou, tak budeme indikovat sestavy ktere maji kolizi a já se
na ně podivam."*

**Není to seznam konkrétních sestav, je to obecný ukazatel.** Sestava s
kolizí má ve scéně červený název; když se kolize opraví, červená zmizí
sama. Týž údaj nese i sloupec v přehledové tabulce — proto se **ukládá
jednou pro obojí**, ne zvlášť pro scénu a zvlášť pro dashboard.

Co se ukládá per sestava: má/nemá kolizi · počet kolizních dílů · kdy se
to měřilo. Příznak, který se počítá jen ručně, **zastará a bude lhát
oběma směry** — musí mít spouštěč přepočtu.

> **Kolize se rozhoduje na SÍTI, ne na `Box3`** (recept `id=7`, verze 3,
> bot16 2026-09-11). Obálka je jen předfiltr. Tři pasti, které to stálo:
> **(a)** hloubka není nejhlouběji zanořený vrchol — díly sdílejí roviny,
> takže vrcholy zabořeného dílu leží přesně NA stěně druhého a vzdálenost
> vyjde 0; **(b)** hloubka není ani nejmenší rozměr společné hmoty — u
> úhelníku, jehož stěna projde skrz profil, je to tloušťka jeho plechu
> (6,3 mm) bez ohledu na zaboření, proto se hlásí **odsun** potřebný k
> rozpojení; **(c)** **katalogové sítě nejsou vodotěsné** — profil je
> vytlačený průřez otevřený na koncích, takže paprsek po jeho ose vyletí
> bez průsečíku a parita řekne „venku", i když je bod uprostřed materiálu.

**Nezávislé potvrzení, že pozice nesmí být kritériem:** obálka hlásila
přesahy 5 až 22 mm, ale skutečný odsun je u **všech 60** kolizních
úhelníků mezi **4,96 a 5,95 mm**. Obálka nadhodnocovala podle toho, jak
daleko na profilu úhelník sedí, ne jak hluboko je zabořený. Je to jedna a
tatáž vada posazená pokaždé jinam.

### C) Blokace

Jediné volně psané pole na obrazovce. Data neumí říct **proč** něco
stojí — „čeká na Roberta", „8mm kolize", „čeká na přestavbu vzoru".
Ukládá se s historií (kdo, kdy, `resolved_at`), na obrazovce se ukazuje
jen poslední nevyřešená.

### D) Další krok

Dopočítaný z první nesplněné fáze, jedna krátká fráze: *doplnit kusovník ·
čeká na schválení · založit kartu · pustit rendery · publikovat · hotovo*.

---

## Pracovní seznam

Průběžně aktualizovaný stav — **zapisuje jen bot3**. Boti hlásí změny
zprávou.

### Běží (2026-09-11)

| Co | Kdo | Stav |
|---|---|---|
| Zkušební otočka nástupnické sestavy 344 (dřív 333) + ověření razítek na snímcích | bot8 | čeká na doběhnutí |
| Oprava `ttStillsForFront()` ve `scene.html` (upload stills padá na 400) | bot8 | zadáno |
| Rozšířené pravidlo kolizních úhelníků + výpis 20 kusů k posouzení | bot16 | běží |

### 8mm kolize — podklad hotový, čeká na Robertovo rozhodnutí

Nález existoval na **(dnes smazané) sestavě 337** (`K-075-EB-30-C-0063-6-0`,
produkt 3942 „Regál na euroboxy – Fiat Doblò L1H1 (do 2022)"). OPRAVENO
audit bot9 2026-09-12: produkt 3942 dnes nemá napojenou sestavu, nástupce
je produkt 3943 (sestavy 341-347) - ověřit, jestli 10/30mm kolizní
rezerva na nástupnických sestavách tenhle nález řeší. Obě
dvojice byly v ní:
`pricka-spodni-0` × `vypln-bok-prepazka-a` a
`pricka-police-0` × `vypln-bok-prepazka-b`.

Hrana MDF desky boční výplně u přepážky zasahuje do dutiny příčky o
**8 mm** v ose tloušťky desky, místo navržených 7 mm.

Řezy ze živého stavu (`2026-08-20_live_section_cut.js`, matice přímo z
`data.parts`) na Sdíleném disku, složka **Produktové sestavy → Fiat**:
`2026-09-11_rez_8mm_nalez1_pricka-spodni-0_x_vypln-bok-prepazka-a_sestava337.png`
a `…_nalez2_pricka-police-0_x_vypln-bok-prepazka-b_sestava337.png`.

> **Omezení měření, ať se to nepodává s falešnou přesností:** metoda
> (nejmenší osa `Box3` překryvu, tatáž, jakou používá generátor)
> nerozliší „hloubku konkrétní drážky" od „celé tloušťky desky uvnitř
> 30mm profilu". Číslo 8 mm je konzistentní a reprodukovatelné, ale není
> to proměření posuvkou.

### Dluhy renderovací cesty — nalezené 2026-09-11, neopravené

| Co | Proč to bolí |
|---|---|
| **Zrušení renderu nic neruší** | Agent na stanici ho neumí přečíst, takže dávku dopočítá do konce a server výsledek zahodí. Každý omyl v zadání stojí **plnou cenu GPU**, i když se odhalí po minutě. Dnes to znamenalo, že ověřovací snímek čekal půl hodiny za dávkou, kterou jsem zrušil. |
| **Lokální render běží uvnitř webové služby** | Restart ho zabije. Dnes dvakrát za 35 minut. Bot8 to obešel spuštěním mimo službu, ale příčina trvá — dokud tam je, je každé nasazení hazard a všichni čekající boti rukojmí. |
| **Idempotence nerozlišuje tentýž render od varianty** | „Jedna sestava = jedna aktivní úloha" správně brání dvojímu renderu téhož, ale odmítne i **tři varianty téhož snímku** (jiný barevný převod, jiná elevace). Dnes to zablokovalo srovnání, které si Robert vyžádal. Zpřesnit rozlišením podle parametrů úlohy, ne narychlo — je to pojistka, kterou bot4 ověřoval. |
| **Sdílené cesty v `/tmp` u backfillu** | `2026-09-06_backfill_bom_price.js` píše dumpy na pevné cesty bez atomického přejmenování. Dnes teoretický souběh; jakmile poběží automat pravidelně, pravděpodobnější. Dopad je „běh selže a zkusí se znovu", ne špatná cena. |

### Čeká na Roberta

| Co | Proč |
|---|---|
| Spustit mazání kolizních úhelníků dole v nohách (24 kusů z 12 sestav) | vrstva oprávnění to botům zamítá natvrdo |
| Posoudit 20 kolizních úhelníků jinde než dole | Robert 2026-09-11: *„Napřed mi je ukázat"* |
| Potvrdit zkušební otočku, než se pustí zbytek | Robert 2026-09-11: *„Jedna sestava jako zkouška"* |

### Hotovo 2026-09-11

- Mazání starých horních bloků (167 dílů ze 7 sestav: 134,135,182,189,209,219,289) — `scripts/2026-09-11_smazat_stare_horni_bloky.py`, záloha `backups/2026-09-11_stare_horni_bloky_pred_smazanim.json` (OPRAVENO audit bot9 2026-09-12, dřív uvedeno jako "Čeká na Roberta").
- Ingest z GPU do otočného náhledu (`3adf36f6`) — přední azimut povinný
  z manifestu, chyba je vidět, snímky se po neúspěchu nemažou.
- Sjednocení `stills_for_front()` se `STILL_VIEWS` (`4402d074`) — do té
  doby se nedala postavit úloha pro **žádnou** sestavu. Opraveno podruhé
  (`629db00d`): první oprava srovnala seznamy, ale hlídala **špatný
  invariant** — pravidlo 29 říká, že se stills nemají dělat vůbec, ne že
  mají sedět. Ty čtyři se pořád renderovaly a nikdo je nečetl, ~10 min
  GPU navíc **na sestavu**, přes 264 sestav desítky hodin. Teď
  `stills_for_front()` vrací `[]` a kontrola hlídá „nic se nerenderuje".
- Audit zbylých výskytů pohledu „zezadu": DB čistá, zbytek komentáře.
  Jeden živý nález zůstává — `ttStillsForFront()` ve `scene.html`.
- Číslování a formát kódu sestavy (`19d8104b`), 268 z 269 sestav.
- SKU už neobsahuje `SEST-` (Robert: *„v sku nebude slovo SEST"*).
- Karoserie v renderu uzavřena: `resolve_parts()` `car_body_*`
  přeskakuje, mazat je ze sestav NELZE, dokud je `car_model_id` NULL.

### Nová osa: typ sestavy (auto/stůl/…) — zadáno 2026-09-26

Robert: *„nekde v adminu potrebujeme centrálně spravovaný text a
strukturu pro detail sestav, podle toho jestli je to větev 1 nebo 2,
jestli to bude sestava do auta nebo stůl nebo jiná struktura… Každá
sestava kromě svého vlastního popisu vycházejícího z geometrie a
příslušenství bude mít centrálně řízené společné části popisu/textu i
volitelné služby právě podle toho, jestli je to autosestava nebo
např. stůl do skladu."*

Dnes model **neexistuje** — `product_assemblies` je skrz naskrz stavěný
kolem auta (`car_model_id`, `karoserie_kod`, `umisteni_id` jsou core
sloupce, ne volitelné). `regal_typologie`/`typologie_varianty` řeší jen
KONSTRUKCI regálu (euroboxy/univerzální/šuplíky…), ne to, jestli je
cílová sestava vůbec auto. Jediný existující kus "centrálně řízeného
textu" je `app_settings.vandrawee_cena_obsahuje_text` +
`regal_umisteni.kotveni_zakaznicky`/`montaz_zakaznicky` (admin →
Koeficienty cen → "Vandr – opakující se texty") — ale je natvrdo pro
Vandr (=vždy auto), ne obecný podle typu sestavy.

Souvisí přímo s [[bot10_role_scena2_tables.md]] — stoly do skladu jsou
první reálný spotřebitel druhého typu, ne hypotéza.

Zadáno bot16 (návrh + admin UI), s povinnou konzultací bot8 (větev 1 —
jak se `product_assemblies` naváže na typ), bot5 (Vandr texty/služby už
existují, nedělat druhý paralelní mechanismus vedle nich) a bot10
(stoly — aby se schéma nemuselo předělávat, až na ně dojde). Zápis
najdou zprávou, jakmile bude návrh hotový k ověření.



`WORKFLOW.md` (pravidla 24–26, 29) · `PRODUKTOVE_RENDERY.md` (kontrakt
otočného náhledu, šablona, materiály) · `VLASTNOSTI_PROFILU.md`
(rozcestník geometrických pravidel) · `TASKS.md` · `AGENTS_LOG.md`.
