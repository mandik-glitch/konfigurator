# Organizéry PACKOUT: fotografie a model, v6

John, 8. 10. 2026. Navázáno na existující v5. Přečtené celé zadání včetně doplnění 8, AGENTS.md 4c–4f a povinné geometrické podklady. V5 zůstala beze změny. Dynamic komponenty a trubkový generátor 01 jsou pozastavené na Robertův pokyn.

[Náhled v6](https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v6/) · [Fotografie ↔ model, 30 dvojic](https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v6/srovnani.html) · [Zachovaná v5](https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v5/).

Pět organizérů je přepracovaných a připravených k posouzení. **Nevydávám je za přesný výrobní CAD ani za prokázanou shodu detailů do 2 mm.** Podklady potvrzují vnější rozměry a část vnitřních rozměrů; fotografie potvrzují počty a viditelné členění. Nekótované rozměry detailů zůstávají neověřené. Viditelný rozdíl nebo doložená odchylka nad 2 mm je chyba, kterou je potřeba dále opravit.

## Vidím v kódu a fotografiích: hlavní chyby v5 a provedené změny

| SKU | Soubor a řádek v5 | Co bylo špatně a proč | Změna v6 |
|---|---|---|---|
| 4932478625 | `vytvor_doladene_tvary_v5.js:683` | Jen dva červené děliče a čtyři oddíly; fotografie Hero_2 vlastního SKU ukazuje tři dlouhé a tři krátké děliče po stranách pevného středu. | Šest samostatných červených děličů, jejich vodicí drážky, pevný střed, osm oddílů. |
| 4932498323 | `vytvor_doladene_tvary_v5.js:513` | Vysoký souvislý obvod zakrýval čela výklopných nádob. Chybělo odpovídající členění rámu a tři kovové tyče. | Otevřený nosný rám, střední sloupek, tři přídržné tyče, 8 malých + 2 velké duté boxy s víčky, dva děliče velkých boxů, západka T a zvednutelná rukojeť. Otevírání opravené kolem dolní hrany boxu směrem ven. |
| 4932471064 | `vytvor_doladene_tvary_v5.js:130`, `:669` | Přihrádky opticky splývaly; chyběly výrazné meziprostory, děliče a členění víka. Vnitřní výška byla celá přidělená spodnímu tělu, takže víko vycházelo příliš nízké. | 10 samostatných zaoblených dutých nádob, děliče a vodicí žebra, vlastní těsnicí okénka, střední pruh víka, průchozí vodorovný úchop, čelní kapsa a spony. |
| 4932464082 | `vytvor_doladene_tvary_v5.js:653`, `:669` | Tenké červené U nenahrazovalo doloženou rukojeť s černým úchopem. Čelní sloupky, kapsy a výška víka neodpovídaly fotografiím. | Červená rukojeť s černým vroubkovaným úchopem a čepy, nové spony, rohy a prolisy, 10 samostatných nádob a členěné průhledné víko. Spodní pole 3 × 4 vychází z fotografie tohoto SKU. |
| 4932471065 | `vytvor_doladene_tvary_v5.js:130`, `:669` | Pět nádob bylo téměř bez mezer a děličů. Trup byl prodloužený až k přední hraně rukojeti; úchop a spony neodpovídaly kompaktnímu SKU. | 4 malé + 1 velká nádoba, děliče, kratší trup a předsazený úchop podle jeho vlastní fotografie, dvě viditelné spony. Spodní pole 3 × 2 podle vlastního spodního snímku. |
| Tři SKU bez přímého spodku | `vytvor_doladene_tvary_v5.js:625` | Část spodních pozic se přenášela mezi typy. To nedokládá skutečný tvar ani funkční rozteče jiného SKU. | U 1064, 8625 a 8323 nepřebírám spojovací pozice jiného SKU. Chybějící spodek a rozteče jsou výslovně neověřené; model nemůže sloužit jako podklad funkčního spojení. |

Implementace: `geometrie_organizery_v6.js` obsahuje nové nádoby, víka, úchopy, spodní pole a výklopný typ. `vytvor_doladene_tvary_v6.js:209` ukotvuje patky do skutečného obrysu dna a kontroluje obálku bez dodatečného natažení modelu. Veškeré změny jsou pouze ve vlastní výstupní složce a vlastním statickém náhledu.

## Zdroje a srovnání

Použito 77 uložených fotografických podkladů pěti SKU z předchozí rešerše. Každé SKU má vlastní anotaci horní fotografie, nikoli převzaté rozteče jiného organizéru. Nově přečtený [oficiální katalog PACKOUT 2023](https://uk.milwaukeetool.eu/NetC.MilwaukeeTools/media/MediaLibrary/HomeBanners/Milwaukee_Accessories_Packout_Brochure_2023_UK.pdf) potvrzuje u hlubokého organizéru osm oddílů. Rozpor s některými jazykovými produktovými listy uvádějícími deset nádob je zachovaný; v6 reprodukuje zobrazenou sestavu s děliči. Počet oddílů dna se nezaměňuje s počtem prolisů průhledného víka.

Přímé pohledy běžného organizéru poskytuje [galerie TIM 4932464082](https://www.tim.pl/organizer-narzedziowy-10-pojemnikow-na-akcesoria-packout-4932464082/p/0001-00018-63769); kompaktní typ má vlastní [slovenskou galerii 4932471065](https://www.stavbaeu.sk/milwaukee-packout-slim-kompaktny-organizer-4932471065-235267). Další zdroje: [výrobce, organizéry](https://www.milwaukeetool.eu/en-eu/packout-organisers/packout-organisers/) a [výrobce, výklopný organizér](https://www.milwaukeetool.eu/en-eu/packout-tip-bin-organiser/packout-tip-bin-organiser/). Přesné odkazy každého snímku jsou v soukromém `zdroje/doladeni-v6/srovnani.json` a veřejné srovnávací stránce.

Pro každý organizér je připraveno šest dvojic: čelo, bok, horní a spodní strana, šikmo zavřený a otevřený stav. **Sedm z třiceti dvojic nemá přímou fotografii konkrétního SKU**: bok a spodek 1064, bok 1065, bok a spodek 8625, bok a spodek 8323. V těchto místech je místo odkazu informace „neověřeno“. U čela dostupného pouze šikmo je render ze stejného šikmého směru a tento rozdíl je uvedený. Ohnisko, perspektiva a přesný úhel nekalibrovaných fotografií nejsou ověřené, takže toto srovnání nedokládá milimetrovou přesnost.

Veřejná stránka má vlevo odkaz na originální snímek u autora a vpravo náš render. Cizí fotografie se veřejně nevkládají ani nestahují. Skutečné dvojice s místními fotografiemi jsou pouze v soukromých podkladech `zdroje/doladeni-v6/porovnani-soukrome/`. Přímé obrázky níže obsahují výhradně naše rendery:

- [4932471064 – šest pohledů](https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v6/srovnani/4932471064-prehled.png)
- [4932464082 – šest pohledů](https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v6/srovnani/4932464082-prehled.png)
- [4932471065 – šest pohledů](https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v6/srovnani/4932471065-prehled.png)
- [4932478625 – šest pohledů](https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v6/srovnani/4932478625-prehled.png)
- [4932498323 – šest pohledů](https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v6/srovnani/4932498323-prehled.png)

## Výpočty a digitální ověření [mm]

Konvence katalogu: X = šířka, Y = délka, Z = výška; jednotky mm, počátek ve středu uzavřené obálky. Kompaktní SKU má čelo +Y; ostatní +X. Obálka slouží ke kontrole skutečných součástí, nikoli jako náhradní model.

| SKU | Zdrojová obálka X × Y × Z | Zdrojový uzavřený vnitřní prostor Š × L × V | Počet nádob / oddílů |
|---|---|---|---|
| 4932471064 | 414 × 500 × 64 | 305 × 457 × 46 | 2 × (2 + 1 + 2) = 10 |
| 4932464082 | 386 × 500 × 117 | 305 × 457 × 99 | 2 × (2 + 1 + 2) = 10 |
| 4932471065 | 249 × 411 × 64 | 203 × 305 × 46 | 2 + 1 + 2 = 5 |
| 4932478625 | 386 × 507 × 178 | 305 × 457 × 139 | 2 × (3 děliče + 1) = 8 |
| 4932498323 | 386 × 500 × 170 | nezískáno, není doplněný odhad | 8 malých + 2 velké = 10 |

Vnější a vnitřní kóty i jejich URL jsou převzaté z existujícího katalogu beze změny. Přesné vypočtené rozměry jednotlivých **digitálních** součástí jsou v nové veřejné tabulce `soucasti.csv`; stará tabulka v5 nebyla převzatá jako aktuální měření v6.

Uzavřená vnitřní výška zahrnuje i prostor pod víkem. V pracovních souřadnicích před vystředěním platí `z_dno = H − 2 − V_vnitřní` a `z_strop = H − 2`. Tloušťka 2 mm je **nekótovaný parametr rekonstrukce**, nikoli tvrzení o materiálu skutečného výrobku:

- 1064 a 1065: `64 − 2 − 46 = 16`; ověření `62 − 16 = 46 mm`. Vizuální výška víka `64 × 0,29 = 18,56`; výška stěny dna `64 − 18,56 − 16 = 29,44 mm`.
- 4082: `117 − 2 − 99 = 16`; ověření `115 − 16 = 99 mm`. Víko `117 × 0,22 = 25,74`; stěna dna `117 − 25,74 − 16 = 75,26 mm`.
- 8625: `178 − 2 − 139 = 37`; ověření `176 − 37 = 139 mm`. Víko `178 × 0,15 = 26,70`; stěna dna `178 − 26,70 − 37 = 114,30 mm`.

Poměry výšek víka jsou vizuální anotace, **ne potvrzené fyzické kóty**. Horní fotografie kompaktního SKU ukazuje kratší tělo a předsazené držadlo. Odečet projekce: `D_tělo = 411 × (792 − 72) / (793 − 6) = 376,01 mm`; předsazení vůči celkovému rozměru `411 − 376,01 = 34,99 mm`. Je to odvození obrazového poměru, nikoli fyzické doměření. Celkový zdrojový rozměr 411 mm zůstává zachovaný. Výjimka přesahu je povolená pouze těmto doloženým čelním součástem kompaktního SKU; patky nemají povolený přesah.

Anotace nádob: například 1064 má v projekci první řádek `506 − 312 = 194 px` při celkovém rozsahu `1000 − 200 = 800 px`; poměr `194/800 = 0,2425`. V6 normalizuje rozsah všech řádků do doloženého vnitřního půdorysu. Tabulka pixelů, vzorce normalizace i odvozené digitální rozměry jsou v `anotace.json`, `binGridV6()` a měřeních. Tato normalizace neprokazuje absolutní polohu fyzických nádob do 2 mm.

Spodní členění: 4082 má `3 × 4 = 12` viditelných pozic a 1065 `3 × 2 = 6`, podle samostatných spodních fotografií. Rozměry zubů, rozteče a funkční vůle nejsou kótované ani potvrzené. Obecné čtyři podstavné patky neznamenají potvrzení skrytého spojovacího systému u zbývajících SKU.

Kontrola přesahu v X: `max(0; X_min_dna − X_min_dílu; X_max_dílu − X_max_dna)`, obdobně Y. Kontroluje se i skutečný zaoblený obrys s čelním vybráním: každý vrchol horní plochy patky musí zasáhnout skutečnou spodní plochu dna paprskem. Digitální tolerance 0,01 mm není fyzická tolerance výrobku. Nejsou zavedené výjimky podle barvy nebo libovolného názvu dílu.

Výsledky čistých kontrol: **3 701 kontrol, 21 GLB, pět přepracovaných organizérů, 930 nezměněných místních a veřejných souborů v5**. Vnější obálky, osy, jednotky, nenulové plochy, duté nádoby, počty dílů, opory patek a uzavřené vnitřní výšky prošly. Ostatních 16 GLB zůstalo bitově shodných s v5. Stávající katalogový parser načetl všech 21 modelů i tři skutečné katalogové reference. Největší GLB zůstává 2 733 308 B, pod 3 MB.

Offline prohlížeč ověřil všech 20 typů, otevírání, skrývání víka, barvení dílů, vyhledávání, mobilní šířku, zvedání rukojeti a **směr otevření výklopných boxů ven z rámu**, ne pouze nenulovou rotaci. Srovnávací stránka má 30 dvojic a žádnou vzdálenou vloženou fotografii. Žádné chyby nebo síťové přístupy při čistých kontrolách.

## Domnívám se / co zbývá

V6 věrněji vystihuje viditelné členění než v5; **není doložené**, že její nekótované detaily odpovídají skutečnému kusu do 2 mm. Chybí měřitelné poloměry, tloušťky, hloubky prolisů, úkosy, přesné pantové osy, spojovací profily a vůle. Textová značka připomíná označení, nereprodukuje přesný tvar písma. Pro doložení geometrie je potřeba licencovaný kótovaný CAD, sken nebo doměření konkrétních SKU. Přesných výrobcem potvrzených CAD je stále 0; neoznačuji funkční stohování za ověřené.

Karty v náhledu tyto mezery vypisují. Chybějící přímé spodní fotografie se nepodařilo získat novými veřejnými adresami (HTTP 410); některé HTML dotazy skončily časovým limitem. Žádné ochrany nebyly obcházené. U nového XL zůstává omezení jeho samostatné fotodokumentace a u pojízdné zásuvky původní rozpor kót.

Ostatních 15 typů je rychle porovnaných, další rozdíly jsou níže. Jejich geometrie zůstává v5; nejsou označené jako odpovídající skutečnosti. Je to zbývající práce, nikoli potvrzené dokončení všech kufrů.

## Opakování kontroly

Čisté skripty nevyžadují databázi ani síť: `priprav_podklady_v6.py`, `vytvor_doladene_tvary_v6.js`, `sestav_nahled_v6.py`, `renderuj_kontrolu_v6.js`, `srovnani_v6.py`, `over_organizery_v6.py`, `over_v6_katalogovym_parserem.js`, `over_nahled_v6.js`. Staré generátory nesmějí přepsat aktuální modely v6. Nahrání a veřejné kontroly jsou oddělené skripty `publikuj_nahled_v6.py` a `over_verejny_nahled_v6.js`; první pouze jednorázově vytvoří vlastní náhled, druhý čte pouze GET jeho statických souborů.

Režie a její stálá adresa nebyly upravené. Živý web není změněný. Před integrací je potřeba Robertovo posouzení náhledu. Dynamic a trubkový generátor zůstávají pozastavené; připravené části zůstaly zachované.

## Rychlé srovnání zbývajících 15 typů

Vidím na fotografiích a vlastních renderech; přesný úhel a objektiv nejsou kalibrované. Rozdíl polohy otevřeného víka či zvednutého madla se nezaměňuje s chybou uzavřené obálky. Nekótované velikosti neopravují odhady.

| SKU | Nález, proč vadí a návrh pokračování | Fotografie | Náš render |
|---|---|---|---|
| 4932471723 | Nedostatečné čelní prolisy, proporce zámku a horního úchopu. Fotografie má zvednuté držadlo, model má sklopené; tento rozdíl polohy není sám o sobě chyba obálky. Návrh: doměřit uvedené detaily vlastního SKU a přepracovat jejich tvar. | [Zdroj](https://static.milwaukeetool.eu/remote.axd/milwaukee-media-images.s3.amazonaws.com/hi/4932471723--Hero_1.jpg?v=E841FD38A26E03A0C3ADCC376C8E08CD&width=1200) | [Model](https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v6/porovnani/4932471723.png) |
| 4932471724 | Chybí výrazná vodorovná žebra přepravky, členění čela a čelní zámek; stěny jsou příliš hladké. Návrh: doměřit uvedené detaily vlastního SKU a přepracovat jejich tvar. | [Zdroj](https://static.milwaukeetool.eu/remote.axd/milwaukee-media-images.s3.amazonaws.com/hi/4932471724--Hero_1.jpg?v=5D970D1B8DCB2803843A534EA68DB141&width=1200) | [Model](https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v6/porovnani/4932471724.png) |
| 4932480623 | Dvířka, dolní uzávěr a rohy jsou stále příliš zjednodušené. Celková obálka nenahrazuje jejich správný tvar. Návrh: doměřit uvedené detaily vlastního SKU a přepracovat jejich tvar. | [Zdroj](https://static.milwaukeetool.eu/remote.axd/milwaukee-media-images.s3.amazonaws.com/hi/4932480623--Hero_1.jpg?v=E38F1881A4832FEBA766E6DF0C56AA8C&width=1200) | [Model](https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v6/porovnani/4932480623.png) |
| 4932501784, 4932478162 | Čelní rukojeť, rozměry západek a kovové rohové prvky jsou stále nevěrné. Pro novou variantu je potřeba vlastní fotografie a detailní doměření. Návrh: doměřit uvedené detaily vlastního SKU a přepracovat jejich tvar. | [Zdroj](https://static.milwaukeetool.eu/remote.axd/milwaukee-media-images.s3.amazonaws.com/hi/4932478162--Hero_1.jpg?v=49DF2C067DFAF03C45B8DAFBEE9CCCA2&width=1200) | [Model](https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v6/porovnani/4932501784.png) |
| 4932499703 | Profesní vložka a síťované kapsy otevřeného víka nejsou reprodukované. Srovnání se zavřeným modelem samo nevypovídá o vložce. Návrh: doměřit uvedené detaily vlastního SKU a přepracovat jejich tvar. | [Zdroj](https://static.milwaukeetool.eu/remote.axd/milwaukee-media-images.s3.amazonaws.com/hi/4932499703--Hero_1.jpg?v=A7AA5E75DADFB52E46629E8B5333C8B4&width=1200) | [Model](https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v6/porovnani/4932499703.png) |
| 4932499704 | Vložka instalatérské varianty není samostatně doložená; společná fotografie profesních kufrů nestačí k ověření tohoto SKU. Návrh: doměřit uvedené detaily vlastního SKU a přepracovat jejich tvar. | [Zdroj](https://static.milwaukeetool.eu/remote.axd/milwaukee-media-images.s3.amazonaws.com/hi/4932499704--Hero_1.jpg?v=7205611E6F188BC449B7FA30142AF7B5&width=1200) | [Model](https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v6/porovnani/4932499704.png) |
| 4932464080 | Příliš malé západky a nevěrná čelní rukojeť. Chybí výrazné horní prolisy a kovové rohy. Návrh: doměřit uvedené detaily vlastního SKU a přepracovat jejich tvar. | [Zdroj](https://static.milwaukeetool.eu/remote.axd/milwaukee-media-images.s3.amazonaws.com/hi/4932464080--Hero_1.jpg?v=B75D15417D250667A58B9F30FE857CF5&width=1200) | [Model](https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v6/porovnani/4932464080.png) |
| 4932464078 | Rohové sloupky, velikost západek a členění čela se stále liší. Madlo fotografie je vysunuté a model je ve sklopené přepravní poloze. Návrh: doměřit uvedené detaily vlastního SKU a přepracovat jejich tvar. | [Zdroj](https://static.milwaukeetool.eu/remote.axd/milwaukee-media-images.s3.amazonaws.com/hi/4932464078--Hero_1.jpg?v=14D945FBB07B79BA3BD80DFE5A0617F4&width=1200) | [Model](https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v6/porovnani/4932464078.png) |
| 4932464079 | Nevěrný čelní úchop a západky; výrazné rohy a žebra nejsou dostatečné. Horní držadlo je na fotografii zvednuté a v modelu sklopené. Návrh: doměřit uvedené detaily vlastního SKU a přepracovat jejich tvar. | [Zdroj](https://static.milwaukeetool.eu/remote.axd/milwaukee-media-images.s3.amazonaws.com/hi/4932464079--Hero_1.jpg?v=C05DE29A8CAEDB978916A8DF22959731&width=1200) | [Model](https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v6/porovnani/4932464079.png) |
| 4932472129 | Ploché čelo zásuvek, jemné nevýrazné rohy a nepřesné červené úchopy. Počet dvou zásuvek sedí; jejich tvar není ověřený. Návrh: doměřit uvedené detaily vlastního SKU a přepracovat jejich tvar. | [Zdroj](https://static.milwaukeetool.eu/remote.axd/milwaukee-media-images.s3.amazonaws.com/hi/4932472129--Hero_1.jpg?v=93986A64935C84CF2801CC4778FBD219&width=1200) | [Model](https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v6/porovnani/4932472129.png) |
| 4932472130 | Ploché čelo zásuvek a nevěrné úchopy i rohy. Počet tří zásuvek sedí; tvar není ověřený. Návrh: doměřit uvedené detaily vlastního SKU a přepracovat jejich tvar. | [Zdroj](https://static.milwaukeetool.eu/remote.axd/milwaukee-media-images.s3.amazonaws.com/hi/4932472130--Hero_1.jpg?v=B2298CC2161BC7C3A9B33568A613F8F0&width=1200) | [Model](https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v6/porovnani/4932472130.png) |
| 4932493189 | Čela čtyř zásuvek a výrazné rohové sloupky jsou nedostatečně reprodukované. Návrh: doměřit uvedené detaily vlastního SKU a přepracovat jejich tvar. | [Zdroj](https://static.milwaukeetool.eu/remote.axd/milwaukee-media-images.s3.amazonaws.com/hi/4932493189--Hero_1.jpg?v=2A2D4A3C12A6AC7DC27BFF08C858A6D7&width=1200) | [Model](https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v6/porovnani/4932493189.png) |
| 4932493190 | Členění 2 + 1 je přítomné, ale čela, úchopy a rohy jsou nevěrné. Návrh: doměřit uvedené detaily vlastního SKU a přepracovat jejich tvar. | [Zdroj](https://static.milwaukeetool.eu/remote.axd/milwaukee-media-images.s3.amazonaws.com/hi/4932493190--Hero_1.jpg?v=DEAD4B21DB6752B3F0E7D1453084FE49&width=1200) | [Model](https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v6/porovnani/4932493190.png) |
| 4932498651 | Prolisy čela, rukojeť zásuvky a konstrukce madla jsou příliš zjednodušené. Vysunuté madlo fotografie nelze porovnávat s přepravní polohou bez přepnutí. Návrh: doměřit uvedené detaily vlastního SKU a přepracovat jejich tvar. | [Zdroj](https://static.milwaukeetool.eu/remote.axd/milwaukee-media-images.s3.amazonaws.com/hi/4932498651--Hero_1.jpg?v=9BD245EA4F775D9711DF1EC04F05F2B4&width=1200) | [Model](https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v6/porovnani/4932498651.png) |
| 4932478161 | Nesedí tvar podvozku a kapsy kolem kol; kola a boční výsuvný úchop potřebují podrobnější porovnání konkrétní polohy. Návrh: doměřit uvedené detaily vlastního SKU a přepracovat jejich tvar. | [Zdroj](https://static.milwaukeetool.eu/remote.axd/milwaukee-media-images.s3.amazonaws.com/hi/4932478161--Hero_1.jpg?v=826D1548E26CE9750A1D8CE2770C2C47&width=1200) | [Model](https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v6/porovnani/4932478161.png) |

Záznam: `zdroje/doladeni-v6/ostatni-review.json:1`; jednotlivé modely a rozsahy součástí jsou v aktuální veřejné tabulce `soucasti.csv`. Nálezy jsou zároveň u každého typu v přehledu náhledu.

## Nahraný náhled a veřejné ověření

Nahráno pouze do vlastní nové složky v6: **598 statických souborů**, celkem 77566587 B. Hlavní stránka odpověděla curl HTTP 200. Všech 598 souborů následně přečteno veřejným GET: HTTP 200 a SHA-256 shodné s ověřenou místní kopií. Veřejný prohlížeč načetl všech pět organizérů a 30 dvojic včetně všech porovnávacích obrázků; mobil bez přetékání, žádné chyby nebo požadavky mimo vlastní složku. První běh veřejného prohlížeče se zavřel bez zachycené chyby stránky; opakovaný úplný běh prošel. Příčinu zavření nemám doloženou.

Závěrečná kontrola znovu potvrdila 3701 geometrických kontrol a všech 930 nezměněných souborů v5. Stav v přehledu práce: **čeká na schválení**, s uvedenými zbývajícími neověřenými detaily a ostatními rozdíly. Dynamic komponenty a trubkový generátor zůstávají přerušené na pokyn Roberta. Připravená poznámka NAVAZUJ je ve vlastní výstupní složce.

Aktuální modely pěti organizérů:

| SKU | Součástí | GLB B |
|---|---:|---:|
| 4932471064 | 213 | 1068948 |
| 4932464082 | 328 | 1448692 |
| 4932471065 | 199 | 902420 |
| 4932498323 | 127 | 510884 |
| 4932478625 | 179 | 839172 |
