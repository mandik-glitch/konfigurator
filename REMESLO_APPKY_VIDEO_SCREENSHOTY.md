# Video screenshoty appek pro řemeslníky

Navazuje na `REMESLO_APPKY_HLOUBKOVY_PRUZKUM.md`. Robert (2026-08-18):
appky si sám neinstaluje, takže místo toho procházíme dostupný VIDEO
materiál (hlavně YouTube demo/předváděcí/tutorial videa), z videí
děláme screenshoty konkrétních obrazovek appky a z těch popisujeme,
co appka reálně umí (UI, funkce, workflow) - ne jen odvozovat z popisů/
marketingových textů.

Screenshoty jsou uložené v `remeslo_appky_screenshots/<slug-appky>/`.
Konvence zápisu: nadpis `## botN (video) — App1, App2, ...`, pro
každou appku krátký úvod (kolik/jaká videa nalezena) + pro každý
uložený screenshot cesta k souboru a 2-4 věty co je na obrázku vidět.
Než připisuješ, přečti si aktuální konec souboru - píše do něj víc
botů souběžně.

**Metodika extrakce snímků (Robert, 2026-08-18, oprava k prvnímu
kolu):** extrahuj snímky z videa **min. každých 5 sekund**
(`ffmpeg -vf fps=1/5` nebo hustěji, NIKDY řidčeji) - první kolo u
delších videí použilo až 12,5s interval mezi snímky (`fps=0.08`),
což může ztratit "vlákno" (návaznost kroků) demonstrovaného postupu.
Hustší vzorkování NEMUSÍ znamenat víc uloženého místa - snímky
NEPOTŘEBUJÍ vysokou kvalitu/rozlišení (stačí zmenšit např.
`-vf "fps=1/5,scale=640:-1"` + přiměřená JPEG komprese `-q:v 5`) -
pak z husté sady snímků RUČNĚ vyber jen ty nejvýpovědnější k uložení
do repa (stejně jako doteď), ale výběr děláš z hustšího/úplnějšího
vzorku, ne z řídkého, kde mezi snímky mohl proběhnout důležitý krok
beze stopy.

---

## bot3 (video) — Buildary.Online, Faktury.co, Ř21, EasyZakázky

### Buildary.Online (id 16)

Nalezeno hodně relevantního videomateriálu na kanálu **Stavební
Deník** (First information systems, vydavatel appky) - 8+ videí
(založení účtu, přístup do programu, modul úkoly, podpis certifikátem,
mobilní appka pro stavební deník...). Stáhl jsem a projel 2 z nich:
"Buildary.online - Mobilní aplikace pro elektronický stavební deník"
(863s, mobilní appka) a "Buildary.online - modul ÚKOLY stavby -
seznámení" (547s, webové rozhraní).

**Důležité doplňující zjištění k dřívějšímu záznamu**: video je z
r. 2019 (datumy v UI: "duben, 2019", zápisy datované 02.04.2019) -
appka tedy existuje min. od 2019, ne nová. Skutečný obsah dennikových
zápisů potvrzuje, že jde o appku pro **VELKÉ stavební projekty**
(ukázkový projekt "201 - Most Myslík" = stavba mostu), ne pro malé
zakázky jednotlivého řemeslníka.

- `frame_01_prihlaseni.jpg` — přihlašovací obrazovka "FIRSTIS ACCOUNT"
  (appka běží pod účtem vydavatele First Information Systems, ne pod
  vlastní značkou Buildary), jednoduchý email+heslo formulář.
- `frame_02_kalendar.jpg` — výběr data v kalendáři (duben 2019) s
  barevnými tečkami u jednotlivých dnů (patrně indikace zápisů/
  událostí) - ukazuje standardní mobilní date-picker vzor.
- `frame_03_zaznam_denniku.jpg` — **nejdůležitější záběr**: detail
  zápisu stavebního deníku "201 - Most Myslík", 02.04.2019, s taby
  OSOBY/MECHANIZMY/MATERIÁLY/PRÁCE/DALŠÍ. Text popisuje přejímku
  zakrytých prací, kontrolu armatury dle projektové dokumentace,
  "Nečekaná zjištění" sekci (podemletí základů), přiložené fotky ze
  stavby. Potvrzuje appku jako plnohodnotný elektronický stavební
  deník ve smyslu stavebního zákona (strukturované povinné náležitosti
  zápisu), ne obecný "poznámkový" nástroj pro řemeslníky.
- `frame_04_podpis_certifikat.jpg` — nastavení elektronického podpisu
  zápisů: přepínač "Podepisovat v Buildary", volba mezi vlastním
  kvalifikovaným certifikátem (doporučeno pro deník vedený dle zákona)
  nebo certifikátem Buildary (pro nezákonné/subdodavatelské deníky).
  Ukazuje, že appka řeší legislativně závazné elektronické podepisování
  - funkce, kterou obecné "řemeslnické" appky (Kalendo/Timoty/Logeto)
  vůbec neřeší.
- `frame_05_web_seznam_staveb.jpg` — WEBOVÉ rozhraní (ne jen mobilní
  appka): tabulka "Seznam staveb" se sloupci Stavba/Investor/Stav/GPS
  souřadnice - potvrzuje multi-projektový enterprise nástroj pro
  správu více staveb najednou, ne appku na jednu zakázku.
- `frame_06_web_novy_ukol.jpg` — webový formulář "Nový úkol": název,
  kategorie, datum zahájení/ukončení, stav (např. "Nezahájeno"),
  priorita, řešitel, "Části stavby", místo, mapa, přílohy foto/video.
  Strukturovaně bohatší než úkolové systémy v appkách jako Kalendo.

**Syntéza (doplnění k předchozímu kolu)**: video jednoznačně potvrzuje
dřívější odhad, že Buildary.Online je nástroj pro elektronické
stavební deníky u VELKÝCH stavebních projektů (mosty, pozemní stavby s
GPS-trackovanými lokacemi, legislativně podepisované zápisy) -
funkčně i cílovkou zásadně jiná appka než zbytek `full_workflow_cz`
kategorie (drobný řemeslník/OSVČ). Doporučení zůstává: vyřadit ze
srovnávače nebo přeřadit do samostatné kategorie "stavební deníky/
enterprise", ne srovnávat 1:1 s appkami pro jednotlivce.

### Faktury.co (id 23)

Cíleně hledáno i v polštině ("faktury.co aplikacja Kajetan Dudczak")
i česky - **ŽÁDNÉ video nenalezeno** vůbec, ani anglicky/polsky. Jediné
YouTube výsledky na dotaz "Faktury.co" jsou nesouvisející appky
(mPohoda, súčto, Fakturace.cz, FakturaOnline) a jeden 9s klip
"FAKTURY.CO" od kanálu "FAKTURY", který se nepodařilo stáhnout
(YouTube error, pravděpodobně nedostupné/smazané video) - i kdyby šel
stáhnout, 9 vteřin nemůže být použitelné demo. Nulová video stopa dál
potvrzuje dřívější zjištění, že jde o malou appku (pravděpodobně
polskou, viz předchozí kolo) bez marketingové/demo prezentace v ČR.

### Ř21 (id 31)

Hledáno "R21 remeslnici aplikace" a varianty - **žádné výsledky**.
Potvrzuje dřívější zjištění o mrtvé/neexistující doméně - appka nemá
ani žádnou video stopu, což je konzistentní s tím, že produkt
pravděpodobně vůbec reálně nefunguje/nebyl nikdy plně spuštěn.

### EasyZakázky (id 32)

Hledáno "EasyZakazky aplikace" a varianty - **žádné výsledky**.
Stejně jako Ř21: potvrzuje dřívější zjištění o nefunkčním
placeholder webu, appka nemá žádnou video prezentaci.

**Zdroje**: YouTube (kanál Stavební Deník / First information
systems - videa P2kJQEiDRV8, FGiAZeF_DZI a dalších 6 nalezených, ale
nestahovaných), `yt-dlp ytsearch` dotazy pro Faktury.co/Ř21/
EasyZakázky (bez užitečných výsledků).

---

## bot11 (video) — PROFIDAT, Řemeslník PRO, iDoklad, SuperFaktura, Buildo

Metoda: `yt-dlp ytsearch10:"..."` pro rychlý přehled kandidátů
(`--dump-json --flat-playlist`), stažení vybraných videí
(`player_client=android` extractor-args - výchozí klient dostával
HTTP 403), `ffmpeg fps=` extrakce snímků v adaptivním intervalu podle
délky videa (0,33 fps u krátkých ~30-80s videí, 0,08 fps u
13minutového iDoklad videa), kontaktní sheet (`ffmpeg tile=`) pro
rychlý vizuální výběr bez nutnosti prohlížet každý snímek zvlášť,
ruční výběr nejvýpovědnějších snímků, video soubory smazány po
extrakci.

### PROFIDAT (id není v `remeslo_workflow_apps` - PROFIDAT byl
`not_found_on_stores`, viz `REMESLO_PRUZKUM_WORKFLOW_APPS.md` část C)

Nalezen vlastní YouTube kanál appky ("PROFIDAT | Evidence zakázek") se
3 krátkými instruktážními videi (registrace, evidence zakázky bez
papírů). Stažena a projeta 2: "Jak se zaregistrovat do PROFIDAT" (45s)
a "Jak evidovat zakázku bez papírů" (77s, mobilní appka → web app).

- `profidat/frame_01_dashboard.jpg` — Dashboard: KPI karty "Dokončené
  zakázky", "Celkový zisk", "Nejlepší den v týdnu", graf "Přehled
  výkonu" (plocha pod křivkou), "Průměrný zisk/hod", "Průměrná marže"
  - **vizuálně přesně potvrzuje** dřívější textový rozbor finančního
  dashboardu z `REMESLO_PRUZKUM_WORKFLOW_APPS.md` části C (zisk→marže→
  Kč/hod). Vpravo nahoře viditelný tarif "BASIC".
- `profidat/frame_02_platformy.jpg` — sekce "Jak začít s PROFIDAT":
  3 sloupce Android/iPhone-iPad/Počítač. **Potvrzuje** dřívější
  zjištění "Android teď, iOS později" - u iPhone/iPad sloupce doslova
  "Používejte webovou aplikaci (zatím)... iOS aplikace bude dostupná
  později".
- `profidat/frame_03_detail_zakazky_limity.jpg` — **nové zjištění,
  nebylo v textovém průzkumu**: modal "Detail zakázky" s tarifním
  štítkem "STANDARD" a KONKRÉTNÍMI limity vázanými na tarif: "Fotky:
  1/300 (standard)", "Přílohy: 0/50 (standard)" - dřívější rozbor
  uváděl ceník jako "nedohledatelný zvenčí", tohle jsou první reálně
  zjištěné konkrétní limity STANDARD tarifu. Dál vidět sekce "Průběh
  zakázky" (work-log počítadla) a PDF výstupy (Průběžný/Závěrečný
  protokol) - přesně jak popsáno v dřívějším rozboru.

### Řemeslník PRO (elhacom.cz)

**Žádné použitelné video nenalezeno** - 3 nezávislé pokusy s různými
dotazy ("Řemeslník PRO elhacom aplikace", "remeslnikpro.cz",
"Řemeslník PRO app", "elhacom Řemeslník PRO evidence", "\"Řemeslník
PRO\" aplikace zakázky") vrátily buď 0 výsledků, nebo úplně
nesouvisející appky (jiné řemeslnické appky jako Fachman/Službař/
FLOWii/NejŘemeslníci, popř. obecné stavební appky). Potvrzuje dřívější
zjištění ("žádný store listing") - appka evidentně nemá ani žádnou
video prezentaci, konzistentní s obrazem malého/indie produktu.

### iDoklad (id=18)

Vlastní YouTube kanál "iDoklad - online fakturace" s velkým množstvím
videí. Staženy 2: "Mobilní aplikace iDoklad" (13 min, kompletní tour
STARŠÍ tmavé verze appky) a "Tipy na ovládání mobilní aplikace" (2 min,
NOVĚJŠÍ fialová redesignovaná verze - appka evidentně prošla mezi
natočením videí vizuálním redesignem).

- `idoklad/frame_01_dashboard.jpg` — Dashboard: přepínač Měsíce/
  Kvartály/Roky, částka "31 500,00 Kč", 2 donut grafy "Vydané faktury"
  (100 %) / "Přijaté faktury" (0 %) s rozpadem Nezaplaceno/Uhrazeno,
  sloupcový graf "Fakturace za období" po měsících, přepínač "s DPH".
- `idoklad/frame_02_ares_autocomplete.jpg` — "Nový kontakt", psaní
  "Solitea" do vyhledávání spouští ŽIVÝ ARES autocomplete se 2 nabídkami
  firem vč. IČ (Solitea BI Experts s.r.o. IČ 28263901, Solitea Business
  Solutions s.r.o.) - potvrzuje přímou integraci na český registr firem
  přímo v mobilní appce, ne jen na webu.
- `idoklad/frame_03_nova_faktura.jpg` — rozpracovaná "Nová faktura":
  odběratel, hlavička (datum vystavení, "Zobrazit více"), sleva,
  položka "Tiskárna" 3,00 × 4 500,00 Kč = 13 500 Kč (11 157,02 Kč bez
  DPH) - ukazuje výpočet DPH v reálném čase při editaci.
- `idoklad/frame_04_seznam_faktur.jpg` — "Faktury vydané": filtry
  Všechny/Uhrazené/Neuhrazené/Po splatnosti, seznam seskupený podle dne
  (Dnes/Včera) s číslem faktury, klientem, částkou a barevným štítkem
  stavu.
- `idoklad/frame_05_nastaveni_banka_nova_verze.jpg` — z NOVĚJŠÍHO
  redesignu appky: "Nastavení - Banka", "Nový bankovní účet", přepínač
  "Párování bankovních pohybů" (automatické spárování plateb) a
  vyhrazený "Bankovní e-mail" pro přeposílání výpisů - konkrétní
  implementace automatického bankovního párování zmíněného jen obecně
  v dřívějším textovém průzkumu.

### SuperFaktura (id=19)

Vlastní YouTube kanál "SuperFaktura.cz" s krátkými demo videi po
funkcích. Staženy 2: "Pravidelné faktury" (165s) a "Odeslání faktury
emailem nebo poštou" (144s) - obě webové rozhraní (desktop), ne
mobilní appka.

- `superfaktura/frame_01_pravidelna_faktura_menu.jpg` — plné hlavní
  menu appky viditelné: Přehled/Faktury/Náklady/Kontakty/Nástroje,
  podzáložky Faktury/Zálohové faktury/Dodací listy/Přijaté objednávky/
  Cenové nabídky/Pravidelné/Dobropisy/Koncepty - **výrazně širší
  funkční záběr, než uváděl dřívější textový popis** (dodací listy,
  přijaté objednávky navíc). Formulář "Nová pravidelná faktura":
  periodicita (Měsíčně), "Vystavit vždy poslední den v měsíci",
  "Opakovat neomezeně", volba jazyka dokumentu (vlajka), auto-odeslání
  e-mailem/poštou po vystavení.
- `superfaktura/frame_02_seznam_faktur_stavy.jpg` — seznam faktur s
  6 STAVY (barevný piktogram-legenda dole): Uhrazené/Neuhrazené/Po
  splatnosti/Přeplacené/Částečně uhrazené/Nebudou uhrazeny - jemnější
  rozlišení stavu platby, než jednoduché placeno/neplaceno. Souhrnný
  panel "2 doklady, 70 000 Kč, Zbývá uhradit 35 000 Kč".
- `superfaktura/frame_03_odeslani_emailem.jpg` — modal odeslání
  faktury e-mailem: přednastavený text zprávy (pozdrav, částka,
  variabilní symbol, číslo účtu), příloha PDF, možnost skryté kopie a
  kopie na vlastní e-mail.
- `superfaktura/frame_04_odeslani_postou_znamky.jpg` — **nové
  zjištění, nebylo v textovém průzkumu**: appka nabízí odeslání faktury
  FYZICKOU POŠTOU zákazníkům bez e-mailu, přes placené "poštovní
  známky" ("Počet zbývajících poštovních známek je 0", tlačítko "Koupit
  poštovní známky") - spotřební kredit systém, žádná jiná appka ze
  všech dosud zkoumaných tohle nemá. Seznam odeslaných dokumentů se
  stavy Odeslané/Zpracovává se/Zamítnuté.

### Buildo (id=15)

Vlastní YouTube kanál "Buildo - site diary" (jen 13 sledujících) se
6 krátkými reklamními videi (16-59s, jazykové mutace CZ/SK/PL/EN).
Staženy 2 nejdelší: slovenská verze "Buildo - Stavebný denník do
vrecka monteriek" (59s, čitelné UI záběry) a anglická "Site diary in
your pocket" (32s, převážně živá akce/B-roll, telefon v ruce příliš
rozostřený/malý na čitelné UI - nepoužito jako screenshot).

- `buildo/frame_01_stroje_checklist.jpg` — "Upraviť stavbu", sekce
  "STROJE" (checklist strojů/nářadí na stavbě - příklepová vrtačka ✓,
  klincovačka, vrtačka ✓) - ukazuje evidenci vybavení/mechanizace per
  stavba, funkce, kterou PROFIDAT/iDoklad/SuperFaktura nemají.
- `buildo/frame_02_material_detail.jpg` — "Detail záznamu", sekce
  "MATERIÁL": položka "zámková dlažba", množství "9,0 paleta", cena
  "300,00 €", přiložená fotka materiálu s ikonami smazat/foto/upravit -
  konkrétní potvrzení sledování materiálu s množstvím+cenou+fotkou
  (na rozdíl od PROFIDATu, který má jen jedno souhrnné číslo "náklady").

**Syntéza (za celé kolo bot11 (video))**: screenshoty ve všech 4
appkách s dostupným videem POTVRDILY dřívější textová zjištění (žádná
appka se vizuálně neukázala jinak, než popisoval text) a ve 3
případech přidaly KONKRÉTNÍ detail, který textový průzkum nedokázal
zjistit zvenčí (PROFIDAT STANDARD limity 300 fotek/50 příloh,
SuperFaktura fyzické odesílání poštou přes placené známky, iDoklad
živá ARES integrace + novější fialový redesign UI). Řemeslník PRO
zůstává appkou zcela bez veřejné video stopy - v kombinaci s
`not_found_on_stores` posiluje obraz malého/indie produktu s minimální
marketingovou přítomností.

**Zdroje**: YouTube kanály "PROFIDAT | Evidence zakázek", "iDoklad -
online fakturace", "SuperFaktura.cz", "Buildo - site diary" (vlastní
kanály appek), `yt-dlp ytsearch` dotazy pro Řemeslník PRO (bez
užitečných výsledků, 5 nezávislých variant dotazu).

---

## bot8 (video) — Kalendo, Timoty, Logeto, BitFaktura, DílnaTech

Metoda: `yt-dlp ytsearch` pro obecné dotazy + přímé procházení
vlastních YouTube kanálů appek (`https://www.youtube.com/@handle/videos
--flat-playlist`) tam, kde kanál existuje (rychlejší a přesnější než
fulltextové hledání). Stažení `-f 'bv*[height<=720]+ba/b[height<=720]'
--extractor-args "youtube:player_client=android"` (výchozí klient
dostával HTTP 403, stejný problém jako u bota11). `ffmpeg fps=1/8` až
`fps=1/2` extrakce podle délky videa, kontaktní sheet (`ffmpeg tile=`)
pro rychlý výběr, ruční výběr nejvýpovědnějších snímků, video soubory
smazány po extrakci.

### Kalendo (kalendo.cz)

**Žádné použitelné video nenalezeno.** 9 nezávislých dotazů/pokusů
("Kalendo appka predstaveni", "Kalendo appka", "Kalendo cz appka",
"Kalendo remeslnik", "Kalendo.cz", "Kalendo aplikace zakazky",
"Kalendo aplikace pro zivnostniky", vlastní kanál `@kalendo_cz`
neexistuje/nemá videa, "David Mareš Kalendo") - všechny buď 0 výsledků,
nebo jen nesouvisející hity (rumunská popová píseň "Lendo Calendo",
malajsijské cestovatelské video "Moknia Kalendo"). Konzistentní s
dřívějším hloubkovým průzkumem (`REMESLO_APPKY_HLOUBKOVY_PRUZKUM.md`)
- appka má aktivní Instagram/blog/status stránku, ale žádnou YouTube
přítomnost. Appka je navíc ovládaná primárně přes Google kalendář
(hashtagové příkazy) - i kdyby video existovalo, nejzajímavější UI by
bylo v cizí appce (Google Kalendář), ne ve vlastním rozhraní appky.

### Timoty (timoty.cz)

Vlastní YouTube kanál (`@timotycz9294`) s desítkami krátkých
release-note videí ("Timoty X.XX.0 | ...") - na rozdíl od většiny
appek v tomhle průzkumu má Timoty NEJBOHATŠÍ video materiál ze všech
5 mých appek, protože každá verze appky dostává vlastní krátké demo
nové funkce (živé UI, ne animovaná grafika). Stažena a projeta 2:
"Timoty 2.36.0 | Práce = Zakázka, ziskovost a další nové funkce na
webu i mobilu" (671s) a "Timoty 2.35.0 | Výkazy práce v mobilu a nové
možnosti filtrování" (549s).

- `timoty/frame_01_nova_zakazka.jpg` — formulář "Nová zakázka" (web):
  název, popis, přepínač Firemní/Osobní klient, kontaktní údaje
  (jméno, země, telefon, e-mail), tlačítka "Přidat kontaktní osobu" /
  "Vytvořit" / "Vytvořit a naplánovat".
- `timoty/frame_02_detail_zakazky_mobil_navstevy.jpg` — vlevo detail
  zakázky na webu (stavy Hotovo/Uzavřeno/Vyfakturováno/Zaplaceno,
  cena/náklady/zisk s % marží, kalendář návštěv), vpravo mobilní
  appka se stejnou zakázkou v seznamu "Návštěvy - Tento týden" - **live
  synchronizace web↔mobil** stejných dat viditelná v jednom záběru.
- `timoty/frame_03_opravneni_navstevy_modal.jpg` — modal "Oprávnění"
  u konkrétní návštěvy: granulární přepínače ("Může být zodpovědnou
  osobou za návštěvu", "Může změnit pouze stav vlastní návštěvy",
  "Může změnit stav návštěvy všem pracovníkům", "Může odstranit
  všechny návštěvy zakázky") - oprávnění se dají nastavit i na úrovni
  JEDNÉ návštěvy, ne jen globálně na roli.
- `timoty/frame_04_pracovnik_opravneni_profil.jpg` — profil
  pracovníka "Martin Kryl", záložka "Oprávnění": žlutě zvýrazněné
  upozornění "Martin má vlastní práva oproti roli Pracovník" +
  tlačítko "Obnovit oprávnění" (reset na roli), seznam kategorií
  (Společnost/Zakázky a návštěvy/Klienti/Pracovníci/Výkazy práce/
  Formuláře) s ikonami oko-škrtnuté/tužka pro každou.
- `timoty/frame_05_vykaz_prace_dashboard.jpg` — "Výkazy práce" dashbord
  (web i mobil): sloupcový graf odpracovaných hodin po měsících,
  přepínač h/km/Kč, souhrn "Celkem/Čeká na schválení/Hotovo/
  Probíhá/Na cestě/Naplánováno", detail konkrétního dne s časem,
  km a Kč u jména pracovníka.
- `timoty/frame_06_navsteva_stavy_naklady_ztrata.jpg` — detail
  návštěvy "Úklid po malování - Belgická": vizuální pipeline stavů
  (Naplánováno → Na cestě → Probíhá → Hotovo), řádek Cena/Náklady/
  **Ztráta (v %)** (0 Kč cena - 1420 Kč náklady = 1420 Kč ztráta,
  červeně) a seznam pracovníků s jejich odpracovaným časem a
  vyčíslenou Kč částkou u každého zvlášť.
- `timoty/frame_07_opravneni_roli_matice.jpg` — "Oprávnění rolí":
  taby Majitel/Manažer/Vedoucí pracovníků/Pracovník, pod nimi matice
  kategorií (Formuláře/Služby-Produkty-Materiály/Přílohy/Protokoly/
  Výstupní dokumenty/Mobilní aplikace) s ikonami zobrazit/upravit/
  smazat + speciální práva ("Může vypsat", "Zobrazit ceny", "Zobrazit
  náklady") - výrazně granulárnější RBAC systém, než mají ostatní
  appky v celém srovnávači (žádná appka zkoumaná dosud bot3/bot11
  nemá 4-úrovňovou maticovou správu oprávnění).

**Syntéza**: video jednoznačně potvrzuje a rozšiřuje textový popis
("plánování/kalendář, GPS, elektronické zápisy s podpisem, evidence
materiálu, přehled ziskovosti") - navíc odhaluje detail, který
textový průzkum nezachytil: propracovaný VÍCEÚROVŇOVÝ systém oprávnění
(role → uživatel → jednotlivá návštěva), který jde nad rámec
jednoduchého "kdo vidí co" u ostatních appek v kategorii.

### Logeto / Výkaz práce (vykazprace.cz)

Vlastní kanál `@vykazprace71` MÁ video (91s, "Výkaz práce - Snadná
evidence práce a docházky"), stáhnul jsem a projel ho - **ale je to
čistě animovaný marketingový spot (kreslené postavičky u stolu,
dodávka na stavbě, tablet v ruce), NE záznam skutečného UI appky.**
Drobné mockupy obrazovek uvnitř animace ("PODKLADY PRO MZDY",
"DOCHÁZKOVÝ LIST", kalendářová mřížka) jsou stylizované ilustrace, ne
čitelné reálné UI - nepoužitelné jako "screenshot appky" ve smyslu
zadání (Robert chce vidět, co appka REÁLNĚ umí). Slovenský sesterský
kanál `@vykazpracesk7810` má jen 7-8s reklamní klipy se stejným
animovaným stylem. Zkusil jsem navíc 3 další dotazy ("Výkaz práce
aplikace návod ukázka", "vykazprace.cz webinar", "Logeto time
tracking demo") - žádný trefil skutečný produkt appky (jen
nesouvisející konkurenční nástroje typu Aktion CLOUD/Atollon/CAFLOU/
Frekr/Evolio). **Závěr: appka má YouTube přítomnost, ale žádné
použitelné demo se skutečným UI - potvrzuje/rozšiřuje dřívější nález
bota12 ("obsah nedohledán, cookie-wall") o to, že i po stažení videa
je obsah nepoužitelný, ne jen nedostupný.**

### BitFaktura (bitfaktura.cz)

**Oprava dřívějšího zjištění** (`REMESLO_APPKY_HLOUBKOVY_PRUZKUM.md`
tvrdil "žádný český demo kanál nenalezen") - existuje reálný český
obsah, jen ne pod vlastním pojmenovaným kanálem, ale dohledatelný
přes `ytsearch`: "Jak vystavit fakturu online - BitFaktura návod |
Fakturační program zdarma" (84s) a "OCR za pár sekund | BitFaktura.cz"
(51s), oba se skutečným záznamem obrazovky (ne animace, ne cizí
jazyk). Stažena a projeta obě.

- `bitfaktura/frame_01_odberatel_dic_autocomplete.jpg` — formulář
  nové faktury: pole "Odběratel" s live vyhledáváním, dropdown nabízí
  6 firem s DIČ podle napsaného textu ("Abc" → ABC s.r.o., AB CDE
  s.r.o. ...) - stejný princip jako ARES autocomplete u jiných appek
  (iDoklad), i když tady nejde vyloženě o živé ARES demo, spíš
  interní databázi kontaktů appky.
- `bitfaktura/frame_02_detail_faktury_menu.jpg` — plné horní menu
  appky (Příjmy/Výdaje/Zákazníci/Sklad/Platby/Reporty) + náhled
  faktury s akcemi Zpět/Odeslat/Tisk/Export/Více možností/Skladové
  dokumenty - potvrzuje, že appka má i skladový modul integrovaný v
  hlavní navigaci (zmíněno v textovém průzkumu jako `/skladovy-
  program`, tady vizuálně potvrzeno přímo v UI).
- `bitfaktura/frame_03_ocr_nacteni_faktury_ares.jpg` — **klíčový
  záběr z OCR videa**: reálná načtená faktura od Alza.cz vlevo (sken/
  PDF), vpravo automaticky vyplněný formulář nákladové faktury -
  Dodavatel, DIČ, adresa, IČ, banka, i jednotlivé položky (Cartridge
  HP...) s cenou/DPH/množstvím, tlačítko "Načíst údaje z ARES" -
  živá ukázka OCR+ARES kombinace zmíněné jen v ceníku appky
  (`bitfaktura.cz/cenik`), tady vizuálně doložená v akci.

**Syntéza**: video vyvrací dřívější "nulová YouTube stopa" - appka MÁ
krátká, věcná česká demo videa s reálným záznamem obrazovky (ne jen
propagační animace jako Logeto), byť ne na vlastním brandovaném
kanálu. Potvrzuje textový popis (skladový program, OCR/ARES) a přidává
konkrétní vizuální detail (Alza.cz faktura jako reálný testovací
příklad OCR přesnosti).

### DílnaTech (dilnatech.cz)

**Žádné použitelné video nenalezeno.** 5 nezávislých dotazů
("DilnaTech.cz aplikace", "Dílna Tech autoservis appka", "ErokoTech
DilnaTech", "dilnatech.cz autoservis", "\"DílnaTech\" software") -
buď 0 výsledků, nebo nesouvisející auto-opravárenské YouTube video
(Tech Tip Degreasing, Fifth Gear apod., trefené jen shodou slova
"tech"/auto tématem). Potvrzuje dřívější zjištění bota3
(`REMESLO_APPKY_HLOUBKOVY_PRUZKUM.md`: "Demo/JS, YouTube, fóra: nic
nenalezeno") - appka nemá žádnou video prezentaci, konzistentní s
obrazem malého/nového hráče (vydavatel ErokoTech je obecné vývojářské
studio, DílnaTech jen jeden z ~8 různorodých portfolio projektů).

**Souhrn (bot8)**: 2 appky s použitelným reálným UI videem (Timoty -
bohatě, 7 screenshotů ze 2 videí; BitFaktura - 3 screenshoty ze 2
videí), 1 appka s YouTube přítomností, ale nepoužitelným obsahem
(Logeto/Výkaz práce - čistě animovaný spot), 2 appky zcela bez video
stopy (Kalendo, DílnaTech).

**Zdroje**: YouTube kanály `@timotycz9294` (Timoty), `@vykazprace71` +
`@vykazpracesk7810` (Výkaz práce/Logeto), `ytsearch` dotazy pro
BitFaktura (bez vlastního brandovaného kanálu, ale reálný obsah
dohledán fulltextově), `ytsearch` dotazy pro Kalendo/DílnaTech (bez
užitečných výsledků, 9, resp. 5 nezávislých variant dotazu).
