# Etapa 2: stav modelů kufříků

Autor: John, 5. 10. 2026. AGENTS.md včetně 4d a celé zadání včetně všech tří doplnění byly přečteny. Etapa 2 je autorizovaná přímo aktuálním zadáním.

**Požadované přesné modely výrobků: 0 z 20 hotových.** Rozměrové obálky jsou pomocný výstup, nikoli splnění požadavku na skutečný tvar. Neobsahují odhadnuté držadlo, víko, zámky, kola ani spoje.

Náhled: [3D podklady PACKOUT](https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v1/). Schválená tabulka etapy 1 zůstává beze změny.

## Vidím ve zdroji

Nově bylo běžným veřejným GET přečteno devět výrobních rodin. Podklady jsou v `zdroje/cad_etapa2/vyrobce.json`: všechny odpověděly 200; jednotlivé vnější rozměry z tabulky etapy 1 se nezměnily. Kontrola hledala odkazy na CAD v odkazech stránky a ověřila rozměrové tabulky. Nenalezení těchto odkazů není tvrzení o neexistenci CAD v jiné části webu. Profesní boxy mají stejně jako v etapě 1 pouze údaje prodejců; novou výrobní specifikaci pro ně tento průzkum nedoložil.

Veřejné hledání podle všech 20 typů je uložené v `zdroje/cad_hledani_etapa2.json`. Podmínky a rozhodnutí ke kandidátům jsou v `zdroje/cad_etapa2/pruzkum.json`. Licenci nepovažuji za ověřenou podle samotného označení „Free“. Nebyl stažen cizí CAD.

- [Sken na Sketchfabu](https://sketchfab.com/3d-models/milwaukee-packout-case-b0976f4ce0984eb89d1bfa402afb5bf7): veřejný index uvádí CC Attribution, ale SKU, verze licence a mm měřítko nejsou ověřeny. [Dokumentace platformy](https://sketchfab.com/developers/download-api/downloading-models) vyžaduje přihlášení pro download; přímé čtení modelu navíc vrátilo 403.
- [Velký box na GrabCAD](https://grabcad.com/library/milwaukee-packout-large-box-1) a [základna](https://grabcad.com/library/milwaukee-packout-1): čtení vrátilo 403, licence a download nemohly být ověřeny. Nevyvozuji z 403 nutnost registrace, ochranu neobcházím.
- [MakerWorld CAD files](https://makerworld.com/en/models/600550-milwaukee-packout-box-cad-files): čtení vrátilo 402; popis ve veřejném indexu se týká vnitřní vložky.
- [Přihrádky na GitHubu](https://github.com/electronsmith/Packout-Bin-STEP-Files): jsou to vnitřní díly, v přehledu bez doložené licence.
- [Vložky nízkého organizéru](https://www.printables.com/model/1067320-milwaukee-packout-slim-organiser-4932471064-bit-in): licence Public Domain uvedená ve veřejné stránce, ale obsah není celé tělo kufříku.
- [Přepravka FxhDesigns](https://www.printables.com/model/1263953-milwaukee-packout-crate): primární stránka nešla přečíst. Licence CC BY a popis příslušenství pocházejí pouze z indexu; přesnost vůči 4932471724 není ověřená.

Žádný účet, e-mail, formulář, nákup ani přihlášení nebyly použity. Kandidáty nelze prezentovat jako oficiální evropské modely.

## Vidím v kódu a v měření GLB

- `KOMPONENTY_EUROBOXY.md:67` popisuje místní délku na Y a výšku na Z. Skutečný `product_3788.glb` má obálku X × Y × Z = 299,000004 × 398,999985 × 119,999939 mm; `product_3794.glb` = 298,999998 × 398,999985 × 220,000031 mm. `Object_7.glb` má délku Y = 1000 mm. Katalogové soubory nebyly měněny.
- Použita tato konvence: X = Š, Y = L, Z = V, pravotočivá soustava, čísla přímo v mm. Jednotky GLB v tomto projektu nepřevádím na metry. Pro nový pomocný soubor jsem výslovně zvolil pivot ve středu obálky; netvrdím, že je to pivot všech původních katalogových souborů.
- Ve vieweru se jen pro zobrazení otáčí kolem X o −90°: (x, y, z) → (x, z, −y). Posun o V/2 nahoru položí obálku na Y = 0; v souboru GLB tato zobrazovací transformace uložená není.
- `vytvor_obalky.py` ponechává `model_file = null` a `model_status = chybi_presny_model`. Pomocný GLB je pod samostatným polem `envelope`, uvnitř nese `is_product_geometry = false`. CSV má samostatné sloupce pro obálku a chybějící geometrii.
- `over_modely.py` měří binární vrcholy všech primitiv všech aktivních meshů a uzlů, včetně transformací. Nespokojí se s accessor.min/max; prázdná nebo nečitelná geometrie je chyba. Ověřené jsou i testy proti vynechání druhého meshe, primitiva a rodičovské transformace.
- `over_modely_sdilenym_parserem.js` nezávisle měří stejných 21 souborů stávajícím katalogovým parserem. Rozsah: 20 typů, 21 SKU/GLB, 168 vrcholů a 252 trojúhelníků. Všechny tři osy souhlasí přesně s publikovanými čísly.

## Výpočty v mm

Pro každý typ: x ∈ [−Š/2, +Š/2], y ∈ [−L/2, +L/2], z ∈ [−V/2, +V/2]. Rozměr = maximum − minimum. Digitální tolerance porovnání je 0,01 mm. **Nejde o toleranci skutečného plastového výrobku**; ta zůstává null.

- Nízký organizér 4932471064: výrobce H × W × D = 64 × 500 × 414. L = max(500, 414) = 500; Š = min(500, 414) = 414; V = 64. X = ±414/2 = ±207, Y = ±500/2 = ±250, Z = ±64/2 = ±32. Obálka X × Y × Z = (207 − (−207)) × (250 − (−250)) × (32 − (−32)) = 414 × 500 × 64.
- Organizér 4932464082: H × W × D = 117 × 500 × 386. X = ±386/2 = ±193, Y = ±500/2 = ±250, Z = ±117/2 = ±58,5. Obálka = 386 × 500 × 117.

| Pořadí | Typ / SKU | L × Š × V | Poloviční rozsah X; Y; Z | Max. digitální odchylka | Zdroj |
|---|---|---:|---:|---:|---|
| 1 | Nízký organizér / 4932471064 | 500 × 414 × 64 | ±207; ±250; ±32 | 0 mm | [údaj](https://www.milwaukeetool.eu/en-eu/packout-organisers/packout-organisers/) (vyrobce) |
| 2 | Organizér / 4932464082 | 500 × 386 × 117 | ±193; ±250; ±58.5 | 0 mm | [údaj](https://www.milwaukeetool.eu/en-eu/packout-organisers/packout-organisers/) (vyrobce) |
| 3 | Kompaktní nízký organizér / 4932471065 | 411 × 249 × 64 | ±124.5; ±205.5; ±32 | 0 mm | [údaj](https://www.milwaukeetool.eu/en-eu/packout-organisers/packout-organisers/) (vyrobce) |
| 4 | Kompaktní box na nářadí / 4932471723 | 411 × 249 × 330 | ±124.5; ±205.5; ±165 | 0 mm | [údaj](https://www.milwaukeetool.eu/en-eu/packout-boxes/packout-boxes/) (vyrobce) |
| 5 | Otevřená přepravka / 4932471724 | 475 × 389 × 251 | ±194.5; ±237.5; ±125.5 | 0 mm | [údaj](https://www.milwaukeetool.eu/en-eu/packout-crate/packout-crate/) (vyrobce) |
| 6 | Organizér s výklopnými boxy / 4932498323 | 500 × 386 × 170 | ±193; ±250; ±85 | 0 mm | [údaj](https://www.milwaukeetool.eu/en-eu/packout-tip-bin-organiser/packout-tip-bin-organiser/) (vyrobce) |
| 7 | Hluboký organizér / 4932478625 | 507 × 386 × 178 | ±193; ±253.5; ±89 | 0 mm | [údaj](https://www.milwaukeetool.eu/en-eu/packout-organisers/packout-organisers/) (vyrobce) |
| 8 | Skříň s předními dvířky / 4932480623 | 508 × 381 × 381 | ±190.5; ±254; ±190.5 | 0 mm | [údaj](https://www.milwaukeetool.eu/en-eu/packout-cabinet/packout-cabinet/) (vyrobce) |
| 9 | Box na nářadí XL / 4932501784; 4932478162 | 554 × 394 × 422 | ±197; ±277; ±211 | 0 mm | [údaj](https://www.milwaukeetool.eu/en-eu/packout-boxes/packout-boxes/) (vyrobce) |
| 10 | Box pro elektrikáře / 4932499703 | 560 × 410 × 165 | ±205; ±280; ±82.5 | 0 mm | [údaj](https://myloesch.com/de/milwaukee-koffer-fuer-elektriker-560-x-410-165-mm-packout-leer/90-9813) (prodejce) |
| 11 | Box pro instalatéry / 4932499704 | 560 × 410 × 165 | ±205; ±280; ±82.5 | 0 mm | [údaj](https://www.muellershop.ch/?artId=101138385&groupId=100040772&markid=MI4932499704&pg=det&srv=marken) (prodejce) |
| 12 | Pojízdný box s výsuvným držadlem / 4932464078 | 561 × 472 × 530 | ±236; ±280.5; ±265 | 0 mm | [údaj](https://www.milwaukeetool.eu/en-eu/packout-trolley-box/packout-trolley-box/) (vyrobce) |
| 13 | Velký box na nářadí / 4932464079 | 561 × 411 × 282 | ±205.5; ±280.5; ±141 | 0 mm | [údaj](https://www.milwaukeetool.eu/en-eu/packout-boxes/packout-boxes/) (vyrobce) |
| 14 | Box na nářadí / 4932464080 | 561 × 411 × 165 | ±205.5; ±280.5; ±82.5 | 0 mm | [údaj](https://www.milwaukeetool.eu/en-eu/packout-boxes/packout-boxes/) (vyrobce) |
| 15 | Box se 2 zásuvkami / 4932472129 | 564 × 414 × 363 | ±207; ±282; ±181.5 | 0 mm | [údaj](https://www.milwaukeetool.eu/en-eu/packout-drawer-tool-boxes/packout-drawer-tool-boxes/) (vyrobce) |
| 16 | Box se 3 zásuvkami / 4932472130 | 564 × 414 × 363 | ±207; ±282; ±181.5 | 0 mm | [údaj](https://www.milwaukeetool.eu/en-eu/packout-drawer-tool-boxes/packout-drawer-tool-boxes/) (vyrobce) |
| 17 | Box se 4 zásuvkami / 4932493189 | 564 × 414 × 363 | ±207; ±282; ±181.5 | 0 mm | [údaj](https://www.milwaukeetool.eu/en-eu/packout-drawer-tool-boxes/packout-drawer-tool-boxes/) (vyrobce) |
| 18 | Box se zásuvkami 2 + 1 / 4932493190 | 564 × 414 × 363 | ±207; ±282; ±181.5 | 0 mm | [údaj](https://www.milwaukeetool.eu/en-eu/packout-drawer-tool-boxes/packout-drawer-tool-boxes/) (vyrobce) |
| 19 | Pojízdný box s čelní zásuvkou / 4932498651 | 610 × 480 × 550 | ±240; ±305; ±275 | 0 mm | [údaj](https://www.milwaukeetool.eu/en-eu/packout-rolling-drawer/packout-rolling-drawer/) (vyrobce) |
| 20 | Pojízdná bedna na nářadí / 4932478161 | 965 × 609 × 401 | ±304.5; ±482.5; ±200.5 | 0 mm | [údaj](https://www.milwaukeetool.eu/en-eu/packout-rolling-tool-chest/packout-rolling-tool-chest/) (vyrobce) |

## Rozhodnutí Johna k hranicím a rozporům

Domnívám se: bez CAD nebo měření nelze z rozměrů vnějšího kvádru a perspektivní fotografie jednoznačně určit tvar ani funkční drážky. Proto žádný pomocný soubor není povýšen na přesný model. Jde o omezení vstupů, nikoli o požadavek na další schválení práce.

- Přepravku a skříň ponechávám v rozsahu 20 typů jako pevné úložné díly z původní schválené tabulky. Nejsou vyřazené jen kvůli odlišnému způsobu otevírání.
- Kompaktní box 4932471723 a nízký kompaktní organizér 4932471065: současný výrobce má vodorovnou délku 411 > 400. Ponechávám v tabulce, ale staré/nepřesné údaje a nutnost měření zůstávají viditelné.
- XL: 4932501784 a 4932478162 zůstávají jeden tabulkový typ a dvě různé varianty/SKU. Vznikly dvě pomocné obálky, nikoli tvrzení konstrukční identity.
- Pojízdný zásuvkový box 4932498651: aktuální údaj 610 × 480 × 550 mm je znovu přečtený, ale starý katalog 570 × 480 × 665 mm nebyl vysvětlen. Přesný model nelze certifikovat bez potvrzení verze a polohy držadla.
- Profesní boxy 4932499703 a 4932499704: přebírám jen původní údaj prodejce 560 × 410 × 165 mm, přičemž zdroj není výrobce. Rozpor 560/561 mm u instalatérského boxu není zahlazený.
- Dalších 14 modulů systému zůstává v katalogu označeno mimo etapu 2 a bez modelu.

## Co přesně chybí

K dokončení kteréhokoli přesného modelu stačí dodat oprávněně použitelný úplný CAD / kalibrovaný 3D sken správného SKU, nebo kótovaný soubor měření všech povrchů a detailů. Konkrétní seznam pro každý typ je v `mereni/<SKU>.json`; souhrn v `mereni/prehled.csv`. Všechny zatím nezměřené hodnoty jsou null, nikdy pracovní odhad.

Nutné jsou skutečný obrys a průřezy těla, úkosy a poloměry; profil a souřadnice horních/spodních spojů PACKOUT; rozměry a polohy víka/čel, pantů, zámků a držadel; spodní opěrné plochy a u pojízdných typů kolečka, jejich osa a obálka držadla v určené poloze. U rozporů navíc revize SKU a potvrzené celkové rozměry. Samotná celková vnitřní délka neurčuje tloušťku stěny ani polohu dutiny.

## Ověření a reprodukce

```bash
python3 vystupy/kufriky/vytvor_obalky.py
python3 vystupy/kufriky/over_katalog.py
python3 vystupy/kufriky/over_modely.py
node vystupy/kufriky/over_modely_sdilenym_parserem.js
node vystupy/kufriky/over_nahled_modely.js
```

Generátor a kontroly jsou bez DB, internetu a přihlašovacích údajů. `pruzkum_cad.py` je zvláštní autorizovaný sběrač veřejných GET, nikoli test. Browser používá již dostupný místní Chromium a knihovny; všechny požadavky se ve zkoušce obslouží z disku.

Souhrny měření: `overeni-modely/obalky.json`, `sdileny-parser.json`, `prohlizec.json`; screenshoty `modely-desktop.png` a `modely-mobil.png`. Zveřejnění a HTTP 200 bude zvlášť doloženo v `overeni-modely/nahrani.json` a `verejny-get.json`.

Veřejný náhled má noindex, místní Three.js s MIT licencí, žádné CDN, účty, formuláře ani runtime dotazy na jiné služby. GLB jsou pro zobrazení vložené do místního data.js, takže je viewer nemusí načítat přes síť. Fotografie mají zdroj a jsou pouze původní interní miniatury výrobce; jejich volnou licenci netvrdím.

Zápis probíhal jen ve vlastní výstupní složce a v nové povolené náhledové podsložce. Nebyl měněn cizí kód, DB, služba ani živá produktová integrace.

John.
