# Pravidla spojů — univerzální geometrie

Univerzální pravidla platná pro VŠECHNY profily/díly/spoje bez ohledu na konkrétní typ — spojovací geometrie, metodika ověření (touchReport, Box3), gotchas kolem kolizního testování, kanonický proces učení dílů. Vydělené z původního `VLASTNOSTI_PROFILU.md` 2026-08-31. Viz taky: `PROFILY_KATALOG.md` (fakta specifická pro konkrétní profil), `PRISLUSENSTVI_PRIPOJENI.md` (klasifikace montážního režimu příslušenství), `KAROSERIE_UMISTENI.md` (umístění sestav do vozidla).

⚠️ **UPOZORNĚNÍ (audit bot9, 2026-09-12):** dokument dál odkazuje na `custom_shapes.id=44/158/169/174/175/176` a `product_assemblies.id=44` jako testovací/ověřovací sestavy - VŠECHNY tyhle konkrétní řádky jsou dnes v DB smazané (úklid testovacích dat). Odkazy zůstávají jako historický záznam ODVOZENÍ pravidel, ne jako dohledatelná data - závěry pravidel platí dál.

## SKU místo názvu — TRVALÉ pravidlo (Robert, 2026-08-17, doplněno do dokumentace 2026-08-31)

Robert doslovně: "ty musíš kurva používat SKU a ne názvy, jinak v tom bude pořád bordel" — formálně zapsáno jako **pravidlo 3D scény**: "bot obsluhující 3D scénu musí bezpodmínečně vždy v matematických simulacích a při ukládání pozic a při práci s objekty používat SKU, nikoli jejich názvy." Názvy produktů se mění, jsou nejednoznačné (víc dílů se stejným/podobným názvem) a nejdou spolehlivě parsovat regexem na atributy jako rozměr/typ spoje — SKU je stabilní identifikátor. Konkrétní důsledek: `uhelnikAutPart`/`rozekAutPart` a podobné klasifikační funkce používají `skuTypeSuffix(p)` (poslední segment SKU za poslední tečkou), ne text názvu.

## Přesná definice spoje dvou profilů — TRVALÉ pravidlo + oprava přeceňování spojů (Robert, 2026-08-31)

Robert po nahlášení špatného počtu spojů v cenovém panelu (23 místo skutečných 20 u 16dílné sestavy) formuloval závaznou definici: **"existuje pouze pokud se celá plocha čela jednoho profilu dotýká buď celé plochy čela druhého profilu nebo kterékoli stěny."** Platí univerzálně — je to jen upřesnění už existujícího ⭐ pravidla "žádné zanoření, žádné částečně kryté čelo", ale teď explicitně jako definice PRO POČÍTÁNÍ SPOJŮ, ne jen pro platnost fyzického spoje při stavbě.

**Bug nalezený a opravený:** `autoRegisterTouchedProfileJoints()` (`webapp/scene.html`, volá se automaticky po vložení JAKÉKOLI sestavy do scény, i naprogramované botem) testovala na dvou "bočních" osách jen `overlap > 0` (JAKÝKOLI, i částečný průnik ploch) místo `overlap ≈ min(sizeA, sizeB)` (CELÁ menší plocha uvnitř větší). U hustší sestavy (noha+nosník+příčka) to vyrábělo falešné spoje mezi díly, které jsou geometricky blízko, ale fyzicky se nedotýkají celou plochou (typicky "cap" díl u vrcholu nohy, blízko místa, kde na nohu dosedá nosník). **Opraveno** — overlap na obou bočních osách teď musí pokrýt celou menší z obou ploch (`hi - lo >= minSize - tolerance`). Ověřeno na reálné 16dílné sestavě (`product_assemblies.id=44`, regál na euroboxy 2ks): před opravou 23 spojů (3 falešné), po opravě přesně 20 — potvrzeno i nezávislým strukturálním výpočtem (5+5 spojů uvnitř dvou noh, 4 nosník↔noha, 6 spojnice↔nosník).

**Důležitý vedlejší nález (netýká se přímo opravy, ale ovlivňuje bot-stavěné sestavy):** tlačítko "Spočítej spoje" zahazuje VŠECHNY "měkké" spoje (vzniklé jen touch-detekcí, ne přes tlačítko Připoj/AI generátor/presety) bez ohledu na jejich geometrickou správnost — u sestavy postavené přímo zápisem do DB (bez `join_groups`) jsou VŠECHNY spoje "měkké", takže by tlačítko spadlo na 0, ne na správný počet. Díky opravě výše už touhle cestou vznikají jen geometricky správné spoje, takže není důvod je zahazovat - ale "Spočítej spoje" pro bot-stavěné sestavy zatím zůstává riskantní nástroj, ne spolehlivá kontrola. Otevřené pro budoucí práci.

## 2. Spojování a konektory
- **Kolmé (90°) spojování** — konektory na koncích nejdelší osy, snap při opačných normálách.
- **OPRAVENO (audit bot9, 2026-09-12): libovolný úhel přes spojovací díl "kloub" JE produkční, ne plánovaný.** Tlačítko "🔗 Připoj kloub" (`btnAttachKloub`, funkce `attachTwoProfilesToKloub()` ve `webapp/scene.html`) od 2026-08-21 označí 2 profily + 1 kloub a napojí každý profil na jeho naučenou plochu kloubu - žádný úhel není omezen na 45°/90°, kloub sám nese naučenou geometrii spoje.
- Zbytek (jaký hardware/konzoly k jakým spojům, jestli jde spojit napřímo bez konzoly) *(čeká na doplnění)*

## 2c. Přesná geometrie spoje — POTVRZENO Robertem (2026-07-23, upřesněno 2026-07-23)

Robert dodal referenční soubor `spojení vice profilu.fbx` (3 profily 30×30 mm sbíhající se do jednoho rohu ve 3 osách + plastová krytka). Rozměry z tohoto souboru byly přímo přepočítány.

**Pravidlo (výsledek, ne postup):** Rodičovský profil zůstává celý/neprodloužený ("průchozí"). Připojovaný profil dosedá čelem **přesně na vnější stěnu rodiče** — žádný průnik doprostřed rodiče, žádný přesah za jeho hranu/špičku. Přesně lícující, plochý spoj.

> **Oprava (2026-07-23):** Dřívější zápis popisoval tohle jako "krok 1 (ven od osy) + krok 2 (zpět podél osy rodiče)" a prezentoval to jako Robertem popsaný postup — **to Robert takhle nikdy nepopsal** ("krok 0 a 1 jsou nesmysl"). Ten dvoukrokový výpočet je jen INTERNÍ IMPLEMENTAČNÍ DETAIL v `attachEntryToParent()` (jak se k výsledné pozici numericky dojde), ne pravidlo/postup, který by Robert diktoval. Zapisovat sem napříště jen POTVRZENÝ VÝSLEDEK (jak má spoj vypadat), ne odvozené mezikroky, pokud je Robert sám takhle nepopsal.

U T-spoje (napojení doprostřed boku, ne na konec) žádná "špička" není — díl se napojí přímo doprostřed délky rodiče.

**Výjimka — svislý spoj (sloupek/kvádr):** Pravidlo výše platí jen mezi dvěma vodorovnými díly ve stejné rovině. Jakmile je jedna strana spoje SVISLÁ (sloupek roste z rohu nahoru, nebo vodorovný rám navazuje na špičku sloupku), žádný z výše uvedených posunů se neaplikuje — svislý díl se připojí přesně do rohového bodu a roste rovně vzhůru. Fyzicky tam nejde o dvě plochy vedle sebe, ale o sloupek vyrůstající přímo z bodu, kde se setkávají dva vodorovné profily.

Implementace (OPRAVENO umístění, audit bot9 2026-09-12): `attachEntryToParent()` a `crossAxisHalfWidthTowardDirection()` žijí ve `webapp/js/scene-geometry-shared.js` (sdílený soubor, načítá ho `scene.html`) - ne v `webapp/index.html` (to je e-shop storefront bez geometrie).

**Vyplývající, ještě nevyřešené omezení:** takto sestavené UZAVŘENÉ smyčky (čtverec, kvádr) mají v jednom rohu (tam, kde se řetěz vrací zpět ke svému výchozímu dílu) malou zbytkovou odchylku v řádu šířky profilu — protože reálný uzavřený rám potřebuje na rozích zkrácené kusy nebo pokosový řez, což zatím appka nepočítá. Není to bug tohoto pravidla, je to další úroveň (parametrické zkracování rohů), na kterou zatím appka nemá mechanismus.

## 2d. Definice fyzického spoje (pro konstrukci i pro cenotvorbu) — POTVRZENO Robertem (2026-07-23)

Jeden **"spoj"** mezi dvěma profily je jedno konkrétní reálné spojovací místo, definované takto:
- **Čelo** jednoho profilu (na kterém je vyřezaný **závit**) dolehne **celou svou plochou** na **stěnu** druhého profilu (ve které je vyvrtaný **průchozí otvor**).
- **Spojovací šroub** prochází otvorem ve druhém profilu a zašroubuje se do závitu v čele prvního.
- Šroub se dotahuje **imbusovým klíčem přes otvor**.
- **Hlava šroubu musí být předem nasunutá v T-drážce** profilu, do kterého se šroubuje — s tímhle se musí počítat PŘED sesazením dílů, ne až po něm.

Tahle definice platí **stejně** pro:
- spoj **na konci** profilu (tvar L — konec na konec),
- spoj **uprostřed/kdekoli podél délky** profilu (tvar T — konec jednoho profilu se napojuje na bok druhého kdekoli po jeho délce, ne nutně na jeho konec).

V obou případech je to **pořád jen JEDEN spoj** (jeden šroub, jeden závit, jeden otvor) — i když se na něm fyzicky podílí konec/bok OBOU profilů, nepočítá se to jako 2 spoje.

**Počet spojů podle tvaru z Průvodce** (kolik reálných spojovacích míst má hotový tvar, tak jak ho appka postaví):

| Tvar (Průvodce) | Počet dílů | Počet spojů | Poznámka |
|---|---|---|---|
| Úsečka (1 profil) | 1 | 0 | Žádné napojení, jen 1 volný kus. |
| Tvar L | 2 | 1 | Konec na konec. |
| Tvar T | 2 | 1 | Konec jednoho na bok druhého (kdekoli po délce). |
| Prostorový L | 3 | 2 | 2× vodorovný spoj/sloupek, řeší se stejně jako L, jen jeden díl navíc svisle. |
| Čtverec / rám | 4 | 4 | Uzavřená smyčka — každý ze 4 rohů = 1 spoj (viz oprava níže, appka dřív počítala jen 3). |
| Kvádr (krabice) | 12 | 16 | 4 dole (spodní rám) + 4 nahoře (horní rám) + 4 sloupky × 2 (dole i nahoře). **Robert 2026-07-23: ke kvádru se ještě vrátíme, je to zatím rozpracované/složitější případ, nebrat čísla jako finální.** |

> **Dopad na appku:** Počet spojů v sestavě = počet úspěšných "přichycení" dílu k rodiči (`attachEntryToParent()` v `webapp/js/scene-geometry-shared.js` - OPRAVENO audit bot9 2026-09-12, ne přímo ve `scene.html`, počítadlo `entry.jointCount`) — **NE** součet volných/obsazených koncových konektorů přes všechny díly (to by u spoje konec-na-konec počítalo 2×, protože se na něm podílí konec obou profilů — přesně tenhle bug Robert nahlásil na tvaru L, kde appka ukazovala 2 spoje místo 1). Používá se pro výpočet "Cena spojů" a "Příslušenství" v živém přehledu sestavy (nastavení v administraci: záložka "Spoje a příslušenství") a je zahrnuto i do systémového promptu 3Dbota (`/api/ai/generate`, pravidlo 6), aby AI stavitel rozuměl stejné definici.
>
> **Uzavřené smyčky (čtvercový rám, kvádr):** uzavírací roh smyčky (poslední díl řetězu se vrací zpět k prvnímu) vznikne jen geometricky (rotace 0/90/180/270 se přesně sejde), `attachEntryToParent()` ho nikdy nezavolá, takže by se bez dalšího zásahu vůbec nezapočítal. Řeší to `closeLoopIfCoincident()` / `registerJoint()` — po postavení tvaru dohledají dva ještě volné konce, které jsou geometricky na stejném místě, a spoj mezi nimi dodatečně zaregistrují (Robertovo "rám čtverec má 4 rohy... nikoli 3 spoje"). Kvádr navíc takhle dopočítává i vnitřní spoje horního rámu (ten je jen zkopírovaná geometrie spodního, taky nejde přes `attachEntryToParent()`) a napojení každého sloupku nahoře — plný kvádr má tedy 16 spojů (4 dole + 4 nahoře + 4 sloupky × 2).

## 2e. Polarita spoje — závit může být v kterémkoli z obou profilů — POTVRZENO Robertem (2026-07-23)

Spoj definovaný výše (2d: čelo se závitem dolehne na stěnu s otvorem) **může být poskládaný oběma směry** — u dvou profilů A a B jde udělat:
- **buď** závit v čele profilu A + otvor ve stěně profilu B,
- **nebo naopak** závit v čele profilu B + otvor ve stěně profilu A.

**Cenově je to úplně jedno** — pořád je to jeden spoj, stejná cena (viz 2d), appka mezi variantami cenově nerozlišuje a ani nemusí.

**Konstrukčně to ale NENÍ zaměnitelné/libovolné** — volba směru záleží na:
1. Aby šlo výslednou sestavu **reálně smontovat** (přístup imbusem k dotažení, pořadí skládání dílů — někdy jde šroubovat jen z jedné strany).
2. Jestli má zůstat u některého z profilů **volná/otevřená T-drážka** — profil, který "dostane" díru pro šroub (ne závit), může potřebovat mít svou drážku jinde volnou pro něco dalšího (další díl, panel, doplněk), zatímco profil se závitem v čele tam žádnou drážku nepotřebuje mít volnou navíc.

Který profil dostane závit a který díru se tedy rozhoduje případ od případu podle toho, co sestava/montáž vyžaduje — **ne** podle pevného univerzálního pravidla. Appka/3Dbot si tohle zatím nemusí řešit konstrukčně (nemá vliv na cenu ani na počet spojů), ale je to potřeba znát, až se bude řešit reálná montážní proveditelnost sestavy nebo se bude generovat výrobní dokumentace/kusovník s orientací šroubů.

> **Přesná definice obráceného spoje — ověřeno přímo na Robertových referenčních souborech (2026-07-23):** Robert dodal `Profil 30x30 spoj A.fbx` a `Profil 30x30 spoj B.fbx` (dva profily svírající 90° roh, v obou souborech stejné umístění/natočení, jen jinak spočítaný spoj). Přeměřeno (assimp_py, world bounding boxy sítí):
> - **Spoj A:** svislý díl beze změny/celý (Y 0→1000, prochází přesně rohem). Vodorovný díl je připojovaný — jeho čelo dolehá na stěnu svislého dílu u jeho paty.
> - **Spoj B:** přesně obráceně — vodorovný díl je teď beze změny/celý (prochází rohem), svislý díl je připojovaný — zvednutý o šířku profilu, čelem dolehá na vrch vodorovného.
>
> Klíčové zjištění: **natočení/orientace obou dílů se mezi A a B vůbec nemění** — mění se jen to, který díl zůstává na místě (průchozí) a který se k němu čelem přikládá (připojovaný). Dva předchozí pokusy o implementaci byly proto oba špatně: 1) metadata závit/otvor beze změny geometrie (3D objekt se vůbec nehnul), 2) prohození čísel "1"/"2" mezi stejnou, jen jinak označenou geometrií (3D objekt se taky nehnul — Robert: "pořád tam jen prohazuješ číslování profilů").
>
> **Opravená implementace (`buildLReversedShape()`):** díl "1" i díl "2" mají **stejné natočení a stejné přirozené pořadí vložení do Kusovníku** jako u běžného "Tvaru L" (0° = "1.", 90° = "2."). Mění se jen **výpočet pozice**: u "Tvaru L" zůstává na místě díl "1" (0°) a díl "2" (90°) se k němu čelem přikládá; u "Tvaru L (obrácený spoj)" je to obráceně — na místě zůstává díl "2" (90°), a díl "1" (0°) se PŘESTOŽE je vykreslený/očíslovaný jako první, geometricky přikládá čelem k dílu "2". `attachEntryToParent()` na pořadí v poli `placed` nezávisí (pracuje přímo s 3D transformacemi), takže číslování a geometrický vztah (kdo na koho navazuje) jdou nastavit nezávisle na sobě. Role dílu se zobrazuje v Kusovníku jako poznámka ("průchozí (celý)" / "připojovaný (zarovnaný)").
>
> **ZRUŠENO (2026-07-23) — dřívější "oprava" celkové polohy/natočení byla špatná:** Po Robertově hlášení "změnila se poloha profilů... jaksi se to otočilo celé" jsem sem předtím zapsal a naimplementoval **globální dodatečné otočení celé sestavy o -90°**, aby "Tvar L" a "Tvar L (obrácený spoj)" zabíraly stejné místo v prostoru. **Robert to opravil: "otočení způsobu spoje znamená, že si dítě a rodič vymění role, nikoli prostorové pozice."** Jinými slovy — obrácení spoje je čistě záměna rolí (kdo je pevný/průchozí, kdo se připojuje), **žádná dodatečná prostorová/rotační korekce se dělat nemá**. Že výsledná sestava zabírá jinou polohu/orientaci než normální "Tvar L" je OČEKÁVANÝ, správný důsledek toho, že pevný díl má jinou přirozenou rotaci — není to chyba k opravování. Hack s `-90°` otočením byl z `buildLReversedShape()` odstraněn, funkce teď dělá čistou záměnu rolí přes `attachEntryToParent()`, stejně jako běžný "Tvar L".

## 2f. Dva různé způsoby "obrácení" spoje — LEARNING (2026-07-23)

Robert upřesnil, že "obrácený spoj" (kdo je průchozí / kdo se připojuje, viz 2e) lze geometricky vyřešit **dvěma zásadně odlišnými způsoby** — nejsou zaměnitelné, appka/3Dbot musí vždy vědět, který z nich se právě řeší:

1. **Beze změny délky, se změnou pozice na podélné ose** — žádný z profilů nezmění svou délku, ale změní se **pozice spoje podél podélné osy** jednoho z nich (kde přesně podél své délky se připojí, podle aktuální potřeby ve scéně). Tohle je složitější případ a je to přesně to, co se zatím řeší u "Tvar L (obrácený spoj)" (`buildLReversedShape()`) — stále se dolaďuje (viz poznámky výše u 2e o poloze/natočení celé sestavy).

2. **Se změnou délek obou profilů, beze změny pozice na ose** — žádný profil nezmění svou pozici vůči vlastní podélné ose (jeho začátek zůstává tam, kde byl), ale **změní se délky**: jeden profil se **zkrátí o rozměr profilu v řezu** (např. u 30x30 profilu o 30 mm) a druhý se o **stejnou délku prodlouží** — tím se dosáhne požadované skladby profilů v prostoru, aniž by se cokoli posouvalo mimo svou osu.

**Dopad na appku/3Dbota:** Pokud uživatel (nebo AI stavitel) chce "obrácený spoj" a nespecifikuje, kterou variantu myslí, je potřeba se zeptat / rozlišit — jde o dvě různé transformace geometrie s různým výsledkem (jinde umístěný spoj vs. jinak dlouhé profily), ne o jednu věc řešitelnou jedním obecným přepínačem. Zapsáno i do systémového promptu 3Dbota (`/api/ai/generate`, pravidlo 8).

> **Implementace varianty 2) — POTVRZENO Robertem (2026-07-23), finální geometrie:** Řešeno přes 2D náhledové diagramy (varianty A/B/C, viz níže) — Robert vybral **variantu C: úplně zarovnáno, žádný přesah ani průnik** jako správnou, pro obě verze (normální i obrácený spoj).
>
> **"Tvar L (změna délek)" — `buildLLengthShape()`:** Díl "1" (průchozí, 0°) zůstává na svém přirozeném místě jako u "Tvaru L" (roh = pevný bod), **prodlouží se o w** (rozměr průřezu) na svém volném konci. Díl "2" (připojovaný, 90°) se napojí na rohový konektor dílu "1" se stejným "krokem 1" jako `attachEntryToParent()` — odsazení OD středové osy dílu "1" o polovinu jeho šířky, aby díl "2" dosedl na jeho VNĚJŠÍ stěnu, ne na střed (to byl původní bug — díl 2 pronikal do dílu 1). Na rozdíl od `attachEntryToParent()` se ale VYNECHÁVÁ "krok 2" (zpětné zasunutí podél osy rodiče) — tuhle korekci tu řeší až následné **zkrácení dílu "2" o w**, se zafixovaným BLÍZKÝM/rohovým koncem (ne vzdáleným — to byl druhý bug, který způsoboval mezeru mezi díly). Výsledek: žádný průnik, žádný přesah, přesně varianta C.
>
> **"Tvar L (změna délek, obrácený spoj)" — `buildLLengthReversedShape()`:** Zrcadlová verze, role prohozené. Díl "2" (90°) je teď průchozí (prodloužený o w, pevný bod na svém místě), díl "1" (0°) je teď připojovaný — dosedne na VNĚJŠÍ stěnu dílu "2" (stejný princip jako výše), pak se zkrátí o w se zafixovaným rohovým koncem. Číslování zůstává přirozené (0° = "1.", 90° = "2."), stejně jako u pozičního `buildLReversedShape()`. Varianta C' (zrcadlo C).
>
> Obě funkce sdílí stejný princip: **odsazení kolmo od osy rodiče (perpendikulárně) se řeší pozicí (nutné vždy, žádná délka to nenahradí), odsazení PODÉL osy rodiče (aby dílu nepřesahoval/nechyběl na špičce) se řeší zkrácením/prodloužením délky** — to je to, co dělá tuhle varientu "beze změny pozice na ose" odlišnou od `attachEntryToParent()`.

> **OPRAVA (bot8, 2026-08-19, nalezeno hloubkovou matematickou kontrolou na reálné .glb geometrii):** tvrzení výše ("odsazení PODÉL osy rodiče se řeší zkrácením délky") bylo geometricky CHYBNÉ — zkrácení působí podél VLASTNÍ osy připojovaného dílu, která je na osu rodiče KOLMÁ, takže přesah v ose rodiče vůbec neovlivní. Změřený důsledek: připojovaný díl přečníval o polovinu svého průřezu (15mm u 30×30) ZA konec průchozího ("zub") a jeho čelo bylo kryté jen z poloviny — porušení varianty C ("žádný přesah") i nadřazeného pravidla "žádné částečně kryté čelo". Přesně tahle chyba byla u Čtverce reklamována Robertem ("zelený profil musí jít zarovno koncem bílého") a opravena (`placeAttached`), ale `buildLLengthShape`/`buildLLengthReversedShape` opravu nikdy nedostaly. Opraveno 2026-08-19: obě funkce teď používají i "krok 2" z `attachEntryToParent` (zasunutí o vlastní půlšířku proti vnější normále rohového konektoru) — zkrácení/prodloužení délek (podstata varianty C) zůstává beze změny. Ověřeno na 3 reálných profilech: přesah 0.0000mm, krytí čela plné, mezera 0.0000mm, délky L+w/L−w zachovány.

## Pravidlo profilů - ŽÁDNÉ zanoření, ŽÁDNÉ částečně kryté čelo (2026-08-18, POTVRZENO Robertem, nadřazené pravidlo)

Robert, po nahlášení chyby na testovací sestavě (viz níže): **"profily nikdy nemohou být zanořené !!! nikdy nemohou mít čelo zakryté částečně !!! máli čelo doléhat na stěnu jiného profilu tak vždy pouze celou plochou čela."**

Tohle NENÍ nové pravidlo - je to ostřejší, bezvýjimečná formulace toho, co už říká 2c ("žádný průnik doprostřed rodiče, žádný přesah za jeho hranu/špičku") a 2d (čelo dolehne CELOU svou plochou na stěnu). Důležitý rozdíl oproti dosavadnímu zápisu: **platí to jako absolutní zákon pro KAŽDÝ spoj profil-profil, i pro typy spojů, které appka/scene.html ještě vůbec nemá implementované** - není to jen popis toho, jak se chovají už hotové funkce (`attachEntryToParent`, `buildSpatialLShape`...), je to KRITÉRIUM, podle kterého se musí navrhnout i každý BUDOUCÍ, dosud nenapsaný typ spoje. Pro každý profil-profil spoj musí platit současně:
- **mezera = 0** (žádná plovoucí/nedolehlá část čela),
- **průnik = 0** (žádná část čela zanořená do těla druhého profilu),
- na ploše doteku vždy **CELÁ plocha čela** dosedající na druhý profil, ne polovina/libovolný zlomek.

Prakticky: pro libovolnou dvojici "rodič/dítě" a libovolnou osu, po které se dítě/jeho konektor odchyluje od pozice, kde by se jeho průřez octl PŮLKOU uvnitř těla rodiče a půlkou v prázdnu, existuje PRÁVĚ JEDEN správný posun (o polovinu vlastní šířky dítěte, ve směru PRYČ od rodičova těla) - ne kompromis/aproximace, přesný matematický požadavek.

**Ověřený příklad, kde se tohle pravidlo poprvé muselo odvodit pro úplně NOVOU kombinaci (bot8, testovací sestava `custom_shapes.id=169`, "točité schodiště" - vodorovné profily střídané se svislými, viz sekce výše o testu na 20 profilech):** spoj "vodorovný profil dosedá na SPIČKU (volný horní konec) svislého sloupku" nemá ve `scene.html` žádnou existující funkci/precedens (`buildSpatialLShape` řeší jen opačný směr - sloupek rostoucí ZE společného rohu dvou vodorovných profilů, ne vodorovný profil kladený NA vrchol sloupku). Bez korekce vycházel cílový bod přesně NA vrcholu sloupku, takže se průřez vodorovného dílu podél svislé osy rozdělil přesně napůl - polovina zanořená do sloupku, polovina visící nad ním v prázdnu (přesně to, co pravidlo výše zakazuje).

**Odvozená oprava #1 - svislá osa** (analogická retreatu sloupku z 2h, ale s OPAČNÝM znaménkem - viz zdůvodnění): vodorovný díl se posune o svou VLASTNÍ polovinu šířky (`crossAxisHalfWidthTowardDirection` na dítěti, ve směru normály rodičova použitého konektoru) ve směru TÉTO NORMÁLY (ne proti ní jako u sloupku) - tak, aby celá jeho spodní plocha ležela nad vrcholem sloupku, žádná část nezasahovala do jeho těla. Proč opačné znaménko než u sloupku na 2h: u sloupku rostoucího z konce vodorovného profilu chceme jeho tělo zarovnat DO půdorysu rodiče (ať ho má čím podepřít) - retreat PROTI normále. U vodorovného dílu kladeného NA špičku sloupku chceme přesný opak - jeho tělo nesmí zasahovat DOLŮ do sloupku, musí ležet CELÉ NAD jeho vrcholem - posun VE SMĚRU normály. Obojí je stejný jeden princip (žádné zanoření, žádný přesah) jen aplikovaný na dvě geometricky zrcadlové situace - odvozovat znaménko z toho, na které straně konektorové normály fyzicky leží tělo rodiče vs. kam má ležet tělo dítěte, ne z povrchní podobnosti "je to taky sloupek/spoj s rodičem".

**Chyba v ověření #1 (odhalil Robert, ne vlastní kontrola)**: po opravě #1 appka spočítala 0.000mm mezeru/průnik na SVISLÉ ose (dotykové) a plný 40×40mm překryv na OBOU zbylých osách - vypadalo to jako kompletní důkaz. Robert ale upozornil, že sudé spoje jsou "vlastně nespoje, doléhající k sobě pouze hrany čel" - **skutečná chyba v mém ověření byla, že jsem změřil jen DVA díly IZOLOVANĚ na dotykové rovině, ne SKUTEČNÝ obsah plochy doteku napříč VŠEMI třemi osami současně.** Přeměřením (`overlap` na všech 3 osách zvlášť, ne jen dotyková) vyšlo: osa Z (druhá vodorovná, kolmá na růst) měla skutečně plných 40mm překryvu (OK), ale osa X (osa RŮSTU vodorovného dílu) měla **překryv 0.00mm** - konektor vodorovného dílu se položil přesně na BLIŽŠÍ hranu sloupku (`krok1`, `parentHalf` posun ve směru růstu), takže dílec od tohoto bodu rostl AŽ DÁL, mimo půdorys sloupku úplně - dotyk jen v jedné hraně/přímce, ne v ploše. Ověření #1 tenhle typ chyby nemohlo odhalit, protože kontrolovalo jen "gap/overlap na dotykové ose" u páru sousedních dílů, ne PLNÉ pokrytí menšího čela (tady: sloupku) tělem druhého dílu ve VŠECH osách roviny doteku.

**Odvozená oprava #2 - osa růstu:** aby čelo SLOUPKU (jeho vrchní plocha, `parentEntry`) bylo skutečně KOMPLETNĚ kryté tělem vodorovného dílu (ne jen z hrany), musí vodorovný díl začínat na VZDÁLENĚJŠÍ hraně sloupku (v protisměru růstu) a růst přes celý půdorys sloupku a dál - posun o **dvojnásobek `parentHalf`** (stejná hodnota, jakou už použil krok1, jen navíc v OPAČNÉM směru) podél `childDirWorld` (směr růstu dítěte). Obecná formulace pro příště: kdykoli je rodič (v místě spoje) UŽŠÍ NEBO STEJNĚ ŠIROKÝ jako dítě ve směru, kterým dítě roste, nestačí položit dítě "hranou na hranu rodiče" (běžné `krok1` chování pro spoj mezi dvěma rovnocennými vodorovnými profily) - dítě musí začínat na PROTĚJŠÍ hraně rodiče, aby ho jeho tělo celé "podjelo"/překrylo, ne se ho jen dotklo.

**Poučení pro příště (metodika ověření):** "mezera/překryv = 0 na dotykové ose" NESTAČÍ jako důkaz platného spoje - je nutné zkontrolovat překryv na VŠECH osách roviny doteku (u čtvercového/obdélníkového profilu obě zbylé osy), a navíc ověřit, že MENŠÍ (nebo rovné) ze dvou čel je SVOU CELOU PLOCHOU podmnožinou plochy druhého dílu na dotykové rovině - ne jen že se plochy někde překrývají. Jednoduchý "touch test" na jedné ose může vypadat jako 100% úspěch a přitom skrývat spoj s nulovou reálnou plochou styku.

Ověřeno přímým měřením world-space bounding boxů na všech 19 spojích testovací sestavy PO OBOU opravách - `custom_shapes.id=169`: 0.000 mm mezera i překryv na dotykové ose, plný 40×40mm styk (skutečná plocha, ne jen hrana) na zbylých dvou osách, u všech 19 spojů bez výjimky (9× sloupek-na-konci-profilu, 10× profil-na-špičce-sloupku), žádná kolize mezi nesousedícími díly.

## Pravidlo profilů - noha (svislý profil) se zespoda zpravidla neuzavírá jiným profilem (2026-08-18, Logiman/vanDrawee konvence, ne fyzický zákaz)

Robert, po nahlášení "horní 2 patra hrůza, zabořené do sebe" na testovací sestavě regálu (viz níže):

> "noha tj svislý profil není zespoda uzavřená nikdy jiným profilem, ale má volné čelo směrem dolů. Toto čelo se osadí zpravidla prvkem Patka, kolečko, záslepka, podle toho k čemu konstrukce slouží atd."

**Upřesnění (Robert, hned poté):** "ono to není jako úplně zakázané, konkurence to používá, když ten kvádr natočím o 90 stupňů už to plní náš standard. Resp. Logiman/vanDrawee/já kreslím téměř vždy tak, že splňuju pravidlo, které jsem napsal." **Tedy: NENÍ to fyzická nemožnost ani univerzální zákaz** - konkurence běžně staví i s nohou capnutou zespoda, a stačí stejnou geometrii (Kvádr) natočit o 90°, aby "problematický" spoj přestal hrát roli nohy s volným spodkem. Je to **Logimanova/vanDrawee vlastní konstrukční konvence** (jak Robert téměř vždy sám kreslí), ne pravidlo, které by appka měla tvrdě vynucovat/zakazovat u každé možné orientace dílu.

**Pravidlo (jako výchozí konvence, ne tvrdý zákaz):** má-li svislý profil hrát roli NOHY (styk s podlahou), jeho spodní čelo se navrhuje volné/otevřené, ne dolehlé na jiný profil. V reálné konstrukci se na tohle volné čelo obvykle osazuje samostatný katalogový PŘÍSLUŠENSTVÍ díl (ne profil) - patka (pevná noha), kolečko (mobilní/pojízdná konstrukce), záslepka (jen estetický/ochranný uzávěr) - podle účelu konstrukce. Rám/příčka poblíž spodního konce nohy se pak připojuje BOČNĚ (T-styl, stejný princip jako `mid` konektor/průchozí spoj), ne jako čepička na konci - noha pod tím dál pokračuje volně k podlaze.

**Ověřený příklad (bot8, `custom_shapes.id=174`, regál 30×30):** přestavěno na nohu s volným spodkem (Y=0, nic ho nezakrývá) + spodní/střední rám připojený bočně (T-styl, sloupek prochází skrz). Noha `Y=[0,900]`, spodní rám `Y=[75,105]` (celá jeho tloušťka uvnitř nohy - sloupek tudy jen prochází, správně), horní rám `Y=[900,930]` (cap SHORA, bez problému - noha v TÉTO orientaci/roli nefunguje jako "noha stojící na podlaze").

**`buildKvadrShape()` (`webapp/js/scene/catalog-panels.js`, přesunuto z `scene.html` refaktoringem `61c0ede1` 2026-09-03 - OPRAVENO audit bot9 2026-09-12) NEVYŽADUJE opravu** - staví sloupky s capem zespoda (`attachEntryToParent(postEntry, spec.entry, vertQuat, spec.connIdx, 1)`), což je přesně ten vzor z tohodle zápisu, ALE Robert potvrdil, že jde o platnou, konkurencí běžně používanou variantu - jen ne tu, kterou on sám/Logiman/vanDrawee obvykle kreslí. Kvádr zůstává beze změny; tenhle zápis slouží jako VÝCHOZÍ doporučená konvence pro NOVÉ konstrukce (3D bot ji použije jako default, pokud zadání nebo kontext neříká jinak), ne jako kontrola/oprava stávajících tvarů.

## Pravidlo profilů - T-styl (průchozí) spoj: připojovaný díl se zkracuje o CELOU šířku průchozího, ne o půlku (2026-08-18, POTVRZENO Robertem)

**Skutečná chyba, kterou odhalil Robert na regálu (`id=174`) hned po předchozím zápisu výše**: "oba konce profilů 500 spodního a středního patra jsou zanořené do stojek" + "bounding box kopírují nohy, tak nemůžu sahat spojnice nohou" (v adminu/scéně nešly boxy od sebe rozlišit/vybrat, protože se doslova překrývaly).

**Příčina:** rám na "průchozím" patře (T-styl - sloupek prochází skrz, nekončí tam) jsem postavil na STEJNOU délku (roh-k-rohu, přes celou šířku sloupku na obou koncích) jako u "cap"-stylového patra (kde sloupek KONČÍ). U cap-stylu je to správně - 500mm přesně vyplní mezeru mezi vnějšími rohy sloupku, protože sloupek dál nepokračuje. U T-stylu je to ALE špatně - sloupek prochází přes CELOU svou tloušťku i tam, kde se rám "napojuje", takže díl, který zasahuje až k ose/protější straně sloupku, se s jeho tělem fyzicky překrývá po celé této hloubce (ne jen v jednom bodě jako u cap-spoje) - přesné porušení pravidla "žádné zanoření" výše, jen já sám jsem si ho u TOHOTO konkrétního typu spoje neuvědomil.

**Oprava (obecné pravidlo pro každý budoucí T-styl/průchozí spoj):** připojovaný díl se musí zkrátit o **CELOU šířku průřezu** průchozího dílu (ne o polovinu, jako u běžného rohového `krok1/krok2` retreatu) - jeho konec musí dosednout na VNITŘNÍ stěnu průchozího dílu (tu odvrácenou/vzdálenější od připojovaného dílu), ne na jeho osu ani na jeho vnější stranu. Ověřeno na regálu: rám zkrácen z 500mm na 440mm (500 − 2×30mm šířka sloupku) a posunut o celou šířku sloupku (30mm, ne 15mm půlky) - výsledek `gap=0.000mm`/`overlap=0.000mm` přesně na dotykové rovině (žádné zanoření, žádná mezera), na rozdíl od předchozí verze, kde měl stejný spoj plný 30×30mm překryv (zanoření) na místo správného nulového.

## Pravidlo profilů - i NEJVYŠŠÍ patro/police je stejný T-styl spoj jako ostatní, noha má volné čelo nahoře STEJNĚ jako dole (2026-08-18, POTVRZENO Robertem, rozšíření pravidla o noze výše)

Robert, po zhodnocení opraveného regálu ("když pominu ten horní kříž ve vzduchu, je to správně... s tím mě napadá, udělat si tím to způsobem více komponent/polic"), pak přímo: **"nejvyšší police nemá důvod být jiná než ty spodní, většinou našim produktům nezavíráme stojky shora jiným profilem, necháváme nohám čela nahoře volné jako vespod."**

**Rozšíření pravidla "noha se zespoda nezavírá" (viz výše) - PLATÍ STEJNĚ I PRO VRCHOL:** předchozí testovací verze (`id=174` až do tohohle bodu) měla nejvyšší patro jako výjimku - "cap" styl (noha tam KONČÍ, rám ji zespoda kapuje celou plochou, přesně jako `buildKvadrShape` dělá pro horní rám). To byla myšlenková chyba - Logiman/vanDrawee konvence (žádný profil nezavírá čelo nohy) platí STEJNĚ na obou koncích, ne jen dole. Noha má být delší než nejvyšší patro (přečnívá nad ním, volný konec, stejná logika jako přečnívá pod nejnižším patrem) a VŠECHNA patra (včetně toho vizuálně nejvyššího) se k ní připojují STEJNÝM T-stylovým bočním spojem (viz pravidlo výše - zkrácení o celou šířku nohy).

**Praktický důsledek:** "kolik má regál pater" a "jak vysoko sahá noha" jsou DVĚ NEZÁVISLÉ věci - noha vždy o kousek přečnívá NAD posledním (nejvyšším) patrem, žádné patro neurčuje celkovou výšku nohy tím, že by ji "capovalo".

**Ověřeno** (`custom_shapes.id=174/175/176`, přestavěno pomocí `scripts/2026-08-18_shelf_builder.js` - viz sekce J indexu výše): všechna patra na všech 3 sestavách teď dávají stejný vzor `x:plný překryv z:gap=0/overlap=0 y:plný překryv (noha)` - žádná výjimka pro nejvyšší patro, žádná kolize.

**Nástroje pro příště** (ať se nemusí psát znova): `scripts/2026-08-18_scene_geometry_lib.js` (znovupoužitelná knihovna - doslovný opis produkčních funkcí ze `scene.html` + ověřovací helpery) a `scripts/2026-08-18_shelf_builder.js` (parametrizovaná stavba police/regálu na knihovně). Viz `.claude/skills/3d-scena-spoje/SKILL.md` pro návod k použití - tenhle skill se automaticky nabízí každé budoucí session v tomhle projektu.

## Pravidlo profilů - pivot dílu (lokální počátek) NENÍ vždy jeho geometrický střed - měř skutečnou hranu, neodvozuj z position ± half-size (2026-08-19, nalezeno bot8 přímým ověřením matematiky na SKUTEČNÉ .glb geometrii, ne syntetické)

Robert, po druhém kole gap-auditu (rozšíření mimo architekturu modulů, viz `AGENTS_LOG.md`): "ještě jednou projdi zda 'novy system' nemá nějaké mezery" a po mé odpovědi (jen čtení kódu, žádné měření) přímo: "No a proč nekontrolujeme matematiku?" - správná výtka. Čtení kódu NENÍ důkaz - přesně tohle už jednou selhalo (viz "ŽÁDNÉ zanoření" výše, "mezera/překryv = 0 na dotykové ose NESTAČÍ").

**Co se stalo:** veškeré dosavadní Node.js ověřování v tomhle projektu (staircase, stůl, kříže, regál) používalo `mkProfileEntry()` se **syntetickým** `THREE.BoxGeometry(dimX, dimY, dimZ)` - ten je vždy dokonale symetrický kolem lokálního počátku (0,0,0) podle definice. Skutečné `.glb` soubory v `webapp/katalog/` ale symetrické být NEMUSÍ - pivot (lokální počátek, `position` objektu) může sedět kdekoli, geometrický střed se počítá zvlášť (`Box3.getCenter()`). Přímým parsováním glTF JSON chunku (`accessors[].min/max` pro `POSITION`, žádná knihovna potřeba) zjištěno: `profil_30x30_uzavreny.glb` má geometrický střed prurezu posunutý o **~0.752mm** od lokálního počátku (ostatní testované profily `20x20`/`20x40`/`20x80`/`35x35` mají posun jen 0.0001-0.002mm, zanedbatelný - je to specifické pro tenhle jeden soubor, ne systémová vada).

**Skutečný nalezený bug (`buildKvadrShape()`, dnes `webapp/js/scene/catalog-panels.js` - OPRAVENO audit bot9 2026-09-12):** svislé ukotvení spodního rámu ("posunout nahoru o `railHalfHeight`, aby skutečná spodní hrana seděla na Y=0") a výpočet výšky pro kopii horního rámu (`translateY = postTopWorld.y + railHalfHeight - entryA.object3d.position.y`) OBOJÍ tiše předpokládaly, že `object3d.position.y` (pivot) odpovídá geometrickému středu dílu - u syntetického testu to platí vždy, u `profil_30x30_uzavreny.glb` ne. Důsledek, ověřeno přímo reprodukcí s reálnou `.glb` geometrií (ne syntetickou): mezi sloupky a horním rámem vznikala mezera **přesně 0.7522mm** (odpovídá naměřenému posunu pivotu) místo požadovaných 0.0000mm - jemná, vizuálně skoro neznatelná na metrové konstrukci, ale reálné porušení pravidla "žádná mezera, nikdy".

**Proč to neodhalilo NIC z dosavadního ověřování:** (1) vizuální kontrola v prohlížeči - 0.75mm na 1000mm konstrukci je pod prahem pozornosti; (2) veškeré Node.js testy v tomhle projektu dosud používaly syntetický `BoxGeometry`, který tuhle třídu chyby ze své podstaty nikdy nemůže vyvolat (je vždy symetrický). Teprve spuštění matematiky na SKUTEČNÉ, přímo z `.glb` naparsované geometrii (viz technika níže) chybu odhalilo.

**Oprava (obecné pravidlo pro každý budoucí výpočet "posuň o půl výšky/šířky, aby hrana seděla na cíli"):** NIKDY neodvozovat cílovou hranu z `position ± (size/2)` - vždy ZMĚŘIT skutečnou aktuální hranu přímo (`new THREE.Box3().setFromObject(obj).min.y` / `.max.y` podle směru) a posunout o rozdíl mezi naměřenou a cílovou hodnotou. Funguje správně bez ohledu na to, kde přesně v `.glb` sedí pivot - `attachEntryToParent`/`computeConnectorsLocal`/`worldConnectorsOf` už tohle dělají správně (pracují s konektory odvozenými z `box.getCenter()`, ne z `position`), bug byl jen v `buildKvadrShape()`'s vlastním doplňkovém Y-ukotvení, které tenhle princip nedodrželo.

**Ověřeno** (přímá reprodukce `buildSquareFrameEntries`+`buildKvadrShape` v Node.js s REÁLNĚ naparsovanou `.glb` geometrií, ne syntetickým boxem - viz technika níže): PŘED opravou 4× `FAIL` (sloupek-horní rám, `gap=0.7522mm`), PO opravě všech 20 kontrolovaných spojů (4 rohy dolní rám, 4 sloupek-dolní rám, 4 rohy horní rám, 4 sloupek-horní rám, plus rozměrová kontrola) `gap=0.0000mm/overlap=0.0000mm` přesně na dotykové ose, plný překryv na zbylých dvou, 0 kolizí. Opakovaně ověřeno i na `20x20`/`20x40`/`20x80`/`35x35` (beze změny, žádná regrese).

**Technika pro příště - jak testovat na SKUTEČNÉ geometrii, ne na odhadu:** `.glb` je čitelný bez knihovny - 12bajtová hlavička (`magic`, `version`, `length`), pak chunky (`chunkLength` `chunkType` `chunkData`), `chunkType===0x4E4F534A` je JSON ('JSON' v ASCII), `chunkType===0x004E4942` je binární buffer ('BIN' + padding). `accessors[].min/max` v JSON chunku dá rovnou bounding box bez nutnosti cokoli renderovat. Pro plnou geometrii (`THREE.BufferGeometry` s reálnými vertexy, ne jen bbox) přečíst `POSITION` accessor přes jeho `bufferView` offset do binárního chunku - viz konkrétní parser v `AGENTS_LOG.md` u tohoto zápisu.

## Pravidlo profilů - dvě topologie rohu = dvě RŮZNÁ kritéria platnosti spoje, nezaměňovat (2026-08-19, zapsáno po vlastním FALEŠNÉM POPLACHU bot8 u větrníku)

**Kontext (poctivě, včetně vlastního omylu):** při závěrečné hloubkové kontrole jsem u "Čtverec — větrník" (`buildSquarePinwheelFrameEntries`) naměřil 21.2mm vzdálenost mezi volnými konektorovými body dílů 1 a 4 a chybně to prohlásil za vážný bug (stejný vzorec `w×√2/2` jako u historicky opraveného řetězového čtverce). **Větrník byl ale celou dobu správně** — a moje "oprava" (natažení dílů, aby konektorové body splynuly) by vyrobila SKUTEČNÉ zaboření 15mm. Odhalil to až test přesné kopie produkčního kódu před commitem (nic nebylo commitnuto, úprava vrácena). Viz `AGENTS_LOG.md` u tohoto data pro plný průběh.

**Pravidlo — před posuzováním rohu VŽDY nejdřív klasifikovat jeho topologii:**

1. **Smyčka ČELO-NA-ČELO** (starý řetězový čtverec, uzavírací roh, kde oba díly v rohu KONČÍ): platnost = konektorové body uzavíracího rohu MUSÍ splynout (vzdálenost ≈ 0). Box test tady může lhát — boxy se mohou dotýkat "hezky vypadajícím" způsobem i při 21mm offsetu skutečného šroubového bodu. Přesně tahle třída chyby vedla k nahrazení řetězového čtverce přímou konstrukcí (`buildSquareFrameEntries`).

2. **Spoj ČELO-NA-BOK** (větrník, T-spoj, regálová patra — jeden díl pokračuje, druhý na něj dosedá čelem): platnost = box test (přesně 1 osa gap≈0/overlap≈0, zbylé 2 osy plný překryv). Konektorová vzdálenost mezi volnými konci `w×√2/2` je tady INHERENTNÍ vlastnost topologie, ne vada — konektorové body splývat NEMAJÍ.

**Proč na tom záleží:** použití kritéria (1) na topologii (2) vyrábí falešný poplach — a "oprava" falešného poplachu pak vyrábí skutečnou chybu (ověřeno na vlastní kůži: po mé chybné opravě `x:g=-15/o=15 z:g=-15/o=15` = reálný průnik těl). Obráceně, použití kritéria (2) na topologii (1) nechá projít skutečnou chybu (proto starý řetězový čtverec vypadal roky "OK" na pohled).

**Procesní pojistka, která to zachytila (držet se jí):** před commitem jakékoli geometrické opravy otestovat PŘESNOU KOPII výsledného produkčního kódu (ne vlastní paralelní implementaci opravy) na více reálných profilech — rozdíl mezi "moje verze opravy funguje" a "produkční kód s opravou funguje" byl přesně tam, kde se omyl projevil.

## Pravidlo procesu učení - schvalovací podklady = TECHNICKÉ ŘEZY (2026-08-20, POTVRZENO Robertem, závazné)

Robert (po sérii nečitelných 3D náhledů a wireframe pokusů u posuvného
kolečka): "není to vidět dobře, takové učení je k ničemu, když mi nedáš
přesné podklady ke schvalování" → následně výslovné pravidlo: **"pro
schvalování umístění dílů musí bot předkládat technické řezy."**

Co to znamená prakticky:
- Podklad pro Robertovo ANO/NE = **přesný 2D řez** rovinou (typicky
  kolmo na osu profilu skrz střed dílu): černě obrys profilu (vč.
  drážek), barevně obrys dílu, modře rovina stěny, červená kóta
  rozměru, o kterém se rozhoduje (zasunutí apod.), milimetrová mřížka.
- Řez se počítá PŘÍMO z reálné .glb geometrie (průnik trojúhelníků s
  rovinou) - Node skript (výstup JSON segmentů) + matplotlib
  vykreslení. ŽÁDNÉ 3D perspektivní náhledy, wireframe celého meshe
  ani bbox aproximace jako schvalovací podklad.
- **Řez potvrzující výsledek MUSÍ vznikat ZE ŽIVÉHO STAVU SCÉNY** -
  `scripts/2026-08-20_live_section_cut.js`: headless scéna umístí díl
  (runWallAut atd. z DB), exportují se `matrixWorld` profilu i dílu +
  osa profilu, a řez se počítá nad těmito transformy. NIKDY nad
  samostatným rigem, který si díl orientuje sám
  (`scripts/2026-08-20_section_cut.js` - jen pro TABULKY variant před
  výběrem): u kolečka 3404 vlastní rig vyrobil schválený obrázek
  (osa kolečka v rovině stěny), který NEODPOVÍDAL scéně (osa kolmo ke
  stěně) - Robert pak právem hlásil "nefunguje to kolečko ve scéně".
- Varianty k výběru předkládat jako ÚPLNOU tabulku možností (orientace
  × hloubka), očíslovanou, bez UI panelů přes předmět.
- **Výkresy VELKÉ** (Robert 2026-08-20: "musíš ty výkresy dělat velké,
  nevidím detaily a písmo"): raději VÍC samostatných velkých obrázků
  než jeden složený - jeden pohled na obrázek, písmo ~17-24 pt, čáry
  ~3 pt, dlouhé profily ořezané na okolí zkoumaného místa
  (interpolovaný trim, ne zahazování segmentů).
- **Rožky: zobáčky VŽDY v drážce** (Robert 2026-08-20, po kontrole
  3176 ve scéně): v rohu rožek sedí dobře (výstupky v drážkách obou
  profilů - schválená matematika uhelnikAutPlaceForPair). Na VOLNOU
  stěnu jediného profilu se ale nesmí položit jen tak naplocho -
  dosedací plocha na stěně A ZÁROVEŇ řada zobáčků zapadlá v drážce
  (zobáčky zarovnat na osu drážky, řada podél profilu). Platí pro
  magnet i jakékoli jednostěnové umístění.
- Ověřený příklad: posuvné kolečko 3404 - Robert vybral C9.5 z řezové
  tabulky na první pohled, po třech neúspěšných kolech s 3D náhledy.

## Pravidlo procesu učení - přísně sekvenční (2026-08-20, POTVRZENO Robertem, závazné)

Robert: **"NIKDY nezačínat další díl, dokud není předchozí díl
FUNKČNÍ."** Žádné paralelně rozdělané díly, žádné "tenhle necháme
otevřený a jdeme na další."

Díl je hotový, až když platí VŠECHNO z:
1. zvolená orientace/hloubka je uložená v DB (`attach_pose` /
   `attach_offset_mm`, `attach_pose_source='robert'`, řádek v
   `attach_learning_log`),
2. je změřená (headless ověření, že runtime funkce pózu ctí a zasunutí
   sedí na desetinu mm),
3. Robert ji potvrdil nad TECHNICKÝM ŘEZEM ze živého stavu scény (viz
   pravidlo výše),
4. **Robert VÝSLOVNĚ potvrdil funkčnost PŘÍMO VE SCÉNĚ** (Robert
   2026-08-20: "dokud nepotvrdím ve scéně poslední zadávaný díl, že je
   funkční, nejde se dál"). Bod 3 je podklad volby, bod 4 je finální
   slovo - schválení řezu NENÍ totéž co potvrzení ve scéně.

Teprve pak se generuje tabulka variant pro další díl. (Přesně tahle
záměna bodů 3 a 4 se 2026-08-20 stala: bot po schválení řezů koleček
rozjel kloub 3415, ačkoli Robert kolečka ve scéně ještě nezkontroloval.)

## Pravidlo učení dílů na profily - KANONICKÝ POSTUP (2026-08-20, formuloval Robert, závazné)

Robert (po uzavření koleček 3404/3386): **"Pravidlo učení díly vs
profily: postup co jsme provedli s učením koleček principiálně -
technické výkresy variant pozic, mé schválení, propis do scény na
PlaceAll a Magnet, mé potvrzení že to funguje, následný zápis do DB."**

Pět kroků, přesně v tomhle pořadí, žádný se nepřeskakuje:

1. **Technické výkresy variant pozic** - úplná očíslovaná tabulka
   řezů ZE ŽIVÉHO STAVU scény (`scripts/2026-08-20_live_section_cut.js`),
   kolizní verdikt z kontroly VŠECH vrcholů dílu proti skutečnému
   průřezu (point-in-polygon), ne jen ze středového řezu (S9 kloubu:
   žebro pantu mimo řezovou rovinu = skrytá kolize 6.9 mm). Žádné 3D
   náhledy, žádné UI panely přes předmět.
2. **Robertovo schválení** - vybere číslo varianty (nebo "ani jedno").
3. **Propis do scény na Place All A Magnet** - volba se zapíše do
   `shop_products.attach_pose`/`attach_offset_mm` (source `'robert'`)
   a číst ji MUSÍ OBĚ cesty: Place All (`runWallAut` čte
   wall_face/wall_spin, `runZaslepkaAut` čte end_face/end_spin) i
   magnet při tažení (`findBestAccessorySnap` + offset v náhledu i
   commitu). Bot doměří headless (póza ctěná, zasunutí na desetinu mm)
   a pošle potvrzující řez živého stavu.
4. **Robertovo potvrzení, že to FUNGUJE** - výslovné, po vlastní
   kontrole PŘÍMO VE SCÉNĚ (Place All i magnetem).
5. **Následný (finální) zápis do DB** - `verified_ok` s
   `verified_by='robert'` do `attach_learning_log` (append-only) +
   snapshot do `backups/`. Teprve teď je díl UZAVŘENÝ a smí se začít
   učit další (viz pravidlo přísné sekvence výše).

Ověřený vzorový průběh: kolečka 3404 (C9.5 → 9.50 mm v drážce 10) a
3386 (D10 → 6.50 mm v drážce 8); kód commity 060e3ab (Place All wall),
b3c84a6 (Place All čelo), 68238a7 (magnet + offset + spinIndex).

## Pravidlo profilů - u STEJNĚ VELKÉ přípojné plochy použij hraniční střed obálky, ne plošně vážené těžiště (2026-08-20, nalezeno bot8 na spojce 3220, POTVRZENO Robertem)

Robert po prvním zápisu spojky 3220: **"ty spojky ujíždí od středu
profilu cca 1mm odhad."** Root cause: box konektor (`computeConnectorsLocal`)
i `detectGeometricFaces` počítají bod plochy jako PLOŠNĚ VÁŽENÉ TĚŽIŠTĚ
(těžiště se posouvá, když je v ploše asymetrický otvor/nákružek - u 3220
o 0.71 mm) - tenhle bod se pak mapuje přímo na odpovídající bod
protistrany (`applyFaceToFaceCandidate`).

**Kdy je to problém:** jen když se připojovaná plocha SVOU VELIKOSTÍ ROVNÁ
protistraně (typicky čelo-na-čelo, oba přesně stejný průřez) - pak
"vycentrovat na těžiště" ve skutečnosti plochu posune, protože skutečná
hranice plochy (viditelná hrana dílu) je jinde než její těžiště. Změřeno
přímo: `faceWorldBboxY:[-20.71,19.29]` vs `profileEndBboxY:[-20,20]` -
přesah 0.71mm na jedné straně, mezera na druhé.

**Kdy to problém NENÍ:** u malé kontaktní plošky menší než protistrana
(rožky/zobáčky do drážky, corner3 apod.) - tam je těžiště SPRÁVNÝ
referenční bod, protože jde o to, KDE dochází ke skutečnému kontaktu, ne
o zarovnání dvou stejně velkých hranic. Neplést dohromady - tahle oprava
platí jen pro rodinu "endcap na stejný průřez".

**Náprava:** zjisti skutečnou hranici plochy (bbox JEN vrcholů patřících
té konkrétní ploše - filtr normála úhel <4° A offset roviny <0.6mm, ne
jen normála samotná, jinak se slijí i rovnoběžné ale posunuté plošky),
zapiš opravený bod do `geo_faces_json` (ne do sdílené `computeConnectorsLocal`
- ta zůstává beze změny, používá se správně pro VĚTŠINU dílů). Souvisí:
[[pravidlo-profilů-pivot-dílu]], [[pravidlo-profilů-montážní-plocha-nejdelší-osa]].

## Pravidlo profilů - `Matrix4.makeBasis` se 2 nezávisle volenými osami umí tiše vyrobit zrcadlení místo rotace (2026-08-23, nalezeno bot8 při vkládání "Noha" tvarů do karoserie, čeká na Robertovo ověření ve scéně)

Úkol: vložit tvar "Noha" (žebřinová sestava, lokální osy X=podél stěny,
Y=výška, Z=tloušťka) do karoserie tak, aby lokální Z směřoval ven ze
stěny (`outFromWallDir`, odvozeno ze znaménka `carCenter.x - wallX`) a
lokální X podél stěny směrem k přepážce B (`alongWallDir`, odvozeno
NEZÁVISLE ze znaménka `bZ - rearEdgeZ`). Rotace složena přes
`m.makeBasis(alongWallDir, upDir, outFromWallDir); quat.setFromRotationMatrix(m)`.

**Příznak:** výsledný kvaternion `[0,0,0,0.7071...]` - na pohled skoro
platný (normalizovaný by dal identitu), ale ve skutečnosti signalizuje,
že `setFromRotationMatrix` dostal degenerovanou/neortonormální matici.
Umístěné díly pak mají POSUNUTOU (ne jen pootočenou) Y-souřadnici -
lokální Y se "kontaminuje" příspěvky z lokálního X/Z, protože výsledná
transformace není čistá rotace.

**Root cause:** `alongWallDir` a `outFromWallDir` byly voleny NEZÁVISLE
na sobě (každý z jiného geometrického měření), ale spolu s `upDir` musí
tvořit PRAVOTOČIVOU bázi (determinant matice `[alongWallDir|upDir|outFromWallDir]`
musí být +1). Determinant vyšel `-(inwardZ·inwardX)` - když obě
znaménka vyjdou STEJNÁ (typický, ne okrajový případ - v tomhle úkolu se
stalo hned napoprvé), determinant je -1, tj. zrcadlení. `Quaternion.
setFromRotationMatrix` na zrcadlení NEHÁZÍ chybu, jen vrátí nesmyslný
(ale na první pohled nenápadný) kvaternion - žádný console error, žádný
throw, jen tiše špatná geometrie.

**Náprava:** nikdy nevolit všechny 3 osy báze nezávisle. Zafixuj JEN ty
osy, na kterých skutečně záleží (tady: `outFromWallDir` - určuje dotyk
se stěnou, a `upDir` - určuje svislost), a TŘETÍ dopočítej křížovým
součinem, aby byla pravotočivost zaručená matematicky, ne odhadem:
`alongWallDir = new THREE.Vector3().crossVectors(outFromWallDir, upDir).multiplyScalar(-1)`
(ověřeno: determinant vyjde vždy přesně `inwardX² = 1`, nezávisle na
znaménku). Směr "kam posunout druhý díl podél zdi" (např. přední noha
+1500mm k B) NENÍ nutné vázat na stejný vektor jako `alongWallDir` -
řeš ho zvlášť, přímo přes měřené světové Z (`inwardZtoB`), jinak si
vynucená oprava `alongWallDir` protiřečí s tím, kam měl díl "logicky"
směřovat.

**Jak to odhalit vizuálně:** neshoda nemusí být na screenshotu vidět už
jako "posunuté", pokud je díl tenký/na pozadí stěny - nejjistější je
DOČASNĚ přebarvit obě porovnávané části výrazně odlišnou barvou
(`material.color.set(0x....)`) přímo v testovacím skriptu, ne spoléhat
na výchozí barvu + orbit kameru; teprve pak je rozestup/dotyk se stěnou
na snímku nezpochybnitelný. Číselné ověření (Box3 min/max obou dílů
proti očekávanému rozsahu) zůstává povinné i tak - vizuál je jen
kontrola NAVÍC, ne náhrada.

## Pravidlo profilů - i skutečný mesh test (SAT + volumetrické vzorkování) může ohlásit kolizi, která je záměr, ne vada - profil + jeho vlastní záslepka (2026-09-11, nalezeno bot16 při nezávislém ověření sestavy 337, POTVRZENO bot3/Robertem jako známý/vysvětlený jev)

Kontext: bot9 při triáži fronty nahlásil "sestava 337 má 4 zanoření" na
schválené sestavě. Zadání znělo ověřit to MĚŘENÍM (`scripts/2026-09-11_
mesh_kolize_lib.js`, SAT + volumetrické vzorkování dovnitř obou sítí -
přesně nástroj proti pasti #8 skillu `3d-scena-spoje` / eurobox-nesting),
ne čtením hlášení, a testovat VŠECHNY dvojice dílů v sestavě, ne jen
úhelníky (dosavadní sweep byl na úhelníky zúžený).

Výsledek na 337: 11 skutečných zanoření na síti. Z toho 4 byly
sestavě-specifické (souhlasí s bot9, 2 vážné - výplň boční přepážky
`vypln-bok-prepazka` visí ~8mm do příčky `pricka-*` po celé délce
219mm, `odsun=10.97mm`; 2 hraniční, ~1.3mm). Zbylých **7 bylo vzorem
`<role profilu> + zaslepka-<role profilu>`** (`predni-svislice +
zaslepka-predni-svislice`, `cap + zaslepka-cap`,
`zadni-svislice-* + zaslepka-zadni-svislice-*`) s **bit přesně
identickým `odsun=5.25mm`, rozměr překryvu `7.5×5.44×7.5mm`** na KAŽDÉM
výskytu. Ověřeno navíc na sestavě 336 (jiná sestava, jiné pozice) -
úplně stejné číslo.

**Verdikt (bot3/Robert 2026-09-11): tohle NENÍ vada 337, je to
konstanta vztahu dvou konkrétních GLB, ne nehoda umístění.** Záslepka
je čep, který se zasouvá do dutiny profilu na pevnou hloubku - mesh
test o té dutině neví (vzorkuje objem podle povrchu GLB), takže když
GLB profilu nemá modelovanou skutečnou dutinu na tomhle místě (nebo
GLB záslepky zahrnuje i část určenou "k zasunutí"), objemový vzorek
vyjde uvnitř obojího, i když fyzicky nic nekoliduje. Bitová shoda
přes různé sestavy a pozice je právě ten signál, který to odlišuje od
nehody - nehoda umístění by se lišila sestava od sestavy.

**Co z toho plyne:**
- **Neopravovat jako nález.** Kdykoli tenhle vzor (`role + zaslepka-role`,
  `odsun≈5.25mm`, `oblast≈[7.5,5.44,7.5]`) vyjde z obecného (ne
  úhelníkového) mesh kolizního testu, je to ZAPSANÝ jev, ne otevřená
  vada - nezačínat opravovat něco, co je záměr.
- **Obecný (všechny dvojice, ne jen úhelníky) mesh kolizní test dosud
  NIKDY neběžel přes celý katalog** - jen přes 337 a 336 (bot16,
  2026-09-11). Je tedy jisté, že se stejný vzor objeví ve VĚTŠINĚ/VŠECH
  sestavách se záslepkami, ne že by byl vzácný.
- **Kdyby to bylo někdy potřeba doopravdy rozřešit:** ne dalším
  kolizním testem, ale pohledem do katalogu (`cfg_dily`/GLB) - jestli
  profil v definici má modelovanou dutinu a jakou hloubku má mít čep.
  To je samostatná práce, ne rozšíření týhle kontroly.

Viz i `.claude/skills/3d-scena-spoje/SKILL.md`, Metodika ověření, bod 9
(stejný nález, kratší verze pro onboarding).

## Postup profilů - přepočet kolizní rezervy na existující sestavě (2026-09-12, Robert/bot8)

Zdroj pravdy je `shape_geometry_methods.id=11`
(`prepocet-kolizni-rezervy-existujici-sestavy`, v1, ověřeno Robertem na
K-075/Doblo L1, `product_assemblies.id=340`) - přesný strukturovaný
postup (8 kroků včetně odůvodnění "proč", reálný aplikovaný příklad
čísel, odkazy na reference kód) je TAM, sem se NEKOPÍRUJE (stejná
konvence jako u ostatních `shape_geometry_methods`/
`car_body_placement_methods` receptů, viz `VLASTNOSTI_PROFILU.md`).

Shrnutí: na JIŽ POSTAVENÉ sestavě (ne od nuly) přepočítat kolizní
bezpečnostní rezervu (přepážka/podběh) jako přesnou aritmetickou deltu
(NE novým kolizním krokováním), aplikovat jen na dotčené nohy/sloupce,
zkontrolovat a dorovnat lůžka, která po zkrácení nohy visí ve vzduchu
(rozložit rovnoměrně do mezer mezi patry, ne jen posunout spodní
patro), ověřit SAT testem + přesným švem na 0.000mm, nikdy nepřepsat
chráněné/zamčené sestavy.

