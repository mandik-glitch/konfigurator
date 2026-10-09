# Nářadové kufříky – doladění modelů v3

John, 6. 10. 2026. Přečteno celé AGENTS.md včetně 4d, 4e a 4f, celé zadání včetně doplnění 1–5 a geometrické podklady. Samostatná práce pouze na výstupech a povoleném statickém náhledu.

Náhled: [kufříky v3](https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v3/). V2 zůstává na původní adrese beze změny. Upraveno 20 typů / 21 SKU; dalších 14 dílů systému zůstává mimo modelování.

## Vidím ve zdrojích a v souborech

Z galerií konkrétních variant bylo přečteno 202 fotografií. John prohlédl všechny soukromé přehledy. Každá fotografie má přímou URL, produktovou stránku, místní soubor, rozlišení a SHA-256 v `zdroje/doladeni-v3/fotografie.json` a CSV. Dostupné jsou zavřené a otevřené kusy, spodní pohledy organizérů, zadní pohled pojízdného boxu, čelní pohledy zásuvek a detailní snímky spon a vnitřních vložek. Pokrytí úhlů není úplné pro každý typ. Profesní kufry mají pouze jediný výrobní snímek; veřejné CZ/SK nabídky opakují tentýž záběr. To není nezávislé potvrzení jejich vložek.

Soukromé fotografie nebyly vložené do veřejného v3. V náhledu jsou pouze vlastní rendery v2/v3, odkazy na použité fotografie, seznam oprav, stav shody a konkrétní neověřené body. Porovnání fotografie–vlastní render je lokálně v `zdroje/doladeni-v3/porovnani-soukrome/<SKU>.jpg`. Směr pohledu byl přiblížen vybranému snímku; perspektiva není kalibrovaná a není to měřicí porovnání každého povrchu. U zdvižených či vysunutých madel se fotografie liší od přepravní polohy modelu.

Nový průzkum CAD navázal na dřívější kandidáty; žádný úplný licencovaný CAD správného EU SKU se stažením bez účtu nebyl získán. Nebyl založen účet, odeslán formulář ani použit přihlašovací údaj. Dočasný soubor `zdroje/doladeni-v3/stranka-organizery.html` obsahoval vložený přístupový údaj z veřejné stránky; plná kopie byla odstraněna a podklady nyní obsahují pouze galerii a seznam variant.

V3 neprovádí dodatečné natažení celého modelu. Ve všech GLB je `axis_scale=[1,1,1]` a `applied=false`. Kóty dutin a průměry kol proto nebyly přizpůsobením obálce zdeformovány. Konvence zůstává mm, X = šířka, Y = délka, Z = výška; kompaktní typy mají čelo na krátké straně. Všechny uzly mají souřadnice přímo ve vrcholech; katalogový parser přezkoumal 21 modelů a 3 původní katalogové reference.

### Ověřené příčiny a opravy

- `vytvor_realne_tvary.js:183–194` (původní v2): součet trčících detailů určil obálku, poté se celý model nestejně natahoval po osách. Kolo bedny 230 mm tak mělo digitální rozsah 246,234 × 229,585 mm. Nový generátor kontroluje obálku bez škálování; kola i známé dutiny měří nezávislý skript.
- V2 řadila kompaktní organizér a kompaktní box stejně jako široké kufry; kompaktní organizér měl jednu sponu. Fotografie dokládají krátké čelo a dvě spony organizéru. V3 opravuje orientaci a počet, kompaktní box si ponechává jedinou širokou sponu.
- V2 opakovala deset červených vložek i v hlubokém organizéru. Otevřené fotografie ukazují tři přední oddíly a zadní dlouhou přihrádku. V3 změnila vnitřní topologii.
- V2 otáčela dvířka skříně do strany. Fotografie otevřeného kusu ukazuje horní vodorovný pant. V3 mění pant i směr otevření a odstraňuje vzorkováním zjištěný průnik panelu dvířek se stropem.
- V2 umísťovala kola bedny na opačné konce a osy podél délky. Fotografie dokládají obě kola na jednom konci; ve v3 mají osu X a shodnou polohu Y. Doplněny dvě horní stohovací pozice.
- V3 propojuje jednotlivé vrstvy víka, spodní spojovací patky, madla, zajišťovací rámy a úchopy s oporami. Profesní vložky mají duté kapsy a spočívají na dně. Žádný výsledek kontroly kontaktu není založen pouze na obálce.

## Domnívám se / přesnost zůstává neověřená

**Jde o vlastní modely se znovu upraveným reálným uspořádáním, nikoli o výrobcem ověřený přesný CAD všech povrchů.** Fotografie dokládají přítomnost a topologii dílů; nekótované proporce, poloměry, tloušťky a polohy zůstávají rekonstrukční parametry. Žádná z těchto hodnot nebyla zapsána jako ověřená technická vlastnost. Počet přesných CAD zůstává 0.

Zjednodušené zůstává jemné odlehčení spodku, výztužná síť uvnitř víka, textová loga a drobné prolisy. Spojovací profily PACKOUT, vůle, montážní otvory, dráhy mechanismů, šířky kol a rozsahy madel je nutné doměřit nebo získat z kótovaného CAD. Barvy a povrch jsou pouze vzhledové. U nového XL SKU je galerie starší revize; u pojízdné zásuvky zůstává rozpor zdrojových vnějších rozměrů. Náhled tato slabá místa ukazuje.

## Čisté kontroly a jejich rozsah

Všech 21 GLB: 1023484 skutečných vrcholů, 452672 trojúhelníků, normály, indexy a digitální obálka. Tolerance obálky 0,01 mm; největší soubor 1774324 B, všechny pod 3 MB. Nejde o toleranci fyzického výrobku.

Raycasting ověřil 24 zdrojových dutin přímo proti skutečným stěnám. Kontakt dokládá bod na trojúhelníku nebo průsečík hrany: 488 vyčnívajících dílů, 1398 kandidátních párů, 0 nedoložených kontaktů. Samostatná kontrola ověřuje opory přihrádek a vložek.

Objemové vzorkování vnitřních nádob, zásuvek a dvířek proti nosnému tělu: 82 kandidátních párů, 2916 materiálových vzorků, 0 zachycených průniků po opravě. Záměrně nejsou tímto kritériem hodnocené styky uvnitř jednoho výlisku, osy a upevňovací uložení. Není to důkaz úplné absence všech kolizí ani ověření pohybu mechanismu.

```bash
node vystupy/kufriky/vytvor_doladene_tvary_v3.js
python3 vystupy/kufriky/sestav_nahled_v3.py
python3 vystupy/kufriky/over_doladeni_v3.py
python3 vystupy/kufriky/audit_kolizi_v3.py
node vystupy/kufriky/over_v3_katalogovym_parserem.js
node vystupy/kufriky/renderuj_porovnani_v3.js
node vystupy/kufriky/over_nahled_v3.js
```

Všechny tyto přípravy a kontroly jsou místní, bez DB, sítě a hesel. Síť používá pouze oddělený průzkum veřejným GET a přečtení hotového statického náhledu. Historické generátory v1/v2 nespouštět přes nový katalog: vrátily by modely na starší stav.

## Tabulka kontroly všech typů

| SKU | Typ | Fotografií | Vidím na snímcích | Opraveno | Stav shody / slabé místo |
|---|---|---:|---|---|---|
| 4932471064 | Nízký organizér | 6 | Nízké tělo, dvě západky, 10 vložek, šest obdélníkových polí spodního spojení. | Uchycení spon a držadla, okraj víka, spodní prvky uvnitř obálky. | Shoduje se hlavní uspořádání; rozdíly zůstávají v nekótovaných detailech. |
| 4932464082 | Organizér | 5 | 10 vyjímatelných vložek; červená pevná rukojeť mezi dvěma sponami. | Červený úchop s kotvením, propojení víka a prolisů. | Shoduje se hlavní uspořádání; rozdíly zůstávají v nekótovaných detailech. |
| 4932471065 | Kompaktní nízký organizér | 5 | Dvě západky po stranách úzkého čela, 5 vložek; čelo na kratší straně. | Dvě spony místo jedné, otočení čela na krátkou stranu, uchycení držadla. | Shoduje se hlavní uspořádání; rozdíly zůstávají v nekótovaných detailech. |
| 4932471723 | Kompaktní box na nářadí | 9 | Jedna široká spona na krátkém čele, horní výklopné držadlo, vnitřní dělič. | Šířka spony, správná orientace, horní držadlo s čepy a vnitřní dělič. | Shoduje se hlavní uspořádání; rozdíly zůstávají v nekótovaných detailech. |
| 4932471724 | Otevřená přepravka | 4 | Otevřená přepravka; boční otvory tvoří samotné stěny; vodorovná žebra. | Odstraněna nadbytečná přidaná držadla; žebra a spodní červený odjišťovací prvek. | Shoduje se hlavní uspořádání; rozdíly zůstávají v nekótovaných detailech. |
| 4932498323 | Organizér s výklopnými boxy | 12 | 8 menších + 2 větší výklopné nádoby, čelní rukojeť; v přepravě nádoby směrem vzhůru. | Rukojeť přesunuta na krátkou stěnu; nádoby, skutečná dutina, víčka a samostatné panty. | Shoduje se hlavní uspořádání; rozdíly zůstávají v nekótovaných detailech. |
| 4932478625 | Hluboký organizér | 10 | Tři úložné sloupce s červenými děliči a zadní dlouhá přihrádka; nejde o 10 červených vložek. | Odstraněno chybné uspořádání 10 vložek; nové přepážky podle otevřených snímků. | Shoduje se hlavní uspořádání; rozdíly zůstávají v nekótovaných detailech. |
| 4932480623 | Skříň s předními dvířky | 7 | Dvířka mají pant nahoře a vyklápějí se vzhůru. | Horní vodorovný pant a směr otevření; dveřní výztuhy, dolní uzávěr a kotvení. | Shoduje se hlavní uspořádání; rozdíly zůstávají v nekótovaných detailech. |
| 4932501784 / 4932478162 | Box na nářadí XL | 20 | XL má dvě přední spony, boční rukojeti a kovové rohové tyče. | Odstraněn obecný přední úchop; doplněny boční rukojeti a uložení tyčí. | Slabé místo: galerie nedokládá novou revizi SKU. |
| 4932499703 | Box pro elektrikáře | 1 | Výrobce ukazuje otevřený kufr s červenými rámy vnitřních panelů a kapsami. | Upraveny rámy a skutečně duté kapsy; vložka přestala být řadou plných kvádrů. | Slabé místo: chybí odlišné pohledy a doložení vložky. |
| 4932499704 | Box pro instalatéry | 1 | Výrobce ukazuje otevřený kufr s červenými rámy vnitřních panelů a kapsami. | Upraveny rámy a duté kapsy; rozdíl oproti elektrikářské variantě není doložen fotografiemi. | Slabé místo: chybí odlišné pohledy a doložení vložky. |
| 4932464078 | Pojízdný box s výsuvným držadlem | 28 | Dvě kola vzadu, teleskopické tyče na zadní straně, dvě čelní spony a boční držadla. | Kruhová kola 228 mm, skutečná osa a upevnění, zadní vedení madla, boční rukojeti. | Shoduje se hlavní uspořádání; rozdíly zůstávají v nekótovaných detailech. |
| 4932464079 | Velký box na nářadí | 6 | Výklopné držadlo nahoře, pevný čelní úchop a dvě spony; horní vložka. | Kotvení sklopeného držadla a výztuhy víka; držadlo se otevírá společně s víkem. | Shoduje se hlavní uspořádání; rozdíly zůstávají v nekótovaných detailech. |
| 4932464080 | Box na nářadí | 6 | Dvě čelní spony, pevný červený úchop a vnitřní vyjímatelné vložky. | Čelní úchop s kotvením, propojené vrstvy víka a spony. | Shoduje se hlavní uspořádání; rozdíly zůstávají v nekótovaných detailech. |
| 4932472129 | Box se 2 zásuvkami | 14 | Dvě zásuvky, červené přepážky, zajišťovací rám uchycený dole. | Kotvení rámu nahoře i dole; úchopy připojené k čelům, výška dutin zachována. | Shoduje se hlavní uspořádání; rozdíly zůstávají v nekótovaných detailech. |
| 4932472130 | Box se 3 zásuvkami | 14 | Tři zásuvky; červené přepážky a dolní kloub zajišťovacího rámu. | Kotvení rámu a úchopů; dutiny a mezery mezi čely bez škálování. | Shoduje se hlavní uspořádání; rozdíly zůstávají v nekótovaných detailech. |
| 4932493189 | Box se 4 zásuvkami | 11 | Čtyři čela, červené úchopy, dolní kloub a horní uzávěr rámu. | Kotvení čtyř úchopů, rámu a přepážek; zachované zdrojové dutiny. | Shoduje se hlavní uspořádání; rozdíly zůstávají v nekótovaných detailech. |
| 4932493190 | Box se zásuvkami 2 + 1 | 13 | Dvě nízké zásuvky nahoře, jedna vysoká dole. | Výšky dutin 61 / 61 / 130 mm, přepážky a kotvení zajišťovacího rámu. | Shoduje se hlavní uspořádání; rozdíly zůstávají v nekótovaných detailech. |
| 4932498651 | Pojízdný box s čelní zásuvkou | 13 | Jediná vysoká čelní zásuvka, horní uzávěr, kola vzadu a teleskopické madlo. | Dutina vysoká 400 mm, kruhová kola 228 mm, upevněné madlo a úchop; odstraněn rám víc zásuvek. | Slabé místo: rozpor vnějších rozměrů ve zdrojích. |
| 4932478161 | Pojízdná bedna na nářadí | 17 | Obě kola na jednom konci dlouhé bedny; osy podél kratší strany. Dvě horní stohovací pozice. | Opravená strana a osa kol; kruhový průměr 230 mm, uchycené boční madlo, dvě pole horních spojů. | Shoduje se hlavní uspořádání; rozdíly zůstávají v nekótovaných detailech. |

## Rozměrové výpočty v mm

Rozsah = maximum − minimum všech skutečných vrcholů. Bez posunu měřítka po osách.

| SKU | Výpočet X; Y; Z [mm] | Odchylka [mm] | Zdroj |
|---|---|---|---|
| 4932471723 | 124.5 − (-124.5) = 249; 205.5 − (-205.5) = 411; 165 − (-165) = 330 | 0.000000, 0.000000, 0.000000 | [rozměry](https://www.milwaukeetool.eu/en-eu/packout-boxes/packout-boxes/) |
| 4932471065 | 124.5 − (-124.5) = 249; 205.5 − (-205.5) = 411; 32 − (-32) = 64 | 0.000000, 0.000000, 0.000000 | [rozměry](https://www.milwaukeetool.eu/en-eu/packout-organisers/packout-organisers/) |
| 4932471724 | 194.5 − (-194.5) = 389; 237.5 − (-237.5) = 475; 125.5 − (-125.5) = 251 | 0.000000, 0.000000, 0.000000 | [rozměry](https://www.milwaukeetool.eu/en-eu/packout-crate/packout-crate/) |
| 4932471064 | 207 − (-207) = 414; 250 − (-250) = 500; 32 − (-32) = 64 | 0.000000, 0.000000, 0.000000 | [rozměry](https://www.milwaukeetool.eu/en-eu/packout-organisers/packout-organisers/) |
| 4932464082 | 193 − (-193) = 386; 250 − (-250) = 500; 58.5 − (-58.5) = 117 | 0.000000, 0.000000, 0.000000 | [rozměry](https://www.milwaukeetool.eu/en-eu/packout-organisers/packout-organisers/) |
| 4932498323 | 193 − (-193) = 386; 250 − (-250) = 500; 85 − (-85) = 170 | 0.000000, 0.000000, 0.000000 | [rozměry](https://www.milwaukeetool.eu/en-eu/packout-tip-bin-organiser/packout-tip-bin-organiser/) |
| 4932478625 | 193 − (-193) = 386; 253.5 − (-253.5) = 507; 89 − (-89) = 178 | 0.000000, 0.000000, 0.000000 | [rozměry](https://www.milwaukeetool.eu/en-eu/packout-organisers/packout-organisers/) |
| 4932480623 | 190.5 − (-190.5) = 381; 254 − (-254) = 508; 190.5 − (-190.5) = 381 | 0.000000, 0.000000, 0.000000 | [rozměry](https://www.milwaukeetool.eu/en-eu/packout-cabinet/packout-cabinet/) |
| 4932501784 | 197 − (-197) = 394; 277 − (-277) = 554; 211 − (-211) = 422 | 0.000000, 0.000000, 0.000000 | [rozměry](https://www.milwaukeetool.eu/en-eu/packout-boxes/packout-boxes/) |
| 4932478162 | 197 − (-197) = 394; 277 − (-277) = 554; 211 − (-211) = 422 | 0.000000, 0.000000, 0.000000 | [rozměry](https://www.milwaukeetool.eu/en-eu/packout-boxes/packout-boxes/) |
| 4932499703 | 205 − (-205) = 410; 280 − (-280) = 560; 82.5 − (-82.5) = 165 | 0.000000, 0.000000, 0.000000 | [rozměry](https://myloesch.com/de/milwaukee-koffer-fuer-elektriker-560-x-410-165-mm-packout-leer/90-9813) |
| 4932499704 | 205 − (-205) = 410; 280 − (-280) = 560; 82.5 − (-82.5) = 165 | 0.000000, 0.000000, 0.000000 | [rozměry](https://www.muellershop.ch/?artId=101138385&groupId=100040772&markid=MI4932499704&pg=det&srv=marken) |
| 4932464080 | 205.5 − (-205.5) = 411; 280.5 − (-280.5) = 561; 82.5 − (-82.5) = 165 | 0.000000, 0.000000, 0.000000 | [rozměry](https://www.milwaukeetool.eu/en-eu/packout-boxes/packout-boxes/) |
| 4932464078 | 236 − (-236) = 472; 280.5 − (-280.5) = 561; 265 − (-265) = 530 | 0.000000, 0.000000, 0.000000 | [rozměry](https://www.milwaukeetool.eu/en-eu/packout-trolley-box/packout-trolley-box/) |
| 4932464079 | 205.5 − (-205.5) = 411; 280.5 − (-280.5) = 561; 141 − (-141) = 282 | 0.000000, 0.000000, 0.000000 | [rozměry](https://www.milwaukeetool.eu/en-eu/packout-boxes/packout-boxes/) |
| 4932472129 | 207 − (-207) = 414; 282 − (-282) = 564; 181.5 − (-181.5) = 363 | 0.000000, 0.000000, 0.000000 | [rozměry](https://www.milwaukeetool.eu/en-eu/packout-drawer-tool-boxes/packout-drawer-tool-boxes/) |
| 4932472130 | 207 − (-207) = 414; 282 − (-282) = 564; 181.5 − (-181.5) = 363 | 0.000000, 0.000000, 0.000000 | [rozměry](https://www.milwaukeetool.eu/en-eu/packout-drawer-tool-boxes/packout-drawer-tool-boxes/) |
| 4932493189 | 207 − (-207) = 414; 282 − (-282) = 564; 181.5 − (-181.5) = 363 | 0.000000, 0.000000, 0.000000 | [rozměry](https://www.milwaukeetool.eu/en-eu/packout-drawer-tool-boxes/packout-drawer-tool-boxes/) |
| 4932493190 | 207 − (-207) = 414; 282 − (-282) = 564; 181.5 − (-181.5) = 363 | 0.000000, 0.000000, 0.000000 | [rozměry](https://www.milwaukeetool.eu/en-eu/packout-drawer-tool-boxes/packout-drawer-tool-boxes/) |
| 4932498651 | 240 − (-240) = 480; 305 − (-305) = 610; 275 − (-275) = 550 | 0.000000, 0.000000, 0.000000 | [rozměry](https://www.milwaukeetool.eu/en-eu/packout-rolling-drawer/packout-rolling-drawer/) |
| 4932478161 | 304.5 − (-304.5) = 609; 482.5 − (-482.5) = 965; 200.5 − (-200.5) = 401 | 0.000000, 0.000000, 0.000000 | [rozměry](https://www.milwaukeetool.eu/en-eu/packout-rolling-tool-chest/packout-rolling-tool-chest/) |

### Kola a známé dutiny

Bedna: D = 23 cm × 10 = 230 mm, R = 230 / 2 = 115 mm; skutečné vrcholy pneumatiky mají Y = 230 a Z = 230 mm. Pojízdný box a zásuvka: R = 228 / 2 = 114 mm; jejich skutečný rozsah X = 228 a Z = 228 mm. Osa kola bedny X, ostatních Y.

Zdrojové dutiny mají šířku a délku ověřenou jako součet prvních zásahů paprsků od středu k protilehlým stěnám. Výšku měří rozsah skutečné duté stěny:

| SKU | Komponenta | X: levá + pravá stěna [mm] | Y: přední + zadní stěna [mm] | Z: výška stěny [mm] |
|---|---|---:|---:|---:|
| 4932471723 | telo-duta-stena | 114.500 + 114.500 = 229.000 | 181.500 + 181.500 = 363.000 | 269.000 |
| 4932471065 | telo-duta-stena | 101.500 + 101.500 = 203.000 | 152.500 + 152.500 = 305.000 | 46.000 |
| 4932471064 | telo-duta-stena | 152.500 + 152.500 = 305.000 | 228.500 + 228.500 = 457.000 | 46.000 |
| 4932464082 | telo-duta-stena | 152.500 + 152.500 = 305.000 | 228.500 + 228.500 = 457.000 | 99.000 |
| 4932478625 | telo-duta-stena | 152.500 + 152.500 = 305.000 | 228.500 + 228.500 = 457.000 | 139.000 |
| 4932501784 | telo-duta-stena | 185.500 + 185.500 = 371.000 | 242.500 + 242.500 = 485.000 | 353.000 |
| 4932478162 | telo-duta-stena | 185.500 + 185.500 = 371.000 | 242.500 + 242.500 = 485.000 | 353.000 |
| 4932464080 | telo-duta-stena | 167.500 + 167.500 = 335.000 | 250.000 + 250.000 = 500.000 | 114.000 |
| 4932464078 | pojezdove-telo-duta-stena | 185.500 + 185.500 = 371.000 | 242.500 + 242.500 = 485.000 | 353.000 |
| 4932464079 | telo-duta-stena | 167.500 + 167.500 = 335.000 | 250.000 + 250.000 = 500.000 | 216.000 |
| 4932472129 | zasuvka-1-dute-steny | 159.000 + 159.000 = 318.000 | 207.000 + 207.000 = 414.000 | 127.000 |
| 4932472129 | zasuvka-0-dute-steny | 159.000 + 159.000 = 318.000 | 207.000 + 207.000 = 414.000 | 127.000 |
| 4932472130 | zasuvka-2-dute-steny | 159.000 + 159.000 = 318.000 | 207.000 + 207.000 = 414.000 | 76.000 |
| 4932472130 | zasuvka-1-dute-steny | 159.000 + 159.000 = 318.000 | 207.000 + 207.000 = 414.000 | 76.000 |
| 4932472130 | zasuvka-0-dute-steny | 159.000 + 159.000 = 318.000 | 207.000 + 207.000 = 414.000 | 76.000 |
| 4932493189 | zasuvka-3-dute-steny | 161.000 + 161.000 = 322.000 | 208.000 + 208.000 = 416.000 | 61.000 |
| 4932493189 | zasuvka-2-dute-steny | 161.000 + 161.000 = 322.000 | 208.000 + 208.000 = 416.000 | 61.000 |
| 4932493189 | zasuvka-1-dute-steny | 161.000 + 161.000 = 322.000 | 208.000 + 208.000 = 416.000 | 61.000 |
| 4932493189 | zasuvka-0-dute-steny | 161.000 + 161.000 = 322.000 | 208.000 + 208.000 = 416.000 | 61.000 |
| 4932493190 | zasuvka-2-dute-steny | 161.000 + 161.000 = 322.000 | 208.000 + 208.000 = 416.000 | 130.000 |
| 4932493190 | zasuvka-1-dute-steny | 161.000 + 161.000 = 322.000 | 208.000 + 208.000 = 416.000 | 61.000 |
| 4932493190 | zasuvka-0-dute-steny | 161.000 + 161.000 = 322.000 | 208.000 + 208.000 = 416.000 | 61.000 |
| 4932498651 | zasuvka-0-dute-steny | 165.000 + 165.000 = 330.000 | 215.000 + 215.000 = 430.000 | 400.000 |
| 4932478161 | pojezdove-telo-duta-stena | 247.500 + 247.500 = 495.000 | 412.500 + 412.500 = 825.000 | 305.000 |

## Uložení výsledků

- Aktuální GLB: `modely/`; zachované modely v2: `modely-v2/` a původní místní/veřejný náhled v2.
- Úplný katalog: `kufriky.json` a CSV; poznámky shody v poli `review`, odkazy na fotografie v `photo_sources`.
- Soukromé galerie a porovnání: `zdroje/doladeni-v3/`; veřejné vlastní rendery: `nahled-modely-v3/porovnani/`.
- Zprávy skutečné geometrie: `mereni-tvar-v3/`; nezávislé výsledky a snímky prohlížeče: `overeni-tvar-v3/`.

## Zbývá

Robert posoudí náhled v3. K potvrzení přesných nekótovaných detailů je potřeba měření kusu, kalibrovaný sken nebo licencovaný kótovaný CAD. Zapojení schválených modelů do živého katalogu provede vlastník. Produkční kód, služby a databáze nebyly změněné.

John.

Ověření prohlížeče: PASS; 20 typů, 0 chyb, 0 nepovolených požadavků.

Veřejné čtení: PASS; 94 statických souborů se shodným SHA-256.
