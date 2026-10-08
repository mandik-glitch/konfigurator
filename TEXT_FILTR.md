# Filtr pro popisné texty (storefronty + hlavní kategorie + stránky kategorií)

Vyčleněno z `WORKFLOW.md` bodu 21 (bot20, 2026-09-05, Robert přes
bot3/toscanaccio-7f) - **obsah pravidel se tímhle vyčleněním nemění**,
mění se jen umístění. Důvod vyčlenění a co zůstává ve `WORKFLOW.md`
místo něj viz tam (bod 21 je teď krátký ukazatel sem, ne smazaný).

**ŽIVÝ dokument** - doplňuj nová pravidla, jak se najdou další vzorce
chyb (stejný vzor jako `AGENTS_LOG.md` zápis + `api/qa_checks.py`
kontrola, ne jen jednorázová oprava jedné věty).

**Robert, 2026-09-17: tenhle soubor je zatím jen rychlá záplata, ne
kompletní/finální sada pravidel** - "skoro nic neobsahuje". Neber
dosavadní obsah jako vyčerpávající - u nejasného případu se ptát, ne
předpokládat, že když tu chybějící situace není výslovně vyjmenovaná,
je automaticky v pořádku.

## Rozsah (na co se filtr vztahuje)

Původně jen Fiat mini-eshopy, **rozšířeno 2026-09-05 (Robert) i na
hlavní kategorie konfigurátoru**, **téhož dne dál rozšířeno (Robert,
přes bot3) i na `content_pages`** (viditelný text stránky kategorie -
viz níže, proč šlo dřív o vědomě zapsanou mezeru, ne přehlédnutí):

- `car_storefronts` / `car_storefront_models` (`hero_title`,
  `hero_text`, `meta_title`, `meta_description`, `variant_description`)
  - fiat-autovestavby.top a budoucí obdobné domény.
- `content_categories` (`meta_title`, `meta_description`, `nav_label`)
  - hlavní kategorie konfigurátoru (autovestavby.logiman.cz, dřív
    vandrawee.cz - doména změněna 2026-09-06, viz AGENTS_LOG.md).
- `content_pages` (`intro_html`, `body_html`, `bottom_body_html`,
  navázané na kategorii přes `category_id`) - **stejná pravidla jako
  `content_categories`**, jde o texty stejné stránky (meta vs. viditelný
  obsah), jen jiný sloupec/tabulka. Bez vlastní automatické kontroly
  zatím (`api/qa_checks.py::_category_text_fields()` čte jen
  `content_categories` - rozšíření na `content_pages` je otevřený úkol,
  ne provedené - do té doby jen ruční review, stejně jako pravidla
  3/6/7/8/9/9a u obou tabulek výš).
- `shop_products` (`name`, `short_description`, `description`,
  `meta_title`, `meta_description`) - **doplněno 2026-09-12 (bot5, se
  souhlasem bot3)**. Není to rozšíření rozsahu, jen dopsání toho, co už
  platilo: pravidlo 10 níž vzniklo přímo nad textem produktové karty
  3942 a Robert 2026-09-11 ho označil za obecné pro VŠECHNY produktové
  texty, ne jen pro tu kartu - jenže v tomhle seznamu `shop_products`
  chybělo, takže si toho bot píšící text karty nemusel všimnout. Stejná
  mezera je v `CLAUDE.md` bodu 5 (podmínka odkazuje jen na storefronty a
  hlavní kategorie). Pozor na dvojí dosah: text karty je vidět na hlavním
  webu, ale `name` navázané sestavy se přes `api/car_storefronts.py`
  dostane i na skryté Fiat domény - tam pak platí i pravidla 4 a 5
  (žádné sdílené identifikátory, žádná zmínka mateřské firmy), která pro
  hlavní web neplatí. Bez vlastní automatické kontroly zatím.

**Automatizované pokrytí kategorií - stav k 2026-09-05** (bot20,
follow-up dotažen): pravidla **1 a 2** teď kontrolují OBĚ tabulky -
nová `api/qa_checks.py::_category_text_fields()` (`content_categories`)
je zapojená do `storefront_full_height_claim`/
`storefront_nonsense_door_phrasing` vedle `_storefront_text_fields()`.
Ověřeno živě (dočasné testovací kategorie s porušující větou, obě
kontroly správně zachytily, uklizeno, `CHECKSUM TABLE` po úklidu sedí).

Pravidla **1a, 4, 5 zůstávají JEN pro storefronty**, záměrně:
- **1a** (`storefront_rack_height_exceeds_door`) potřebuje 1:1 vazbu na
  konkrétní model/karoserii auta (JOIN na `karoserie_model_reference`) -
  kategorie pokrývá víc značek/modelů najednou, nemá jedno číslo dveří,
  proti kterému by šlo porovnat. Strukturální důvod, ne mezera k
  dodělání.
- **4/5** (`storefront_identifier_leak`/`storefront_brand_mention`) mají
  smysl jen tam, kde text žije na JINÉ, skryté doméně než mateřská firma
  (Fiat mini-eshop). `content_categories` JE hlavní web Logiman/
  autovestavby.logiman.cz - vlastní jméno v `meta_title` je tam správně a
  očekávaně (ověřeno v datech - "Katalog hliníkových profilů Logiman"
  a další). Napojení by generovalo desítky falešných nálezů na
  správném textu.

Pravidla 3/6/7/8/9 (a 9a) nejdou automatizovat vůbec (fyzická/obsahová
podstata) - platí pro obě tabulky stejně, jen ručním review.

Pravidla vykrystalizovaná z chyb nalezených 2026-08-29/30 (detaily a
příklady oprav viz `AGENTS_LOG.md`, hledej "věcné opravy textu
variant"/"Logiman"/"HP-0579"):

1. **Žádné tvrzení o fyzické instalační praxi bez ověření skutečné
   praxe.** Věty typu "regál se dá postavit do plné výšky X mm" jsou
   tvrzení JAK SE TO SKUTEČNĚ DĚLÁ, ne jen odvozený fakt z rozměru
   karoserie. Bez ověřené znalosti skutečné instalační praxe (jako u
   fotky Ducato L2H1) takové tvrzení nepsat - buď to ověřit, nebo
   formulovat obecněji bez konkrétní zavádějící hranice. Automatická
   kontrola (od 2026-09-05 obě tabulky, viz rozsah výš):
   `storefront_full_height_claim` (`api/qa_checks.py`).
1a. **Konkrétní vysvětlení/upřesnění pravidla 1** (Robert, doplněno
    2026-08-30): regál má vždy maximální výšku takovou, aby se dal
    vložit do auta zadními dveřmi - reálný strop výšky regálu je výška
    ZADNÍHO NAKLÁDACÍHO OTVORU
    (`karoserie_model_reference.official_door_opening_height_mm`), NE
    výška stropu nákladového prostoru (`cargo_height_mm`). U vyšších
    karoserií (H2 apod.) bývá otvor nižší než strop - text nikdy nesmí
    naznačovat/uvádět vyšší regál, než kolik se vejde skrz dveře.
    Přesně tenhle vzorec unikl první verzi kontroly
    `storefront_full_height_claim` (ta hlídá jen frázi "plnou/celou
    výšku", ne konkrétní ČÍSLO) - Ducato L2H2 psalo "Výška 1932 mm
    dovoluje postavit vysoký regál", 1932 mm byl ale strop, skutečná
    výška dveří 1790 mm. Automatická kontrola (číselná, porovnává
    skutečnou `door_h` z DB - JOIN přes `karoserie_model_reference.
    car_models_id`, funguje pro všechny značky, viz komentář u funkce):
    `storefront_rack_height_exceeds_door`. Variantu bez
    známé výšky dveří (NULL v DB) nechat obecnou bez vymyšleného čísla.
2. **Žádná nesmyslná/spletená technická formulace.** Dimenze musí
   popisovat to, co skutečně měří (výška NAKLÁDACÍHO OTVORU, ne že
   "dveře se otevírají do výšky"). Kontrolní otázka: dává ta věta
   fyzický smysl, nebo jen zní technicky? Automatická kontrola (od
   2026-09-05 obě tabulky, viz rozsah výš): `storefront_nonsense_door_phrasing`.
3. **Žádná fabrikace certifikací/technických specifikací.** Jen ověřené
   oficiální zdroje, konzervativní rámování ("až", ne přesná čísla,
   když nejsou jistá). Nejde spolehlivě ověřit automaticky - rozhodnutí
   zůstává na tom, kdo text píše/reviduje.
4. **Žádné konkrétní identifikátory/kódy sdílené s hlavním webem** (viz
   HP-0579 případ). I nebrandové unikátní řetězce jsou fingerprint
   riziko, ne jen jméno firmy - kdokoli by kód vygooglil, najde obě
   domény pohromadě. Automatická kontrola (informativní, širší vzorec,
   každý nález posoudit ručně, JEN storefronty - viz rozsah výš proč ne
   kategorie): `storefront_identifier_leak`.
5. **Žádná zmínka mateřské firmy/brandu** (Logiman/konfigurátor/
   vandrawee) - patička, meta tagy, alt texty, JSON-LD, kdekoli v HTML
   zdroji. Automatická kontrola (JEN storefronty - viz rozsah výš proč
   ne kategorie): `storefront_brand_mention` (texty v DB) a
   `static_page_brand_leak` (SOUBORY: `storefront-*.html`, formuláře
   `login/register/forgot-password/reset-password/verify-email.html` a
   jimi načítané `.js/.css`).
   **Pozor - sdílené statické stránky (bot16, 2026-10-01):** nginx servíruje
   na storefront doménách celý `webapp/` jako statický fallback, takže
   přihlašovací formuláře vidí zákazník i na doméně BEZ značky (a
   `forgot/reset-password` i na `app.remeslnik.pro`). Logo Logiman se do nich
   proto NIKDY nevkládá do HTML, ale přes `GET /api/site-brand`
   (`api/site_brand.py`): server ho vrátí jen pro hosty autovestavby.logiman.cz
   (+www, IP vhost), jinde `null`. Stránka má jen prázdné `#siteLogoSlot` a
   vložený skript. Nová doména je tedy anonymní, dokud ji někdo výslovně
   nepovolí v `_LOGO_HOSTS`.

   **⭐ ÚZCE VYMEZENÁ VÝJIMKA z pravidel 4-5 (Robert, 2026-09-17, přes
   bot3, `PLAN_TVORBY_MINIWEBU.md`):** hub `fiat-autovestavby.top`
   (a JEN ten - ne 6 modelových domén pod ním, `ducato.fiat-autovestavby.top`
   ani standalone `fiat-ducato-vestavby.top` apod.) smí mít **2 prolinky**
   na hlavní web `autovestavby.logiman.cz`. Důvod: nová architektura
   miniwebů (podadresáře pod konsolidovanou doménou pro budoucí značky/
   státy) hub od zbytku Fiat sítě odlišuje - zbylých 6 domén zůstává
   plně anonymních/odbrandovaných jako dosud, pravidla 4-5 tam platí
   BEZE ZMĚNY. Není to zrušení principu, jen jeden bod v jedné doméně.
   **Vyřešeno (bot16, 2026-10-01):** DB kontroly `storefront_brand_mention`/
   `storefront_identifier_leak` šablonu hubu nevidí (skenují jen DB textová
   pole). Šablony hlídá `static_page_brand_leak`: v `storefront-hub.html`
   toleruje nejvýš 2× host `autovestavby.logiman.cz` (ty 2 prolinky), žádný
   jiný text značky, a v ostatních šablonách nic. Šablona hubu dnes žádnou
   zmínku značky nemá (0 výskytů, ověřeno 2026-10-01).
6. **Unikátní text per varianta** - žádná duplicita mezi variantami,
   každá popisuje svoje skutečné rozměry/použití. Zatím bez automatické
   kontroly (těžké spolehlivě odlišit "podobné, ale platné" od
   "duplicitní/šablonovité" - kontrola by potřebovala fuzzy porovnání
   textu napříč variantami, ne jen exact-match).
7. **Žádné fingované fotky.** Jen reálné fotky nebo GLB rendery
   existující geometrie, nikdy nic nevydávat za fotku, která není.
   Nejde ověřit automaticky (obsah obrázku, ne text).
8. **Dev komentáře v `<style>`/`<script>` bloku šablony JSOU veřejný
   obsah** (bot14, 2026-09-01, skutečná chyba - viz AGENTS_LOG.md "3
   nové standalone storefront domény"). Komentář v inline CSS souboru
   `webapp/storefront-*.html` se servíruje 1:1 každému návštěvníkovi/
   crawlerovi, i kdyz vypada jako "jen poznamka pro bota". Psat je
   STEJNE opatrne jako viditelny text - zadne nazvy sesterskych domen,
   zadne interni kody. `qa_checks.py` kontroly (`storefront_*`) tohle
   NEHLÍDAJÍ (čtou jen DB texty, ne statické šablony) - před nasazením
   nové/upravené šablony ověřit `curl`em živé stránky, ne jen review DB
   obsahu.
9. **Žádné tvrzení, které si fyzicky odporuje s vlastním popisem
   uchycení** (Robert, 2026-09-05). Živý příklad nesmyslné věty:
   "hliníkové police, přepážky a upínací body kotvené do bočnic a
   podlahy, bez vrtání do karoserie" - bočnice a podlaha JSOU karoserie
   (jsou její součást), takže "kotveno do X, bez zásahu do X" je
   vnitřně rozporné, ne jen nepřesné. Tahle logická chyba platí
   obecně, nezávisle na tom, jak montáž skutečně probíhá.

    **OPRAVA vlastního dřívějšího zápisu** (bot20, 2026-09-05, po
    doplnění referenčních faktů 9a téhož dne): první verze týhle rady
    jako "správný" opravný příklad navrhovala formulaci "bez nutnosti
    nových otvorů, využívá stávající upínací body/lišty". Podle faktů
    9a je tohle u dodávek N1 TYPICKY NEPRAVDIVÉ (originálních
    kotevních bodů je velmi málo/skoro žádné) - ta formulace by v praxi
    zaváděla novou nepravdu, jen jinam. Obecné vodítko se tedy OBRACÍ:
    **vrtání do zpevněných částí karoserie je BĚŽNÉ, OČEKÁVANÉ A
    HOMOLOGAČNĚ V POŘÁDKU** - text to má umět říct přímo (např.
    "kotveno do zpevněných částí karoserie (bočnice/podlaha) - montáž
    zahrnuje vrtání do těchto částí v souladu s požadavky na
    homologaci"), ne se tvářit, že se vrtání vyhýbáme. Skutečná
    bezvrtací montáž (na originální kotevní body) je u N1 vozidel spíš
    výjimka - pokud produkt opravdu žádné nové otvory nevyžaduje, tahle
    výjimečnost by se v textu měla zdůraznit jako přednost, ne
    předpokládat jako výchozí stav. Nejde ověřit automaticky (vyžaduje
    fyzickou znalost montáže, podobně jako pravidlo 3) - posoudit ručně
    před uložením.
9a. **Referenční fakta o uchycení/vestavbách** (Robert, 2026-09-05) -
    znát PŘED psaním textu o uchycení, ne až při revizi:
    - "Vestavby do aut/dodávek na míru znamená že vyrobíme úložný
      systém na milimetr dle požadavku, dle potřeby která vzejde z
      konzultace se zákazníkem."
    - "Přizpůsobujeme se zcela na milimetr vercajku, kufrům a
      představám zákazníka, proto je zřejmé že nelze využít
      originálních kotevních bodů v autech. Vždy je nezbytné vrtat do
      zpevněných částí karoserie a zároveň to koresponduje s nároky na
      homologaci."
    - "Originálních kotevních bodů v dodávkách typu N1 obecně moc
      není, spíše velmi málo."

10. **Text produktové karty musí obsahovat myšlenku "stavíme na míru na
    milimetr podle toho, co zákazník vozí"** (Robert, 2026-09-11, k
    textu karty 3942, ale rozhodnutí je obecné pro VŠECHNY produktové
    texty, ne jen tuhle kartu): *„k textu se musí přidávat ruzne verze
    této věty: Cokoli lze v sestave upravit, zmenit, predělat, přestavět
    na míru na milimetr dle představy. Přesně podle Vašich kufrů a
    vercajku."* Sestava není hotový výrobek s pevnými rozměry - je to
    hlavní prodejní argument a bez něj je text neúplný, i kdyby byl
    jinak technicky správný.

    **Musí se pokaždé formulovat jinak**, ne kopírovat stejnou větu.
    Robert: „různé verze", nejen jazykově - **10 (OPRAVENO audit bot9 2026-09-12: ověř živě `SELECT COUNT(*) FROM product_assemblies` - číslo se mění denně, nepiš sem pevnou hodnotu) karet se
    stejným odstavcem vypadá jako kopírka a vyhledávače to trestají jako
    duplicitní obsah** (viz i pravidlo 6 výš, unikátní text per
    varianta - tohle je jeho konkrétní, časem nejčastější případ).

    Hotové obměny k vycházení (dál obměňovat, ne používat furt tutéž):
    - *„Rozměry nejsou dané. Každý díl jde posunout, zvětšit nebo
      vynechat na milimetr přesně tak, aby sestava seděla na vaše kufry
      a nářadí."*
    - *„Cokoli v sestavě jde upravit, změnit, předělat nebo přestavět -
      na míru, na milimetr, podle toho, co v autě opravdu vozíte."*
    - *„Tohle je jedno z provedení, ne jediná možnost. Sestavu
      postavíme přesně podle vašich kufrů a vercajku, na milimetr."*

    **Slovo „vercajk" je Robertovo, hovorové - u KAŽDÉ karty připravit
    obě varianty (s „vercajkem" i spisovně „nářadí") a nechat Roberta
    vybrat tón, nerozhodovat to za něj.** Je to jeho řeč a jeho
    zákazník.

    **Rozhodnuto (Robert, 2026-09-11, po první kartě 3942): tón se
    STŘÍDÁ podle karty, není to jednorázová volba jednoho slova pro celý
    katalog.** „Vercajk" je stejná obměna jako celá věta kolem něj - kde
    se hodí hovorověji, jde tam; jinde spisovné „nářadí". Nevybírat
    jednou napevno pro všechny karty (počet se mění, nepiš sem pevné
    číslo - OPRAVENO audit bot9 2026-09-12) - je to součást stejného
    obměňování, co drží text nešablonovitý (viz odstavec výš o
    duplicitním obsahu).

11. **Popis produktu musí být složený z více částí, nikdy jeden jednolitý
    blok textu** (Robert, 2026-09-13, doslova): *„Popisy v detailech
    produktu musí být jakoby složený z více částí, nemůže to být jeden
    jednolitý text, jak z důvodu čitelnosti tak z praktického hlediska
    psaní článků."* Dva důvody, oba závazné: čitelnost pro zákazníka
    (dlouhý nedělený odstavec se nečte) a praktičnost psaní/údržby
    (kratší, pojmenované části jdou upravovat/obměňovat nezávisle na
    sobě, viz pravidlo 6/10 výš o obměňování a duplicitě). Technicky:
    rozdělit na nadpisy/odstavce/odrážky (HTML struktura, ne jen vizuální
    zalomení řádku uvnitř jednoho `<p>`), ne nutně pevný počet částí -
    záleží na obsahu, ale VŽDY víc než jeden nedělený blok.

12. **Produkty vyžadující montáž musí mít montáž popsanou v ODDĚLENÉ
    části textu** (Robert, 2026-09-13, doslova): *„Produkty které
    vyžadují montáž, což je prakticky téměř jakýkoli náš produkt z
    profilů, musí právě část montáž popisovat odděleně. Zákazník si
    nemusí montáž zvolit od nás, může montovat svépomocí."* Konkrétní
    naplnění pravidla 11 (více částí, ne jeden blok) - montáž je jedna z
    povinných samostatných částí, protože se netýká VŠECH zákazníků
    stejně: kdo montáž objedná u nás, tuhle část jen potvrzuje/přeskočí,
    kdo montuje svépomocí, potřebuje ji jako samostatně čitelný návod,
    ne rozpuštěnou v obecném popisu produktu. Platí prakticky pro celý
    katalog profilových sestav, ne jen pro vybrané produkty.

13. **Popis produktu musí odpovídat vybrané variantě - popisy jsou
    dynamické podle vybrané sestavy** (Robert, 2026-09-13, doslova):
    *„Popis v detailu produktové sestavě musí korespondovat s vybranou
    variantou, tzn. popisy jsou dynamické podle vybrané sestavy."* Jedna
    karta nese víc variant (viz `PLAN_TVORBY_SESTAV.md` "Dvě osy, jedna
    karta" - verze × horní blok, dnes 7, časem až 18 kombinací na
    kartě), takže jeden statický popis společný pro celou kartu
    nestačí - při přepnutí ekvalizérem se má zobrazený popis
    odpovídajícím způsobem změnit podle toho, co konkrétní kombinace
    reálně je/obsahuje. **Závisí na otevřené otázce** ("❓ Zákaznický
    název chybí", `PLAN_TVORBY_SESTAV.md` Fáze 1) - varianta dnes nemá
    vlastní zákaznické pojmenování/popis, jen interní název s "NÁHLED".
    Dokud tohle pole neexistuje, pravidlo 13 nejde technicky naplnit -
    zapsáno jako závazné pravidlo, ne jako hotové.

    **Platí stejně i pro montážní část (pravidlo 12).** Robert
    2026-09-13, doslova: *„Stejné pravidlo platí i pro popis ohledně
    montáže."* Různé varianty (jiný horní blok, jiný rozpis boxů) mají
    reálně jiný montážní postup/kroky - montážní text tedy NENÍ
    společný pro celou kartu o nic víc než zbytek popisu a musí se
    přepínat stejným mechanismem (per-variantní pole na katalogovém
    číselníku, ne na kartě).

    **Statická část nesmí duplikovat, co už říká dynamická část.**
    Robert (2026-09-13, doslova, přes bot5): *„Ve statické části nemůže
    být to, co je v dynamické."* Nejde jen o to mít dynamickou část
    navíc - jakmile něco řekne dynamický text (konkrétní rozpis boxů,
    konkrétní provedení horního bloku), stejná informace musí ze
    statické části produktu ZMIZET, ať už doslovně nebo parafrázovaně
    (nález bot5 na kartě 3943, commit `02399dc8`: dva případy, jedna
    doslovná duplicita a jeden parafrázovaný výčet). **Obecná věta, že
    volba/varianta existuje** (např. "vyberete si z několika
    provedení"), naopak zůstává - tu dynamická část neříká, protože
    ukazuje vždy jen JEDNU aktuálně vybranou variantu, ne přehled všech
    možností.

14. **Sestavy z více profilů — montáž jako související služba s vlastní
    cenou, kotvení jako vlastní oddělená část** (Robert, 2026-09-13,
    doslova):

    a. *„Montáž se uvede jako služba související, cena montáže se
       přebírá u sestavy ze scény."* Montáž NENÍ jen popisný text -
       je to samostatná NABÍZENÁ SLUŽBA s vlastní cenou, a ta cena se
       nesmí vymýšlet/odhadovat na kartě, musí se přebírat z toho, co
       spočítá scéna pro konkrétní sestavu (stejný princip jako
       `price_summary` u materiálu/řezání/spojů dnes -
       `ASSEMBLY_PRICE_SUMMARY_FIELDS` v `api/product_assemblies.py`
       zatím žádné pole pro montáž nemá, potřeba doplnit).
    b. *„Popis kotvení a montáže v popisu produktu musí být oddělen
       stejně jako popis konkrétní sestavy."* Kotvení (kam/jak se regál
       fyzicky kotví - dnes ověřeno bot8: závisí na `umisteni`, ne na
       horním bloku) je VLASTNÍ oddělená část stejně jako montáž
       (pravidlo 12) a stejně jako zbytek popisu (pravidlo 13) -
       dynamická podle vybrané varianty, nesloučená do jednoho odstavce.
    c. *„Při výběru produktu včetně montáže se bude nabízet jako
       varianta podle nastavení v adminu."* Jestli se zákazníkovi
       vůbec NABÍDNE možnost "včetně montáže" jako volitelná
       varianta, řídí se nastavením v adminu (per produkt/kategorie,
       ne napevno pro celý katalog) - někde se nabízet nemusí (např.
       kde montáž nedává smysl nebo ji Logiman nezajišťuje).

    Vztah k rule 12/13: tohle je rozšíření na SESTAVY z více profilů
    konkrétně (ne obecná pravidla pro libovolný produkt) a přidává
    obchodní/cenovou stránku montáže, ne jen textovou. Implementace
    (nové pole ceny montáže ve scéně/`price_summary`, admin nastavení
    nabízení varianty) je mimo dosah TEXT_FILTR - domény bot5
    (obchod/karty) a bot8 (scéna/cena), zapsáno zde jen jako závazné
    pravidlo pro obsah a jeho zdroj pravdy.

15. **„vanDrawee" se v ČESKÝCH textech nepoužívá vůbec.** Robert,
    2026-09-15, doslova: *„Logiman je nazev firmy, značka firmy, cokoli
    co vyrobí z alu profilů nese logo Logiman. vanDrawee je jakoby
    znacka uzšího segmentu produktů > kdyz jsou urcené pro auta. Ale
    vanDrawee si nechame na marketing do zahranicí, v českých textech
    ho nebudeme pouzivat."* Značková hierarchie: **Logiman** = firma/
    hlavní značka, na všem z hliníkových profilů. **vanDrawee** = užší
    segmentová značka pro produkty do aut - existuje, ale je vyhrazená
    výhradně pro **zahraniční marketing**, ne pro český obsah.
    Praktický důsledek: jakákoli zmínka „vanDrawee" v ČESKÉM
    zákaznickém textu (popis kategorie/produktu/FAQ) je k odstranění -
    nahradit obecnou formulací funkce/vlastnosti, ne jménem značky.
    Nálezem 2026-09-15 byly 3 stránky kategorií (Regály do auta,
    Montážní stoly a pracoviště, Přívěsný vozík s úložným systémem,
    `content_pages` id 27/7/24) se sdíleným odstavcem z let 2019/2020 a
    FAQ odpovědí stavěnou na jméně vanDrawee - oprava zadána bot5.

16. **Text se SKLÁDÁ z ověřených zdrojů, nikdy se nevymýšlí volně.**
    (Robert, 2026-09-17, doslova): *„vsiml jsem si ze kdyz bot skládá
    text casto nedává obsahove plný smysl, obsahuje protiklady takže
    nemuzes ty texty vymýšlet, jen správně skládat ze zdrojů konkurence
    a z logiman.cz."* Důvod: volně generovaná spojovací próza je přesně
    tam, kde bot nejčastěji vyrobí vnitřně rozpornou nebo obsahově
    prázdnou větu - zní to hladce, ale neříká to nic pravdivého ani
    konzistentního. Bezpečnější metoda: skládat text z reálných, už
    jednou napsaných (a tedy ověřeně smysluplných) fragmentů - z
    **vlastních textů logiman.cz** (fakticky pravdivé o nás, viz
    `backups/otisk_logiman_cz_2026-08-10.md`) a z **textů konkurence**
    (ověřeně srozumitelná formulace/terminologie).

    **Nemění to prioritu zdrojů OBSAHU** (`SEO_STANDARD_TEXTY_KATEGORII.md`):
    konkurence pořád nesmí dodat FAKTA o nás (rozměry, certifikace, co
    skutečně vyrábíme) - to musí sedět s naším výrobním programem, viz
    pravidlo 3 výš. **Mění to METODU SKLÁDÁNÍ**: i tam, kde je obsah
    pravdivý, formulace/věta se má PŘEVZÍT a upravit z reálného zdroje,
    ne vygenerovat jako zcela nová souvislá próza od nuly. Kontrolní
    otázka před uložením: dá se každá věta dohledat/odůvodnit v nějakém
    reálném zdroji (naše DB/logiman.cz/ověřený vzor konkurence), nebo je
    to čistě "vymyšlené, protože to zní dobře"? Druhý případ se nesmí
    uložit. Je to širší verze pravidla 3 (žádná fabrikace) - netýká se
    jen certifikací/specifikací, ale JAKÉKOLI věty popisného textu.

17. **Popisný text nesmí opakovat informaci, kterou stránka už ukazuje
    v UI widgetu/tabulce.** Robert, 2026-09-23, u karty Citroën Jumpy
    L1 (K-120-RL-EB-30), doslova: *„porad se tam pise text ohledne
    boxu pricemz boxy zobrazujeme v tabulce!!! nechceme to v textu."*
    Nález (bot3): stránka produktu má widget "Skladba boxů"/"Horní
    blok" se seznamem variant euroboxů - popisný odstavec pod ním
    tutéž informaci ZNOVU vypisoval jako větu ("Na výběr jsou tři
    skladby euroboxů: 3× box výšky 170 mm a 6× 120 mm; ..."). Kořen:
    věta byla napevno napsaná v bot5ových kartu-zakládacích skriptech
    (`scripts/2026-09-1*_bot5_zalozit_kart*.py`), ne generovaná
    šablonou - postihlo 8 karet (Citroën Jumpy ×4, Ford Transit
    Connect ×2, VW Caddy, Toyota Proace), opraveno 2026-09-23
    (`backups/2026-09-23_euroboxy_redundant_text_pred_opravou/`).
    Praktický důsledek: než se do popisu napíše konkrétní číselný/
    výčtový údaj (skladba boxů, rozměry variant, cena...), ověřit, jestli
    ho stránka NEUKAZUJE UŽ JINDE strukturovaně (tabulka/widget/
    přepínač) - pokud ano, text ho nesmí opakovat, i kdyby to znělo
    jako přirozené doplnění popisu. Toto pravidlo je NEZÁVISLÉ na
    pravidle 16 (skládání ze zdrojů) - týká se DUPLICITY v rámci JEDNÉ
    stránky, ne fabrikace faktů.

18. **Do polí centrálního panelu "Typy sestav" (`sestava_typ.popis_
    sablona`, `sestava_typ_sluzba.nazev`) smí psát VÝHRADNĚ Robert.**
    Robert (přes bot3, 2026-09-27), doslova: *„na texty v centrálním
    panelu nemá bot právo měnit."* Bot smí postavit mechanismus (DB
    schéma, UI formulář, migraci) a nechat pole prázdná/NULL, ale
    NIKDY do nich sám nevkládá text - ani jako dočasný příklad nebo
    placeholder, který by mohl omylem zůstat živý.

**Retroaktivní audit** (bot14, 2026-08-30): všech 22 tehdy existujících
variant prošlo pravidly 1/2/4/5 přes `api/qa_checks.py`
(`storefront_full_height_claim`, `storefront_nonsense_door_phrasing`,
`storefront_identifier_leak`, `storefront_brand_mention`) - všechny 4
kontroly čisté (0 nálezů) po opravě dříve nalezených chyb. **Druhé kolo
auditu** (pravidlo 1a, stejný den) odhalilo 2 další skutečné případy
(Ducato L2H2/L2H1) unikátní právě téhle první "čisté" kontrole, protože
hlídala jen frázi, ne konkrétní čísla - poučení: automatická kontrola
je jen tak dobrá, jak přesně formulované pravidlo hlídá, "0 nálezů"
jedné kontroly neznamená "text je v pořádku" bez ohledu na to, co jiná
(i budoucí) kontrola/člověk najde. Kontroly běží dál automaticky (admin
dashboard QA audit + `konfigurator-qa-audit.timer`, podle rozvrhu v jednotce timeru - OPRAVENO audit bot9 2026-09-12: aktuálně 1x týdně (pondělí), ne 2x denně; ověřit `systemctl list-timers konfigurator-qa-audit.timer`) - regrese
v nových i starých variantách se odhalí samy, ne jen při ručním review.

---

Git/zámek disciplína (kdo smí tenhle soubor editovat, jak, s jakým
zámkem) je řešená ve `WORKFLOW.md` - tenhle soubor řeší jen OBSAH
textů, ne proces jejich úpravy.
