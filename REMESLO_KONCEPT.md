# Řemeslo — koncept podprojektu (návrh, zatím NEIMPLEMENTOVÁNO)

## Cíl 1. etapy (Robert, 2026-08-17, přes bot3)

**"Zaujmout řemeslníky službami zdarma, které mu ušetří čas, a
vytvořit si jakousi základnu uživatelů."** Tohle je rámující cíl pro
CELOU etapu 1 - vysvětluje i dosavadní rozhodnutí (srovnávač cen
zdarma bez poplatku, žádný poptávkový/placený systém zatím - viz bod
3 níž) a je vodítkem pro budoucí prioritizaci: v etapě 1 se staví to,
co řemeslníkovi něco ušetří ZDARMA a přivede ho na platformu, ne co
z něj rovnou vydělá. Monetizace/lead-gen přijde až po vybudování
základny uživatelů, ne současně s ní.

Zadání (Robert, 2026-08-17, přes bot3): platforma pro řemeslníky = do
budoucna potenciální zákazníky konfigurátoru. Idea: sada menších i
větších procedur/systémů/funkcí, co dobrému řemeslníkovi ušetří čas
v jakémkoli ohledu. Umístění v adminu (až se bude stavět): samostatná
sekce/skupina panelů v levém menu, oddělená od stávajících položek.

Tenhle dokument je **jen plán** — nic z něj zatím není naprogramováno.
Napřed má projít schválením u bot3/Roberta (viz konec dokumentu).

Doprovodný dokument: **`REMESLO_PRUZKUM.md`** (bot11, 2026-08-17) —
průzkum konkurenčních/inspirativních platforem (české i zahraniční
lead-gen portály, "ověřené" adresáře jako Checkatrade, provozní SaaS
nástroje jako Houzz Pro, pokusy o srovnávač cen materiálu). Jeho
doporučení jsou zapracovaná do tohohle plánu níž - odkazuje se na ně
jmenovitě, ne kopírováno znovu.

## Rozhodnutí Roberta k tomuhle konceptu (chronologicky, 2026-08-17)

1. **Databáze řemeslníků je INTERNÍ, ne veřejná** (GDPR).
2. **ID schéma řemeslníka**: prefix podle profese, KAŽDÝ prefix má
   vlastní číselnou řadu od 0001 (např. "ELE-0001", "TRUH-0001" -
   ne jedno globální číslo napříč profesemi).
3. **Poptávkový/nabídkový systém (lead-gen mezi zákazník-řemeslník)
   NENÍ v současném scopu** - na trhu už je dost podobných platforem
   (`REMESLO_PRUZKUM.md` doporučení č. 4). Odloženo, NE zrušeno -
   mantinely (jak NEkopírovat anti-patterny konkurence) zůstávají
   zaznamenané v sekci "Mimo současný scope" níž. **POZOR, tohle NENÍ
   totéž co bod 6 níž ("jednoduché CRM")** - lead-gen = NAŠE platforma
   párující zákazníky s řemeslníky (jako NejŘemeslníci.cz), CRM =
   nástroj pro KAŽDÉHO řemeslníka na správu JEHO VLASTNÍCH poptávek/
   zákazníků, dvě různé věci.
4. **Doporučení č. 1 z `REMESLO_PRUZKUM.md` (ověřovací mechanismus,
   Checkatrade model)** zůstává v scopu, ale s NIŽŠÍ prioritou (viz
   bod 8 níž - postaví se AŽ PO srovnávači cen).
5. **Přidány 2 nové moduly**: evidence zakázek (sledování zakázek
   řemeslníka) a jednoduché CRM.
6. **CRM se NESTAVÍ od nuly** - znovupoužije se stávající systém
   poptávek (`api/crm.py`, `crm_leads`/`crm_lead_messages`), rozšířený
   o volitelné navázání na konkrétního řemeslníka - žádná nová
   paralelní CRM tabulka/UI.
7. **Priorita č. 1 ze VŠECH modulů: srovnávač cen materiálu, PODLE
   PROFESE řemeslníka** (materiál relevantní JEHO profesi, ne obecný
   seznam) - staví se PRVNÍ, před evidencí zakázek, CRM i ověřovacím
   mechanismem.
8. **AI-čtení faktur (crowdsourcing, `REMESLO_PRUZKUM.md` doporučení
   č.3) se ZATÍM NEPOUŽIJE jako zdroj dat pro start srovnávače.**
   Robertovo zdůvodnění: "bude trvat týdny, než si vytvoříme zájemce
   o náš systém, oni mají faktury pořešené, ale nemají srovnávač" -
   crowdsourcing má studený start (nulová báze uživatelů, kteří by
   faktury nahrávali) a srovnávač cen JE SÁM hlavní hodnota, která má
   řemeslníky přilákat - musí fungovat i BEZ jejich dat, jinak nemají
   důvod přijít. **Pilotní scraping (případně ruční zadání) se tak
   mění z "doplňku" na PRIMÁRNÍ zdroj dat pro start** - crowdsourcing
   zůstává jako budoucí rozšíření, AŽ bude existovat uživatelská
   základna, ne launch mechanismus. Zapracováno do přehodnocené fáze
   "Srovnávač cen" níž.

## Priorita modulů (aktuální, po všech rozhodnutích výš)

1. 🥇 **Srovnávač cen materiálu (dle profese)** — STAVÍ SE PRVNÍ.
2. Evidence zakázek řemeslníka.
3. Jednoduché CRM (rozšíření `api/crm.py`, ne nová stavba).
4. Ověřovací mechanismus (`remeslo_verification_checks`, doplněk
   databáze řemeslníků).
5. Foto-analýzy — DEPRIORITIZOVÁNO (blokováno neplatným
   `ANTHROPIC_API_KEY` i Robertovým rozhodnutím bod 8 výš), zůstává
   v plánu jako budoucí rozšíření (viz "Foto-analýzy a budoucí
   crowdsourcing" níž), ne jako aktuální krok.
6. Akvizice řemeslníků — nejnižší priorita, primárně analytická
   praxe nad daty modulu 1/2/3, ne systém k naprogramování.

**Důležitá závislost, kterou priorita č.1 skrytě nese**: srovnávač cen
"dle profese" a "podle vzdálenosti od řemeslníka" potřebuje ZNÁT
profesi a polohu konkrétního řemeslníka, který se ptá - to znamená, že
i když se "Databáze řemeslníků" jako samostatný modul/ověřovací
mechanismus staví AŽ ve 4. kroku, **minimální jádro** (tabulka
řemeslníků + profesí + jejich ID schéma + geokódovaná adresa, BEZ
ověřovací vrstvy a bez plného admin CRUD) musí vzniknout SOUČASNĚ s
modulem 1, ne až po něm - jinak srovnávač nemá o co se opřít. Viz
"Co jde první implementovat" níž pro přesný rozsah týhle nutné
menší podmnožiny.

## Jak vzniknul tenhle dokument

Před psaním plánu jsem prostudoval existující kód konfigurátoru, ať
návrh navazuje na to, co už tu funguje, místo aby něco duplikoval nebo
vymýšlel od nuly. Konkrétní nalezené vzory jsou citované u každé
oblasti níž — shrnutí:

- **`api/app.py` `/api/ai/generate`** (řádek ~8247-8550) — 3Dbot chat
  UŽ dnes umí poslat Claude obrázek jako součást zprávy +
  strukturovanou odpověď přes `tools`/`tool_choice`. Hotový vzor pro
  budoucí foto-analýzy (modul 5, deprioritizováno). `ANTHROPIC_API_KEY`
  v `api/.env` je navíc aktuálně **neplatný** (401, potvrzeno bot8
  2026-08-17) - i kdyby modul 5 měl prioritu, nešel by teď reálně
  spustit. Pro AKTUÁLNÍ prioritu (srovnávač cen) je tohle nepodstatné -
  scraping/ruční zadání na AI-vrstvě vůbec nestaví.
- **`webapp/capture.html`** (skener dokladu V3) — živý rámeček přes
  náhled kamery, ořez + perspektivní narovnání. Vstupní krok pro
  budoucí foto-analýzy, ne pro aktuální prioritu.
- **`api/incoming_documents.py`** — staging → schvalovací fronta →
  přesun do složky na Sdíleném disku. Vzor pro budoucí schvalovací
  tok, až přijde na řadu crowdsourcing (modul 5).
- **`sql/2026-07-25_purchase_orders.sql`** (`shop_suppliers` tabulka)
  — karta dodavatele, strukturálně blízko "minimálnímu jádru"
  databáze řemeslníků (viz níž).
- **`api/purchase_orders.py::_generate_po_number()`** (`NO-{rok}-
  {id:05d}`) — nejbližší existující vzor prefixovaného číslování,
  ALE generuje se z globálního auto-increment `id`. Robertovo zadání
  (řada od 0001 ZVLÁŠŤ pro každou profesi) potřebuje jiný mechanismus
  - viz `remeslo_professions.next_seq` + `SELECT ... FOR UPDATE` níž.
- **`api/gallery_items.py`** (řádek ~600-634) — hotová Haversine
  vzdálenostní SQL query nad `latitude`/`longitude`. Přímý vzor pro
  filtraci srovnávače podle vzdálenosti — **žádné geokódování adresy
  na lat/lon v repu není** (ověřeno), to je nová část.
- **`scripts/2026-08-09_dogus_price_recompute.py`** — jediný existující
  vzor "stáhni cenu z cizího webu, ulož, přepočítej". Funguje pro
  JEDNOHO dodavatele s vlastním parserem (2 parsery pro 2 rozvržení
  stránek téhož dodavatele) - přímý technický vzor pro pilotní
  scraping v modulu 1, i s jasným varováním o křehkosti/údržbě.
- **`api/crm.py` / `crm_leads` / `crm_lead_messages`** — existující
  poptávkový systém (zachytává e-mailové poptávky, viz
  `crm.classify_incoming_email`/`find_or_create_lead`). Robertovo
  rozhodnutí bod 6 výš: modul 3 (jednoduché CRM) tohle ZNOVUPOUŽIJE,
  ne staví paralelně - návrh rozšíření viz modul 3 níž.
- **`webapp/admin.html`** (nav-group vzor, `data-group` atribut,
  existující skupiny `prehled`/`katalog`/`importy`/`sklad`/`prodej`/
  `nastaveni`) — nová skupina `remeslo` se přidá stejným způsobem.
- **Permissions**: nové sekce se zakládají fail-closed (vzor
  `prijate_doklady`) - Řemeslo dostane vlastní `PERMISSION_SECTIONS`
  klíč (`remeslo`), stejný princip.
- **`api/qa_checks.py`** — projektová konvence (WORKFLOW.md bod 9):
  každý nalezený opakovatelný bug se přelije do automatické kontroly,
  platí i pro nový kód Řemesla.

## Vize (rozpracováno)

Řemeslo NENÍ prodloužení stávajícího e-shopu — je to samostatná, volně
navázaná sada nástrojů, které řeší BĚŽNÉ provozní starosti řemeslníka
jako profese, nezávisle na tom, jestli si zrovna něco kupuje od nás.
Logika propojení s hlavním byznysem: řemeslník, který u nás pravidelně
používá užitečné nástroje zdarma/levně, je blíž k tomu stát se
zákazníkem konfigurátoru — obdoba "content marketingu", jen ve formě
funkčních nástrojů místo článků.

`REMESLO_PRUZKUM.md` tohle potvrzuje zvenčí: všechny nalezené
platformy jsou lead-generation tržiště — **žádná nedělá AI foto-
analýzu ani srovnávač cen materiálu napříč dodavateli.** Srovnávač
cen (modul 1, priorita č.1) je skutečná bílá plocha na trhu, ne
"dohnat konkurenci" - přesně proto ho Robert staví jako první, je to
nejsilnější odlišující hodnota, kterou lze nabídnout HNED, bez
závislosti na tom, aby už měl Řemeslo uživatelskou základnu (na
rozdíl od crowdsourcingu, viz rozhodnutí č.8 výš).

Důsledek pro architekturu: Řemeslo je navrženo jako VOLNĚ PROPOJENÁ
sada modulů (společná jen "karta řemeslníka" jako sdílený
identifikátor), ne jeden svázaný systém — každý modul jde
zprovoznit/rozšiřovat nezávisle na ostatních.

## Modul 1 (PRIORITA) — Srovnávač cen materiálu, podle profese

**Zdroj dat pro start (přehodnoceno, viz rozhodnutí č.8 výš):**
AI-crowdsourcing z nahraných faktur NENÍ launch mechanismus - má
studený start (nulová báze přispěvatelů) a srovnávač musí fungovat
sám o sobě, aby měl řemeslník důvod k nám vůbec přijít. Primární
zdroj dat na start jsou proto:
- **Pilotní scraping** 2-3 ručně vybraných dodavatelů s velkým online
  katalogem PRO JEDNU ZVOLENOU PROFESI (přímý vzor:
  `scripts/2026-08-09_dogus_price_recompute.py`, i s jeho varováním o
  křehkosti/parseru na míru).
- **Ruční zadání** (jednoduchý admin formulář, bez AI) jako doplněk
  pro kategorie, které scraper nepokryje, nebo na korekce.
- AI-čtení faktur (foto-analýzy, modul 5) zůstává navržené jako
  BUDOUCÍ rozšíření, až bude existovat uživatelská základna
  řemeslníků, kteří mají motivaci přispívat - schéma níž je s tímhle
  rozšířením už dopředu kompatibilní (`origin` sloupec), jen se
  nestaví TEĎ.

```sql
CREATE TABLE remeslo_professions (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(100) NOT NULL UNIQUE,   -- "Elektrikář", "Instalatér", "Truhlář"...
    slug          VARCHAR(100) NOT NULL UNIQUE,
    -- Robert: "prefix podle profese a každý prefix má svoji řadu od
    -- 0001" - KAŽDÁ profese vlastní prefix, číslování NEZÁVISLE od
    -- ostatních profesí (ne jedno globální číslo).
    code_prefix   VARCHAR(10) NOT NULL UNIQUE,     -- "ELE", "TRUH", "ZED"...
    next_seq      INT NOT NULL DEFAULT 1,          -- dalsi volne cislo v rade TETO profese
    active        TINYINT(1) NOT NULL DEFAULT 1
);

-- MINIMALNI JADRO databaze remeslniku - jen to, co modul 1 potrebuje
-- (profese + poloha pro vzdalenost). Plna verze s overovanim/CRM
-- navazanim prijde az v modulech 3-4, tahle tabulka uz ale musi
-- pocitat s jejich budoucim rozsirenim (proto FK-pripravene sloupce
-- i kdyz se zatim nepouzivaji).
CREATE TABLE remeslo_craftsmen (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    code            VARCHAR(20) NOT NULL UNIQUE,    -- "ELE-0001", viz _assign_craftsman_code() nize
    name            VARCHAR(255) NOT NULL,
    company_name    VARCHAR(255) NULL,
    profession_id   INT NOT NULL,                   -- FK remeslo_professions - kod vyzaduje znamou profesi HNED pri vytvoreni
    address         TEXT NULL,
    city            VARCHAR(255) NULL,
    zip_code        VARCHAR(10) NULL,
    latitude        DECIMAL(10,7) NULL,              -- geokodovano z adresy, viz nize
    longitude       DECIMAL(10,7) NULL,
    email           VARCHAR(255) NULL,
    phone           VARCHAR(50) NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'candidate',  -- rozsireno v modulu 4 (akvizice)
    note            TEXT NULL,
    active          TINYINT(1) NOT NULL DEFAULT 1,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Robert (doplneni): "hodne materialu se prolina napric profesemi
-- (napr. sroubovak/spojovaci material pouzije elektrikar i truhlar) -
-- NESMI se to duplikovat v DB, profese je jen FILTR/pohled nad
-- sdilenou tabulkou materialu". Material je proto JEDNA sdilena
-- tabulka BEZ profession_id sloupce, vazba na profese jde pres
-- samostatnou M:N tabulku nize - stejny material se da najit pod
-- vice profesemi, aniz by existoval vicekrat.
CREATE TABLE remeslo_material_categories (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,        -- "Měděná trubka 15mm", "Sádrokarton 12.5mm", "Vrut do dřeva 4x40"...
    unit            VARCHAR(20) NOT NULL           -- "m", "ks", "kg", "m2"...
);

-- M:N vazba material<->profese (Robert: "profese je jen filtr/pohled,
-- ne duplicitni kopie dat") - jeden material muze mit vic radku tady
-- (napr. spojovaci material -> elektrikar I truhlar), srovnavac
-- filtruje "materialy relevantni MOJI profesi" JOINem pres tuhle
-- tabulku, ne podle sloupce primo na remeslo_material_categories.
CREATE TABLE remeslo_material_category_professions (
    category_id     INT NOT NULL,                 -- FK remeslo_material_categories
    profession_id   INT NOT NULL,                 -- FK remeslo_professions
    PRIMARY KEY (category_id, profession_id)
);

CREATE TABLE remeslo_price_sources (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    supplier_name   VARCHAR(255) NOT NULL,
    website         VARCHAR(255) NULL,
    address         TEXT NULL,
    latitude        DECIMAL(10,7) NULL,
    longitude       DECIMAL(10,7) NULL,
    -- 'scrape_pilot' | 'manual' | 'crowdsourced' (posledni hodnota
    -- pripravena pro BUDOUCI rozsireni z modulu 5, nepouziva se ted).
    origin          VARCHAR(20) NOT NULL DEFAULT 'scrape_pilot',
    scrape_config   JSON NULL,                     -- jen u origin='scrape_pilot' - parser-specific nastaveni jako dogus_url/dogus_stock_code dnes
    active          TINYINT(1) NOT NULL DEFAULT 1
);

CREATE TABLE remeslo_material_prices (
    id                      INT AUTO_INCREMENT PRIMARY KEY,
    category_id             INT NOT NULL,          -- FK remeslo_material_categories
    source_id               INT NOT NULL,          -- FK remeslo_price_sources
    product_name            VARCHAR(255) NOT NULL,  -- přesný název u dodavatele (transparentnost, jako dogus_list_price_usd dnes)
    price_czk               DECIMAL(10,2) NOT NULL,
    product_url             VARCHAR(500) NULL,      -- jen u origin='scrape_pilot'
    -- pripraveno pro budouci crowdsourcing (modul 5) - NULL, dokud
    -- se ten modul nestavi.
    contributed_by_craftsman_id INT NULL,
    source_photo_analysis_id    INT NULL,
    scraped_at               DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

**Přiřazení kódu řemeslníka (Python, návrh)**:
```python
def _assign_craftsman_code(cur, profession_id):
    cur.execute(
        "SELECT code_prefix, next_seq FROM remeslo_professions WHERE id=%s FOR UPDATE",
        (profession_id,),
    )
    row = cur.fetchone()
    code = f"{row['code_prefix']}-{row['next_seq']:04d}"
    cur.execute("UPDATE remeslo_professions SET next_seq=next_seq+1 WHERE id=%s", (profession_id,))
    return code
```
`FOR UPDATE` zamyká řádek profese na dobu transakce - dva souběžné
vznikající záznamy stejné profese nedostanou stejné číslo.

**Dotaz "porovnej ceny pro řemeslníka X"** = JOIN
`remeslo_material_prices` → `remeslo_price_sources`, filtr přes
`remeslo_material_category_professions WHERE profession_id=<profese
řemeslníka X>` (ne přímý sloupec na `remeslo_material_categories` -
viz M:N vazba výš), řazení podle ceny. Materiál sdílený víc profesemi
(např. spojovací materiál) se tak zobrazí správně KAŽDÉ z nich, bez
duplicitních řádků v datech.

**Geokódování/vzdálenostní filtr ZAHOZENO** (Robert, přes bot3,
2026-08-17: "nám stačí ceny které jsou normálně na eshopech") - modul
1 NEPOTŘEBUJE adresu→lat/lon ani Haversine vzdálenost dodavatele,
srovnává se čistě podle ceny z e-shopu. `remeslo_craftsmen.latitude/
longitude` a `remeslo_price_sources.latitude/longitude` sloupce v DB
zůstávají (neškodí, nejsou NOT NULL), ale nejsou vyplňované ani
používané - žádná závislost na Mapy.com API klíči (ten se ukázal
jako blocker, viz níž) ani na hledání ČÚZK/RÚIAN geocoding endpointu.

> **PŘEKONÁNO (Robert, 2026-08-20)** — "Vzdálenostní filtr podle
> polohy řemeslníka je klíčová hodnota konceptu" (přesně to samé, co
> už tehdy říkalo kritérium 2 níž - "jinak nemá smysl vzdálenostní
> filtr, který je klíčová hodnota srovnávače" - ZAHOZENÍ výš bylo
> vždy jen dočasné zjednodušení pro start pilotu, ne trvalé
> rozhodnutí). Blocker z bodu 1 v seznamu níž ("Mapy.com potřebuje
> klíč, ČÚZK/RÚIAN nemá endpoint") je MEZITÍM VYŘEŠENÝ - `api/
> remeslo_weather.py` (bot14, počasí navázané na kalkulačky) mezitím
> integrovalo Nominatim/OSM geokódování (`geocode(conn, place)`,
> cache `remeslo_geo_cache`, `NOMINATIM_URL`) přesně pro tenhle účel
> (město → lat/lon), zdarma, bez API klíče, už ověřené a živě
> používané. Viz sekce "UI srovnávače + vzdálenostní filtr" níž pro
> plán oživení.

**Co v repu NEEXISTUJE a musí se postavit od nuly**:
1. ~~Geokódování adresy → lat/lon~~ - ZAHOZENO výš, netýká se modulu 1.
   (Pro dohledatelnost: Mapy.com v1 REST geocoding vyžaduje API klíč -
   ověřeno přímo curl, `401 Unauthorized` bez klíče, navzdory prvotnímu
   shrnutí z websearch, že prý klíč nepotřebuje; zdarma ČÚZK/RÚIAN
   alternativa nemá dohledatelný `GeocodeServer` endpoint - kdyby se
   geo filtr v budoucnu vrátil, začínat tímhle stavem, ne od nuly.)
2. **Scraper pro 2-3 pilotní dodavatele** — teď PRIMÁRNÍ zdroj dat,
   ne doplněk. Riziko křehkosti/údržby zůstává stejné jako u Dogus
   vzoru, ale je vědomě přijaté (Robertovo rozhodnutí prioritu
   posunout, ne technické doporučení tohodle plánu).
3. **Jednoduchý admin formulář na ruční zadání ceny** (doplněk ke
   scraperu, ne náhrada).

**Kritéria výběru dodavatelů (Robert: "vést databázi VĚTŠINY
DŮLEŽITÝCH dodavatelů, ne úplně všech" - potřeba filtr, ne masový
scraping čehokoli, co existuje).** Stejný duch jako u Toscanaccia
`supplier_leads` (kvalitativní kontrola zdrojů, ne "sebrat vše, co
jde"), tady konkrétně 5 kritérií - dodavatel se do
`remeslo_price_sources` zapíše, jen když splní VŠECHNA:
1. **Velikost firmy**: velké nebo střední firmy (Robert - na startu
   cílit sem, ne na drobné lokální živnostníky-prodejce) - orientační
   signál: síť poboček, obrat/velikost katalogu, celostátní
   známost značky.
2. **Dosah**: kamenné pobočky NAPŘÍČ ČR, nebo e-shop s celostátním
   rozvozem - ne jedna lokální prodejna bez webu (jinak nemá smysl
   vzdálenostní filtr, který je klíčová hodnota srovnávače).
3. **Strukturovaný veřejný ceník**: e-shop/ceník s dostatečně
   strukturovanými daty (název položky + cena, ideálně i kód) -
   bez toho není co spolehlivě scrapovat (přesně proto Dogus skript
   potřeboval 2 parsery na 2 rozvržení stránek - u nestrukturovaného
   webu by to bylo ještě hůř).
4. **Relevance k cílené profesi** - dodavatel prodává materiál
   relevantní profesi/profesím, které modul 1 aktuálně pilotuje (viz
   krok 1 v "Co jde první implementovat" níž), ne libovolný sortiment.
5. **Šíře sortimentu** - mezi kandidáty splňujícími 1-4 se
   upřednostní ti s VĚTŠÍM katalogem (blíž Robertovu cíli "tisíce
   položek") - dva téměř identické menší dodavatele nemá smysl
   scrapovat oba, raději jeden širší.

**Rozsah scrapingu u KAŽDÉHO vybraného dodavatele (samostatné
upřesnění, Robert)**: jen **hlavní sortiment podle cílené profese**,
NE celý katalog dodavatele. I velký stavebninový dodavatel prodává
spoustu věcí, co s cílenou profesí nesouvisí (např. zahradní technika
u elektro-velkoobchodu) - scrapuje/zadává se jen podmnožina relevantní
zvolené profesi (přes `remeslo_material_category_professions`), ne
automaticky vše, co dodavatel nabízí. "Tisíce položek" tak vzniknou
souhrnem NAPŘÍČ dodavateli a profesemi v čase, ne z jednoho
vyčerpávajícího výpisu jednoho e-shopu.

"2-3 dodavatelé" v kroku 1 níž je startovní dávka PRVNÍHO pilotu, ne
natrvalo daný strop - kritéria výš jsou skutečná brána pro to, kdo se
časem do databáze dostane, jak se pokrytí profesí rozšiřuje.

### UI srovnávače pro řemeslníka + vzdálenostní filtr (bot13, 2026-08-20)

Zadání Robert (přesné znění): *"rozjet SROVNÁVÁNÍ CEN hlavního
sortimentu podle profesí (Modul 1, jeho původní účel - dosud existuje
jen backend, v remeslo.html není ani řádek UI)."* **Vlastník: bot13.**

**Zjištěno živě před psaním návrhu** - "ani řádek UI" je jen zčásti
přesné: `webapp/remeslo.html` má tab `tab-compare` ("Srovnávač cen
materiálu") s funkčním admin nástrojem (výběr kategorie → tabulka
produkt/dodavatel/cena/zdroj/odkaz seřazená podle ceny, + formulář
ručního zadání) - transparentnost (název produktu u dodavatele +
odkaz) je tak UŽ hotová. Co v něm chybí a je předmětem tohohle
doplňku: **filtr podle profese přihlášeného řemeslníka** (dnes
dropdown nabízí VŠECHNY kategorie napříč všemi profesemi bez
rozlišení) a **vzdálenostní filtr** (dnes žádný - viz "ZAHOZENO"
výš). Endpoint je navíc pořád `@admin_required` - `remeslnik` se k
němu vůbec nedostane.

**Stav dat (ověřeno živě)**: 68 `remeslo_material_categories`, 3510
`remeslo_material_prices`, 6 `remeslo_price_sources` (5 reálných
e-shopů + "Ruční zadání (admin)" pseudo-zdroj bez fyzické adresy).
`remeslo_material_category_professions` má **VŠECH 68 řádků na
`profession_id`=1 ("Instalatér")** - reálné srovnání dnes existuje
JEN pro tuhle profesi, přesně podle plánu "pilot na jednu profesi" v
sekci výš. Pro ostatních 13 profesí z Modulu 11 vrátí filtrovaný
dotaz prázdný seznam - UI to musí ukázat jako srozumitelný stav
("zatím žádná data pro tvoji profesi"), ne jako prázdnou/rozbitou
tabulku.

#### Geokódování - blocker vyřešen, žádná nová závislost

`api/remeslo_weather.py` (bot14, "počasí navázané na kalkulačky")
mezitím integrovalo přesně to, co modulu 1 dřív chybělo:
`geocode(conn, place)` - město → (lat, lon) přes Nominatim/OSM,
zdarma, bez API klíče, s POVINNOU cache (`remeslo_geo_cache`, klíč
`place` malými písmeny) a limitem 1 req/s (Nominatim usage policy).
Znovupoužije se BEZE ZMĚNY (`from remeslo_weather import geocode`),
žádný nový geokódovací kód, žádná nová tabulka.

**Přesnost je na úrovni MĚSTA, ne přesné adresy** - stejná
konvence jako u počasí (souřadnice zaokrouhlené, cache klíčovaná na
název místa). Pro "je dodavatel X blíž než Y" účel srovnávače je to
dostatečné, přesná ulice by jen zbytečně zatěžovala Nominatim.

#### Data k doplnění (jednorázově, ne za běhu)

1. **`remeslo_price_sources.address`/`latitude`/`longitude`** pro 5
   reálných dodavatelů - sídla dohledaná veřejně (ARES/firemní weby):

   | Dodavatel | Sídlo (město pro geokódování) |
   |---|---|
   | Ptáček - velkoobchod, a.s. | Praha |
   | AQUATOPSHOP s.r.o. | Záryby (okr. Mělník) |
   | HECKL s.r.o. | Kralupy nad Vltavou |
   | TZBcentrum s.r.o. (TZBeshop.cz) | Brno |
   | DEK a.s. | Praha |

   **Vědomé zjednodušení pro v1**: jde o SÍDLO firmy, ne nutně
   nejbližší pobočku - všech 5 jsou řetězce s pobočkami napříč ČR
   (kritérium 2 výběru dodavatelů výš), takže vzdálenost k sídlu je
   jen orientační proxy, ne přesná vzdálenost k nejbližšímu výdejnímu
   místu. Odpovídá to ale existujícímu schématu (1 lat/lon na
   `price_source`, ne tabulka poboček) - přesnější "nejbližší
   pobočka" by vyžadovalo novou tabulku a je to možné budoucí
   rozšíření, ne blocker pro tenhle krok. "Ruční zadání (admin)"
   zdroj zůstává bez adresy (`latitude IS NULL`) - u něj se vzdálenost
   nikdy nepočítá/nezobrazuje, zdroj se v porovnání ukáže vždy.
   Jednorázový skript (`scripts/2026-08-20_remeslo_geocode_sources.py`
   - `--kontrola`/`--apply` jako ostatní skripty modulu 1), ne
   migrace (adresy nejsou v repu k dohledání zpětně, jsou to živá
   data z DB).

2. **`remeslo_craftsmen.latitude`/`longitude`** - dopočítá se
   geokódováním `city` (pole už dnes existuje, sbírá ho "Můj profil"
   z Modulu 11) při KAŽDÉM uložení profilu (`PUT /api/remeslo/
   craftsmen/me`), ne při registraci (tam se `city` ještě nesbírá).
   Žádné nové pole na řemeslníkovi navíc - jen se začne používat, co
   tam už je.

#### Endpointy (rozšíření existujících, ne nové)

- **`GET /api/remeslo/categories?profession_id=`** → `remeslnik_or_
  admin_required`. Pro `remeslnik` se `profession_id` NEBERE z query
  parametru (stejná zásada jako `_require_own_craftsman_id` jinde) -
  vždy se použije vlastní `profession_id` z `current_craftsman()`,
  cizí hodnota v query se ignoruje/přepíše, ne 403 (tohle je čistě
  filtr vlastního zobrazení, ne cizí data).
- **`GET /api/remeslo/compare?category_id=`** → `remeslnik_or_admin_
  required`. Rozšíření odpovědi o `distance_km` u každé položky
  (Haversine, Python, žádná DB-side geo funkce - 3510 řádků je málo
  na to, aby se to muselo počítat v SQL) - `null`, když řemeslník
  NEBO zdroj nemá lat/lon (chybějící město, "Ruční zadání"). Nový
  parametr `?sort=distance` (výchozí zůstává cena, jako dnes -
  nejlevnější první je pořád hlavní účel, vzdálenost je doplňkový
  pohled, ne náhrada).
- **Kontrola vlastnictví u `category_id`** pro `remeslnik`: kategorie
  musí být navázaná (přes `remeslo_material_category_professions`) na
  JEHO profesi, jinak 403 - řemeslník nemá vidět srovnání pro cizí
  profesi, i kdyby uhodl/zkusil cizí `category_id`.

#### UI (`webapp/remeslo.html`, rozšíření `tab-compare`)

- Tab přidán do `REMESLNIK_ALLOWED_TABS`. Pro `remeslnik` roli:
  - Výběr kategorie (`remesloCategorySelect`) načítá jen kategorie
    VLASTNÍ profese (`?profession_id=` se pošle, i když ho backend
    stejně přepíše vlastní hodnotou - jde o to, aby se do dropdownu
    vůbec nedostaly cizí kategorie).
  - Žádné kategorie pro profesi → místo prázdné tabulky
    srozumitelná zpráva: *"Zatím žádná data pro tvoji profesi - modul
    pilotujeme na instalatérech, další profese přibývají postupně."*
  - Nový sloupec **Vzdálenost** v tabulce srovnání + přepínač řazení
    (cena / vzdálenost). Řádek bez vzdálenosti (chybí lat/lon) se
    zobrazí s "–", ne skrytý (pořád to je platná cenová nabídka).
  - Když `craftsman.city` není vyplněné vůbec → místo sloupce
    vzdálenosti nápověda *"Doplňte město v Můj profil pro
    vzdálenostní srovnání"* s odkazem na záložku Profil.
  - **Formulář ručního zadání ceny (`remesloManualAdd`) zůstává
    admin-only** (skrytý pro `remeslnik`) - je to nástroj kurace dat
    pro celý systém, ne osobní poznámka řemeslníka (stejný princip
    jako `is_mandatory`/`is_system` u Ceníku v Modulu 9 - kurace
    společných dat zůstává na adminovi).
- Pro `admin` roli: beze změny (žádný profesní filtr, žádná
  vzdálenost - admin spravuje data napříč všemi profesemi, osobní
  poloha adminovi nedává smysl).

#### Ověření

`test_client`: kategorie/compare scoping (`remeslnik` nedostane cizí
profesi ani při vyzkoušení cizího `category_id` → 403; prázdný
seznam pro profesi bez dat vrací validní prázdné pole, ne chybu),
`distance_km` výpočet na známých souřadnicích (kontrolní hodnota
Haversine vzorce), `sort=distance` řazení, chybějící lat/lon → `null`
bez pádu. Playwright: reálný `remeslnik` účet (profese Instalatér, s
vyplněným městem) vidí srovnání s vzdálenostmi, `remeslnik` jiné
profese vidí "zatím žádná data" stav, admin beze změny. Stejná
disciplína jako předchozí moduly - živé ověření přes skutečný
prohlížeč, ne jen `test_client` (viz poučení z dnešního rána -
frontend "kdo spouští načtení dat" bugy `test_client` neodhalí).

#### Doplněk: jednotný seznam dodavatelů napříč Srovnávačem a Ceníkem (Robert, 2026-08-20)

Zadání (přesné znění): *"Ve srovnávači musí být uvedeni právě oni, co
už máme jako dodavatele do kalkulátoru"* - JEDEN společný seznam
dodavatelů pro celý systém, ne dva oddělené světy.

**Zjištěný stav (dvě STRUKTURÁLNĚ ODDĚLENÉ představy o "dodavateli",
viz i `TASKS.md` nález bot10 "DŮLEŽITÁ REPRIORITIZACE")**:
- `remeslo_price_sources` (Srovnávač, Modul 1) - skutečná entita s
  webem/adresou/GPS/kritérii výběru (5 bodů výš), zdroj pro scrapery.
- `remeslo_pricelist_items.supplier` (Ceník, Modul 9) - obyčejný
  `VARCHAR(255)`, bez vazby, bez validace. **Ověřeno živě 2026-08-20:
  0 řádků v celém Ceníku má vyplněné `supplier` (0 řádků má vůbec
  cenu) - žádná migrace historických dat není potřeba, pole se
  nepoužívá.**

**Rozhodnutí**: `remeslo_price_sources` se stává JEDINÝM zdrojem
pravdy o dodavatelích pro CELÝ systém (Srovnávač i Ceník). Robertův
koncept navíc počítá s tím, že řemeslník nakupuje i mimo velké sítě
(5 kritérií výš jsou brána pro Srovnávač/scrapery, ne omezení, KDE
si řemeslník smí něco koupit) - proto se tabulka rozšiřuje o STEJNÝ
vzor, jaký už má `remeslo_pricelist_categories` ("Přidat vlastní
kategorii"):

```sql
ALTER TABLE remeslo_price_sources
  ADD COLUMN craftsman_id INT NULL AFTER id;  -- NULL = sdileny/oficialni
                                               -- (prosel 5 kriterii, ve
                                               -- Srovnavaci), hodnota =
                                               -- VLASTNI dodavatel PRAVE
                                               -- tohoto remeslnika (mistni
                                               -- prodejna, nesplnuje
                                               -- kriteria, jen pro jeho Cenik)

-- UNIQUE(supplier_name) by kolidovalo, kdyz dva ruzni remeslnici
-- pridaji vlastniho dodavatele se stejnym nazvem ("Misto zelezarstvi") -
-- nahrazeno slozenym klicem (NULL craftsman_id = porad globalne
-- unikatni nazev mezi oficialnimi, ruzni remeslnici muzou mit
-- shodne vlastni nazvy mezi sebou).
ALTER TABLE remeslo_price_sources
  DROP INDEX supplier_name,
  ADD UNIQUE KEY uq_source_name_per_craftsman (craftsman_id, supplier_name);

ALTER TABLE remeslo_pricelist_items
  ADD COLUMN supplier_source_id INT NULL AFTER supplier;
  -- `supplier` (VARCHAR) NEMAZAT hned - viz "postup nasazení" níž.
```

**U položky v Ceníku**: `supplier` textové pole nahrazeno výběrem ze
`remeslo_price_sources` (oficiální dodavatelé + VLASTNÍ dodavatelé
tohoto řemeslníka), s volbou "+ Přidat vlastního dodavatele" přímo
ve formuláři (jen název, zbytek - web/adresa/GPS - volitelné,
`craftsman_id`=vlastní, `origin`='manual'). Endpointy:
- `GET /api/remeslo/price-sources` (rozšířeno o `remeslnik_or_admin_
  required`) - pro `remeslnik` vrací `WHERE craftsman_id IS NULL OR
  craftsman_id=<vlastní>`, pro `admin` beze změny (jen oficiální,
  spravuje je admin).
- `POST /api/remeslo/price-sources` pro `remeslnik` zakládá VŽDY s
  `craftsman_id`=vlastní (nemůže založit "oficiálního" dodavatele,
  to zůstává admin akce se scrape kritérii).
- `POST/PUT /api/remeslo/pricelist/items` přijímá `supplier_source_id`
  místo `supplier` - musí patřit `NULL` NEBO vlastnímu `craftsman_id`
  (stejná kontrola jako u kategorie, viz Modul 9 self-service výš).

**Opačný směr (bidirekční propojení, Robert)**: u položky v Ceníku,
která má `supplier_source_id` ukazující na OFICIÁLNÍHO dodavatele
(`craftsman_id IS NULL`), se dá dohledat katalogová cena STEJNÉHO
dodavatele ve Srovnávači pro srovnání s vlastní cenou v Ceníku.
**Poctivé omezení k zapsání, ne zamlčet**: `remeslo_pricelist_
categories` (Ceník) a `remeslo_material_categories` (Srovnávač) jsou
DVĚ ODDĚLENÉ tabulky bez FK mezi sebou (bot10 nález - scraper OBI
"jen připravuje půdu stejnými názvy kategorií, mapování je
samostatný úkol"). V1 tohohle propojení proto párování dělá
**best-effort podle NÁZVU kategorie** (`remeslo_pricelist_categories.
name` = `remeslo_material_categories.name`), ne podle ID - u
kategorií, které se název neshoduje (typicky nové OBI kategorie, než
je někdo sesouhlasí), se katalogová cena prostě NEZOBRAZÍ (`null`,
ne chyba) - přesné 1:1 sjednocení obou katalogů kategorií (aby
kalkulačky konečně počítaly Kč ze scrapnutých dat) je ten samostatný
"propojení/import" úkol z `TASKS.md`, tenhle doplněk ho nenahrazuje,
jen navazuje kompatibilním směrem (sdílení DODAVATELE, ne dat o ceně).
- `GET /api/remeslo/pricelist/items` (existující self-service
  endpoint) rozšířen o `catalog_price_czk`/`catalog_product_name`
  u položek s oficiálním `supplier_source_id` (LEFT JOIN podle jména
  kategorie, `NULL` když se nenajde shoda).

**Postup nasazení** (`supplier` sloupec zůstává, ne mazán rovnou):
1. Migrace přidá `craftsman_id`/`supplier_source_id`, přepíše UNIQUE.
2. Backend přepnut na `supplier_source_id`, `supplier` se PŘESTANE
   zapisovat (formulář ho už neukazuje).
3. Po jedné otestované iteraci v produkci (Robertovo potvrzení, že
   výběr dodavatele funguje) `supplier` sloupec smazat jako
   samostatný úklidový krok - 0 řádků s daty ho stejně nepotřebuje
   zachovat "pro historii".

Nahlášeno Robertovi po dopsání týhle sekce, pokračuji stavbou.

### Obnova cen - dvě URL cesty s oddělenou politikou aktualizace (Robert, 2026-08-20, TRVALÉ PRAVIDLO)

**Problém, který pravidlo řeší**: kompletní scrape jednoho dodavatele
(projít kategorie, stránkování, najít/zařadit produkty) trvá ~40 min -
u 7-10 dodavatelů je to půl dne, a hned druhý den jsou ceny zase o den
starší. Plošné pravidelné přescrapování CELÉHO katalogu každého
dodavatele takhle dlouhodobě neškáluje.

**Řešení - u každé položky `remeslo_material_prices` se sleduje DVOJICE
URL, každá s VLASTNÍ politikou aktualizace, ne jedna společná:**

1. **UMÍSTĚNÍ POLOŽKY** (`product_url`, existující sloupec) - adresa
   produktové stránky u dodavatele. Aktualizuje se/ověřuje **JEN při
   problému se získáním ceny** - tedy drahé dohledávání (dodavatel
   mohl produkt přejmenovat/přesunout/zrušit) se spouští AŽ jako
   fallback, když selže (2), ne rutinně.
2. **UMÍSTĚNÍ SAMOTNÉ CENY** (`price_source_url`, nový sloupec) - přímý
   zdroj ceny: lehký AJAX/API endpoint e-shopu vracející cenu/
   dostupnost, JSON-LD `Offer.price` blok, nebo konkrétní strukturovaná
   cesta k ceně na stránce. Aktualizuje se **individuálně** (per
   položka / per dodavatel, ne plošně dávkou) - tohle je BĚŽNÁ,
   levná a rychlá cesta obnovy (jeden GET, žádné parsování názvu/
   popisu/kategorie znovu).

Běžná obnova sahá JEN na (2). Teprve když (2) opakovaně selže (produkt
zmizel, URL vrací 404, cena nejde z odpovědi vytáhnout), spustí se
dražší (1). **Přesnou podobu (2) si určuje KAŽDÝ dodavatel zvlášť**
podle toho, co reálně nabízí - u někoho to bude oddělený API endpoint,
u jiného JSON-LD v hlavičce produktové stránky, u dalšího přímo
konkrétní CSS/regex selektor na produktové stránce. **Pokud u dodavatele
samostatný (rychlejší) zdroj ceny neexistuje, je v pořádku použít
produktovou stránku i pro (2)** - ale MUSÍ se to přiznat/zapsat, ať je
vidět, kde je mechanismus slabší (stejná cena za dvě různé URL, žádné
tiché předstírání, že jde o odlehčenou cestu, když není).

**Ověřeno živě (bot10, 2026-08-20) na produktových stránkách (NE na
kategoriích-výpisech, které mají jinou HTML strukturu) - stav per
dodavatel k tomuto zápisu:**

| Dodavatel | `price_source_url` = | Poznámka |
|---|---|---|
| HECKL | stejná URL jako `product_url`, parsuje se `<script type="application/ld+json">` blok, klíč `offers.price` | Čisté schema.org `Product`/`Offer`, nejrobustnější případ - přežije redesign HTML, dokud zůstane JSON-LD. |
| DEK.cz | stejná URL, stejný JSON-LD `Product`/`Offer` mechanismus jako HECKL (sdílený `_extract_jsonld_product_offer`) | Ověřeno živě 2026-08-20 (bot10) - cena JIŽ S DPH (25,92 v JSON-LD = "25,92 Kč s DPH", odlišeno od "21,42 Kč bez DPH"). **POZOR na past**: DEK vykresluje tag jako `<script type="application/ld+json" >` (MEZERA před `>`), zatímco HECKL/Mereo bez mezery - regex musí tolerovat obojí, jinak DEK tiše selže (0 shod, ne chyba). |
| Mereo.cz | stejná URL, stejný JSON-LD `Product`/`Offer` mechanismus | Ověřeno živě 2026-08-20 (bot10) - cena JIŽ S DPH (1799 v JSON-LD = "1 799 Kč s DPH"), navíc nezávisle potvrzeno `<meta itemprop="price">` mikrodaty i vlastním `upgates.product.price.withVat` JS objektem na téže stránce (trojitá shoda, nejrobustnější ze všech ověřených dodavatelů). |
| OBI.cz | stejná URL jako `product_url`, parsuje se Google Analytics `dataLayer` JSON (`ecommerce.detail.products[0].price`) | Taky strukturovaná, spolehlivá, i když ne schema.org standard. **POZOR na past**: cena je BEZ DPH, nutný přepočet `*1,21`. |
| Ptáček-shop.cz | stejná URL jako `product_url`, parsuje se `dataLayer.push(...).products.totalValue` JSON klíč přímo v `<head>` (server-rendered, ne JS/AJAX) | Ověřeno živě 2026-08-20 (bot10) na 3 produktech - dřívější zápis "cena není server-rendered" byl mylný (pravděpodobně zastaralý/vadný test), skutečná stránka `totalValue` obsahuje a přesně odpovídá viditelné ceně "včetně DPH" (10913.00≈"10 913 Kč včetně DPH" atd.), žádný přepočet DPH potřeba. Klíč se na stránce vyskytuje jen jednou. |
| HORNBACH.cz | stejná URL, parsuje se `window.__ARTICLE_DETAIL_APOLLO_STATE__` (Apollo GraphQL cache serializovaná do stránky), klíč `defaultPrice.price` (PRVNÍ výskyt) | Ověřeno živě 2026-08-20 (bot10) na 2 produktech - **dřívější zápis "aktivní bot-challenge, nedostupné" byl mylný** (bez problému 2× HTTP 200 s běžným UA, žádný challenge). **DVOJITÁ past**: (1) JSON-LD `offers[].price` NENÍ použitelná - je to cena za CELOU PALETU, ne za kus (36 Kč/ks × paleta 280 ks = "10080.00" v JSON-LD). (2) i uvnitř Apollo stavu není každý `defaultPrice` správný - u produktu s množstevní slevou existuje DRUHÝ výskyt uvnitř `volumePriceList` (nižší cena za větší odběr) - musí se vzít VŽDY JEN PRVNÍ výskyt. Křehčí mechanismus než JSON-LD u ostatních - spoléhá na pořadí serializace, ne na explicitní schéma. |
| Aquatopshop.cz | stejná URL, JSON-LD `Product`/`Offer` (sdílený extraktor), ale Product je zabalený v poli `@graph` (`{"@graph":[{"@type":"Product",...}]}`), ne top-level jako u HECKL | Ověřeno živě 2026-08-20 (bot10) - cena JIŽ S DPH (9614 = protipól "7 945,45 Kč bez DPH" ve vlastním `eshopDataLayer` objektu, matematicky 7945,45×1,21=9614,0 přesně). Zjištěno cestou: DB cena byla 8014 (starší, 2026-08-17), živá cena 9614 - GENUINNÍ posun ceny za pár dní, ne chyba mechanismu (přesně k tomuhle je "Cena na vyžádání" určená). |
| TZBeshop.cz | stejná URL, stejný `@graph`-obalený JSON-LD vzor jako Aquatopshop | Ověřeno živě 2026-08-20 (bot10) - cena JIŽ S DPH (857,00 = "857,00 Kč s DPH / ks"). **Dřívější zápis "žádný Offer.price" byl mylný** - `Offer.price` tam JE, jen ho předchozí test nenašel, protože u NĚKTERÝCH produktů je JSON-LD technicky NEPLATNÝ (název obsahuje neescapovanou uvozovku u palcových rozměrů, např. `3/4"`, což `json.loads` na celém `@graph` bloku rozbije). Řešeno regexovým fallbackem, když `json.loads` selže - ověřeno na obou variantách (1 produkt s vadou, 1 bez ní). |

**Datový model**: nový sloupec `remeslo_material_prices.price_source_url`
(VARCHAR, nullable = "použij `product_url`"), extrakční LOGIKA (jak z
dané URL vytáhnout cenu) je kód per `source_id`, ne DB sloupec - je to
vlastnost DODAVATELE (pevná strategie), ne jednotlivé položky, i když
samotná URL se u položek liší.

**Provozní důsledky**: on-demand obnova (kalkulačka/srovnávač narazí
na cenu starší než práh) smí sáhnout JEN na (2), s krátkým timeoutem,
ať pomalý dodavatel neblokuje odpověď uživateli - při timeoutu/chybě
se vrátí stará cena se zobrazeným stářím, ne čekání. Dohledávání (1) je
vyhrazené pro asynchronní/dávkové doběhnutí (typicky na pozadí), nikdy
ne v cestě uživatelovy odpovědi.

**Toto pravidlo platí i pro BUDOUCÍ dodavatele** přidávané do Modulu 1 -
při zavádění nového zdroje se od začátku zjišťuje/zapisuje, jestli má
vlastní (2), nebo jestli sdílí URL s (1) a proč.

Nový, ne v původní verzi plánu (přidáno na Robertův pokyn 2026-08-17).
Sledování zakázek KONKRÉTNÍHO řemeslníka (ne našeho vztahu k němu -
to řeší `remeslo_craftsmen.status` v modulu 4) - "co řemeslníkovi
ušetří čas" v duchu vize.

```sql
CREATE TABLE remeslo_jobs (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    craftsman_id    INT NOT NULL,                  -- FK remeslo_craftsmen
    customer_name   VARCHAR(255) NOT NULL,
    description     TEXT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'planovano',  -- planovano/probiha/hotovo/fakturovano
    start_date      DATE NULL,
    due_date        DATE NULL,
    price_czk       DECIMAL(10,2) NULL,
    costs_czk       DECIMAL(10,2) NULL,             -- naklady na zakazku (material apod.) - viz financni dashboard nize
    hours_worked    DECIMAL(6,2) NULL,             -- VOLITELNE - jen pro remeslniky fakturujici hodinovkou
    note            TEXT NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```
Jednoduchý CRUD list+detail, stejný vzor jako `api/purchase_orders.py`
(bez schvalovacích stavů navíc - tady jde jen o vlastní evidenci
řemeslníka, ne o transakci vůči nám). Podrobný návrh (admin UI,
případně mobilní přístup pro řemeslníka samotného) přijde na řadu,
až se dostane k implementaci - zatím jen datový model.

**Doplnění po `REMESLO_PRUZKUM_WORKFLOW_APPS.md` (bot10, 2026-08-18,
schváleno Robertem přes bot3)** - průzkum appek na řízení denní práce
řemeslníka (Jobber/Housecall Pro/Tradify/Fergus + české PROFIDAT/
Řemeslník PRO/Timoty.cz) ukázal 2 prvky, co má prakticky každá
zkoumaná appka a co v původním návrhu chybělo:
1. `hours_worked` výš - VOLITELNÉ pole (ne všechny appky/řemeslníci
   to potřebují - jen ti co fakturují hodinovkou, ne paušálem/
   položkově).
2. **Foto-dokumentace zakázky** (před/po zásahu) - u Housecall Pro i
   Řemeslník PRO jde o jednu z hlavních funkcí, ne doplněk. Řešeno
   BEZ nové tabulky/sloupce - znovupoužití existujícího obecného
   "připojitelného" fotogalerie modulu `api/gallery_items.py`
   (`content_gallery_items`, polymorfní `owner_type`/`owner_id`,
   dnes `'category'|'product'|'document'|'stock_movement'|'po_item'`)
   s novou hodnotou `owner_type='remeslo_job'`, `owner_id=remeslo_jobs.id`
   - přesně stejný vzor, jakým byl modul navržen (viz jeho vlastní
     docstring: "obecný 'připojitelný' k libovolnému vlastníkovi").
   Implementace: přidat `'remeslo_job'` do `delete_items_for_owner()`
   volání (úklid osiřelých fotek při smazání zakázky, stejně jako
   `categories_delete`/`shop_products_delete` dnes) + použít stávající
   `POST /api/gallery-items`/`GET /api/gallery-items` s tímhle
   `owner_type` z UI evidence zakázek - ŽÁDNÝ nový endpoint.

GPS sledování vozidel (Housecall Pro) a pokročilý reporting
(ServiceTitan) vědomě NEPŘEBÍRÁME - cílí na firmy s víc zaměstnanci/
vozidly, ne na jednotlivého řemeslníka/malou partu (náš cílový
segment, stejně jako Jobber/Tradify/Řemeslník PRO).

Modul 3 (Jednoduché CRM, níž) - průzkum POTVRDIL současný návrh
(`crm_leads.craftsman_id`, žádná nová tabulka) beze změny - přesně
tak fungují i konkurenční české appky (PROFIDAT/Řemeslník PRO/
EasyZakázky všechny spojují klienta↔zakázky↔fakturu v jednom
jednoduchém modelu, ne odděleným "CRM produktem").

**Finanční dashboard (2026-08-18, po hloubkovém rozboru PROFIDATu -
REMESLO_PRUZKUM_WORKFLOW_APPS.md sekce C, schváleno Robertem přes
bot3)** - PROFIDATova nejsilnější/nejodlišnější funkce (zisk/marže/
Kč-hod per zakázka), zjištěná přímo z jejich veřejně dostupného JS
kódu appky (žádné obcházení přihlášení, jen čtení statických
souborů). `costs_czk` výš je jediný nový sloupec - `profit`/
`margin_percent`/`profit_per_hour` se NEUKLÁDAJÍ, počítají se za
běhu (`api/remeslo.py::_job_finance()`), je to čistá funkce 3
sloupců. Klasifikace zakázky (Ztrátová/Riziková/Slabší marže/Zdravá/
Výborná) 1:1 převzala prahy z PROFIDATu jako reálně otestovanou
výchozí hodnotu (marže <0/<5/<15/<30/≥30 %, Kč/hod <300 = samostatné
varování "nízký výdělek") - konstanty na začátku modulu, snadno
upravitelné. `GET /api/remeslo/jobs/summary` vrací souhrn za období
+ žebříček nejvýnosnějších zakázek + jednořádkový generovaný
"insight" text (stejný UX nápad jako PROFIDATův dashboard banner).
PDF protokol (2 typy u PROFIDATu - průběžný/závěrečný) záměrně MIMO
scope teď - až přijde na řadu, konfigurátor už má PDF pipeline
(`reportlab`, `api/documents.py`), žádná nová závislost.

## Modul 3 — Jednoduché CRM (rozšíření `api/crm.py`, NE nová stavba)

Robertovo výslovné zadání: znovupoužít stávající `crm_leads`/
`crm_lead_messages` (dnes zachytává poptávky do NAŠEHO e-shopu přes
`crm.classify_incoming_email`/`find_or_create_lead`), ne stavět
paralelní systém.

**Návrh rozšíření (minimální zásah, ne redesign)**:
```sql
ALTER TABLE crm_leads ADD COLUMN craftsman_id INT NULL;  -- FK remeslo_craftsmen
-- NULL = puvodni vyznam (nas vlastni e-shopovy lead, beze zmeny
-- chovani stavajiciho kodu). Vyplnene = lead patri KONKRETNIMU
-- remeslnikovi jako JEHO vlastni "mini-CRM" zaznam, ne nas.
```
Admin (nebo časem sám řemeslník, pokud dostane vlastní přístup - mimo
rozsah tohohle konceptu) filtruje/spravuje leady podle
`craftsman_id`, stejným UI vzorem, jaký `crm.py`/admin.html už mají
pro poptávky dnes - žádná nová tabulka, žádné nové API endpointy
kromě filtru navíc. Nejmenší možný zásah, jak si Robert vyžádal.

## Modul 4 — Ověřovací mechanismus (doplněk databáze řemeslníků)

`REMESLO_PRUZKUM.md` doporučení č.1 (Checkatrade model - PRŮBĚŽNÉ
ověřování, ne jednorázový vstupní check + SeznamRemeslniku.cz "doklad
jako důkaz reference"). Staví se AŽ po modulech 1-3 (nižší priorita,
Robertovo rozhodnutí), ale datový model zůstává zapsaný teď, ať
zapadne do `remeslo_craftsmen`/`code` základu z modulu 1 bez potřeby
zpětných úprav.

```sql
CREATE TABLE remeslo_verification_checks (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    craftsman_id    INT NOT NULL,                   -- FK remeslo_craftsmen
    check_type      VARCHAR(50) NOT NULL,            -- 'opravneni_k_remeslu' | 'reference_s_dokladem' | 'insolvencni_rejstrik' | ...
    status          VARCHAR(20) NOT NULL DEFAULT 'ceka',  -- ceka/proslo/neproslo
    evidence_note   TEXT NULL,
    document_photo_analysis_id INT NULL,             -- FK budoucí remeslo_photo_analyses (modul 5), az bude existovat
    checked_by      INT NULL,                        -- FK app_users
    checked_at      DATETIME NULL,
    valid_until     DATETIME NULL,                   -- REVALIDACE, ne jednorazovy check
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### Ověřování PŘI ZAKLÁDÁNÍ řemeslníka (Robert, 2026-08-19)

Robert: *"Při zakládání řemeslníka chceme rovnou ověřovat v dostupných
registrech bezúhonnost, platnost oprávnění podnikat, bezdlužnost a
navrhni ještě další kritéria."* Tím se Modul 4 posouvá z "až po
modulech 1-3" na aktivní - je to zároveň podmínka pro spuštění už
hotového, ale flagem vypnutého Modulu 10 (Faktury/Finance).

**DŮLEŽITÉ ROZLIŠENÍ, které se nesmí zamlčet:** ne všechna tři
Robertova kritéria jsou veřejně strojově dostupná. Míchat je do jednoho
"ověřeno" štítku by znamenalo tvrdit uživatelům víc, než reálně víme.
Proto se dělí na tři pásma podle toho, jak se dají získat:

**Pásmo A — plně automatické, veřejné, zdarma** (dotaz proběhne
okamžitě při zakládání, bez součinnosti řemeslníka):

| Kritérium | Zdroj | Poznámka |
|---|---|---|
| Existence a stav subjektu | **ARES** (`ares.gov.cz`) | **Už v projektu je** - `api/scene_offers.py` `public_ares_lookup()`, znovupoužít, nepsat znovu |
| Platnost živnostenského oprávnění + obory činnosti | **RŽP** (živnostenský rejstřík, přes ARES) | pokrývá Robertovo *"platnost oprávnění podnikat"* |
| Insolvence | **ISIR** (`isir.justice.cz`) | veřejné, strojově dostupné |
| Nespolehlivý plátce DPH | **ADIS / MFČR** | **kriticky důležité pro fakturaci**: u nespolehlivého plátce ručí odběratel za neodvedenou DPH - přímá finanční škoda pro klienta řemeslníka |
| Zveřejněný bankovní účet plátce DPH | ADIS | platba na nezveřejněný účet zakládá ručení za DPH |
| Statutární orgán, likvidace, datum vzniku | **Veřejný rejstřík** (justice.cz) | délka podnikání jako proxy zkušenosti |

**Pásmo B — vyžaduje SOUČINNOST řemeslníka** (nelze zjistit bez něj,
appka o doklad požádá a eviduje jeho platnost/expiraci):

- **Bezúhonnost** — výpis z Rejstříku trestů **NENÍ veřejný**. Zjistit
  ho o někom bez jeho souhlasu nejde (a jde o údaje o trestné činnosti,
  GDPR čl. 10 - zvlášť chráněná kategorie). Řešení: řemeslník doloží
  výpis sám (CzechPOINT/datová schránka), appka eviduje datum vydání +
  expiraci, revalidace po X měsících.
  Pozn.: bezúhonnost je zároveň zákonná podmínka provozování živnosti,
  takže **platné živnostenské oprávnění ji nepřímo indikuje** - to je
  automatizovatelné (pásmo A) a pro většinu případů dostatečné.
- **Bezdlužnost** — potvrzení od **FÚ**, **ČSSZ** a **zdravotní
  pojišťovny** taky nejsou veřejné. Doloží řemeslník, appka eviduje
  platnost (potvrzení mají omezenou dobu - proto `valid_until` výš).
- **Pojištění odpovědnosti za škodu** — není v žádném registru, doloží
  se pojistnou smlouvou. Pro klienta je to prakticky nejdůležitější
  papír vůbec (kdo zaplatí vytopeného souseda).
- **Odborná způsobilost u vázaných/regulovaných činností** — elektro
  (vyhláška 250/2021 Sb., dřív "vyhláška 50"), plyn, tlaková zařízení,
  revizní technici, práce ve výškách. RŽP ukáže, že subjekt živnost MÁ,
  ale konkrétní osobní certifikát doloží řemeslník.

**Pásmo C — vlastní/měkká kritéria** (návrh bot3 nad rámec zadání,
levné na implementaci, vysoká vypovídací hodnota):

- **Délka podnikání** (z ARES) - subjekt založený před týdnem je jiné
  riziko než ten po 12 letech.
- **Sídlo na virtuální adrese** - porovnat adresu proti známým
  "sídlo-na-adresu" poskytovatelům; není to samo o sobě problém, ale
  v kombinaci s čerstvým IČO je to signál.
- **Historie změn statutárního orgánu / názvu** (justice.cz) - časté
  změny bývají červená vlajka.
- **Shoda jména subjektu s prezentovaným jménem** - řemeslník se v
  profilu prezentuje jinak, než jak je zapsaný.
- **Reference s dokladem** - už zapsané v `check_type` výš
  (SeznamRemeslniku.cz vzor z `REMESLO_PRUZKUM.md`).

**Zásady pro implementaci:**
1. **Nikdy nezobrazovat jedno souhrnné "ověřeno"** - klient musí vidět,
   CO přesně bylo ověřeno a jak (automaticky z registru vs. doloženo
   řemeslníkem). Jinak appka ručí za něco, co neví.
2. **Průběžná revalidace, ne jednorázový vstupní check** (Checkatrade
   model, `valid_until` už v modelu) - živnost může být pozastavena,
   plátce se může stát nespolehlivým, potvrzení expirují.
3. **Selhání dotazu ≠ neprošel** - když registr neodpoví, stav zůstává
   `ceka`, ne `neproslo`.
4. Založení řemeslníka **nesmí blokovat** čekání na registry - stejný
   async vzor jako hlasové poznámky (zapiš, dotazuj na pozadí).
5. GDPR: údaje o trestné činnosti (pásmo B) mají zvláštní režim -
   uchovávat jen fakt "doloženo + do kdy", ne samotný dokument déle,
   než je nezbytné.

### Návrh implementace 1. iterace (bot14, 2026-08-19, čeká na schválení)

**Dostupnost registrů ŽIVĚ OVĚŘENA před psaním návrhu** (2026-08-19,
testovací IČO 45274649/ČEZ): ARES RŽP větev
(`/ekonomicke-subjekty-rzp/{ico}`) vrací seznam živností se stavem -
OK; ADIS nespolehlivý plátce (SOAP `adisrws.mfcr.cz`, bez klíče) vrací
`nespolehlivyPlatce="NE"` - OK; ISIR veřejná WS
(`isir.justice.cz:8443/isir_cuzk_ws`, SOAP) žije a validuje vstup
(jen chce elementy bez namespace - detail pro implementaci). Žádný
z registrů nepotřebuje API klíč ani registraci.

**Rozsah 1. iterace:**
- **Pásmo A (automaticky)**: 4 kontroly - `ares_existence` (subjekt
  existuje + stav + datum vzniku), `rzp_zivnost` (aspoň jedna aktivní
  živnost; seznam oborů do `result_detail`), `isir_insolvence`
  (žádné aktivní insolvenční řízení), `dph_nespolehlivy` (jen pro
  plátce DPH - neplátce dostane status `netyka_se`, viz níž).
- **Pásmo C zdarma s tím**: `delka_podnikani` se NEukládá jako vlastní
  check - datum vzniku je v `result_detail` ARES checku a UI ho jen
  zobrazí ("podniká od X, tj. Y let"). Žádná další tabulka/logika.
- **Pásmo B (evidence doložení)**: 5 typů - `bezuhonnost`,
  `bezdluznost_fu`, `bezdluznost_cssz`, `bezdluznost_zp`,
  `pojisteni_odpovednosti` (+ `odborna_zpusobilost` jako 6. typ,
  volitelně zadávaný vícekrát s poznámkou o jaký certifikát jde).
  Admin zapíše "doloženo dne + platí do + poznámka" - ŽÁDNÝ upload
  dokumentu v 1. iteraci (GDPR zásada 5: u bezúhonnosti se dokument
  stejně nemá skladovat; pro ostatní jde doplnit později přes
  gallery_items vzor, až o to Robert požádá).
- **Odloženo na později** (vědomě mimo 1. iteraci): zveřejněné bankovní
  účty plátce DPH (další ADIS dotaz - přidá se, až bude fakturace
  spuštěná naostro), historie změn statutára, detekce virtuálního
  sídla, odznak na veřejném profilu (Modul 7) - ten až Robert potvrdí
  vizuál.

**Schéma** (`remeslo_verification_checks` z náčrtu výš, upřesnění;
DB: Remeslnik, migrace přes `api/db_migrate_remeslo.py`):
- `status`: `ceka` / `proslo` / `neproslo` / `netyka_se` (nové -
  např. DPH check u neplátce; bez něj by neplátce věčně visel v
  "čeká" a kazil přehled) / `dolozeno` (pásmo B - terminologicky
  odlišené od `proslo`, protože appka NEověřila obsah, jen eviduje
  doložení - zásada 1).
- Nové sloupce: `source` (`auto`/`dolozeno`), `result_detail` TEXT
  (JSON výtah odpovědi registru - doklad "z čeho se stav vzal", stejný
  princip transparentnosti jako `dogus_list_price_usd` u cen),
  `attempts` INT + `last_attempt_at` DATETIME (viditelnost opakovaných
  selhání registru - po N pokusech UI ukáže "registr opakovaně
  nedostupný", stav ale zůstává `ceka`, zásada 3).
- `checked_by`/`document_photo_analysis_id` zůstávají obyčejné INT bez
  FK (cross-DB FK nejde - stejný vzor jako `author_user_id` jinde).
- UNIQUE KEY `(craftsman_id, check_type)` pro pásmo A (1 aktuální stav
  na kontrolu - historie běhů se NEarchivuje v 1. iteraci, jen
  poslední výsledek; u `odborna_zpusobilost` unikátnost neplatí -
  řemeslník může doložit víc certifikátů → bez unique, rozlišeno v
  aplikační logice).

**Async zpracování**: nový malý worker
`api/remeslo_verification_worker.py` + systemd unita (1:1 vzor
`konfigurator-remeslo-voice-worker.service` - poll DB fronty, ale BEZ
Whisperu, takže žádné RAM nároky). Proč worker a ne background thread
v gunicornu: (a) přesně tenhle vzor už v projektu běží a je ověřený,
(b) retry zadarmo - řádek zůstane `ceka` a příští tik ho zkusí znovu,
(c) **revalidace zadarmo** - stejný poll navíc jednou za hodinu
re-enqueuene `auto` checky s `valid_until < NOW()` (výchozí platnost
automatického checku: 30 dní), čímž je zásada 2 splněná bez cronu
navíc. Worker čte/píše VÝHRADNĚ Remeslnik DB (`REMESLO_DB_*`).

**Tok při založení řemeslníka**: `remeslo_craftsman_create()` po
INSERTu řemeslníka s vyplněným IČO vloží 4 řádky pásma A se `status=
'ceka'` (+ u neplátce DPH rovnou `netyka_se` pro DPH check) - žádné
čekání na registry (zásada 4). Bez IČO se nic neenqueuje a UI ukáže
"Doplňte IČO pro automatické ověření". Doplnění IČO později (update) →
enqueue při updatu. Tlačítko "Spustit ověření znovu" v UI = re-enqueue
(reset na `ceka`).

**API** (všechno `@admin_required`, stejně jako zbytek Řemesla):
- `GET /api/remeslo/craftsmen/<id>/verification` - všechny checky
  seskupené po pásmech + odvozené info (délka podnikání).
- `POST /api/remeslo/craftsmen/<id>/verification/run` - re-enqueue
  pásma A.
- `PUT /api/remeslo/verification/<check_id>` - zápis doložení pásma B
  (`status='dolozeno'`, `valid_until`, `evidence_note`, `checked_by`
  = aktuální admin).

**UI** (`webapp/remeslo.html`, tab Řemeslníci): sekce "Ověření" v
modalu řemeslníka - tabulka po pásmech (název kontroly, jak ověřeno
[automaticky z registru / doloženo řemeslníkem - zásada 1], stav
badge, kdy, platí do, poznámka), tlačítko "Spustit ověření znovu",
formulář pro zápis doložení u pásma B. ŽÁDNÝ souhrnný "ověřeno"
badge nikde.

**Ověření**: `test_client` (enqueue při create s IČO/bez IČO, PUT
doložení, stavové přechody, `netyka_se` u neplátce) + živý běh workeru
proti reálným registrům s reálným IČO + Playwright (reálná session,
celý flow v UI). Stejná disciplína jako Modul 10.

## Modul 5 — Foto-analýzy a budoucí crowdsourcing (deprioritizováno)

Beze změny oproti dřívější verzi plánu co do TECHNICKÉHO návrhu
(multimodální `/api/ai/generate` vzor, `tools` schémata, staging přes
`capture.html`/`incoming_documents.py` vzor) - jen priorita klesla na
poslední místo před akvizicí. Blokátory: neplatný
`ANTHROPIC_API_KEY` + Robertovo rozhodnutí č.8 výš (crowdsourcing má
smysl AŽ s existující uživatelskou základnou, ne na startu).

Až přijde na řadu, `analysis_type='cteni_faktury_nabidky'` bude psát
do `remeslo_material_prices` s `origin='crowdsourced'` a vyplněným
`contributed_by_craftsman_id`/`source_photo_analysis_id` - schéma
z modulu 1 je na tohle už teď připravené, nebude potřeba migrace
navíc, jen nová aplikační logika.

## Modul 6 — Analýzy, jak získat zájem řemeslníků (akvizice)

Beze změny oproti dřívější verzi - primárně analytická/research
práce nad daty modulu 1 (`remeslo_craftsmen.status`/`.note`, stejný
vzor jako Toscanaccio `chef_outreach`), ne systém k naprogramování.
`REMESLO_PRUZKUM.md` doporučení č.6 (Remsygo.cz školní/učňovský
přesah) jako dlouhodobá inspirace, ne okamžitá stavba.

## Modul 7 — Mini-web řemeslníka (veřejný profil + neveřejné pokyny spolupracovníkům)

Robert, 2026-08-19: appka "musí fungovat tak, že se dá komplexně řídit
hlasem a foťákem" - stejná filozofie (minimum psaní/klikání) se teď
rozšiřuje i na týmovou spolupráci. Nápad prošel několika koly
upřesnění v konverzaci, výsledný tvar (obě části na STEJNÉ doméně/
mini-webu, ale s jinou viditelností):

**Část A — veřejný profil (SEO, dohledatelný)** - struktura (návrh,
čeká na upřesnění/schválení):

- **URL**: `https://autovestavby.logiman.cz/r/<slug>` (potvrzená doména - je to
  `APP_BASE_URL` z `api/.env` konfigurátoru, stejná doména, na které
  jede appka samotná). Slug SEO-friendly, odvozený z
  `remeslo_craftsmen.name` (+ `code` pro jednoznačnost při shodě jmen).
- **Publikace NENÍ automatická** - nový sloupec
  `remeslo_craftsmen.public_profile_enabled` (výchozí `0`), řemeslník/
  admin musí zveřejnění explicitně zapnout (soukromí - ne každý chce
  mít veřejný profil).
- **Obsah stránky**:
  1. Jméno, profese, lokalita (město) - z `remeslo_craftsmen`.
  2. Kontakt (telefon/e-mail) - jen pokud řemeslník zvlášť odsouhlasí
     zveřejnění kontaktu (samostatný příznak, ne součást
     `public_profile_enabled`).
  3. Ukázky práce - fotky ze zakázek, ale JEN ty, co řemeslník
     jednotlivě označí jako veřejné (nový příznak na `gallery_items`
     nebo vazební tabulka `remeslo_public_showcase`) - NIKDY
     automaticky všechny fotky ze zakázek (ochrana soukromí klientů -
     fotka interiéru domu klienta nesmí skončit veřejně bez svolení).
  4. Časem důvěryhodnostní odznak z Modulu 4 (ověřovací mechanismus),
     až bude hotový.
  5. **Patička s backlinkem** (Robert: "s hláškou aplikaci vám
     sponzoruje") - text ve smyslu "Tuto stránku vám zdarma poskytuje
     **autovestavby.logiman.cz**" s odkazem zpět na hlavní web - to je ten
     "zpětný odkaz" pro SEO.
- **SEO technika**: `<title>`/meta description per profil, zápis do
  `sitemap.xml`, structured data (schema.org `LocalBusiness`/`Person`)
  pro lepší zobrazení ve vyhledávačích.

Přesné znění hlášky v patičce a přesný výběr polí kontaktu čeká na
Robertovo doladění textu, struktura výš je návrh k připomínkování.

**Část B — individuální pokyny spolupracovníkům (NEveřejné, bez přihlášení)**
- Robert: "dává smysl mini web s oběma body... náhledy pro
  spolupracovníky na práci, pokyny každému jeho spolupracovníkovi
  individuálně, co má dělat - skryté, ale bez nutnosti přihlašování."
- Řemeslník má často víc spolupracovníků/pomocníků, kteří nepotřebují
  (a nemají) plný účet do administrace - jen potřebují vidět, co mají
  dnes dělat.
- Mechanismus: KAŽDÝ spolupracovník dostane VLASTNÍ individuální
  odkaz (dlouhý neuhodnutelný token v URL, ne prohledávatelný slug) -
  technicky bez přihlášení (žádné heslo), ale zároveň NEindexovaný/
  nedohledatelný (na rozdíl od části A) - princip "neveřejný odkaz"
  (podobně jako nezapsané YouTube video), ne skutečně veřejná stránka.
- **Viditelnost (upřesněno Robertem, 2026-08-19):** základ (vždy
  viditelné, bez výjimky) jsou samotné pracovní úkony (co dělat, kde,
  jaký materiál vzít). VŠECHNO NAD RÁMEC ZÁKLADU (např. cena zakázky,
  náklady, kontakt na klienta, historie...) je VOLITELNÉ a řídí ho
  výhradně řemeslník/administrátor - ten sám individuálně rozhoduje,
  co konkrétnímu spolupracovníkovi navíc odemkne. Není to pevně daný
  seznam "tohle nikdy, tamto vždy" - je to nastavitelné per
  spolupracovník. Které konkrétní moduly/položky půjde takhle
  odemykat, se teprve specifikuje (otevřené, ne dořešené).
- Datový model (návrh, čeká na schválení než se začne stavět):
  nová tabulka `remeslo_collaborators` (craftsman_id FK, jméno,
  access_token) + způsob přiřazení konkrétních zakázek/úkolů
  konkrétnímu spolupracovníkovi (buď nový sloupec na `remeslo_jobs`,
  nebo vazební tabulka, pokud jedna zakázka může mít víc lidí) +
  jednoduchá sada příznaků/oprávnění per spolupracovník (ne plná
  RBAC matice jako u Timoty - viz dřívější rozhodnutí "přeskočit
  přehnaně granulární oprávnění", tohle je odlehčená varianta jen
  pro tenhle konkrétní účel).

Nezačato - zapsáno pro budoucí stavbu, čeká na rozhodnutí o pořadí
(vzhledem k tomu, že fakturace je záměrně až na konci nabalování,
tenhle modul by mohl jít dřív, protože nemá stejné bezpečnostní
nároky jako doklady).

## Modul 8 — Nabídky + Nastavení (fakturační údaje, číselné řady)

Zadání (Robert, 2026-08-19, přes bot3, po živém průzkumu přihlášeného
konkurenta remeslnik.online - viz `AGENTS_LOG.md` dnešní zápisy pro
konkrétní screeny). Přiřazeno bot13. Dvě části, obě jen INFRASTRUKTURA/
NASTAVENÍ a evidence CENOVÝCH NABÍDEK - **žádná faktura/doklad se tu
nevystavuje**, to zůstává gated podle rozhodnutí v sekci "Mimo
současný scope" níž (ověření identity před fakturací). Nabídka není
fiskální doklad (na rozdíl od faktury), takže na ni tahle podmínka
nedopadá - jen infrastruktura (číselná řada) pro budoucí faktury se
připravuje předem, aby ji nebylo nutné dodělávat zpětně.

### 8a. Nastavení → Firemní profil

Rozšíření existující `remeslo_craftsmen` (ne nová tabulka - řemeslník
už v ní má jméno/firmu/adresu/kontakty, tohle jen doplňuje
identifikační údaje a "vzhled dokumentů"):

```sql
ALTER TABLE remeslo_craftsmen
    ADD COLUMN subject_type ENUM('osvc','firma','jiny') NOT NULL DEFAULT 'osvc' AFTER company_name,
    ADD COLUMN ico VARCHAR(20) NULL AFTER subject_type,
    ADD COLUMN dic VARCHAR(20) NULL AFTER ico,
    ADD COLUMN subject_type_other_label VARCHAR(120) NULL AFTER dic,  -- jen pri 'jiny'
    ADD COLUMN doc_accent_color VARCHAR(7) NULL AFTER note,           -- vzhled dokumentu, napr. '#2f6f4f'
    ADD COLUMN doc_footer_note TEXT NULL AFTER doc_accent_color;      -- paticka na nabidkach/fakturach
```

`subject_type` mění, která identifikační pole jsou POVINNÁ na frontendu
(OSVČ: jméno+příjmení+IČO povinné, DIČ jen když `vat_payer`; Firma:
`company_name`+IČO+DIČ dle plátcovství; Jiný subjekt: `company_name`
nebo `subject_type_other_label` + volitelné IČO) - žádná nová
DB validace navíc, jen JS/API-level kontrola stejně jako dnešní
`name`/`profession_id` povinná pole. ARES doplnění znovupoužívá
hotový `GET /api/public/ares/<ico>` (`api/scene_offers.py`, dnes
používaný u zákazníka v Evidenci zakázek) - stejné tlačítko "Doplnit
z ARES" u vlastního profilu řemeslníka.

**"Dokončení profilu X %"** - čistě orientační ukazatel v UI (podíl
vyplněných z definované sady polí: identifikace dle typu subjektu,
kontakt, adresa, fakturační údaje z 8b), **NEBLOKUJE žádnou funkci**
(nabídku i bez dokončeného profilu jde založit) - výslovně tak popsáno
na screenech konkurence, přebíráme 1:1.

### 8b. Nastavení → Fakturace

Nová tabulka, 1:1 vztah k řemeslníkovi (ne rozšíření `remeslo_craftsmen`
- jde o oddělenou, řidčeji měněnou sadu polí):

```sql
CREATE TABLE remeslo_invoicing_settings (
    craftsman_id        INT PRIMARY KEY,             -- FK remeslo_craftsmen, 1:1
    vat_payer            TINYINT(1) NOT NULL DEFAULT 0,
    bank_account_number  VARCHAR(30) NULL,
    bank_code            VARCHAR(10) NULL,
    iban                 VARCHAR(34) NULL,
    swift                VARCHAR(11) NULL,
    default_due_days     SMALLINT NOT NULL DEFAULT 14,
    default_vat_rate     DECIMAL(5,2) NOT NULL DEFAULT 21.00,
    currency             VARCHAR(3) NOT NULL DEFAULT 'CZK',
    created_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

Bankovní údaje jsou buď číslo účtu+kód banky, NEBO IBAN/SWIFT (oba
páry volitelné, žádná FK/CHECK vazba - stejná volnost jako u
konkurence, validace formátu jen na frontendu).

**Číselné řady** - SAMOSTATNĚ konfigurovatelné pro nabídky i (budoucí)
faktury, proto vlastní tabulka místo sloupců na `remeslo_invoicing_
settings`:

```sql
CREATE TABLE remeslo_numbering_sequences (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    craftsman_id   INT NOT NULL,                 -- FK remeslo_craftsmen
    doc_type       ENUM('nabidka','faktura') NOT NULL,
    prefix         VARCHAR(20) NOT NULL DEFAULT '',
    separator      VARCHAR(5) NOT NULL DEFAULT '-',
    digit_count    TINYINT NOT NULL DEFAULT 4,
    start_number   INT NOT NULL DEFAULT 1,
    include_year   TINYINT(1) NOT NULL DEFAULT 1,
    current_number INT NOT NULL DEFAULT 0,       -- posledni vydane poradove cislo (bez roku/prefixu)
    current_year   INT NULL,                     -- rok, pro ktery current_number plati (reset pri zmene roku, jen kdyz include_year)
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_craftsman_doctype (craftsman_id, doc_type)
);
```

Formát čísla dokladu: `{prefix}{separator}{rok pokud include_year}
{separator}{poradove cislo doplnene nulami na digit_count}` (např.
`NAB-2026-0001`). Živý náhled se počítá na frontendu ze stejných polí
formuláře (žádný zvláštní preview endpoint). Generování REÁLNÉHO čísla
při vytvoření nabídky (8c) běží přes `SELECT ... FOR UPDATE` na řádek
sekvence (stejný vzorec jako `_assign_craftsman_code()` v modulu 1/4),
s resetem `current_number` na `start_number - 1` při přechodu na nový
rok, pokud `include_year=1`. **Řada pro `'faktura'` se v tomhle
modulu jen KONFIGURUJE** - žádný endpoint ji reálně nespotřebovává,
dokud nevznikne fakturační modul samotný (gated, viz výš).

### 8c. Nabídky (`/nabidky` tab v `remeslo.html`)

Nová tabulka:

```sql
CREATE TABLE remeslo_offers (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    craftsman_id     INT NOT NULL,               -- FK remeslo_craftsmen
    job_id           INT NULL,                   -- FK remeslo_jobs, volitelne navazani na zakazku
    number           VARCHAR(40) NOT NULL,        -- vygenerovane pri zalozeni, viz 8b
    title            VARCHAR(255) NOT NULL,
    customer_name    VARCHAR(255) NOT NULL,
    customer_ico     VARCHAR(20) NULL,
    customer_dic     VARCHAR(20) NULL,
    customer_address VARCHAR(500) NULL,
    status           ENUM('koncept','vystaveno','reakce_zakaznika','revize') NOT NULL DEFAULT 'koncept',
    valid_until      DATE NULL,
    is_template      TINYINT(1) NOT NULL DEFAULT 0,
    active            TINYINT(1) NOT NULL DEFAULT 1,
    total_czk        DECIMAL(10,2) NOT NULL DEFAULT 0,   -- cache souctu polozek, prepocita se pri zmene polozek
    note             TEXT NULL,
    revision_of_id   INT NULL,                    -- FK remeslo_offers.id, predchozi verze pri revizi
    revision_number  INT NOT NULL DEFAULT 1,
    created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_number (number),
    KEY idx_craftsman (craftsman_id),
    KEY idx_status (status)
);

CREATE TABLE remeslo_offer_items (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    offer_id          INT NOT NULL,               -- FK remeslo_offers
    popis             VARCHAR(500) NOT NULL,
    mnozstvi          DECIMAL(10,2) NOT NULL DEFAULT 1,
    jednotka          VARCHAR(20) NOT NULL DEFAULT 'ks',
    cena_za_jednotku  DECIMAL(10,2) NOT NULL DEFAULT 0,
    sort_order        INT NOT NULL DEFAULT 0,
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

**Revize** = nová řádka v `remeslo_offers` s `revision_of_id` na
předchozí verzi a `revision_number+1` (ne přepis původní - historie
zůstává dohledatelná), analogicky `remeslo_photo_analyses` verzování
pattern jinde v projektu. **Šablona** (`is_template=1`) = nabídka bez
zákazníka/`customer_name` volitelně prázdný, sloužící jen jako
předloha položek pro "Nová nabídka ze šablony" (kopie položek, ne
FK-odkaz - šablona se pak může nezávisle měnit).

Filtr (`GET /api/remeslo/offers`) dle zadání: číslo/název/zákazník
(`?q=`, LIKE přes `number`/`title`/`customer_name`), stav (`?status=`),
zákazník (`?customer_name=`, přesnější než `q`), zakázka (`?job_id=`),
platnost (`?valid_before=`/`?valid_after=` na `valid_until`), aktivní/
neaktivní (`?active=`), řazení (`?sort=` - number/created_at/
valid_until, `?dir=`).

### 8d. Online veřejná nabídka + import položek z kalkulace

Dodatečné rozšíření (Robert, 2026-08-19, přes bot3, po dokončení
8a-8c): "chci i online verzi nabídky, stejný princip jako u
konfigurátoru (`api/scene_offers.py`/`nabidka-online.html`), jen jiná
data/vzhled podle profese řemeslníka." Souběžně platné pravidlo
(TASKS.md, sekce Faktury a Finance): **položky nabídky (i budoucí
faktury) se netahají z 3D scény ani nezadávají od nuly - přebírají se
z Kalkuláček** (`remeslo_calculations`/`remeslo_calculation_items`,
Modul 9), se SNAPSHOTEM názvu/množství/ceny v okamžiku převzetí (ruční
zadání beze vztahu ke kalkulaci zůstává možné, jen kalkulace je teď
PREFEROVANÝ zdroj).

**Znovupoužité z `api/scene_offers.py` (přesně stejný princip, jen bez
3D/render/model částí, které se řemeslníka netýkají):**
- Token: `secrets.token_urlsafe(32)` + SHA-256 hash do
  `remeslo_offers.view_token_hash` - syrový token se nikde neukládá,
  vrací se adminovi JEN jednou (při vytvoření/regeneraci).
- Veřejné no-login endpointy `/api/public/remeslo-offers/<token>` -
  `GET` (detail), `POST .../accept`, `POST .../decline`, analogie
  `public_offer_get`/`_accept`/`_decline`. Append-only tabulky
  `remeslo_offer_acceptances`/`remeslo_offer_declines` (1:1
  `scene_offer_acceptances`/`scene_offer_declines`).
- QR Platba: `_build_spayd()`/`_cz_account_to_iban()` z
  `scene_offers.py` beze změny (čistý výpočet, žádná závislost na
  scéně) - jen zdroj bankovního účtu je jiný: `remeslo_invoicing_
  settings` KONKRÉTNÍHO řemeslníka (IBAN přímo, nebo číslo účtu+kód
  banky přes `_cz_account_to_iban`), ne globální `SUPPLIER` konfigurátoru.
  Chybí-li bankovní údaje, endpoint vrátí chybu (žádný fingovaný QR).
- E-mail upozornění řemeslníkovi při přijetí/odmítnutí (pokud má
  vyplněný e-mail) - `send_email()`, stejný vzor jako `public_offer_
  accept`, nekritická návaznost (selhání se jen zaloguje).

**VĚDOMĚ VYNECHÁNO** (na rozdíl od `scene_offers.py`) - netýká se
řemeslníka: 3D model/rendery/ghost pohledy, kreslené značky (markups),
live chat panel, WhatsApp panel, Toptrans doprava, PDF na Sdíleném
disku. Veřejná stránka (`remeslo-nabidka-online.html`) je proto MNOHEM
menší než `nabidka-online.html` - hlavička (vzhled dokumentů
řemeslníka: `doc_accent_color`/`doc_footer_note`/název), číslo/stav/
platnost nabídky, tabulka položek, celková cena, poznámka, tlačítka
Souhlasím/objednávám (jméno + kontakt) a Nemám zájem (nepovinný
důvod), QR platba. `<meta name="robots" content="noindex,nofollow">`
stejně jako `remeslo-spolupracovnik.html`.

**Import z kalkulace** (`POST /api/remeslo/offers` rozšířeno o
volitelné `calculation_id`) - zkopíruje jen `is_used=1` položky dané
kalkulace do nabídky se snapshotem (`nazev`→`popis`, `mnozstvi`,
`cena_jednotka_czk`→`cena_za_jednotku`). Pokud je mezi přebíranými
položkami POVINNÁ a NENACENĚNÁ (`cena_jednotka_czk IS NULL`), import
se ODMÍTNE s jasnou chybou (stejný princip jako blokující hláška v
kalkulačce/Ceníku - nabídka pro zákazníka NIKDY nesmí tiše dostat
cenu 0 Kč u nenaceněné položky, na rozdíl od interní kalkulačky je
tohle dokument směrem ven, takže i nulová cena by byla zavádějící).
`remeslo_offers.source_calculation_id` je jen TRACEABILITY (odkud
nabídka vznikla) - žádný živý odkaz, pozdější změna kalkulace nabídku
tiše nezmění.

### Co jde v modulu 8 první implementovat

1. SQL migrace (ALTER `remeslo_craftsmen`, 3 nové tabulky).
2. Backend `api/remeslo.py`: rozšíření craftsman create/update o nová
   pole 8a, CRUD `remeslo_invoicing_settings` (GET/PUT, upsert - řádek
   vzniká lazily při prvním PUT), CRUD `remeslo_numbering_sequences`
   (GET vrací obě řady najednou, PUT upsertuje jednu podle `doc_type`),
   CRUD `remeslo_offers` + `remeslo_offer_items` (vzor `remeslo_jobs`/
   `remeslo_job_materials` - `_recalc_offer_total()` po každé změně
   položky, stejně jako `_recalc_job_costs()`).
3. UI `webapp/remeslo.html`: nový tab `Nabídky` (filtr + tabulka +
   modal s položkami, vzor tab `jobs`) a nový tab `Nastavení` se 4
   podzáložkami - **Firemní profil** a **Fakturace** plně funkční,
   **Tarif a platby** a **Soukromí a data** jen jako viditelný stub
   ("připravujeme" placeholder) - na screenech konkurence jsou, ale
   nejsou v zadání rozpracované a monetizace/platby nejsou v etapě 1
   (viz cíl 1. etapy na začátku dokumentu), takže se nestaví naprázdno.

## Modul 9 — Kalkulačky + Ceník (návrh, čeká na schválení)

Zadání: `TASKS.md` "Řemeslo - modul Kalkulačky + Ceník" (Robert,
2026-08-19, po hloubkovém živém průzkumu konkurenta remeslnik.online -
posílal screeny přímo bot3, plný popis viz `AGENTS_LOG.md` "hloubkovy
pruzkum noveho konkurenta remeslnik.online"). Cíl: "chci přidat do
našeho systému podprojektu Řemeslo všechno co je na screenech" -
sada technologických kalkuláček (min. 9: Zámková dlažba, Obklady a
dlažby, Malování, Sádrokarton, Podlahy, Fasáda a zateplení, Betonáž,
Zemní práce, Univerzální kalkulace) napojených na centrální cenovou
knihovnu (Ceník). **Vlastník: bot11.**

**FAKTURACE/DOKLADY SE NESTAVÍ ANI TADY** (viz "Mimo současný scope"
níž) - kalkulačky/Ceník počítají MNOŽSTVÍ a ORIENTAČNÍ NÁKUPNÍ CENU
materiálu pro vlastní potřebu řemeslníka (kolik čeho koupit a za
kolik), ne doklad/nabídku pro zákazníka. Žádné PDF/QR/vystavení.

### Ceník - schéma (návrh)

```sql
CREATE TABLE remeslo_pricelist_categories (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    craftsman_id    INT NULL,        -- NULL = systemova kategorie (sdilena
                                      -- vsemi), vyplnene = vlastni kategorie
                                      -- KONKRETNIHO remeslnika ("Pridat
                                      -- vlastni kategorii")
    name            VARCHAR(255) NOT NULL,
    is_system       TINYINT NOT NULL DEFAULT 0,
    sort_order      INT NOT NULL DEFAULT 0,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE remeslo_pricelist_items (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    category_id         INT NOT NULL,           -- FK remeslo_pricelist_categories
    craftsman_id        INT NOT NULL,           -- FK remeslo_craftsmen - cena je
                                                 -- VZDY per-remeslnik (jeho vlastni
                                                 -- nakupni cena od JEHO dodavatele),
                                                 -- i u systemove polozky/kategorie
    name                VARCHAR(255) NOT NULL,
    unit                VARCHAR(20) NOT NULL,   -- m2/m/ks/kg/t...
    price_czk           DECIMAL(10,2) NULL,     -- NULL = "nenacenovano" (nikdy
                                                 -- tise nahrazovano nulou)
    vat_percent         DECIMAL(5,2) NULL,
    valid_from          DATE NULL,              -- "Platna k" - datum, od ktereho
                                                 -- current cena plati
    supplier            VARCHAR(255) NULL,
    note                TEXT NULL,
    is_used             TINYINT NOT NULL DEFAULT 1,   -- toggle "Pouzivam"
    is_mandatory        TINYINT NOT NULL DEFAULT 0,   -- Povinna/Volitelna stitek
    is_system           TINYINT NOT NULL DEFAULT 0,   -- Systemova/Vlastni material
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Historie zmen ceny - append-only log, zapisuje se PRED kazdou
-- zmenou price_czk/vat_percent/valid_from na polozce (ne trigger,
-- explicitne v api/remeslo.py pri UPDATE) - viz zduvodneni nize.
CREATE TABLE remeslo_pricelist_item_price_history (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    item_id         INT NOT NULL,
    price_czk       DECIMAL(10,2) NULL,
    vat_percent     DECIMAL(5,2) NULL,
    valid_from      DATE NULL,
    changed_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

**Verzování ceny - zdůvodnění volby:** současná cena zůstává přímo na
`remeslo_pricelist_items` (mutable pole, jednoduché čtení "kolik to
teď stojí" bez nutnosti dotazu "poslední řádek historie"), a PŘED
každou změnou se stará hodnota zapíše do
`remeslo_pricelist_item_price_history` (append-only, žádný UPDATE/
DELETE) - stejný princip jako `remeslo_job_materials`/`remeslo_job_
time_entries`: jedna cesta pravdy pro "aktuální stav", historie je
vedlejší log pro audit/dohledatelnost ("kdy a jak se cena měnila"),
ne primární zdroj čtení. Čistě append-only historie (bez mutable
current pole) byla zvažována, ale zbytečně komplikuje každý prostý
dotaz "kolik to stojí teď" (vyžadovalo by `ORDER BY valid_from DESC
LIMIT 1` všude) pro benefit, který tahle appka nepotřebuje (žádné
"zobraz mi cenu k libovolnému datu v minulosti", jen "co se změnilo a
kdy").

Progress "X z Y povinných položek naceněno" a "Přidat vlastní
kategorii" jsou čisté SQL dotazy nad tímhle schématem (COUNT s
podmínkou `is_mandatory=1 AND price_czk IS NOT NULL`), žádná nová
tabulka.

### Kalkulačky - schéma (návrh)

```sql
CREATE TABLE remeslo_calculator_types (
    id      INT AUTO_INCREMENT PRIMARY KEY,
    code    VARCHAR(50) NOT NULL UNIQUE,   -- 'zamkova_dlazba', 'malovani', 'univerzalni'...
    name    VARCHAR(255) NOT NULL,
    is_system TINYINT NOT NULL DEFAULT 1   -- vsech 9 + univerzalni jsou systemove,
                                            -- vlastni typy mimo scope v1
);

CREATE TABLE remeslo_calculations (
    id                      INT AUTO_INCREMENT PRIMARY KEY,
    calculator_type_id     INT NOT NULL,       -- FK remeslo_calculator_types
    craftsman_id            INT NOT NULL,       -- FK remeslo_craftsmen
    job_id                  INT NULL,           -- FK remeslo_jobs, volitelne napojeni
    parent_calculation_id  INT NULL,            -- FK remeslo_calculations (sebe
                                                 -- sama) - vyplnene = tohle je REVIZE
                                                 -- puvodni kalkulace, ne novy zaznam
    name                    VARCHAR(255) NOT NULL,
    status                  VARCHAR(20) NOT NULL DEFAULT 'koncept',  -- koncept/hotovo
    author_user_id          INT NOT NULL,
    inputs_json             JSON NULL,          -- vstupni rozmery/preset - viz zduvodneni
    created_at               DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at               DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE remeslo_calculation_items (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    calculation_id      INT NOT NULL,       -- FK remeslo_calculations ON DELETE CASCADE
    pricelist_item_id   INT NULL,           -- FK remeslo_pricelist_items, NULL =
                                             -- rucne pridana polozka mimo Cenik
    nazev               VARCHAR(255) NOT NULL,   -- SNAPSHOT nazvu v okamziku pridani
                                                  -- (kalkulace se nesmi tise zmenit,
                                                  -- kdyz nekdo pozdeji prejmenuje/smaze
                                                  -- polozku v Ceniku)
    mnozstvi             DECIMAL(10,2) NOT NULL,
    jednotka             VARCHAR(20) NULL,
    cena_jednotka_czk   DECIMAL(10,2) NULL,      -- SNAPSHOT ceny v okamziku pridani
                                                  -- (stejny princip - stara kalkulace/
                                                  -- revize se NEPREPOCITA, kdyz se
                                                  -- zmeni cena v Ceniku pozdeji)
    is_mandatory        TINYINT NOT NULL DEFAULT 0,
    is_used              TINYINT NOT NULL DEFAULT 1,   -- checkbox pouzit/nepouzit
    sort_order           INT NOT NULL DEFAULT 0,
    CONSTRAINT fk_remeslo_calculation_items_calc
        FOREIGN KEY (calculation_id) REFERENCES remeslo_calculations(id) ON DELETE CASCADE
);
```

**Dynamická skladba vrstev** (zdůrazněno ve spec jako příklad u
Zámkové dlažby) NEMÁ vlastní tabulku - je to prostě `remeslo_
calculation_items` samotné: "vrstva" = jeden řádek položky (štěrkové
lože, pískové lože, dlažba, spárovací hmota, obrubníky...), "přidat/
odebrat vrstvu" = INSERT/DELETE řádku. Živý výsledek (sticky panel) je
čistě frontendová agregace nad aktuálním seznamem položek v editoru,
žádná další tabulka.

**Vstupy (`inputs_json`) jako JSON, ne normalizované sloupce** -
zdůvodnění: 9 různých kalkuláček má 9 různých sad vstupů (plocha+sklon
u fasády, plocha+počet vrstev nátěru u malování, objem+tloušťka desky
u betonáže...) - normalizovaný sloupec per vstup by vedl buď k jedné
tabulce s desítkami řídce vyplněných sloupců, nebo k 9 samostatným
tabulkám jen pro vstupy. JSON blob je pragmatická volba pro
heterogenní, appkou samotnou interpretovaná data (podobný princip,
jaký MySQL JSON sloupec umožňuje - připraveno v `pymysql`/schématu
projektu, žádná nová závislost). Frontend vstupní formulář je řízený
`calculator_type_id` (9 formulářů), backend JSON jen ukládá/vrací
beze změny - validace/výpočet zůstává na typové funkci (viz níž).

**Revize** = nová řádka v `remeslo_calculations` s vyplněným
`parent_calculation_id` (řetěz odkazů, ne verzovací sloupec) - stejný
princip jako "append-only historie ceny" výš, ale tady dává smysl
plná nezávislá řádka (ne jen historie diffu), protože revize
kalkulace má vlastní kompletní sadu položek/vstupů, ne jen jednu
změněnou hodnotu. "Moje kalkulace" list zobrazuje buď jen NEJNOVĚJŠÍ
řádku každého řetězu (výchozí pohled), s možností rozbalit celou
historii revizí - stejný UX vzor jako filtr v zadání (název/typ/
zakázka/autor/stav/datum).

### Výpočetní architektura

9 technologicky odlišných výpočtů (jiná vzorec/logika pro každou) -
NE jeden univerzální DSL/rule-engine (přehnaně abstraktní pro v1, viz
projektové pravidlo "nestavět abstrakce nad rámec potřeby"). Návrh:
každý typ kalkulačky má VLASTNÍ malou Python funkci v `api/remeslo.py`
(např. `_calc_zamkova_dlazba(inputs) -> list[navrhovana_polozka]`),
která z `inputs_json` navrhne výchozí sadu položek (množství
dopočítané z technologických koeficientů/norem spotřeby) - řemeslník
je pak může upravit/smazat/přidat ručně stejně jako u itemizovaného
materiálu. Sdílená kostra (uložení, revize, seznam "Moje kalkulace",
CRUD položek, propojení na Ceník/zakázku) je 100% společná napříč
všemi 9 typy - liší se jen (a) vstupní formulář na frontendu a (b) tahle
jedna výpočetní funkce na backendu. Univerzální kalkulačka (9.) nemá
žádnou výpočetní funkci vůbec - jen prázdný seznam položek k ručnímu
sestavení, čistě UI nad sdílenou kostrou.

Pokud se časem ukáže, že se vzorce mezi typy hodně opakují (např.
"plocha × norma spotřeby na m² ÷ balení = počet balení" je společný
vzor pro malování/obklady/fasádu), dá se to REFAKTOROVAT na sdílenou
pomocnou funkci až DODATEČNĚ, ne navrhovat abstrakci předem bez
důkazu, že se skutečně opakuje 1:1.

**Fotky/přílohy ke kalkulaci** - NENÍ ve spec (`TASKS.md`) zmíněno,
proto se v tomhle návrhu vědomě NESTAVÍ v první verzi (žádný scope
creep). Infrastruktura `api/gallery_items.py` (polymorfní `owner_type`)
by šla triviálně rozšířit o `'remeslo_calculation'` později, pokud
by o to Robert požádal - žádná architektonická překážka, jen záměrně
mimo v1.

### Pořadí implementace (návrh)

1. **Ceník musí být hotový první** - kalkulačky na něm závisí
   (blokující hláška "Doplnit ceník", pokud povinné položky nejsou
   naceněné, viz zadání). Bez Ceníku nejde smysluplně otestovat ani
   jednu kalkulačku end-to-end.
2. **Pilotní kalkulačka: Zámková dlažba** - zdůvodnění výběru: zadání
   v `TASKS.md` explicitně používá ZROVNA tuhle kalkulačku jako
   příklad nejsložitějšího UI vzoru ("dynamická skladba vrstev -
   přidat/odebrat vrstvu u zámkové dlažby"). Vyřešit nejtěžší případ
   jako první ověří vzor (dynamické položky, snapshot cen, napojení
   na zakázku, revize) pro VŠECH 9 typů najednou - jednodušší
   kalkulačky (např. Malování) by ověřily jen podmnožinu stejné
   kostry a nezaručily by, že složitější případ funguje.
3. Zbylých 7 systémových kalkuláček + univerzální - replikace
   ověřeného vzoru, jen nová vstupní forma + výpočetní funkce per typ.

Tenhle modul čeká na schválení bot3/Robertem před psaním kódu (stejný
proces jako Modul 7).

### Kolo 2 — zbylých 8 kalkuláček (schváleno, pilot hotový)

Pilotní kalkulačka (Zámková dlažba, bot11) hotová a ověřená - vzor
(sdílená kostra + vlastní vstupní formulář/výpočetní funkce per typ,
viz "Výpočetní architektura" výš) se replikuje beze změny. Rozdělení
(bot3, 2026-08-19): **bot11** bere "Interiéry" (Obklady a dlažby,
Malování, Sádrokarton, Podlahy), **bot13** bere zbytek (Fasáda a
zateplení, Betonáž, Zemní práce, Univerzální kalkulace).

**Fasáda a zateplení** (ETICS - vnější kontaktní zateplovací systém).
Vstupy: `plocha_m2` (plocha fasády), `obvod_m` (volitelné - zakládací/
soklová lišta), `rezerva_percent` (výchozí 5 %, prořez izolantu).
Koeficienty (orientační výchozí, přepisovatelné v UI, zdroj: běžné
české technické listy/kalkulačky ETICS, WebSearch 2026-08-19):
- Tepelná izolace (EPS/minerální vata) — m², `plocha × (1 + rezerva)`.
- Lepicí hmota (lepení izolantu) — kg, `plocha × 5` (5 kg/m²).
- Armovací stěrka s perlinkou (základní vrstva) — kg, `plocha × 4`
  (4 kg/m²).
- Perlinka (sklotextilní síťovina) — m², `plocha × 1,10` (10 % na
  přesahy pásů).
- Talířové hmoždinky — ks, `plocha × 6` (6 ks/m², standardní kotvení
  po 24 h).
- Penetrační nátěr — l, `plocha × 0,15` (0,15 l/m² pro fasádu/omítku).
- Tenkovrstvá omítka (finální vrstva) — kg, `plocha × 3` (orientační
  střední hodnota pro běžné 2mm zrno - reálná spotřeba silně závisí na
  zrnitosti/výrobci, viz technický list konkrétního produktu; proto
  vždy jen výchozí návrh, ne autoritativní číslo).
- Zakládací/soklová lišta — m, `obvod` (jen když `obvod_m` vyplněné,
  volitelná položka - stejný vzor jako "Obrubníky" u zámkové dlažby).

**Betonáž.** Vstupy: `plocha_m2`, `tloustka_m` (výchozí 0,15 m),
`rezerva_percent` (výchozí 5 %), `s_vyztuzi` (bool, výchozí true),
`tl_podsyp_m` (volitelné). Koeficienty (WebSearch 2026-08-19):
- Beton (transportbeton) — m³, `plocha × tloustka × (1 + rezerva)`.
- KARI síť (výztuž) — m², `plocha × 1,15` (15% rezerva na přesahy,
  běžná hodnota profesních kalkulaček základových desek) - jen když
  `s_vyztuzi`.
- Štěrkopískový podsyp — m³, `plocha × tl_podsyp_m` - jen když
  `tl_podsyp_m > 0` (typická tloušťka 15-20 cm dle podloží, ale
  necháváme čistě na uživateli, žádný vynucený default).
- Bednění (boční) — m², `obvod × tloustka_m` - volitelné, jen když
  `obvod_m` vyplněné.

**Zemní práce.** Vstupy: `plocha_m2`, `hloubka_m`, `koef_nakypreni`
(výchozí 1,22 - "3. třída zemin, zeminy kopné", ČSN/oceňovací
podklady, WebSearch 2026-08-19), `tl_zasyp_m` (volitelné).
- Výkop zeminy (rostlý objem) — m³, `plocha × hloubka`.
- Odvoz a uložení vytěžené zeminy (nakypřený objem) — m³,
  `plocha × hloubka × koef_nakypreni` (nakypřená zemina zabírá víc
  objemu než v rostlém stavu - jiné číslo než samotný výkop, proto
  samostatná položka).
- Štěrkopísek na zásyp/podsyp — m³, `plocha × tl_zasyp_m` - jen když
  `tl_zasyp_m > 0`.

**Univerzální kalkulace.** Beze změny oproti architektuře výš - ŽÁDNÁ
výpočetní funkce, prázdný seznam položek k ručnímu sestavení. Jediná
odlišnost od ostatních typů: ve frontendu nemá žádný geometrický vstup
(jen název + volitelné napojení na zakázku, obojí už společná kostra),
takže se z formuláře rovnou zakládá s `inputs={}` a otevře editor s 0
položkami.

## Modul 10 — Faktury a Finance (`/faktury`, `/finance`) (návrh, čeká na schválení)

Zadání: `TASKS.md` "Řemeslo - Faktury a Finance" (Robert, 2026-08-19, přes
bot3) - vlastník bot14. Postavit CELOU funkčnost, důkladně živě otestovat,
ale NEZAPOJOVAT do hlavní navigace pro běžné řemeslníky - viz "Gating"
níž. **Tohle NENÍ zrušení gatingu ze sekce "Mimo současný scope"
(identita před fakturací)** - jen jeho posun z "nestavět" na "postavit a
otestovat, se spuštěním počkat" (Robert: "modul chceme mít otestovaný
funkční, jen na spuštění modulu budeme opatrní").

Faktury jsou odděleny od Nabídek (modul 8) - vlastní tabulka, vlastní
číselná řada (`remeslo_numbering_sequences` `doc_type='faktura'`, dosud
jen KONFIGUROVANÁ, žádný endpoint ji nespotřebovával - tenhle modul je
první, kdo ji reálně použije). Finance je 3. vrstva NAD Fakturami a
Evidencí zakázek (modul 2) - ne duplicitní úložiště, ale vlastní ÚČETNÍ
DENÍK potvrzených peněžních událostí.

### 10a. Faktury

Položky faktury se **NEZADÁVAJÍ ručně od nuly** (na rozdíl od dnešních
Nabídek, které mají čistě ruční položky) - tahají se buď z uložené
Kalkulace (modul 9, snapshot názvu/množství/ceny v okamžiku převzetí,
stejný princip jako revize kalkulace), nebo se zakládají ručně, pokud
řemeslník kalkulačku nepoužil. (Zadání zmiňuje stejný princip i pro
Nabídky - to je ale existující, bot13/bot11 vlastněný modul, mimo tenhle
úkol; navrhuji zapsat jako budoucí navazující drobnost, NEzasahovat do
Nabídek v rámci tohohle modulu.)

```sql
CREATE TABLE remeslo_invoices (
    id                    INT AUTO_INCREMENT PRIMARY KEY,
    craftsman_id          INT NOT NULL,                 -- FK remeslo_craftsmen
    job_id                INT NULL,                     -- FK remeslo_jobs, volitelne navazani na zakazku
    source_calculation_id INT NULL,                     -- FK remeslo_calculations, ODKUD vznikla (informativni, polozky jsou snapshot)
    number                VARCHAR(40) NOT NULL,          -- vygenerovane pres remeslo_numbering_sequences doc_type='faktura'
    variable_symbol       VARCHAR(20) NULL,              -- default = number bez prefixu/oddelovacu, editovatelne
    customer_name         VARCHAR(255) NOT NULL,
    customer_ico          VARCHAR(20) NULL,
    customer_dic          VARCHAR(20) NULL,
    customer_address      VARCHAR(500) NULL,
    status                ENUM('koncept','vystaveno','stornovano') NOT NULL DEFAULT 'koncept',
    issue_date            DATE NOT NULL,
    due_date              DATE NOT NULL,
    tax_point_date        DATE NULL,                     -- DUZP, jen pro platce DPH
    payment_method        ENUM('prevodem','hotove','kartou') NOT NULL DEFAULT 'prevodem',
    total_czk             DECIMAL(10,2) NOT NULL DEFAULT 0,  -- cache souctu polozek vc. DPH
    note                  TEXT NULL,
    active                TINYINT(1) NOT NULL DEFAULT 1,
    created_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_remeslo_inv_craftsman FOREIGN KEY (craftsman_id) REFERENCES remeslo_craftsmen(id),
    CONSTRAINT fk_remeslo_inv_job FOREIGN KEY (job_id) REFERENCES remeslo_jobs(id) ON DELETE SET NULL,
    CONSTRAINT fk_remeslo_inv_calc FOREIGN KEY (source_calculation_id) REFERENCES remeslo_calculations(id) ON DELETE SET NULL,
    UNIQUE KEY uq_number (number),
    KEY idx_craftsman (craftsman_id),
    KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE remeslo_invoice_items (
    id                         INT AUTO_INCREMENT PRIMARY KEY,
    invoice_id                 INT NOT NULL,
    source_calculation_item_id INT NULL,                 -- FK remeslo_calculation_items, odkud snapshot vznikl (jen informativni)
    popis                      VARCHAR(500) NOT NULL,
    mnozstvi                   DECIMAL(10,2) NOT NULL DEFAULT 1,
    jednotka                   VARCHAR(20) NOT NULL DEFAULT 'ks',
    cena_za_jednotku           DECIMAL(10,2) NOT NULL DEFAULT 0,
    vat_percent                DECIMAL(5,2) NOT NULL DEFAULT 21.00,
    sort_order                 INT NOT NULL DEFAULT 0,
    created_at                 DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_remeslo_inv_items_invoice FOREIGN KEY (invoice_id) REFERENCES remeslo_invoices(id) ON DELETE CASCADE,
    CONSTRAINT fk_remeslo_inv_items_calc_item FOREIGN KEY (source_calculation_item_id) REFERENCES remeslo_calculation_items(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

Vzor převzatý 1:1 z `remeslo_offers`/`remeslo_offer_items` (modul 8c), s
rozdíly, které si vynucuje fiskální povaha dokladu (i když se reálně
zatím nevystavuje):
- `vat_percent` na KAŽDÉ položce (ne jen `default_vat_rate` v
  Nastavení) - faktura umí zobrazit rozpis DPH, výchozí hodnota se
  předvyplní z `remeslo_invoicing_settings.default_vat_rate`, ale je
  editovatelná per řádek (různé sazby práce/materiál na jedné faktuře
  jsou v ČR běžné).
- `issue_date`/`due_date`/`tax_point_date` - datová pole, která Nabídka
  nemá (ta má jen `valid_until`).
- **ŽÁDNÝ `revision_of_id`/`revision_number`** - na rozdíl od Nabídky a
  Kalkulace není revizní řetěz u faktury vhodný vzor (vystavená faktura
  se v ČR needituje, opravuje se dobropisem/opravným dokladem). V1
  proto: `status='koncept'` jde libovolně upravovat (položky i částky),
  po přechodu na `status='vystaveno'` se položky na backendu
  WRITE-LOCKUJÍ (jediný další povolený přechod je `→'stornovano'`).
  Dobropis/opravný doklad NENÍ v tomhle zadání - navrhuji ho vynechat z
  v1 a zapsat jako budoucí rozšíření, ne stavět bez konkrétního
  požadavku.
- Číslo generuje existující `_generate_doc_number()` (modul 8b) s
  `doc_type='faktura'` - žádná nová generovací logika, jen první reálné
  použití dosud nespotřebovávané sekvence.

### 10b. Finance (`/finance`) - 3. vrstva potvrzených finančních událostí

Klíčový princip zadání: **potvrzené finanční události, bez dvojího
započtení.** `remeslo_job_materials` (modul 2 rozšíření, bot11) dnes
eviduje ODHADOVANÉ/PLÁNOVANÉ náklady zakázky (řemeslník si zapisuje
"trubka 5 m za 450 Kč" jako pracovní poznámku) - to NENÍ totéž jako
"opravdu jsem zaplatil a mám doklad". Finance je oddělený, vlastní
ÚČETNÍ DENÍK (ledger) - řádek do něj vznikne buď automaticky (potvrzení
platby faktury), nebo ručně (přidání nákladu, volitelně s foto dokladem),
NIKDY se needituje zpětně existující `remeslo_job_materials`/
`remeslo_invoices` řádek jako by to bylo totéž.

```sql
CREATE TABLE remeslo_finance_transactions (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    craftsman_id      INT NOT NULL,
    type              ENUM('prijem','naklad') NOT NULL,
    category          VARCHAR(50) NOT NULL,           -- 'uhrada_faktury' | 'material' | 'sluzby' | 'ostatni' | ...
    amount_czk        DECIMAL(10,2) NOT NULL,          -- vzdy kladne, znamenko dane `type`
    transaction_date  DATE NOT NULL,
    note              TEXT NULL,
    invoice_id        INT NULL,                        -- FK remeslo_invoices, kdyz jde o uhradu faktury (castecne platby = vic radku, proto NE unikatni)
    job_id            INT NULL,                        -- FK remeslo_jobs, volitelne prirazeni k zakazce
    job_material_id   INT NULL,                        -- FK remeslo_job_materials, kdyz je naklad "potvrzenim" planovane polozky
    author_user_id    INT NOT NULL,
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_remeslo_fin_craftsman FOREIGN KEY (craftsman_id) REFERENCES remeslo_craftsmen(id),
    CONSTRAINT fk_remeslo_fin_invoice FOREIGN KEY (invoice_id) REFERENCES remeslo_invoices(id) ON DELETE SET NULL,
    CONSTRAINT fk_remeslo_fin_job FOREIGN KEY (job_id) REFERENCES remeslo_jobs(id) ON DELETE SET NULL,
    CONSTRAINT fk_remeslo_fin_job_material FOREIGN KEY (job_material_id) REFERENCES remeslo_job_materials(id) ON DELETE SET NULL,
    UNIQUE KEY uq_job_material (job_material_id),      -- max 1x "potvrzeno jako naklad" na 1 planovanou polozku - hlida dvoji zapocteni
    KEY idx_craftsman (craftsman_id),
    KEY idx_type_date (type, transaction_date),
    KEY idx_invoice (invoice_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

Poznámky k "bez dvojího započtení":
- `UNIQUE KEY uq_job_material` - jedna plánovaná položka
  `remeslo_job_materials` může být "Potvrdit jako náklad" nanejvýš 1×;
  UI po potvrzení tlačítko nahradí "✓ Potvrzeno" (žádný druhý klik).
  NULL hodnoty (naprostá většina transakcí bez vazby na job_material)
  MySQL unikátnost nekontroluje, takže to neomezuje běžné ruční náklady.
- `invoice_id` NENÍ unikátní - částečné platby faktury jsou legitimně
  víc řádků; `paid_czk` faktury se počítá ZA BĚHU
  (`SUM(amount_czk) WHERE invoice_id=? AND type='prijem'`), nikde se
  neukládá jako druhý zdroj pravdy (stejný princip jako u `remeslo_jobs`
  profit/marže - "počítají se za běhu, neukládají se").
- **Foto dokladu → náklad**: znovupoužije se `api/gallery_items.py`
  (nový `owner_type='remeslo_finance_transaction'` v `OWNER_TYPES`/
  `OWNER_TABLE`/`OWNER_PERMISSION_SECTION`) - stejný mechanismus jako
  fotky u zakázek/položek materiálu, žádná nová upload logika.
  Vytvoření nákladu z fotky dokladu = ruční formulář (částka/datum/
  kategorie) + přiložení fotky stejným widgetem - **ŽÁDNÉ automatické
  OCR/AI čtení částky z fotky** (`ANTHROPIC_API_KEY` je v projektu
  dlouhodobě neplatný, viz `remeslo_photo_analyses` - stejné omezení
  platí i tady; řemeslník částku/datum vyplní sám, foto je jen doklad).

**KPI (`GET /api/remeslo/finance/kpis?craftsman_id=&from=&to=`, počítáno
za běhu, nic se neukládá):**
- **Fakturováno** = `SUM(remeslo_invoices.total_czk)` kde
  `status='vystaveno'`, podle `issue_date` v období.
- **Přijaté platby** = `SUM(remeslo_finance_transactions.amount_czk)`
  kde `type='prijem'`, podle `transaction_date` v období.
- **Pohledávky** = za KAŽDOU fakturu `status='vystaveno'` (bez ohledu na
  období, "k dnešnímu dni"): `total_czk − COALESCE(SUM přijatých
  plateb vázaných na tuhle fakturu, 0)`, sečteno přes všechny
  nedoplacené.
- **Náklady** = `SUM(remeslo_finance_transactions.amount_czk)` kde
  `type='naklad'`, v období.
- **Závazky** = `SUM(remeslo_job_materials.cena_czk)` u aktivních
  zakázek, které JEŠTĚ NEMAJÍ vlastní `remeslo_finance_transactions`
  řádek (protistrana `job_material_id IS NULL`) - interpretace
  "plánovaný/evidovaný, ale ještě nepotvrzený jako zaplacený náklad" (v
  appce není samostatná evidence PŘIJATÝCH dodavatelských faktur, takže
  se závazky odvozují z existující evidence materiálu zakázky - **tohle
  je moje navržená interpretace, přesná definice "závazků" není v
  zadání rozepsaná do detailu, prosím potvrdit/opravit před kódem**).
- **Zisk** = Přijaté platby − Náklady (v období, cash-basis - jen
  SKUTEČNĚ potvrzené pohyby, ne fakturovaná/plánovaná čísla - odpovídá
  principu "potvrzené finanční události").
- **Cash flow** = časová řada (den/týden/měsíc dle délky období)
  `SUM(prijem) − SUM(naklad)` z `remeslo_finance_transactions`, pro graf.

### Gating — "postavit a otestovat, ale opatrně se spuštěním"

Řemeslo (celá `remeslo.html`) je dnes fakticky admin-only na úrovni
přepínače oblastí (`webapp/admin.html:5569`, `areaSwitchRemeslo`
viditelný jen `role==='admin'`) - žádní skuteční uživatelé-řemeslníci
ještě neexistují (viz komentář `remeslo_photo_analyses.sql`). I tak
Robert žádá EXTRA vrstvu skrytí konkrétně pro Faktury/Finance (ne pro
zbytek Řemesla) - jde o jediné 2 moduly s reálným rizikem (fiskální
doklad, peníze), zatímco zbytek je bezpečná interní evidence.

Návrh: nový `app_settings` klíč `remeslo_faktury_finance_enabled`
(bool, výchozí `0`/vypnuto):
- **Backend**: nové endpointy (`/api/remeslo/invoices*`,
  `/api/remeslo/finance*`) mají STEJNÝ `@login_required` jako zbytek
  `api/remeslo.py` (nic nového) + navíc nový guard
  `require_feature_flag('remeslo_faktury_finance_enabled')` (403 s
  jasnou hláškou, i kdyby flag byl vypnutý a někdo trefil URL přímo) -
  dvojitá pojistka, ne spoléhání jen na skryté UI.
- **Frontend**: taby "Faktury" a "Finance" v `remeslo.html` se do DOM
  vůbec nevykreslí (ne jen `display:none` přes CSS), dokud `GET
  /api/remeslo/settings/feature-flags` nevrátí
  `remeslo_faktury_finance_enabled: true` - server je zdroj pravdy, ne
  jen lokální JS proměnná (stejný princip jako floating-layout
  defaults).
- **Přepnutí flagu NENÍ v UI vůbec** (žádné checkbox tlačítko, aby ho
  omylem nezaklikl jiný bot/tester) - jen ruční `UPDATE app_settings`
  skriptem/SQL, který spustí Robert/bot na jeho výslovný pokyn, až bude
  chtít modul zpřístupnit. Tohle je můj návrh výchozí bezpečné volby -
  kdyby Robert chtěl radši admin-UI toggle (i za cenu rizika omylu),
  potřebuju potvrzení, než to takhle postavím.

### Co jde implementovat (návrh pořadí)

1. SQL migrace: `remeslo_invoices`/`remeslo_invoice_items`,
   `remeslo_finance_transactions`, seed řádek `app_settings` (flag
   vypnutý).
2. Backend `api/remeslo.py`: CRUD faktur (založení z kalkulace = kopie
   položek se snapshotem + `_generate_doc_number(doc_type='faktura')`,
   založení ručně = prázdný seznam položek), přechody `status` s
   write-lockem po `vystaveno`, CRUD finance transakcí (vč. `POST
   .../job-materials/<id>/confirm-as-cost` zkratky), KPI endpoint.
   Rozšíření `api/gallery_items.py` o
   `owner_type='remeslo_finance_transaction'`.
3. Frontend `webapp/remeslo.html`: dva nové taby za flagem výš - Faktury
   (vzor Nabídky - filtr/tabulka/modal, navíc tlačítko "Vytvořit z
   kalkulace" s výběrem uložené kalkulace) a Finance (KPI dlaždice,
   seznam transakcí s filtrem typ/kategorie/období, formulář ruční
   transakce + foto, cash-flow graf).
4. Živé ověření: `test_client` (založení faktury z kalkulace se
   správným snapshotem, write-lock po vystavení, číselná řada `faktura`
   generuje očekávaný formát, KPI výpočty na testovacích datech,
   `uq_job_material` skutečně brání dvojímu potvrzení) + Playwright s
   reálnou podepsanou session (celý flow obou tabů, flag zapnutý jen
   pro test a po testu vrácený na `0`).

Čeká na schválení bot3/Robertem před psaním kódu (stejný proces jako
Modul 7/9).

## Hlasový "Moderátor" — průvodce hlasovým ovládáním (napříč moduly)

Robert 2026-08-19 pojmenoval hlasového průvodce **"Moderátor"** - tenhle
název se od teď používá i v kódu/komentářích/UI textech, ne obecně
"wizard"/"průvodce". Prototyp: `webapp/remeslo-hlas-test.html` +
`api/remeslo_voice_worker.py` (async fronta, lokální faster-whisper +
Piper, viz `AGENTS_LOG.md` 2026-08-19 pro celou historii vzniku -
ElevenLabs bez STT oprávnění, RAM/CPU rozvaha, proč lokální model).
Zatím pokrývá 2 záměry (založit zakázku, zapsat materiál k zakázce) -
architektura (`INTENTS` objekt, banka frází v `localStorage`) je
navržená tak, aby šla rozšířit na další moduly (viz níže).

**Závazná pravidla UX Moderátora** (Robert, živé testování 2026-08-19,
opakovaně potvrzeno):

1. **Vybízecí/žádací odpovědi musí být KRÁTKÉ.** Retry fráze (když
   appka nerozuměla) je přesně **"Prosím?"** - ne delší věta jako
   "Znovu prosím" (vyzkoušeno a zamítnuto), natož původní 5+ vteřinová
   souvětí (`say_again.wav`/`not_understood.wav` původně 5.4s/5.7s -
   příliš dlouhé, blokovaly hands-free tok).
2. **Mikrofon se musí spustit AUTOMATICKY přesně na konec přehrání
   výzvy** - přes `audio.onended` callback, NIKDY přes odhadnutý fixní
   `setTimeout`. Původní implementace s pevným 1800ms zpožděním po
   proměnlivě dlouhé výzvě způsobovala prázdné přepisy (uživatel mluvil
   dřív, než mikrofon reálně naběhl, nebo až po konci nahrávacího okna)
   - živě diagnostikováno 2026-08-19 přes logy workeru (hlasitost
   -55dB u "prázdných" nahrávek = ticho/oříznutý začátek).
3. **Moderátor musí mluvit VELMI RYCHLE** - Piper `SynthesisConfig
   (length_scale=0.72)` (defaultní `1.0` je znatelně pomalejší), platí
   pro všechny prompty, ne jen retry.
4. **Souběžně s hlasem se musí vypisovat text na obrazovku** - na PC
   někde bokem (ne přes celou šířku), na mobilu přes celou šířku
   (responzivní rozdíl, zatím NEIMPLEMENTOVÁNO v prototypu - `facelift`
   úkol níže).
5. **Banka frází musí zahrnovat reálná data z databáze**, ne jen fixní
   spouštěcí slova pro záměr. Robert 2026-08-19: "křičel jsem to do
   mikrofonu, pořád nerozuměl" u jména klienta - obecný Whisper model
   bez kontextu často špatně přepíše krátká izolovaná vlastní jména
   (známý problém, proto i fuzzy matching v kroku "ke které zakázce").
   Řešení: `initial_prompt` u `model.transcribe()` sestavený ze
   skutečných jmen zákazníků (`remeslo_jobs.customer_name`) a názvů
   materiálu (`remeslo_job_materials.nazev`, `remeslo_pricelist_items.
   name`) - viz `build_vocab_hint()` v `remeslo_voice_worker.py`,
   zatím globálně (žádný reálný řemeslnický účet, `craftsman_id` je
   u poznámek pořád NULL), časem filtrovat per-řemeslník.

**Standing pravidlo pro budoucí facelift** (Robert, 2026-08-19): **na
mobilu bude hlasové ovládání PRIORITNÍ způsob ovládání appky** - podle
toho se má přizpůsobit celý budoucí facelift administrace pro mobil
(ne jen doplněk vedle klasického klikání/psaní, ale hlavní interakční
model). Tohle NENÍ jednorázový úkol jako body 1-5 výš, je to trvalý
princip pro každý budoucí návrh mobilního UI Řemesla.

**Rozšíření banky frází - HOTOVO** (Robert, 2026-08-19, zadáno bot13,
komit afda0f8): 15 záměrů celkem - zakázka/materiál (původní 2) +
zákazník (CRM), 8 z 9 kalkuláček (Univerzální vynechána, zní
nepřirozeně nahlas), nabídka, faktura (gatovaná stejnou podmínkou jako
UI - `remeslo_faktury_finance_enabled`, kontrola PŘED kroky), ceník/
nastavení (čistá navigace na `remeslo.html#pricelist`/`#settings`,
žádné kroky). Viz `AGENTS_LOG.md` pro detaily ověření.

**Záměry kalkulaček se generují z DB - strukturální oprava** (bot13,
2026-08-19, na nález bot14): ruční seznam kalkulaček v `INTENTS` byl
strukturální mezera - kalkulačky `zdeni` a `voda_topeni` přibyly bez
hlasového záměru a totéž by se opakovalo s každou další (bot11 chystá
elektroinstalace/střechy/pergoly). Nově `registerCalcIntents()` v
`remeslo-hlas-test.html` staví záměry ze skutečných
`remeslo_calculator_types` → **nová kalkulačka = automaticky nový
hlasový záměr bez zásahu do Moderátora**. Ověřeno testem s dočasným
fake typem v DB (záměr, fráze i klikací tlačítko vznikly samy).
Dvě věci z DB nejdou a zůstávají jako mapy v kódu - autor nové
kalkulačky o nich NEMUSÍ vědět, ale může je využít:
- `CALC_PHRASES[code]`: ručně laděné fráze ("chci kopat", "zámkovku" -
  reálná řemeslnická mluva, z názvu typu nevygenerovatelná). Typ bez
  záznamu dostane automaticky fráze z názvu (`defaultCalcPhrases`:
  název, části názvu kolem "/", "spočítat <název>") - funkční od
  prvního dne, doladit jde v Bance frází nebo doplněním mapy.
- `CALC_NEEDS_HLOUBKA[code]`: DB tabulka nenese schéma vstupů. Všechny
  dnešní kalkulačky povinně chtějí jen `plocha_m2` (ostatní koeficienty
  mají výchozí hodnoty na serveru), jediná `zemni_prace` navíc
  `hloubka_m`. **Nová kalkulačka s dalším POVINNÝM vstupem potřebuje
  záznam v téhle mapě**, jinak se hlasem zeptá jen na plochu a server
  vrátí validační chybu (selhání je hlasité, ne tiché). "Univerzální"
  zůstává hlasově vynechaná (dřívější schválené rozhodnutí, natvrdo v
  `registerCalcIntents()`).

**Cílový stav: VŠE v administraci editovatelné hlasově** (Robert,
2026-08-19, standing princip - NENÍ úkol na jedno kolo): nejde jen o
založení nových záznamů (zakázka/materiál/zákazník/kalkulačka/
nabídka) ani jen o navigaci/vyhledávání - dlouhodobý cíl je, aby šlo
hlasem i EDITOVAT existující záznamy napříč celým adminem (Ceník,
Nastavení, Kalkulačky, Nabídky, Faktury...), ne jen je zakládat/
otvírat. Tohle mění dřívější zjednodušení ("u Ceníku/Nastavení stačí
jen navigace") - platí jako směr, kam se banka frází/Moderátor bude
postupně rozšiřovat, ne jako požadavek postavit editaci VŠEHO najednou
v jednom kole (viz "zpomalit tempo", Robert 2026-08-19 - rozsah roste,
tempo naopak zpomaluje). Praktický důsledek pro návrh: architektura
záměrů/kroků (INTENTS) by měla od začátku počítat s tím, že vedle
"založit X" budou časem přibývat i záměry "upravit X"/"změnit cenu Y".

**Vyhledávání hlasem** (Robert, 2026-08-19): vedle záměrů "něco
založit" musí Moderátor umět i **"hledat"** - řemeslník není u
desktopu, potřebuje si nechat něco z databáze vyhledat/přečíst nahlas
(ne jen zobrazit text, na obrazovku se třeba nedívá s rukama v práci).
Jde o jinou třídu záměru než "založ X" - dotaz + MLUVENÁ odpověď se
skutečnými daty, ne jen spuštění formuláře. Technicky navazuje na
existující vzor dynamické syntézy (`synthesize_confirmation()` ve
workeru už dnes skládá Piper větu za běhu s reálným obsahem, ne jen
přehrává statický soubor) - stejný princip pro odpověď na dotaz.
Rozsah pro v1 (návrh, k potvrzení): hledat zakázku podle jména
zákazníka (fuzzy shoda, stejný vzor jako u kroku "ke které zakázce" v
materiálu) a hledat cenu materiálu v Ceníku - širší "cokoliv z
databáze" nechat na další kola. Samostatný úkol NAVAZUJÍCÍ na
rozšíření banky frází výš, ne součást stejné dávky (jiná
komplexita - dotaz+odpověď, ne jen spuštění formuláře).

**V realizaci (bot13, 2026-08-19)** - návrh pro v1 rozsah přesně podle
zadání výš (hledat zakázku podle klienta + hledat cenu materiálu):
- **Nová backend syntéza mimo async frontu**: `synthesize_confirmation()`
  ve workeru běží jen jako součást zpracování NAHRANÉ poznámky (async
  fronta) - pro "dotaz → mluvená odpověď" je potřeba SYNCHRONNÍ
  syntéza libovolného textu z Flask procesu. Nový `POST /api/remeslo/
  voice-say` (`api/remeslo.py`) - lazy-loaded modulový singleton
  `PiperVoice` (načtení ~1.5s, jen při prvním použití, ne při startu
  appky), vrací WAV bytes přímo v response (stejný vzor jako QR PNG v
  modulu 8d - žádné pollování fronty, syntéza krátké věty trvá zlomek
  vteřiny).
- **`GET /api/remeslo/pricelist/items` rozšířeno o volitelný `?q=`**
  (LIKE na `name`, `category_id` se stává nepovinným, když je `q`
  vyplněné) - dosavadní volání vyžadovala vždy `category_id`
  (procházení jedné kategorie v UI), hledání "cokoliv v ceníku" ale
  potřebuje prohledat NAPŘÍČ kategoriemi jedním dotazem. Zpětně
  kompatibilní (čistě přídavné).
- **Dva nové "search" záměry** (`hledat_zakazka`, `hledat_cena`) -
  jiný TVAR intentu než dosavadní "založit X" (žádný `confirmLabel`/
  `submit`, místo toho `search(values) -> spoken text`), poslední krok
  místo přechodu na obrazovku potvrzení rovnou zavolá `search()`,
  přehraje odpověď přes `voice-say`, a vrátí se na úvod (žádné
  ukládání, dotaz nic nemění).
- **Nalezená a opravená latentní chyba při návrhu**: `detectIntent()`
  vracel PRVNÍ zamer (dle pořadí klíčů v `INTENTS`), jehož JAKÁKOLI
  fráze je podřetězcem přepisu - "hledej zakázku" obsahuje jako
  podřetězec frázi "zakázku" (existující spouštěcí fráze intentu
  "zakázka"), takže by se špatně spustilo založení nové zakázky místo
  hledání. Opraveno na "nejdelší shodující se fráze vyhrává" napříč
  VŠEMI záměry (ne jen podle pořadí) - obecně odolnější řešení, funguje
  i pro budoucí fráze, které si uživatel sám přidá do banky (viz
  "Rozšíření banky frází" výš), ne jen pro tento konkrétní střet.

**Volby ke kliknutí SOUČASNĚ s hlasovou nabídkou** (Robert, 2026-08-19):
u úvodní výzvy "Co založíme?" (a obecně kdekoli appka nabízí možnosti
hlasem) musí být stejné možnosti k dispozici ZÁROVEŇ jako klikatelná
tlačítka na obrazovce, ne jen text + poslech mikrofonu. Řemeslník má
mít vždy oba způsoby - říct to nahlas, nebo prostě kliknout - ne být
nucený mluvit, když se mu to zrovna nehodí (hlučné prostředí, cizí
lidé okolo apod.). Praktický dopad: `resetWizard()`/úvodní obrazovka
by měla vykreslit tlačítko pro KAŽDÝ existující záměr (zakázka,
materiál, zákazník, kalkulačka ×8, nabídka, hledat×2...) vedle
hlasového poslechu, klik na tlačítko rovnou nastartuje stejnou cestu
jako rozpoznání hlasem (`wz.intent = ...; goToStep(0)`).

**Auto-postup dál při jednoznačné shodě s DB** (Robert, 2026-08-19,
živý test kroku "Kdo je klient?" u zakázky - řekl "Novák", appka
přesně rozpoznala): pokud přepis JEDNOZNAČNĚ (jediná shoda) odpovídá
existujícímu záznamu v DB (typicky klient/zákazník), appka NEMÁ čekat
na ruční klik "Další" - má rovnou automaticky potvrdit a pokračovat na
další krok. Ruční potvrzení ("Rozuměl jsem... uprav, pokud je to
špatně" + tlačítka Zkusit znovu/Další) zůstává jen pro případy, kdy
shoda NENÍ jednoznačná (víc kandidátů, žádná shoda, nový/neznámý
klient) - tam je manuální kontrola pořád potřeba. Cíl: snížit friction
"za pochodu" u běžného opakovaného klienta, ne u nového/nejasného
případu. Vztahuje se na kroky, které už dnes mají fuzzy-match logiku
proti DB (např. "ke které zakázce" u materiálu), a nově i na kroky typu
"Kdo je klient?" u zakázky, kde se text dá porovnat proti existujícím
`remeslo_jobs.customer_name`.

**"Nápověda místo odpovědi" - kdykoli, v jakémkoli kroku** (Robert,
2026-08-19): řemeslník si třeba nemůže vzpomenout na jméno klienta
uprostřed kroku (např. "ke které zakázce patří materiál") - Moderátor
musí rozeznat i fráze typu "jaké mám možnosti"/"co je na výběr"/"kdo
jsou poslední klienti" MÍSTO očekávané odpovědi a "může kdykoli
překvapit otázkou namísto odpovědi" (Robert) - tedy tenhle typ fráze
se musí kontrolovat na KAŽDÉM kroku (cross-cutting, ne jen konkrétní
záměr), ne jen v top-level menu záměrů. Prakticky: `handleTranscript()`
by měl nejdřív zkontrolovat, jestli přepis odpovídá "nápovědní" frázi,
a pokud ano, VYPÍCHNOUT z normálního extract/valid flow kroku a
odpovědět nahlas kontextovým seznamem možností (u kroku "zakázka" =
poslední otevřené zakázky/klienti, u kroku "materiál" = naposledy
použité názvy materiálu, apod.) - stejný technický princip jako
"Vyhledávání hlasem" výš (dynamická Piper syntéza reálného obsahu),
jen spouštěč je jiný (žádost o nápovědu uprostřed kroku, ne
samostatný záměr). Po odpovědi se krok NEPOSOUVÁ dál - řemeslník má
pak znovu příležitost odpovědět na původní otázku.

**V realizaci (bot13, 2026-08-19)** - `handleTranscript()` napřed
zkontroluje (jen ve fázi `step`), jestli přepis odpovídá fixní sadě
nápovědních frází ("jaké mám možnosti", "co je na výběr", "nevím",
"nápověda"...) - pokud ano, VYPÍCHNE z běžného extract/valid flow.
Kontextová odpověď: u kroků s `resolveJob`/`resolveCustomer`
(existující fuzzy-match proti DB) = posledních 5 klientů/zakázek
seřazených podle `created_at`; u ostatních kroků (bez DB vazby, např.
"kolik to stálo v korunách") = jednoduše zopakuje otázku kroku, žádný
seznam možností k nabídnutí. Odpověď jde přes stejný nový `voice-say`
endpoint jako Vyhledávání výš. Krok se NEPOSOUVÁ, mikrofon se po
odpovědi znovu spustí na PŮVODNÍ otázku (žádné opakované přehrání
původního zvukového souboru otázky - jen nový dotaz na mikrofon).

**Tři hlavní volby na úvodní mobilní obrazovce** (Robert, 2026-08-19,
skládá se postupně): **Založit** (výš - zakázka/materiál/zákazník/
kalkulačka/nabídka), **Hledat** (výš), a **Přehledy** - předem
definované přehledy/reporty, které si řemeslník NASTAVÍ na desktopu
(v administraci na počítači), a na mobilu se mu pak jen zobrazí/
vyvolají (žádná konfigurace na mobilu, jen spotřeba - stejný princip
jako čekací doba nahrávání výš, "nastavuje se v administraci"). Jaké
konkrétní přehledy (dnešní zakázky? tržby týdne? rozpracované
nabídky?) zatím Robert nespecifikoval - k doplnění.

**Mobilní facelift - HOTOVO 1. kolo** (bot9, 2026-08-19, úkol TASKS.md
"mobilní facelift s hlasem jako primárním ovládáním"):

- **Moderátor je od teď sdílený `webapp/remeslo-hlas.js`**, ne kód uvnitř
  prototypové stránky. Používá ho appka (`webapp/remeslo.html`, mobilní
  hlasový režim) i dosavadní prototyp (`webapp/remeslo-hlas-test.html`,
  zeštíhlen na pár řádků). Důvod: dvě kopie stejné logiky by se rozešly
  při první další úpravě banky frází. Připojení:
  `RemesloHlas.mount({container, craftsmanId, mode, showHistory, exit,
  onNavigate})` - `mode: "mobile"` = text přes celou šířku (22px),
  `mode: "side"` = užší dok bokem na PC (přesně ten responzivní rozdíl
  z pravidla 4 výš).
- **Na mobilu (≤880px) je hlas VÝCHOZÍ pohled celé appky** - otevře se
  sám přes celou obrazovku, ne jako tlačítko někde v adminu. Klasická
  administrace je jedno klepnutí daleko ("✕ Administrace") a volba
  vydrží (localStorage `remeslo_voice_view`); zpátky do hlasu vede
  tlačítko 🎙️ Hlas v hlavičce. Na PC se hlas otevírá jen tím tlačítkem.
- **Tři hlavní volby** (Robertovo zadání) jsou skutečná první obrazovka:
  Založit / Hledat / Přehledy jako velké dlaždice + malý řádek "Otevřít"
  (Ceník, Nastavení). Záměrů je 20+, plochý seznam se na mobil nevejde
  a nedá se odposlechnout. Hlasem jde jít obojí cestou - přes skupinu
  ("založit") i rovnou na konkrétní záměr ("zámkovku"); vyhrává
  nejdelší shodující se fráze, takže zkratka skupinu přebije.
- **Přehledy (v1, 4 kusy)**: Rozdělaná práce, Termíny, Peníze tento
  měsíc, Nabídky - postavené nad UŽ existujícími endpointy
  (`/api/remeslo/jobs`, `jobs/summary`, `offers`), žádný nový backend.
  Odpověď se **řekne nahlas A vypíše** (obrazovka se sama nezavírá -
  na rozdíl od hledání - řemeslník si přehled může číst).
  **Konfigurace přehledů na desktopu zatím NENÍ** - Robert dosud
  neřekl, jaké přehledy chce; až padne jejich seznam, přibude k tomu
  i výběr "co se ukáže na mobilu" (dnes jsou vidět všechny čtyři).
- **Hledání nečeká na ruční "Další"** po posledním kroku (dotaz nic
  nemění a odpověď stejně zazní nahlas). Zakládání záznamu tuhle
  zkratku ZÁMĚRNĚ nemá - tam ruční kontrola zůstává.
- **Zpět odkudkoli**: drobečková navigace ("Moderátor / Založit /
  Zakázka") je klikatelná a vrací na tři hlavní volby - jediná cesta z
  rozdělaného záměru ven bez dokončení.
- **Nalezená a opravená chyba (živý test)**: rozpracovaná nahrávka se
  po odchodu z obrazovky doručila až na tu novou a přebila ji (přepis
  dorazí asynchronně, upload + čekání na worker). Řešeno generací
  nahrávky (`recSession`) - výsledek nahrávky z opuštěné obrazovky se
  zahodí. Stejný princip bude potřeba u každého dalšího asynchronního
  kroku Moderátora.
- **Nová QA kontrola** `missing_voice_prompt_file` (pravidlo #9): nový
  hlasový krok bez vygenerovaného `.wav` selhává TICHE (appka jen
  přeskočí hlas), na mobilu ale řemeslník přijde o celou otázku.
  Kontrola hlásí každý `audio:`/`playPrompt()` klíč bez souboru.
- **Nové výzvy** (Piper, `length_scale=0.72`, hlas jirka-medium, mimo
  git jako ostatní): `menu.wav`, `hledat.wav`, `prehledy.wav`.

**Rozhodnutí o Přehledech - uzavřeno** (Robert přes bot3, 2026-08-19,
odpověď na otevřenou otázku z 1. kola faceliftu):

1. **Zůstávají 4 přehledy** postavené v 1. kole - Rozdělaná práce,
   Termíny, Peníze tento měsíc, Nabídky. Žádný se nepřidává ani neruší.
2. **Počasní varování NENÍ pátý přehled** - zapojuje se DOVNITŘ přehledu
   **Termíny**. Zdůvodnění (proč to dává smysl): řemeslník se u termínů
   ptá "co mě čeká a co hoří" - a mráz na čtvrtek je přesně tak silný
   důvod k přeplánování jako blížící se termín. Samostatná položka by
   znamenala, že se musí zeptat dvakrát, aby se dozvěděl jednu věc.
   Praktický dopad: v mluveném i psaném výstupu Termínů se počasní
   riziko zmiňuje **navíc** k obvyklému overdue / due_soon / on_track,
   ne místo něj.
3. **Žádná konfigurace per řemeslník** - appka nemá reálné uživatele,
   bylo by to předčasné. Všechny 4 přehledy jsou na mobilu vidět vždy.

**Jak je počasí do Termínů zapojené** (bot9, 2026-08-19, implementace):
- **Znovupoužit hotový endpoint bot14** `GET /api/remeslo/weather-
  warnings?craftsman_id=` (pravidla + klienti MET Norway/Nominatim v
  `api/remeslo_weather.py`) - žádná druhá cesta k předpovědi, žádné
  vlastní vyhodnocování pravidel v JS.
- **Počasí Termíny nikdy nerozbije.** Je to doplňková služba nad cizí
  API: volá se souběžně se souhrnem, s vlastním časovým stropem (8 s), a
  když selže/nedoběhne/hlásí nedostupnost, přehled termínů se vypíše a
  přečte normálně - jen s poznámkou, že předpověď teď není. Ztichnout o
  tom by bylo horší než ta poznámka: řemeslník by si myslel, že počasí
  je v pořádku.
- **Mluvený výstup zůstává krátký**: za obvyklou větou o termínech
  přibude věta "Počasí: N rizik" a **detailně se řeknou nejvýš dvě**
  (nejdřív `stop`, pak podle data) - zbytek je na obrazovce. Dlouhá
  věta z technického listu se pro hlas zkracuje na část před pomlčkou
  + naměřenou hodnotu; na obrazovce je text celý, včetně normy.
- **Varování u zakázky bez termínu** (endpoint bere i zakázky, které
  mají jen `start_date`) se NEZAHAZUJE - vypíše se v Termínech zvlášť,
  označené "bez termínu v evidenci". Tiše je zahodit by znamenalo, že
  appka riziko zná a neřekne ho.
- Povinná atribuce MET Norway / OpenStreetMap (licence CC BY 4.0, ne
  kosmetika) se v přehledu vypíše vždy, když endpoint odpověděl -
  stejné pravidlo jako v desktopovém panelu bot14.

**Poslech spouští uživatel tlačítkem "Start"** (Robert, 2026-08-20):
appka **nesmí otevřít mikrofon sama od sebe** ("místo automaticky/naslepo
spuštěného mikrofonu - uživatel klikne Start, až pak appka začne
naslouchat"). **Tohle mění pravidlo 2 výš** (mikrofon automaticky na
konec výzvy) - to pravidlo NEZANIKÁ, jen přestává být výchozí:

- **Výchozí režim (klepací)**: na úvodní obrazovce, v každém kroku
  průvodce, po nepochopení i po nápovědě appka jen ukáže otázku a čeká.
  Nic se nenahrává, dokud uživatel neklepne na **▶ Start — poslouchat**.
- **Hands-free zůstává jako přepínač "Pokračovat samo"** (výchozí
  vypnuto, pamatuje se v zařízení): zapnutý = původní ping-pong,
  mikrofon naskočí sám přesně na konec výzvy. Nemazat ho - Robert si
  ten režim dřív výslovně vyžádal pro práci s rukama v písku; nově se
  jen neděje bez vyžádání. **Robert tohle řešení 2026-08-20 výslovně
  potvrdil** ("hands-free přepínač nechej, je to správné rozhodnutí") -
  není to tedy dočasný kompromis bota, ale schválený stav: příští
  úprava Moderátora ho nesmí zrušit "pro zjednodušení".
- **Technická část pravidla 2 platí dál**: když už mikrofon startuje
  sám (hands-free), startuje na `audio.onended`, NIKDY na odhadnutý
  `setTimeout`.
- **Hlas se neztrácí ani v klepacím režimu**: tlačítko **🔊 Přehrát
  otázku** přečte aktuální otázku nahlas, když se uživatel nechce dívat
  na displej. Výzva se ale sama od sebe nepřehrává - stejný princip
  jako u mikrofonu (a při načtení stránky ji stejně blokuje autoplay
  politika prohlížeče).
- Mount API: `RemesloHlas.mount({..., handsFree: true|false})` -
  volitelné, bez něj rozhoduje volba uživatele z `localStorage`.

**Mluvený výstup Termínů počítá ZAKÁZKY, ne porušená pravidla** (bot9,
2026-08-20, nález ze živého testu): reálná předpověď vrátila u 3 zakázek
10 varování (jedna zakázka klidně poruší 4 pravidla ve 4 dnech).
Původní "Počasí: 10 rizik" a přečtení prvních dvou znamenalo, že obě
mluvená varování patřila TÉŽE zakázce a o druhé ohrožené se řemeslník
nedozvěděl. Nově: "Počasí: riziko u N zakázek" + detailně dvě,
přednostně z RŮZNÝCH zakázek (uvnitř zakázky pořád platí stop před
pozor a pak datum). Mock to neodhalil - měl 2 varování u 2 zakázek.

**Focení zakázky přímo z hlasového rozhraní** (Robert 2026-08-20, podnět
bot14, které stavělo fotodokumentaci): mobilní facelift otevírá appku
rovnou do hlasového shellu, takže nová fotodokumentace (před/průběh/po)
byla dostupná až po zavření hlasu. Hlasem fotit nejde - ale zavírat kvůli
tomu celou obrazovku je krok navíc. Řešení (bot9):

- Focení je **normální záměr "Vyfotit"** ve skupině Založit - je vidět
  jako tlačítko a jde ho i **říct** ("vyfotit", "fotka", "focení").
  Hlas focení SPUSTÍ, dokončí se klepnutím; předstírat hlasové ovládání
  fotoaparátu nemá smysl.
- Kroky jsou klepací: **zakázka → fáze (před/průběh/po) → fotoaparát**.
  Na telefonu se otevře PŘÍMO zadní fotoaparát (`capture="environment"`,
  stejný princip jako skener dokladu i desktopová sekce), vedle je
  volba z galerie.
- **Žádný nový backend** - nahrává se stávajícím `POST /api/gallery-items`
  (`owner_type=remeslo_job`, `job_phase`), takže fotka rovnou sedí ve
  fotodokumentaci zakázky v desktopové administraci.
- Potvrzení se **řekne nahlas** ("Uloženo, 2 fotky k zakázce Novák, po
  dokončení.") - tady hlas smysl dává, uživatel drží telefon jako foťák.
  Následně nabízí "Fotit dál" (stejná zakázka i fáze) nebo Hotovo.
- Mikrofon se během celého focení neotevírá (viz pravidlo Start výš).

**Mobil = PWA, NE nativní appka** (Robert, 2026-08-19, rozhodnuto po
otázce): hlasové ovládání funguje spolehlivě i v mobilním prohlížeči
(`getUserMedia`/`MediaRecorder`) - není důvod pro nativní kód
(Swift/Kotlin/cross-platform), který by kompletně opustil sdílený
Flask/webapp stack, na kterém teď boti staví rychle. Až/pokud by hlas
na PWA narazil na skutečný technický limit, zvážit nativní znovu -
zatím ne.

**"Denní zásobník" hlasových POZNÁMEK - review na desktopu večer**
(Robert, 2026-08-19, koncept UPŘESNĚN - potvrzena varianta "alternativní
volný capture mód", viz níže; STÁLE ČEKÁ na vlastní návrh/schválení,
ne na malou implementaci): vedle živého "ping-pong" Moderátora (kde se
každý krok potvrzuje hned) existuje DRUHÝ, volný capture mód - "Nahrát
POZNÁMKU" - řemeslník kdykoli přes den namluví libovolnou poznámku
BEZ strukturovaných kroků/okamžitého potvrzení (nejnižší friction "za
pochodu"), appka ji jen zaznamená do fronty/zásobníku.

**Předzpracování BĚŽÍ NA POZADÍ PŘES DEN, ne až večer** - než si
řemeslník zásobník večer na desktopu otevře, fronta už MUSÍ být:
1. Přepsaná na text (běžný async worker vzor, `remeslo_voice_notes`).
2. Appka NAVRHNE zařazení podle kontextu - konkrétní příklady od
   Roberta: koncept nové faktury, poznámka k EXISTUJÍCÍ zakázce. Co se
   nedá jednoznačně zařadit ("nevíme, není zřejmé") zůstává jako HOLÁ
   poznámka - řemeslník si ji večer přiřadí sám ručně.
3. **Zpracování je PO JEDNOTLIVÝCH poznámkách** ("nasekané") - každá
   poznámka je samostatná jednotka s vlastním návrhem zařazení, ne
   jeden hromadný text/blob za celý den.

Architektonicky STEJNÝ princip jako dnes hotové "Třídění příchozích
e-mailů" (`api/support.py`, `support_email_triage_*`, dokončeno
2026-08-19 - viz `TASKS.md` Hotovo) - fronta položek s navrhovaným
zařazením + hromadné/řádkové schválení podle jistoty klasifikace,
"nejasné" zůstává k ruční revizi. STEJNÁ otázka jako u e-mailů: appka
dnes nemá žive AI volání (`ANTHROPIC_API_KEY` u jiného modulu
poznamenáno jako neplatný) - klasifikační návrh tedy pravděpodobně
půjde stejnou cestou jako triage e-mailů (bot/skript návrh připraví
mimo živé volání), NE spolehnout se na live LLM klasifikaci za běhu -
k ověření/rozhodnutí v návrhu.

Potřeba navrhnout/doplnit:
- Nové UI "Nahrát poznámku" (volný capture, bez kroků) vedle
  existujícího strukturovaného Moderátora - kde v appce (mobil
  primárně).
- UI "Zásobník" (desktop, večerní review) - seznam poznámek dne s
  navrhovaným zařazením, hromadné/řádkové potvrzení podle vzoru
  e-mailového třídění.
- Datový model: rozšířit `remeslo_voice_notes`, nebo nová tabulka
  (poznámka může mít navrhovaný cíl - `job_id`, "nová faktura" typ,
  nebo nic) - k návrhu.
Než se tohle začne stavět, potřebuje vlastní návrh/schválení (stejný
proces jako Modul 7/9/10/Infrastruktura-DB) - není to malá rozšíření
jako fráze výš.

### Návrh (bot13, 2026-08-19) - SCHVÁLENO A HOTOVO

**1. Datový model — rozšířit `remeslo_voice_notes`, NE nová tabulka.**
Zdůvodnění: každá nahrávka (krok Moderátora i volná poznámka) prochází
IDENTICKÝM životním cyklem (upload → fronta → přepis workerem →
hotovo/chyba) - jde o stejnou operaci s jedním volitelným dalším
krokem navíc (klasifikace) jen pro volné poznámky, ne o dvě různé
věci. Nová tabulka by duplikovala celou frontu/worker/endpoint
infrastrukturu beze smysluplného přínosu. Nové sloupce:
- `capture_mode ENUM('wizard_step','free_note') NOT NULL DEFAULT
  'wizard_step'` - rozlišuje krok Moderátora (dnešní chování, beze
  změny) od volné poznámky. Migrace nastaví všem STÁVAJÍCÍM řádkům
  `'wizard_step'` (přesně odpovídá realitě - dosud žádná volná
  poznámka nevznikla).
- `proposed_type ENUM('job_note','invoice_draft','unclear') NULL` -
  jen pro `free_note`, vyplní worker po přepisu.
- `proposed_job_id INT NULL` (FK `remeslo_jobs`, `ON DELETE SET
  NULL`) - vyplněno jen u `proposed_type='job_note'`.
- `proposed_reasoning VARCHAR(255) NULL` - krátké lidsky čitelné
  zdůvodnění návrhu (např. "shoda se zakázkou Novák"), zobrazí se v
  Zásobníku vedle badge.
- `review_status ENUM('pending','approved','rejected') NULL` - jen
  pro `free_note` (u `wizard_step` zůstává NULL, review tam nedává
  smysl). Výchozí `'pending'` po klasifikaci.
- `reviewed_by INT NULL` / `reviewed_at DATETIME NULL` (FK
  `app_users`) - stejný pattern jako `support_email_triage_proposals`.

**2. Klasifikace — AUTOMATICKÁ, rule-based ve workeru, NE bot-manuální
jako e-mailové třídění.** Tohle je přesně otázka, kterou bot3 označila
k rozhodnutí - řešení:
- E-mailové třídění (`support_email_triage_*`) je bot-manuální
  ("Tridit" tlačítko → bot ručně posoudí → zapíše návrh), protože jde
  o jednorázovou akci NA VYŽÁDÁNÍ s nuancovaným rozhodováním (víc
  kategorií, přílohy, obsah e-mailu) a nemá vhodný nepřetržitě běžící
  proces, na který by se dal navěsit.
- Zásobník má JINÉ zadání: "předzpracování BĚŽÍ NA POZADÍ PŘES DEN"
  (Robert, výslovně) - tedy potřebuje něco, co běží PRŮBĚŽNĚ, ne na
  jedno kliknutí. `remeslo_voice_worker.py` PŘESNĚ tohle už dělá
  (nekonečná smyčka, kontrola `pending` řádků každou 1s) - klasifikace
  se proto připojí HNED za úspěšný přepis (`mark_done()`), stejný
  proces, jen o krok víc, žádný nový worker/služba.
- Klasifikační pravidla jsou navíc jednodušší/úžeji vymezená než u
  e-mailů (Robertovy vlastní příklady: koncept faktury / poznámka k
  existující zakázce / nejasné) a existující fuzzy-match vzor
  (`resolveJob`/`resolveCustomer` v `remeslo-hlas-test.html`,
  "nejednoznačná shoda = radši nezařazovat") jde přímo přenést do
  Pythonu na serveru:
  1. Klíčová slova s kořenem "faktur" (fakturu/fakturovat/fakturou/
     fakturuj...) v přepisu → `invoice_draft`.
  2. Jinak fuzzy shoda přepisu proti `remeslo_jobs.customer_name`
     daného řemeslníka (stejný algoritmus jako `fuzzyNameMatch()` -
     společná předpona ≥70 % kratšího řetězce, nebo obsahování) -
     PŘESNĚ 1 shoda → `job_note` + `proposed_job_id`. 0 nebo 2+ shod
     (stejné pravidlo jako u živého Moderátora - nejednoznačné se
     NEHÁDÁ) → `unclear`.
  3. Jinak → `unclear`.
  Žádné živé LLM volání (stejný důvod jako u e-mailů - neplatný
  `ANTHROPIC_API_KEY`), ale na rozdíl od e-mailů to NENÍ obchvat kvůli
  chybějícímu klíči - i s platným klíčem by pravidlový přístup dával
  smysl kvůli rychlosti/nákladům na tak úzké zadání.

**3. UI "Nahrát poznámku" (mobil, volný capture).** SAMOSTATNÉ
tlačítko na úvodní obrazovce Moderátora (mimo `intentGrid` z předchozí
dávky - koncepčně jiný druh interakce, ne další "založ X" záměr).
Klepnutí spustí nahrávání BEZ automatického stopu po pevné době (na
rozdíl od kroků Moderátora) - řemeslník sám klepnutím nahrávání
ukončí, appka nahraje s `capture_mode=free_note` a OKAMŽITĚ se vrátí
na úvod ("Zapsáno, appka to zpracuje") - žádné čekání na přepis/
klasifikaci, žádné kroky/potvrzení (přesně "nejnižší friction").

**4. UI "Zásobník" (desktop, večerní review).** Nová záložka/panel v
`remeslo.html` (ne v testovacím `remeslo-hlas-test.html` prototypu -
tohle je už "reálná" admin funkce). Seznam dnešních (výběr data)
`free_note` řádků s `review_status='pending'`: přepis, badge podle
`proposed_type` (Faktura / Zakázka: jméno / Nejasné), `proposed_
reasoning`, řádkové Schválit/Zamítnout - stejný vzor jako e-mailové
třídění. Pro `unclear` navíc ruční výběr (dropdown existujících
zakázek, nebo "založit jako koncept faktury", nebo "zahodit").
Hromadné schválení pro vysokou jistotu (job_note s jednoznačnou
shodou) je rozumné UX rozšíření podle vzoru e-mailů, ale NENÍ nutná
součást MVP - lze doplnit později bez změny datového modelu.

**5. Co přesně dělá "Schválit" podle typu:**
- `job_note` → připojí přepis (s časovým razítkem) do `remeslo_jobs.
  note` dané zakázky (žádná nová tabulka pro "log poznámek k
  zakázce" - `note` pole už existuje, jde jen o append, ne
  strukturovaný seznam).
- `invoice_draft` → JEN pokud je `remeslo_faktury_finance_enabled`
  zapnuté (stejná kontrola jako živý záměr "faktura" v Moderátorovi) -
  založí `koncept` fakturu s přepisem jako poznámkou, zákazníka
  doplní admin ručně v Zásobníku před schválením (přepis samotný
  spolehlivé jméno zákazníka negarantuje). Je-li modul vypnutý,
  Schválit u tohohle typu zůstane needitovatelné s vysvětlující
  hláškou - žádné obcházení gatingu.
- `unclear` → čistě podle ruční volby admina (viz bod 4).

**Otevřené otázky - VŠECHNY ZODPOVĚZENY (Robert přes bot3, 2026-08-19):**
- `remeslo_jobs.note` append JE vhodné cílové místo pro `job_note` -
  ano, žádná nová tabulka, ale připojený text dostane časové razítko/
  prefix (`[19.08.2026 19:54 hlasová poznámka] …`), ať je v poli poznat,
  odkud přišel.
- "Nahrát poznámku" MÁ technický strop ~90 s, ale auto-stop až NA něm -
  není to výchovný krátký limit jako u kroků průvodce, řemeslník
  ukončuje sám klepnutím.
- Kořen "faktur" pro `invoice_draft` detekci pro v1 stačí, další
  spouštěče se doplní podle reálného provozu.

**Realizace (bot13, 2026-08-19) - co je hotové a naživo:**
- `sql/2026-08-19_remeslo_voice_notes_inbox.sql` - aplikováno na novou
  DB "Remeslnik" přes `api/db_migrate_remeslo.py` (nový skript, jen
  varianta `db_migrate.py` mířící na `REMESLO_DB_*`). `reviewed_by`
  NEMÁ FK constraint - `app_users` žije v jiné databázi a cross-database
  FK v MySQL nejde, stejně jako u už existujícího `created_by`.
- `api/remeslo_voice_worker.py` - klasifikace `classify_free_note()`
  navěšená hned za `mark_done()`, jen pro `capture_mode='free_note'`.
  Vlastní try/except, aby pád klasifikace neshodil už uložený přepis.
- **Shoda zákazníka je PO SLOVECH, ne přes celý přepis.** Zachyceno
  při testování: `fuzzyNameMatch()` z průvodce porovnává celé řetězce,
  což u krátké jednopolní odpovědi funguje, ale u celé věty ne ("U
  Zkouškovského jsem dodělal obklady" vs zákazník "Zkouškovský Bot13"
  není ani podřetězec, ani nemá společnou předponu od začátku věty).
  `customer_matches_note()` proto aplikuje stejné pravidlo na úrovni
  slov (slova <4 znaky se ignorují). Širší shoda není nebezpečná -
  pravidlo "přesně 1 kandidát, jinak `unclear`" ji stejně zahodí.
- `api/remeslo.py` - `GET /api/remeslo/inbox` (fronta, filtry
  craftsman/datum/review_status) a `PUT /api/remeslo/inbox/<id>`
  (schválit/zamítnout, vzor 1:1 podle `support_triage_proposal_review()`).
  `POST /api/remeslo/voice-notes` navíc přijímá `capture_mode` +
  `craftsman_id` (bez nich se chová přesně jako dřív).
- `webapp/remeslo-hlas-test.html` - tlačítko "Nahrát poznámku (bez
  otázek)" na úvodu, mimo `intentGrid`. Po nahrání se NEČEKÁ na přepis
  ani klasifikaci, appka jen potvrdí a vrátí se na úvod.
- `webapp/remeslo.html` - záložka "Zásobník" s kartami (badge podle
  typu, zdůvodnění návrhu, ruční přepsání cíle, Schválit/Zamítnout,
  přepínač "zobrazit i už vyřízené").
- **Chyba zachycená mimo scope:** worker po cutoveru na vlastní DB
  (91af721) pořád otevíral spojení přes `DB_*` (stará sdílená DB) -
  žádná nová nahrávka by se nikdy nezpracovala, worker by ji v jiné
  databázi neviděl. Opraveno na `REMESLO_DB_*` ve stejném commitu.
- Otestováno: 38 kontrol backendu (`test_client`) + 17 kontrol UI
  (Playwright, skutečné klikání v Zásobníku včetně gatingu fakturace).
  Všechna testovací data po každém kole smazána.

**Čekací doba nahrávání PER KROK, ne jeden globální timeout** (Robert,
2026-08-19): jednoduchá spouštěcí slova na začátku (např. "zakázka",
"materiál") potřebují jen pár vteřin, ale hlubší kroky (diktování
popisu práce, budoucí volné položky) potřebují delší okno. Řešení:
každý krok v `INTENTS[...].steps[]` má VLASTNÍ dobu nahrávání (ne
sdílený `RECORD_MS`), s rozumnými výchozími hodnotami podle typu kroku
(krátká pro spouštěcí slovo/jednoduché pole jako množství/cena, delší
pro volný popisný text). Robert výslovně: "pro každý modul si to bude
moct řemeslník upravit" - ALE zatím jen na desktopu/v administraci,
NE na mobilu ("van ministra ne na mobilu zatím" - přepis nejasný,
smysl: nastavitelnost patří do administrace, ne do mobilní obrazovky
Moderátora). V týhle fázi stačí per-krok konstanta v kódu s rozumnými
výchozími hodnotami - UI pro úpravu čekací doby řemeslníkem je
samostatný budoucí úkol (Nastavení), ne součást týhle dávky.

## Infrastruktura — přesun na vlastní DB (návrh, čeká na schválení)

Zadání: `TASKS.md` "Řemeslo - přesun na vlastní DB" (Robert 2026-08-19,
po zvážení - "teď je nejlevnější moment, dokud nejsou reálná produkční
data"). Nová DBaaS instance **"Remeslnik"** je založená a funkční
(`80.211.73.226:3306`, databáze `sns0vn5g0y` - přihlašovací údaje
`PRISTUPY.md`). Vlastník: bot14 (navazuje na dokončený Modul 10,
nejčerstvější kontext na `api/remeslo.py`).

### Klíčové zjištění před návrhem (živě ověřeno, mění výchozí předpoklad)

**Nová DB je na STEJNÉM fyzickém MySQL serveru jako hlavní DB**
(`80.211.73.226`), jen jiná databáze/účet - NE jiný host, jak by se dalo
čekat z názvu "vlastní DB". Ověřeno živě: účet hlavní DB (`z7bxj74521`)
vidí jen `xebyhtfeaj`, účet Remeslnik (`jz89th5ddg`) vidí jen
`sns0vn5g0y` - `SHOW DATABASES` u obou vrací jen tu vlastní. **Cross-
database JOIN/FK mezi nimi NEJDE** (žádný ze dvou účtů nemá grant na tu
druhou databázi) - i kdyby stejný server teoreticky umožňoval cross-db
FK v rámci jednoho uživatele, tenhle konkrétní DBaaS provisioning to
nedovoluje. **Důsledek pro celý návrh níž: `api/remeslo.py` bude muset
otevírat DVĚ NEZÁVISLÁ spojení** (běžící ve stejném gunicorn workeru,
ale ke dvěma různým databázím) - žádná SQL zkratka přes JOIN mezi
`remeslo_*` a `app_users`/`content_gallery_items` už nikdy nepůjde,
i kdyby dnes existovala (dnes NEexistuje - viz níž).

**Rozsah dat k přesunu je mnohem menší, než by "reálná dnešní práce"
naznačovala** (živě spočítáno, 2026-08-19): 30 `remeslo_*` tabulek,
celkem **2287 řádků**. Rozpad: `remeslo_material_prices` (1912,
scrapovaná srovnávačová data), `remeslo_workflow_app_features`/`_apps`
(136+33, průzkum konkurenčních appek), `remeslo_material_categories`/
`_category_professions` (61+61, taxonomie), `remeslo_pricelist_
categories`/`remeslo_calculator_types`/`remeslo_professions`/`remeslo_
price_sources` (14+9+1+6, systémové seed hodnoty), `remeslo_voice_
notes` (35, testovací nahrávky Moderátora). **`remeslo_craftsmen` má
JEDEN řádek** - `id=4, code='TEST-001', name='Testovací Řemeslník'` -
to je sdílená testovací fixtura zmíněná opakovaně v `AGENTS_LOG.md`
(používaná napříč boty pro testování), NE reálný zákazník. `remeslo_
jobs` má 3 řádky, všechny navázané na tuhle testovací fixturu
(`status='new'`). **Žádná faktura, kalkulace ani finance transakce v DB
aktuálně neexistuje** (moje vlastní testovací data jsem po sobě vždy
smazala - viz Modul 10 výš). `content_gallery_items` pro `remeslo_*`
owner_type má **0 řádků** (žádné foto zatím nahráno). Robertovo "reálná
produkční data" tedy prakticky ještě neexistují - je to buď
reprodukovatelný seed/scraper výstup, nebo sdílená testovací fixtura.
**Tohle mění doporučení u bodu (c) níž** - navrhuju NEPTAT SE "zahodit
vs. zachovat", ale rovnou **plný `mysqldump` všech 30 tabulek** (2287
řádků je triviálně rychlé, žádný důvod cokoli cherry-pickovat/zahazovat
ručním rozhodováním, které by mohlo něco omylem vynechat).

### (a) Směrování DB spojení

Nová `get_remeslo_conn()` v `api/remeslo.py` (ne v `api/app.py` -
Řemeslo-specifická věc), **1:1 stejný vzor jako existující `get_conn()`**
(`api/app.py:265`) - `threading.local()` pooling (1 trvalé spojení na
gunicorn worker/thread, `_PooledConn.close()` jen rollback+vrácení do
fronty, `connect_timeout=10, read_timeout=25, write_timeout=25`,
stejná pojistka v `@app.teardown_request`). Přihlašovací údaje nové
proměnné v `api/.env` (`REMESLO_DB_HOST/PORT/USER/PASSWORD/NAME`) -
`systemd EnvironmentFile` je načte automaticky po restartu služby,
žádný nový loading kód potřeba.

**Mechanický refaktor NENÍ bezpečné udělat jako slepé find-replace**
`get_conn()` → `get_remeslo_conn()` napříč souborem (97 výskytů) - u
API funkcí, které v JEDNOM spojení/kurzoru míchají `remeslo_*` dotaz s
dotazem na `app_users`/`content_gallery_items`, by to potichu rozbilo
běh (dvě různé databáze nejdou sdílet jeden `cur.execute()` řetězec).
**Konkrétní nalezený případ** (`remeslo_public_profile()`, řádek 1799):
jedno `conn`/`cur` postupně čte `remeslo_craftsmen`+`remeslo_
professions` (JOIN, oboje by šlo do Remeslnik DB) a HNED NATO
`content_gallery_items` (zůstává v hlavní DB, viz bod (c) níž) - tenhle
konkrétní endpoint bude muset otevřít DVĚ spojení a udělat dva
oddělené `cur.execute()` běhy místo jednoho. Plán: projít všech ~97
volání `get_conn()` v `api/remeslo.py` funkci po funkci (ne hromadně),
rozhodnout pro každou, jestli dotazuje jen `remeslo_*` (→ přepsat na
`get_remeslo_conn()`), jen `app_users`/audit/`content_gallery_items`
(→ nechat `get_conn()`), nebo obojí (→ rozdělit na dvě spojení).

### (b) Auth/session pro řemeslníky

**Návrh: ŽÁDNÁ ZMĚNA, aspoň v týhle fázi.** Bot3 navrhla v `TASKS.md`
vlastní `app_users`-ekvivalent pro Řemeslo - rozumná úvaha DLOUHODOBĚ,
ale právě teď je předčasná: `remeslo.html` je dnes fakticky admin-only
(`areaSwitchRemeslo` viditelný jen `role==='admin'`, `@admin_required`
na všech endpointech) - **žádní skuteční uživatelé-řemeslníci
neexistují** (potvrzeno i `remeslo_photo_analyses.sql` komentářem).
Veškerý dnešní přístup k Řemeslu (Robert i testující boti) jde přes
STEJNÝ přihlašovací systém jako zbytek administrace. Budovat teď
paralelní auth (vlastní login stránka, session cookie, reset hesla...)
pro nulu reálných uživatelů by bylo scope creep bez jasného přínosu -
a je to PŘESNĚ otázka, kterou už jednou otvírá `Modul 4 — Ověřovací
mechanismus` (identita řemeslníka před fakturací/plnohodnotným
přístupem) - navrhuju nechat rozhodnutí "mají řemeslníci vlastní účty a
kde žijí" na tenhle budoucí modul, ne ho předbíhat teď jen kvůli DB
přesunu.

Prakticky to znamená: `current_user()`, `admin_required()`,
`log_audit()` (všechny importované z `app.py` do `api/remeslo.py`,
řádek 115) **zůstávají BEZE ZMĚNY** - interně dál používají `get_conn()`
(hlavní DB), přesně jak dnes. `api/remeslo.py` se stává HYBRIDNÍM
modulem: byznys data (`remeslo_jobs`, `remeslo_invoices`, ...) přes
novou `get_remeslo_conn()`, identita/audit přes stávající `get_conn()`.
Žádná speciální "cross-db" logika tady není potřeba, protože auth
vrstva se vůbec nedotýká `remeslo_*` tabulek přímo (`current_user()`
čte jen `app_users`).

**Vedlejší dopad**: 2 existující FK (`remeslo_photo_analyses.reviewed_by`,
`remeslo_voice_notes.created_by` → `app_users.id`) musí při přesunu
zaniknout (cross-database FK nejde) - zůstanou jako obyčejné
nevynucené `INT` sloupce, STEJNĚ jako už dnes funguje zbylých 49 z 51
podobných odkazů na uživatele v `remeslo_*` tabulkách (`author_user_id`
u kalkulací/finance transakcí apod. FK nikdy nemělo). Žádná ztráta
funkčnosti v praxi - je to jen sjednocení na vzor, který už převažuje.

> **PŘEKONÁNO (bot13, 2026-08-19)** — rozhodnutí výš ("žádná změna,
> žádní skuteční uživatelé-řemeslníci") bylo přesně tím vzorem
> odkládání kvůli chybějícím uživatelům, který Robert 2026-08-19
> zastavil: *"My přece potřebujeme mít appku komplexní hotovou,
> nemůžeme jít dodělávat až se objeví 1 zájemci."* Zadání "Řemeslník
> se zaregistruje a pak si může volit profesi a přizpůsobovat si
> prostředí" tohle rozhodnutí ruší - viz **Modul 11** níž. Odstavec
> zůstává zapsaný jako historický kontext (proč `current_user()`/
> `admin_required()` dosud zůstávaly beze změny), ne jako platný stav.

### (c) Foto/galerie (`content_gallery_items`) - navrhuju NEPŘESOUVAT

Bot3 v `TASKS.md` navrhla "vlastní gallery tabulku" pro Řemeslo -
rozumná dlouhodobá myšlenka, ale navrhuju **menší zásah s stejným
efektem**, protože dat k přesunu je nula (viz zjištění výš): `content_
gallery_items` ZŮSTÁVÁ v hlavní DB jako dnes, žádná nová tabulka,
žádná duplikace upload/list/delete endpointů. Jediné místo, které
potřebuje úpravu: `_validate_owner()` v `api/gallery_items.py`
(řádek ~141) dělá živý `SELECT id FROM {OWNER_TABLE[owner_type]}
WHERE id=%s` PROTI VLASTNÍMU `get_conn()` (hlavní DB) - jakmile
`remeslo_jobs`/`remeslo_job_materials`/`remeslo_craftsmen`/`remeslo_
finance_transactions` (vlastníci fotek u Řemesla) zmizí z hlavní DB,
tahle validace by vždycky vracela "neexistuje". Oprava: `_validate_
owner()` (a JEN ona - `_serialize_item`/upload/delete/list zůstávají
beze změny, pracují jen s `content_gallery_items` samotnou, ne s
vlastníkem) dostane malou routovací tabulku `owner_type → která
connection funkce se má použít pro EXISTENCE CHECK` (`get_conn` pro
většinu, `get_remeslo_conn` pro `remeslo_job`/`remeslo_job_material`/
`remeslo_craftsman_public`/`remeslo_finance_transaction`) - import
`get_remeslo_conn` z `api/remeslo.py` do `api/gallery_items.py` (nebo
obráceně, ať se předejde kruhovému importu - k doladění při
implementaci). Volání `gallery_items.delete_items_for_owner(...)`
(3 místa v `api/remeslo.py`, cleanup při mazání zakázky/položky)
zůstávají beze změny - mažou jen z `content_gallery_items`, tu
tabulku nikam nepřesouváme.

Pokud by časem objem Řemeslo fotek narostl natolik, že bude dávat
smysl plná separace (Robertova ambice "samostatný SaaS produkt"), jde
to udělat POZDĚJI jako samostatný krok bez zpětné inkompatibility -
tenhle návrh nic nezamyká.

### (d) Plán přesunu dat

1. **Zámek** `scripts/lock.sh acquire bot14 "DB cutover" --wait` na
   `api/app.py`/`webapp/*` PŘED jakoukoli editací (i lokální, viz
   zpřísnění `WORKFLOW.md` 2026-08-18).
2. `mysqldump` VŠECH 30 `remeslo_*` tabulek (schéma i data) ze staré DB
   → import do `sns0vn5g0y`. Celý dump, ne výběr "co je důležité" (viz
   zdůvodnění výš - dat je málo, netřeba nic zahazovat ani cherry-
   pickovat).
3. `ALTER TABLE` na 2 FK zmíněné v (b) (drop constraint, sloupec
   zůstává).
4. Kódová změna `api/remeslo.py` (`get_remeslo_conn()` + funkce-po-
   funkci refaktor podle (a)) + `api/gallery_items.py` (`_validate_
   owner()` podle (c)) - napřed OFFLINE (žádné nasazení), ověřit
   `python3 -m py_compile`.
5. **Krátké okno**: nasadit kód + restart `konfigurator` služby,
   OKAMŽITĚ `curl /api/health` + `test_client` běh nad hlavními Řemeslo
   endpointy (craftsmen/jobs/offers/invoices/finance - existující testy
   z Modulu 10 jde spustit znovu jako smoke test) + Playwright na
   `remeslo.html`.
6. **Stará data (`remeslo_*` tabulky v hlavní DB) se NEMAŽOU**, dokud
   nová DB není prokazatelně funkční naživo aspoň X dní (přesné X k
   domluvě - navrhuju aspoň do doby, kdy vznikne první reálná faktura/
   zakázka v nové DB). Rollback = jen vrátit kódové změny (`git
   checkout` na commit před refaktorem) + restart, žádná ztráta dat.
7. Zápis do `AGENTS_LOG.md` s přesným seznamem, co se přesunulo a kdy,
   pro dohledatelnost.

### Otevřené otázky k potvrzení před implementací

- Souhlas s (c) - NEbudovat zatím vlastní gallery tabulku, jen malou
  routovací opravu `_validate_owner()`? (Bot3 navrhla plnou separaci -
  ptám se, jestli to i tak preferuje, i když dat k přesunu je nula.)
- Potvrzení rozsahu (d)2 - plný dump všech 30 tabulek, žádné ruční
  rozhodování co zahodit?
- Jak dlouho nechat starou `remeslo_*` data v hlavní DB po cutoveru,
  než se smažou (bod 6)?

Čeká na schválení bot3/Robertem před implementací.

## Počasí navázané na kalkulačky — technologická varování (návrh, čeká na schválení)

Zadání: `TASKS.md` "Řemeslo - počasí navázané na kalkulačky" (Robert
2026-08-19, vybráno z návrhu bot3). Vlastník bot14. Diferenciace:
žádná z 15 zkoumaných konkurenčních aplikací tohle nemá.

### Zdroj předpovědi — MET Norway, NE Open-Meteo (důležitá odchylka od zadání)

Bot3 navrhla Open-Meteo s podmínkou "ověřit podmínky použití". Ověřeno
(2026-08-19, open-meteo.com/en/terms): **free tier je VÝSLOVNĚ jen pro
nekomerční použití** ("subscription sites, advertising-supported apps,
and commercial product integration" vyloučeny). Řemeslo je zamýšlený
komerční SaaS - stavět na zdroji, který by při spuštění vyžadoval
migraci nebo placený tarif (~29 €/měs), je zbytečné riziko.

**Náhrada: MET Norway (api.met.no, locationforecast/2.0)** - ověřeno
živě 2026-08-19: komerční použití POVOLENO (CC BY 4.0), žádný API
klíč (jen povinný identifikační User-Agent s kontaktem), limit 20
req/s (nedosažitelný), ~10 dní hodinové předpovědi pro ČR
(air_temperature, relative_humidity, wind_speed + srážky v
next_x_hours blocích). Povinnosti: atribuce "Data: MET Norway" v UI
+ POVINNÁ lokální cache (nesmí se dotazovat opakovaně na totéž).

**Geokódování** (město → souřadnice): Nominatim/OSM (User-Agent,
max 1 req/s, cache povinná) - ověřeno živě. Výsledek se cachuje
NAVŽDY (města se nestěhují) v nové tabulce `remeslo_geo_cache`.

### Rozsah 1. iterace

**5 venkovních technologií**: `betonaz`, `fasada_zatepleni`,
`zamkova_dlazba`, `zdeni`, `zemni_prace`. Interiérové (malování,
sádrokarton, podlahy, obklady) VĚDOMĚ mimo - jejich podmínky (teplota
podkladu, vlhkost vzduchu v místnosti) se řídí vnitřním klimatem,
které předpověď počasí nezná; přidávat je by znamenalo varovat na
základě dat, která s realitou interiéru nesouvisí.

**Klimatické podmínky per technologie** - PŘEDBĚŽNÉ hodnoty (finální
ověření min. 2 nezávislými zdroji per podmínka PROBĚHNE při
implementaci, zdroje do docstringu - stejná metodika jako koeficienty
kalkuláček):
- **Betonáž**: teplota < +5 °C (ČSN EN 13670 - opatření pro betonáž
  za chladu; ebeton.cz/svaz výrobců betonu), > +30 °C (ČSN EN 206 -
  teplota čerstvého betonu), vydatný déšť.
- **ETICS/fasáda**: mimo +5..+25 °C (ČSN 73 2901 - provádění ETICS;
  technické listy Baumit/Weber), déšť, silný vítr (práce z lešení).
- **Zámková dlažba**: mráz (pokládka do nezmrzlého podloží - technické
  listy BEST/DITON, pokládací návody), vydatný déšť (podsyp).
- **Zdění**: teplota < +5 °C (technologické předpisy Wienerberger/
  Porotherm, Ytong - malty bez zimní úpravy), déšť.
- **Zemní práce**: vícedenní mráz (promrzlá zemina - ČSN 73 6133),
  vydatný/vícedenní déšť (rozmoklá zemina, hutnění).

Vyhodnocuje se **pracovní okno 7-17 h** daného dne (noční mráz mimo
pracovní dobu řeší jen betonáž - tuhnoucí beton mrzne i v noci; u
ostatních se hodnotí jen pracovní hodiny). Horizont: dnes + 9 dní
(víc MET nedá).

### Datový model a tok

- **Žádné ukládání varování do DB** - počítají se za běhu z předpovědi
  (stejný princip jako KPI Financí: žádný druhý zdroj pravdy).
- **`remeslo_weather_cache`** (DB Remeslnik): lat/lon zaokrouhlené na
  2 des. místa (~1 km, MET stejně chce max 4), `payload` JSON,
  `fetched_at`; TTL 3 h (MET vyžaduje caching, Expires hlavička ~1 h -
  3 h je konzervativní kompromis mezi čerstvostí a zátěží). Dotaz
  on-demand v endpointu, při cache-miss 1 HTTP volání - ŽÁDNÝ nový
  worker/cron (na rozdíl od Modulu 4 tu není fronta ani retry potřeba,
  předpověď je jen ke čtení a stará se smí použít).
- **Lokalita**: nový nullable sloupec **`remeslo_jobs.site_city`**
  (místo realizace - zadání výslovně chce vazbu na zakázku; dnešní
  `remeslo_jobs` žádnou adresu nemá) s fallbackem na město z profilu
  řemeslníka (`remeslo_craftsmen.city`). Bez obojího se zakázka
  přeskočí (UI: "doplňte město pro předpověď").
- **Vazba technologie**: zakázka → kalkulace (`remeslo_calculations.
  job_id`) → `calculator_type.code`. Zakázka bez kalkulace nebo s
  interiérovou technologií se přeskočí. Kalkulace bez zakázky nemá
  termín - není k čemu varovat (vědomé omezení).

### API + UI

- `GET /api/remeslo/weather-warnings?craftsman_id=` - projde zakázky
  řemeslníka se `start_date`/`due_date` protínajícím horizont, vrátí
  varování `{job, den, technologie, podmínka, naměřená hodnota,
  doporučení}` + atribuci.
- UI (tab Zakázky): panel "Počasí pro zakázky" nad seznamem (jen když
  existují varování nebo zakázky v horizontu) + ⚠ badge u řádku
  zakázky s varováním. Povinná atribuce "Data: MET Norway (CC BY 4.0),
  geokódování © OpenStreetMap" v patičce panelu.

### Ověření

`test_client` s mock předpovědí (vstříknuté hodnoty → očekávaná
varování per technologie - hraniční hodnoty ±0,1 °C), živý běh proti
MET pro reálné město, Playwright (panel + badge + atribuce). Stejná
disciplína jako předchozí moduly.

Čeká na schválení bot3/Robertem před implementací.

## Modul 11 — Samoobslužná registrace řemeslníka + volba profese + přizpůsobení prostředí

Zadání (Robert, 2026-08-19, přesné znění): *"Řemeslník se zaregistruje
a pak si může volit profesi a přizpůsobovat si prostředí."* Doprovodná
oprava chování: appka se má stavět KOMPLETNÍ, ne po částech
odkládaných s odůvodněním "nemáme reálné uživatele" - přesně tahle
věta zrušila dřívější rozhodnutí v sekci "Infrastruktura" bod (b)
výš (odkaz tam). **Vlastník: bot13.**

### Co dnes chybí (zjištěno živě, ne z paměti)

- `webapp/remeslo.html` má tvrdý gate `if (user.role !== "admin")` →
  okamžité odhlášení - appka je fakticky uzavřená pro kohokoli mimo
  `role='admin'`. Žádná cesta dovnitř pro reálného řemeslníka
  neexistuje.
- `remeslo_craftsmen` (DB Remeslnik) nemá ŽÁDNOU vazbu na `app_users`
  (DB hlavní/e-shop) - řemeslníky dnes zakládá výhradně admin ručně
  (`POST /api/remeslo/craftsmen`, `@admin_required`).
- `remeslo_professions` (tabulka pro kódové řady "ELE-0001" a
  materiálový srovnávač Modulu 1) má **jen 1 řádek** ("Instalatér
  (voda, topení)") - Modul 1 se nikdy nerozšířil na víc profesí.
  `remeslo_calculator_types` (Modul 9) má naproti tomu **14 aktivních
  typů** a je to jediný seznam "profesí", který appka dnes reálně
  používá napříč kalkulačkami, nabídkami i Moderátorem.
- E-shop MÁ kompletní, hotovou samoobslužnou registraci/login
  (`POST /api/auth/register`, `/login`, `/logout`, `/me`, session-
  based, `app_users.role` enum) - HLAVNÍ PRAVIDLO projektu (nestavět
  auth od nuly) říká tohle znovupoužít, ne psát vlastní přihlašovací
  systém pro Řemeslo.

### Rozhodnutí

1. **Registrace řemeslníka JE registrace do `app_users`**, ne
   paralelní systém - reuse `/api/auth/register` vzoru (bcrypt/
   werkzeug hash, session cookie, žádné e-mailové ověřování, stejná
   jednoduchost jako e-shop). Nový endpoint `POST
   /api/remeslo/register` (veřejný, bez přihlášení) dělá NAVÍC to, co
   e-shop registrace nedělá: založí i řádek `remeslo_craftsmen`
   propojený s novým účtem, a rovnou podle zvolené profese.
2. **Nová role `remeslnik`** v `app_users.role` ENUM (`ALTER TABLE
   app_users MODIFY role ENUM('admin','manager','user','skladnik',
   'ucetni','monter','sklad','remeslnik') NOT NULL DEFAULT 'user'`) -
   žádná ze stávajících rolí (`user`/`manager`/`skladnik`/`ucetni`/
   `monter`/`sklad`) neodpovídá "externí řemeslník se svým vlastním
   účtem", jsou to všechno interní e-shopové role. Účet e-shopového
   zákazníka (`role='user'`) a účet řemeslníka jsou navíc záměrně
   ODDĚLENÉ i při shodném e-mailu - stejná adresa může mít nezávisle
   oba účty (jiný `id`), appky se nesměšují.
3. **Vazba `remeslo_craftsmen.app_user_id INT NULL UNIQUE`** (nový
   sloupec, DB Remeslnik) - BEZ FK (cross-database FK nejde, stejný
   ustálený vzor jako `created_by`/`reviewed_by` jinde v `remeslo_*`).
   `NULL` = řemeslník založený admin ručně (dnešní stav, žádný login),
   vyplněné = self-service účet. Zpětně kompatibilní, nic se
   nerozbije u existujícího 1 řádku v produkci.
4. **Profese pro volbu VÁŽE na `remeslo_calculator_types`** (Robertovo
   zadání), ne na řídce osídlenou `remeslo_professions` samotnou -
   ale `remeslo_professions` se ZACHOVÁVÁ (kódová řada "PREFIX-0001"
   na ní pořád závisí, měnit teď identitu existujícího řemeslníka by
   bylo zbytečně riskantní). Řešení: nový sloupec
   `remeslo_professions.calculator_type_id INT NULL UNIQUE` (FK v
   rámci JEDNÉ DB Remeslnik - obě tabulky tam už žijí, tady FK jde) +
   jednorázová idempotentní migrace, která:
   - napojí existující řádek "Instalatér (voda, topení)" na
     `calculator_type.code='voda_topeni'` (id 11),
   - založí zbylých 13 `remeslo_professions` řádků (jeden na
     `calculator_type`), s `code_prefix` odvozeným z názvu typu
     (kolize řeší ruční tabulka zkratek v migraci, ne auto-zkracování
     - "Zámková dlažba"/"Zemní práce" by se jinak srazily na stejný
     prefix).
   Výsledek: `profession_id` na `remeslo_craftsmen` zůstává jediný
   zdroj pravdy o profesi (kódování i personalizace), `calculator_
   type_id` je jen přemostění na existující kalkulačkový katalog -
   ŽÁDNÁ třetí duplicitní tabulka profesí.
5. **Profese se PO REGISTRACI NEMĚNÍ** - platí stávající pravidlo z
   Modulu 1 (`profession_id` je zdroj kódu, změna by ho znehodnotila).
   Pokud řemeslník profesi skutečně změní, řeší to admin ručně (nové
   pole je low-frequency edge case, ne self-service tlačítko v 1.
   iteraci).

### Schéma (SQL, doplnění)

```sql
-- Hlavni DB (app_users) - nova role
ALTER TABLE app_users
  MODIFY role ENUM('admin','manager','user','skladnik','ucetni','monter','sklad','remeslnik')
  NOT NULL DEFAULT 'user';

-- DB Remeslnik
ALTER TABLE remeslo_craftsmen
  ADD COLUMN app_user_id INT NULL UNIQUE AFTER id;   -- FK app_users.id, BEZ vynucení (cross-DB)

ALTER TABLE remeslo_professions
  ADD COLUMN calculator_type_id INT NULL UNIQUE,
  ADD CONSTRAINT fk_profession_calc_type FOREIGN KEY (calculator_type_id)
      REFERENCES remeslo_calculator_types(id);

-- Personalizace prostredi podle profese - ktere kalkulacky jsou
-- vychozi/eminentni. Bez radku pro dany typ = kalkulacka existuje,
-- ale neni pro tuhle profesi zvyrazena (porad dostupna pres "Vsechny
-- kalkulacky").
CREATE TABLE remeslo_profession_calculator_defaults (
    profession_id       INT NOT NULL,     -- FK remeslo_professions
    calculator_type_id  INT NOT NULL,     -- FK remeslo_calculator_types
    is_default           TINYINT(1) NOT NULL DEFAULT 0,  -- predvyplnena/pripnuta
    prominence           INT NOT NULL DEFAULT 0,          -- vyssi = vys v razeni
    PRIMARY KEY (profession_id, calculator_type_id)
);
```

**Seed dat `remeslo_profession_calculator_defaults`** (součást stejné
migrace, idempotentní): pro každou profesi její vlastní 1:1
kalkulačka (`prominence=100, is_default=1`) + `univerzalni` pro VŠECHNY
profese (`prominence=50, is_default=0` - univerzální kalkulačka je
napříč profesemi užitečná, ale ne automaticky připnutá). Robert může
matici později doladit ručně (admin UI, bod níž) - seed dává rozumný
start bez nutnosti ruční kurace předem.

### Registrace - tok a endpoint

`POST /api/remeslo/register` (veřejný):
```
{email, password, name, phone?, company_name?, subject_type, ico?, dic?, calculator_type_id}
```
1. Validace stejná jako `/api/auth/register` (e-mail formát, heslo
   ≥8 znaků) + `calculator_type_id` musí existovat a mít napojenou
   `remeslo_professions` řádek (jinak 400 - nemělo by nastat, seed
   pokrývá všech 14).
2. **Zápis do DVOU databází, bez distribuované transakce** (cross-DB,
   stejné omezení jako všude v `remeslo.py`) - pořadí a kompenzace:
   a. INSERT `app_users` (hlavní DB, `role='remeslnik'`), commit.
   b. `_assign_craftsman_code()` (existující funkce z Modulu 1,
      beze změny) + INSERT `remeslo_craftsmen` (DB Remeslnik,
      `app_user_id`=id z kroku a, `status='candidate'` - beze změny
      výchozí hodnoty, žádný nový status jen kvůli self-service).
   c. **Selže-li (b)**: DELETE právě vytvořeného řádku `app_users`
      (kompenzace, ne ponechání osiřelého účtu bez craftsman profilu)
      a vrátit 500 s obecnou chybou - řemeslník to jednoduše zkusí
      znovu, žádný napůl založený stav nezůstane viditelný.
   d. Vyplněné IČO → rovnou `_enqueue_auto_verification()` (stejné
      chování jako u dnešního admin-založení, Modul 4 se nemusí nijak
      měnit).
3. Session (`session["user_id"]`) na nový `app_users.id`, appka rovnou
   přihlásí - stejné UX jako e-shop.
4. Odpověď obsahuje i `craftsman` (kód, profese) - frontend rovnou ví,
   kam přesměrovat (do appky, ne zpátky na registrační formulář).

### Volba profese a "přizpůsobení prostředí" - co konkrétně dělá

- **Nový endpoint `GET /api/remeslo/my-environment`** (nová role
  `remeslnik` NEBO `admin` s `?craftsman_id=` - viz gating níž):
  vrátí `{craftsman, profession, calculators: [{id, code, name,
  is_default, prominence, has_calculation}]}` - `calculators` seřazené
  `prominence DESC`, sloučené s plným seznamem `remeslo_calculator_
  types` (typy bez řádku v `_defaults` mají `prominence=0`).
- **UI (`webapp/remeslo.html`, tab Kalkulačky)**: u `role==='remeslnik'`
  se dlaždice kalkulaček řadí/zvýrazňují podle `my-environment` místo
  dosavadního pevného pořadí; `is_default=1` typy jsou navíc vidět
  hned na "Přehledu" bez prokliku. U `role==='admin'` beze změny
  (admin spravuje všechny profese, personalizace nedává smysl).
- **Moderátor "Přehled" (koordinace s bot9, needituji `webapp/remeslo-
  hlas.js` souběžně)**: `my-environment` je navržený jako STEJNÝ zdroj
  dat, který by měl řídit prioritizaci hlasových záměrů v "Přehledu" -
  zapsáno jako poznámka pro bot9 v `AGENTS_LOG.md` (a zde), konkrétní
  zapojení do `remeslo-hlas.js` dělá bot9 sám, až bude mít volno/
  zámek na svém souboru.

### Řízení přístupu (gating) - co se mění a co NE

**Frontend** (`webapp/remeslo.html` řádek ~5756): gate rozšířen na
`role !== "admin" && role !== "remeslnik"`. U `role==='remeslnik'`
navíc skrýt admin-only navigaci (Řemeslníci-seznam VŠECH, Ověření-
správa, Nastavení fakturačních číselných řad jiných řemeslníků,
Finance) - vidí jen svůj vlastní prostor.

**Backend - nový helper** `remeslnik_or_admin_required` (`api/
remeslo.py`, vzor `admin_required` z `app.py`) + `current_craftsman()`
(najde `remeslo_craftsmen` řádek podle `current_user()["id"]` ==
`app_user_id`). Endpoint pod tímhle dekorátorem: admin prochází vždy,
`remeslnik` prochází JEN pro svůj vlastní `craftsman_id` (kontrola v
těle funkce, ne v dekorátoru - stejný vzor jako `_require_craftsman`
dnes).

**Nasazeno v 1. iteraci na** (aby "přizpůsobení prostředí" mělo koho
obsluhovat, ne aby zůstalo mrtvým formulářem):
- `GET/PUT /api/remeslo/craftsmen/me` (nový - vlastní profil,
  `profession_id` needitovatelné, viz rozhodnutí 5 výš)
- `GET /api/remeslo/my-environment` (nový, viz výš)
- `GET /api/remeslo/calculator-types`, `GET/POST/PUT /api/remeslo/
  calculations` (Modul 9) - vlastní kalkulace řemeslníka
- `GET/POST/PUT /api/remeslo/jobs*` (Modul 2 - evidence zakázek) -
  bez vlastních zakázek by čerstvě registrovaný řemeslník neměl co
  dělat po přihlášení
- `GET /api/remeslo/craftsmen/<id>/verification` (jen READ vlastního
  stavu ověření, Modul 4 - ať řemeslník vidí, co má doložit; `PUT`/
  admin akce zůstávají `@admin_required`)

**ZŮSTÁVÁ `@admin_required` beze změny v týhle iteraci** (jmenovitě,
ne mlčky vynecháno): CRM/poptávky (Modul 3), Nabídky + fakturační
nastavení (Modul 8), Faktury a Finance (Modul 10 - navíc pořád za
feature flagem `remeslo_faktury_finance_enabled=0`), admin akce
Ověřování (Modul 4), správa VŠECH řemeslníků (seznam/edit/delete
cizích profilů), Spolupracovníci (Modul 7 část B). **Důvod NENÍ**
"nemáme uživatele" (přesně tahle věta je teď zakázaná, viz úvod
modulu) - je to uznání, že plný multi-tenant self-service přístup ke
KAŽDÉMU z těchhle modulů je vlastní, samostatně otestovatelná práce
(fakturace navíc má vlastní podmínku "komplexní ověřování identity
před fakturací", viz sekce "Mimo současný scope" níž) - zapsáno jako
**nová položka v `TASKS.md`** ("Řemeslo - self-service přístup k
zakázkám/nabídkám/fakturaci pro roli remeslnik", navazuje na tenhle
modul), ne jako tichý ústupek.

### Ověření

`test_client`: registrace (úspěch, duplicitní e-mail, chybějící
`calculator_type_id`, kompenzační DELETE při selhání kroku b),
`my-environment` obsah pro víc profesí, gating (`remeslnik` nemůže na
cizí `craftsman_id` ani na admin-only endpointy, `admin` prochází
vším beze změny), migrace (idempotence - 2× spuštění nezdvojí 13
nových profesí). Playwright: registrační formulář → volba profese →
přihlášení → Kalkulačky ukazují personalizované pořadí. Stejná
disciplína jako předchozí moduly.

Nahlášeno Robertovi po dopsání týhle sekce (bez čekání na schválení
přes bot3 - pokyn "pojedu dál souborně"), pokračuji rovnou stavbou.

## Mimo současný scope (zaznamenáno, ne zrušeno)

### Poptávkový/nabídkový systém (lead-gen mezi zákazník a řemeslníkem)

Odlišné od modulu 3 (CRM) - viz rozhodnutí č.3 výš. Pokud by se tohle
časem přidalo, mantinely z `REMESLO_PRUZKUM.md` doporučení č.4:
- Nikdy neprodávat jeden kontakt neomezenému počtu řemeslníků.
- Transparentní/predikovatelná cena předem, ne aukční model.
- Žádné auto-renewal smlouvy, reálná refundace (peníze, ne "kredit").
- Zvážit klesající poplatek pro opakované zákazníky (retence).

### Provozní nástroje nad rámec modulů 2-3 (fakturace, plánování kapacit)

`REMESLO_PRUZKUM.md` doporučení č.5 (Houzz Pro) - modul 2 (evidence
zakázek) a modul 3 (CRM) pokrývají základ, ale plná fakturace/
platby/plánování kapacity zůstává mimo současný scope, možné budoucí
rozšíření modulu 2, ne samostatná stavba teď.

**Strategie nabalování a pořadí fakturace (Robert, 2026-08-19):**
appka Řemeslo se buduje POSTUPNÝM nabalováním jednotlivých prvků
(hlas, foto, evidence zakázek...), ne najednou - každá vrstva se
průběžně testuje sama o sobě, dřív než se přidá další. **Fakturace/
doklady jsou v tomhle pořadí záměrně AŽ NA KONCI**, ne proto, že by
byly nedůležité, ale protože vyžadují nejvyšší míru důvěryhodnosti
ze všech modulů - appka musí mít napřed prokázané, že funguje
spolehlivě na méně rizikových věcech.

**Podmínka před spuštěním fakturace: komplexní ověřování identity**
(Robert, 2026-08-19: "určitě potřebujeme komplexní ověřování identity
před plnohodnotným používáním aplikace na doklady") - motivováno
reálným bezpečnostním nálezem z hloubkového průzkumu appek
(`REMESLO_APPKY_HLOUBKOVY_PRUZKUM.md`): BitFaktura byla zneužita
podvodníky k vygenerování falešných faktur, protože dostatečně
neověřuje, že vystavitel skutečně vlastní firmu na faktuře. Fakturace
v Řemeslu se NESMÍ spustit bez robustního ověření vystavitele -
navazuje na `Modul 4 — Ověřovací mechanismus` výš (tam je to zatím
pojaté jako ověření řemeslníka/reference obecně, tady jde specificky
o ověření identity PŘED vystavením dokladu - stejný datový základ
`remeslo_verification_checks`, jen přidat `check_type`
`'identita_pred_fakturaci'` až se k modulu dojde). Konkrétní úroveň
ověření (ARES/DIČ kontrola vs. silnější KYC typu BankID) zatím
nerozhodnuto, řeší se až ve fázi návrhu fakturačního modulu.

## Odhad rozsahu/složitosti (orientační, ne závazný odhad hodin)

| Modul | Rozsah | Hlavní riziko |
|---|---|---|
| 1. Srovnávač cen (PRIORITA) | Střední (minimální jádro řemeslníků/profesí + pilotní scraper + ruční formulář, BEZ geokódování - zahozeno) | Údržba scraperu při změně cizích webů; rozsah "tisíce položek" závisí na tom, jak velké katalogy 2-3 pilotní dodavatelé skutečně mají |
| 2. Evidence zakázek | Malý (1 tabulka, CRUD dle hotového vzoru) | Žádné zásadní |
| 3. Jednoduché CRM | Velmi malý (1 sloupec navíc do existující tabulky + filtr v UI) | Žádné zásadní - záměrně nejmenší možný zásah |
| 4. Ověřovací mechanismus | Malý-střední (1 tabulka, admin UI) | Žádné zásadní |
| 5. Foto-analýzy/crowdsourcing | Střední, ale ODLOŽENO | Neplatný `ANTHROPIC_API_KEY`; smysl dává až s existující uživatelskou základnou |
| 6. Akvizice řemeslníků | Malý jako kód, otevřený jako proces | Není "dokončitelný" úkol |

## Co jde první implementovat (návrh, čeká na schválení)

Konkrétní první krok modulu 1 (srovnávač cen), rozložený na ověřitelné
kroky - schváleno Robertem (přes bot3, 2026-08-17: "Vyber podle svých
kritérií... a pokračuj plánem"), implementace v běhu:

1. ✅ **Výběr 1 profese + 2-3 reálných dodavatelů** - instalatér
   (voda/topení), Ptáček-shop.cz + Aquatopshop.cz (ověřeno živě dle
   5 kritérií výš).
2. ✅ Minimální SQL migrace aplikována a commitnuta
   (`sql/2026-08-17_remeslo_pricing_pilot.sql`).
3. ~~Geokódovací pomocná funkce~~ - ZAHOZENO (Robert, 2026-08-17:
   "nám stačí ceny které jsou normálně na eshopech", žádný
   vzdálenostní filtr v modulu 1 - viz poznámka výš).
4. ✅ Scraper pro OBA dodavatele hotov a spuštěn (`--kontrola` →
   `--apply`) - 16 cen Ptáček-shop.cz + 6 cen Aquatopshop.cz, reálná
   data v `remeslo_material_prices`.
5. Jednoduchý admin formulář na ruční zadání ceny - V BĚHU.
6. Minimální srovnávací dotaz/endpoint (bez plného admin UI zatím) -
   V BĚHU.

---

## Zviditelnění odvození a zdroje u položek kalkulaček — NÁVRH (bot9, 2026-08-20, čeká na schválení)

### Zadání (Robert, 2026-08-20)

Položka kalkulace dnes vrací jen `nazev/mnozstvi/jednotka/is_mandatory` -
řemeslník vidí "Zdicí malta 75 l", ale ne že vzniklo jako 3,0 l/m² ×
25 m², ani že zdrojem je technický list Wienerberger Porotherm Profi.
Koeficienty a zdroje jsou poctivě zapsané, ale jen v docstringu Python
funkce. Cíl: (1) položka nese navíc stručné ODVOZENÍ a ZDROJ, (2) v UI
se zobrazí u položky bez rozbití layoutu, (3) u KLÍČOVÝCH koeficientů
jde přepsat pravidlo, ne jen výsledné číslo. Rozsah: 14 kalkuláček,
**přesně 129 položek** (ověřeno `grep -c '"nazev":'` nad rozsahem
`_calc_*` funkcí).

Tenhle návrh vznikl ve třech nezávislých krocích - vlastní návrh →
nezávislá druhá architektura od nuly (general-purpose agent, žádný
kontext prvního návrhu) → adversární recenze prvního návrhu proti
živému kódu (druhý agent) - a je jejich syntézou. Několik věcí z
prvního draftu recenze prokázala jako chybné nebo mylně orámované;
opraveno níže, ne skryto.

### Ověřený současný stav (ne odhad — citováno konkrétními řádky)

- `remeslo_calculation_items` (`sql/2026-08-19_remeslo_calculators.sql:50-66`):
  `nazev/mnozstvi/jednotka/cena_jednotka_czk/is_mandatory/is_used/
  sort_order/pricelist_item_id` - žádné pole pro odvození/zdroj.
- `POST /api/remeslo/calculations` (`remeslo.py`, `remeslo_calculation_create`)
  volá `calc_fn(inputs)` **jen jednou při založení**.
- `PUT /api/remeslo/calculations/<id>` (`remeslo_calculation_update`) je
  **jediný dnešní způsob editace** - čistý `DELETE`+`INSERT` toho, co
  pošle frontend. Nikdy znovu nevolá `calc_fn` - **recompute dnes
  neexistuje vůbec**.
- `POST .../revise` klonuje aktuální položky do nového řetězového
  řádku, taky bez přepočtu.
- `_match_pricelist_item()` řeší OBCHODNÍ cenu z Ceníku řemeslníka -
  je to jiná věc než technický zdroj koeficientu, nesmí se zaměňovat.
- Frontend: `webapp/remeslo.html`, per-typový formulář
  `.calc-fields[data-code=...]` + ruční JS gatherer
  `REMESLO_CALC_INPUT_GATHERERS` na typ - **dnešní mechanismus
  přepisu koeficientu funguje JEN při zakládání**, ne u existující
  kalkulace. `renderRemesloCalcEditorItems()` vykresluje tabulku
  Název/Množství/Jednotka/Cena/Celkem/Povinná/Použít/Smazat.
- **Důležitá korekce prvního draftu**: `_calc_betonaz` má **už dnes**
  editovatelná pole `rezerva_percent`, `tloustka_m`, `obvod_m`,
  `s_vyztuzi`, `tl_podsyp_m` přímo ve formuláři "Nová kalkulace"
  (`webapp/remeslo.html:1802-1808`, popisek doslova "Technologické
  výchozí hodnoty (můžete přepsat)"). Betonáž tedy NENÍ čistá ukázka
  "dnes se nedá nic přepsat" - je to ukázka jiného problému: koeficient
  JDE přepsat, ale **jen při zakládání**, nikde není vidět ODVOZENÍ ani
  ZDROJ, a po uložení kalkulace se k němu už nedá vrátit.
- 129 položek, ~50 z nich už dnes čte koeficient jako `inputs.get(klíč)
  if … else default` - tenhle vzor je návod, jak by editovatelnost
  MECHANICKY měla vypadat, jen dnes nemá popisek/zdroj a nefunguje po
  uložení.

### Datový model

**1. Item dict z `_calc_*` funkce** — 4 nová nepovinná klíče vedle
stávajících `nazev/mnozstvi/jednotka/is_mandatory`:

```python
{
    "nazev": "Zdicí malta",
    "mnozstvi": 75.0,
    "jednotka": "l",
    "is_mandatory": True,
    "klic": "malta",                                            # NOVÉ
    "odvozeni": "3,0 l/m² × 25 m²",                               # NOVÉ - runtime string se SKUTEČNÝMI čísly
    "zdroj": "Wienerberger Porotherm Profi (technický list)",     # NOVÉ - statická citace
    "koeficienty": [{"input_key": "malta_l_m2", "label": "Spotřeba malty",
                      "hodnota": 3.0, "vychozi": 3.0, "jednotka": "l/m²"}],  # NOVÉ, jen číselné koeficienty
}
```

- **`klic` musí být nezávislý na `nazev`** - potvrzeno na reálném
  precedentu z kódu, ne teoreticky: `nazev` u řady položek obsahuje
  DOPOČÍTANÉ číslo přímo v textu (`f"Rozváděč - skříň (orientačně
  {velikost} modulů)"`, `f"Překlad nad otvor ({delka_mm} mm, {ks} ks
  vedle sebe)"`) a mění se i čistým přejmenováním beze změny obsahu
  (`"Zakládací lišta"` → `"Zakládací lišta s okapničkou"`,
  `remeslo.py:6702`, zdokumentováno v `TASKS.md`). `nazev` proto NELZE
  použít jako párovací klíč mezi dvěma přepočty.
- **`klic` je od nasazení stabilní smluvní hodnota** - přejmenovat ho
  v `_calc_*` funkci bez migrace znamená, že staré uložené přepisy v
  `inputs_json` tiše přestanou platit (spadnou na výchozí hodnotu, ne
  chybu). Psáno jako závazná konvence u helperu (viz níž), ne jen
  doporučení.
- **Žádný pevný `round(mnozstvi, 2)` v infrastruktuře** - reálný kód
  má různé zaokrouhlování v téže funkci (celé kusy, `math.ceil` na
  balení, 1 desetinné místo u výztuže) - o zaokrouhlení rozhoduje
  autor `_calc_*` funkce jako dosud, helper ho nevnucuje.
- **`koeficienty` jen pro ČÍSELNÉ hodnoty.** Booleovské technologické
  přepínače (`s_vyztuzi`, `s_krytinou`, `mokry_provoz`) do stejného
  manifestu NEPATŘÍ (jiný typ ovládacího prvku) - v první verzi
  zůstávají tam, kde jsou dnes (checkbox ve formuláři při zakládání);
  jejich zpřístupnění v editoru existující kalkulace je vědomě MIMO
  rozsah tohohle kola, ne přehlédnutá mezera.
- **Kritérium "klíčový koeficient"**: jen technologicky vázané
  spotřební číslo s citací výrobce/normy (16 ks/m², 3,0 l/m²).
  Geometrická aritmetika a rezervy, které už mají vlastní pole
  (`rezerva_percent`), se do `koeficienty` nezdvojují - jinak by se
  rozbalovací panel zacpal a UI přestalo být přehledné.

**2. `remeslo_calculation_items` — 4 nové nullable sloupce**

```sql
ALTER TABLE remeslo_calculation_items
    ADD COLUMN klic              VARCHAR(80)   NULL AFTER pricelist_item_id,
    ADD COLUMN mnozstvi_formula  DECIMAL(10,2) NULL AFTER mnozstvi,
    ADD COLUMN odvozeni          VARCHAR(500)  NULL AFTER mnozstvi_formula,
    ADD COLUMN zdroj             VARCHAR(300)  NULL AFTER odvozeni,
    ADD COLUMN koeficienty_json  JSON          NULL AFTER zdroj,
    ADD COLUMN is_orphaned       TINYINT NOT NULL DEFAULT 0 AFTER is_used,
    ADD KEY idx_klic (calculation_id, klic);
```

Snapshot princip (stejný jako dnešní `nazev`/`cena_jednotka_czk`) -
`odvozeni`/`zdroj`/`koeficienty_json` se zapíší v okamžiku
výpočtu/přepočtu, ne live. Staré řádky mají `NULL`/`0` → **žádný
backfill**, nic se nerozbíjí.

**`mnozstvi_formula` místo příznaku `manually_edited`** (vylepšení
oproti prvnímu draftu, převzato z nezávislého druhého návrhu - je to
lepší mechanismus, protože se neopírá o to, že frontend spolehlivě
nastaví boolean při každé editaci): sloupec drží POSLEDNÍ hodnotu,
kterou navrhla formule. Při přepočtu se porovná `mnozstvi !=
mnozstvi_formula` - liší se → uživatel ho ručně přepsal → ponechá se
jeho číslo. Rovnají se → volně se přepíše. Odvozeno z dat, ne z toho,
že si frontend "pamatuje" checkbox.

**3. Kam se ukládá PŘEPIS koeficientu**: nikam nově - do už
existujícího `remeslo_calculations.inputs_json`. `calc_fn(inputs)` čte
koeficient jako `inputs.get(klíč, default)`, takže přepis koeficientu
je jen přidání klíče do `inputs`, které appka už dnes ukládá a umí
znovu přehrát.

### Backendový mechanismus

**Dva malé helpery** (zavádí se jednou, retrofituje se kalkulačka po
kalkulačce - žádný jednorázový přepis všech 14 funkcí):

```python
def _coef(inputs, key, label, default, jednotka=""):
    """Cte KLICOVY (cislený) koeficient z inputs - stejny vzor, jaky uz
    dnes pouziva rezerva_percent, jen navic vraci popis pro UI manifest.
    `key` je od nasazeni STABILNI SMLUVNI HODNOTA - nemenit bez migrace."""
    val = inputs.get(key)
    val = float(val) if val not in (None, "") else float(default)
    return val, {"input_key": key, "label": label, "hodnota": val,
                 "vychozi": default, "jednotka": jednotka}

def _item(klic, nazev, mnozstvi, jednotka, is_mandatory, odvozeni=None,
          zdroj=None, koef=None):
    d = {"klic": klic, "nazev": nazev, "mnozstvi": mnozstvi,
         "jednotka": jednotka, "is_mandatory": is_mandatory}
    if odvozeni: d["odvozeni"] = odvozeni
    if zdroj: d["zdroj"] = zdroj
    if koef: d["koeficienty"] = koef
    return d
```

Použití (ilustrace na `_calc_betonaz`, ne finální kód):

```python
rezerva, k_rez = _coef(inputs, "rezerva_percent", "Rezerva na ztráty", 7, "%")
distancniky_ks_m2, k_dist = _coef(inputs, "distancniky_ks_m2", "Hustota distančníků", 4, "ks/m²")
items = [
    _item("beton", "Beton (transportbeton)", plocha*tloustka*(1+rezerva/100), "m3", True,
          odvozeni=f"{plocha:g} m² × {tloustka:g} m × (1 + {rezerva:g} % rezerva)",
          zdroj="kolikmaterialu.cz, zalitobetonem.cz (5-10 % typicky, střed)", koef=[k_rez]),
]
if s_vyztuzi:
    items.append(_item("distancniky", "Distančníky pod výztuž", plocha*distancniky_ks_m2, "ks", True,
                 odvozeni=f"{plocha:g} m² × {distancniky_ks_m2:g} ks/m²",
                 zdroj="ramibar.cz (min. 1,3) / praxe zákl. desek (~4) - zvolena hustší", koef=[k_dist]))
```

**Poctivá korekce k pilotu**: `distancniky_ks_m2` v dnešním kódu je
NAPEVNO `plocha * 4` - žádné `inputs.get("distancniky_ks_m2")`
neexistuje (adversární recenze to ověřila grepem). Zpřístupnění téhle
konkrétní konstanty tedy není "jen obalení existujícího vzoru", je to
**nově přidávaná editovatelnost** - stejná kategorie práce jako u
zbylých ~80 dosud napevno zapsaných konstant. Neskrývám to.

### Nový endpoint: přepočet

```
POST /api/remeslo/calculations/<id>/recompute
body: { "inputs": {...sloučené staré + nové koeficienty, plochý dict...} }
```

**Bezpečnost** (přidáno po recenzi - v tomhle souboru byly za poslední
dny NALEZENY A OPRAVENÉ dvě autorizační díry přesně v sousedních
endpointech `remeslo_calculation_create`/`revise`, kde řemeslník A
mohl navázat na zakázku řemeslníka B): `/recompute` musí projít
STEJNOU kontrolou vlastnictví jako dnešní `PUT` -
`@remeslnik_or_admin_required` + `_require_owns_craftsman(user,
existing["craftsman_id"])` PŘED jakýmkoli čtením/zápisem. Bez
výjimky, žádné nové zjednodušení.

**Merge politika** (položka řádek po řádku, párováno přes `klic`):

- `klic` existuje ve starých ITEMS **a** `mnozstvi == mnozstvi_formula`
  (nedotčeno ručně) → přepsat `mnozstvi/mnozstvi_formula/jednotka/
  nazev/odvozeni/zdroj/koeficienty_json` novým výpočtem. **`nazev` je
  součástí přepisu** (oprava draftu - recenze našla reálný precedent
  přejmenování položky se stejným `klic`, kde by stará `nazev` jinak
  zůstala navěky zavádějící).
- `klic` existuje **a** `mnozstvi != mnozstvi_formula` (ručně
  poladěno) → mnozstvi/cena/pricelist_item_id/is_used se **nesahá**,
  jen `mnozstvi_formula` se aktualizuje pro příští srovnání.
- `klic` je v novém výstupu, ale ve starých položkách chybí → nový
  řádek, doplní se `_match_pricelist_item` jako u `create`.
- `klic` byl ve starých položkách, ale nový výstup ho už neobsahuje →
  **nikdy se nemaže** (bez ohledu na to, jestli byl ručně upravený) -
  jen `is_orphaned=1, is_used=0`. Reverzibilní: vrátí-li se `klic` v
  příštím přepočtu, řádek ožije. (Oprava draftu — původní verze mazala
  needitované osiřelé položky; "nikdy nemazat, jen orphan-mark" je
  bezpečnější a je to i konzistentnější chování napříč všemi řádky.)
- Položky BEZ `klic` (ručně přidané tlačítkem "+ Přidat položku") →
  recompute se jich nikdy nedotkne.

**Nezbytná pojistka — neretrofitovaná kalkulačka** (kriticky
nalezeno recenzí, chybělo v draftu úplně): dokud `_calc_*` funkce
nevrací `klic` u ŽÁDNÉ položky (13 ze 14 kalkuláček na startu), mají
staré položky `klic IS NULL` stejně jako ručně přidané - merge
politika by je nerozeznala od sebe a při prvním přepočtu by **zdvojila
celý seznam položek** (staré beze změny + nové jako "všechno je
nové"). Endpoint `/recompute` proto MUSÍ nejdřív zavolat `calc_fn` a
zkontrolovat, že aspoň jedna vrácená položka má `klic` vyplněný - pokud
ne, vrátit `400` s jasnou zprávou "Tahle kalkulačka zatím nepodporuje
přepočet" a frontend podle toho tlačítko "Přepočítat" vůbec nezobrazí.

**Legacy kalkulace retrofitované kalkulačky** (staré `klic IS NULL`
položky u JIŽ retrofitované funkce, založené před nasazením): první
přepočet takové kalkulace vygeneruje klíčované položky VEDLE starých
neklíčovaných → možná viditelná duplicita. Řešení: potvrzovací dialog
PŘED prvním přepočtem takové kalkulace: *"Tahle kalkulace vznikla
před touto funkcí. Přepočet přidá položky podle aktuálního vzorce
vedle stávajících - zkontrolujte prosím duplicity."* Čestné řešení bez
tichého rizika, cena je jednorázový ruční úklid.

**PUT (`remeslo_calculation_update`) musí dostat stejné nové sloupce**
(kritická oprava draftu — recenze prokázala, že bez tohohle by první
kliknutí na "Uložit" v editoru po založení kalkulace se zdrojem/
odvozením tato data TICHE smazalo, protože dnešní `PUT` handler
`INSERT`uje jen 9 původních sloupců a nezná 4 nové). `PUT` zůstává
sémanticky "nahraď přesně tím, co posílám" (ruční editace), `/recompute`
zůstává "přepočítej podle vzorce a chytře slij" - dvě různé věci,
nesmí se plést, ale OBĚ musí umět persistovat všech 12 sloupců řádku.

**Odemčené, ale explicitně přiznané riziko — souběžná editace**:
`/recompute` bere vstupy z klienta a přepisuje server bez kontroly
verze/konfliktu - stejná slabina, jakou má dnešní `PUT` (žádná
optimistická zámek dnes neexistuje nikde v modulu kalkulaček).
Recompute přidává DRUHOU cestu, jak dvě otevřené karty mohou přepsat
práci druhé. Navrhuji **přijmout jako existující riziko** (shodné s
dnešním stavem, ne nové zhoršení) a NEŘEŠIT ho v tomhle kole - řešení
(verzování řádků, optimistic locking) je samostatný, obecnější úkol
napříč celým modulem kalkulaček, ne specifický pro tenhle návrh.
Robert ať potvrdí, že tohle je přijatelné.

### UI

**Odvození/zdroj — rozbalitelný řádek, ne nový sloupec.** V buňce s
`nazev` nativní `<details>` (žádná nová JS knihovna, žádný layout
shift při zavřeném stavu, staré položky bez `odvozeni`/`zdroj` blok
vůbec nevykreslí - tabulka vypadá identicky jako dnes):

```
┌─────────────────────┬────────┬──────┬────────┬─────────┬──────────┐
│ Zdicí malta ▾        │ 75.00  │  l   │ 12 Kč  │ 900 Kč  │ Povinná  │
├─────────────────────┴────────┴──────┴────────┴─────────┴──────────┤
│ Výpočet: 3,0 l/m² × 25 m²                                          │
│ Zdroj: Wienerberger Porotherm Profi (technický list)               │
└──────────────────────────────────────────────────────────────────┘
```

**Klíčové koeficienty — jeden GENERICKÝ panel, ne ručně psaná pole.**
Tohle je nejdůležitější rozhodnutí z hlediska rozsahu a zároveň přesně
to, co dnes v noci způsobovalo kolize (3 boti současně v jednom obřím
bloku formulářů `webapp/remeslo.html`). Panel `#remesloCalcCoefPanel`
("⚙ Upravit klíčové koeficienty") se vykreslí ZE SEZNAMU koeficientů,
který backend vrátí spolu s položkami po posledním výpočtu/přepočtu -
žádný bot nikdy nepíše nové `<input>` pole ručně pro nový koeficient;
nová kalkulačka/koeficient = jen `_coef()` volání v Pythonu, frontend
ho zobrazí automaticky.

**Vyřešená kolize s dnešním formulářem** (recenze našla, draft
přehlédl): `rezerva_percent` u Betonáže je DNES editovatelné pole ve
formuláři "Nová kalkulace". Po zavedení generického panelu by stejný
koeficient šel měnit na dvou místech - matoucí. Rozhodnutí: **formulář
"Nová kalkulace" zůstává jediné místo pro editaci PŘED prvním
uložením** (jak je dnes), generický panel se objevuje **jen v editoru
JIŽ ULOŽENÉ kalkulace** a při otevření se předvyplní hodnotami z
`inputs_json` (včetně toho, co uživatel zadal při zakládání) - žádná
duplicita v jednu chvíli viditelná, jen dvě různé fáze životního
cyklu. Existující formulářová pole (`remesloCalcFormBetRezerva` apod.)
se NEMAŽOU ani nepřejmenovávají.

**Otevření staré kalkulace s legacy `inputs_json`**: pokud `calc_fn`
při sestavování manifestu koeficientů spadne na `ValueError` (validace
se mezitím zpřísnila), musí to shodit JEN panel koeficientů (zobrazí
se "Přepočet zatím není dostupný"), ne zbytek editoru - položky jsou
statický snapshot a musí zůstat funkční a zobrazitelné bez ohledu na
stav panelu.

### Rollout — postupně, s koordinací

1. **Infrastruktura** (`_coef`/`_item` helpery, 4 DB sloupce,
   `/recompute` s bezpečnostní kontrolou, rozšíření `PUT` o nové
   sloupce, rozšíření `_serialize_calculation_item`) - malý izolovaný
   diff v `api/remeslo.py`.
   - **Ověřeno živě, ne předpokládáno**: `scripts/lock.sh status` teď
     drží bot8 (nesouvisející úkol na scéně) - to potvrzuje, že
     infrastruktura reálně nemůže začít okamžitě bez ohledu na kvalitu
     plánu.
   - **Důležitější zjištění recenze**: `webapp/remeslo.html` a
     `api/remeslo.py` momentálně NEJSOU v klidu obecně - `TASKS.md`
     ukazuje otevřené položky u víc botů současně (UI pole, rozšíření
     zbývajících profesí). Vlastnictví těchto souborů je momentálně
     ROZPTÝLENÉ mezi víc botů, ne jeden konkrétní, na kterého lze
     čekat. Navrhuji **nezahajovat infrastrukturní zásah bez
     krátkého koordinačního oznámení v `AGENTS_LOG.md`/u koordinátora
     těsně před tím**, ne jen kontrolovat zámek.
2. **1 pilotní kalkulačka retrofitovaná + UI panel + rozbalitelný
   řádek** → ukázat Robertovi živě, než se škáluje na zbylých 13.
   Betonáž zůstává navrhovaným pilotem pro OBSAH (je moje, `TASKS.md`
   ji vede jako hotovou, ne rozpracovanou), ALE demo musí rovnou
   ukázat i vyřešenou "dvě místa pro totéž číslo" otázku výš, jinak
   bude první dojem matoucí.
3. Po schválení: zbylých 13 kalkuláček, JEDNA kalkulačka = JEDEN
   commit s explicitním pathspec (osvědčený noční postup), přednostně
   ty, které právě nemá nikdo rozdělané. Funkce jsou v souboru
   odděleny (nesdílejí stav), takže riziko merge kolize mezi boty při
   MIGRACI TĚL funkcí je nízké i bez zámku - zámek/koordinace je
   potřeba hlavně pro krok 1 (sdílené body: DB migrace,
   `_serialize_calculation_item`, endpointy, frontend panel).
4. `webapp/remeslo.html` (rozbalitelný řádek + generický panel) je
   JEDNORÁZOVÝ zásah společný pro všechny kalkulačky - největší
   potřeba koordinace se soustředí PŘESNĚ sem.

### Otevřené otázky pro Roberta

1. **Souhlas s architekturou** (`klic` + `mnozstvi_formula` +
   `is_orphaned`, `/recompute` endpoint, generický panel místo
   ručních HTML polí)?
2. **Souběžná editace zůstává neřešená** (stejné riziko jako dnešní
   `PUT`) - přijatelné pro tohle kolo, řešit později jako samostatný
   úkol?
3. **Rozhodnutí o dvou místech pro koeficient**: formulář "Nová
   kalkulace" = editace před uložením, generický panel = editace po
   uložení, žádné mazání existujících polí. Souhlas?
4. **Betonáž jako pilot** - souhlas, s vědomím že `distancniky_ks_m2`
   je NOVĚ přidávaná editovatelnost (ne jen zviditelnění), a že demo
   musí ukázat řešení bodu 3 hned napoprvé?
5. Kritérium "klíčový koeficient" (technologie mění číslo vs.
   administrativní rezerva s vlastním polem) - souhlas s principem?

---

## Zviditelnění odvození a zdroje — ROZŠÍŘENO o individualizaci (Robert, 2026-08-20)

Robert posunul zadání výš z "zviditelnit odvození" na produktový
slib: *"Nemáme pro vás předchystané řešení, protože vám nabídneme
zdarma řešení zcela na míru."* Kaskáda hodnot, per-řemeslník výchozí
koeficienty a trvale skryté položky - viz samostatná sekce níž (vložena
za původní návrh, číslování otázek 1-5 výš se týká PŮVODNÍHO návrhu a
zůstává v platnosti beze změny, tohle je jeho ROZŠÍŘENÍ, ne náhrada).


### Rozšíření — PER-ŘEMESLNÍK VÝCHOZÍ HODNOTY (individualizace kalkulaček)

**Robert, 2026-08-20** — posunuje předchozí návrh z "zviditelnit
odvození" na produktový slib: *"Nemáme pro vás předchystané řešení,
protože vám nabídneme zdarma řešení zcela na míru."* Odvození + zdroj +
editovatelné koeficienty výš jsou technický základ, ale samy o sobě
řeší jen JEDNU kalkulaci - řemeslník přepíše spotřebu malty a příště
začíná zas od systémové výchozí hodnoty. Tenhle dodatek přidává
TRVALOU vrstvu: koeficient se stává řemeslníkovým osobním nastavením.

#### Kaskáda hodnot (3 úrovně)

```
hodnota v TÉTO kalkulaci  >  výchozí hodnota ŘEMESLNÍKA  >  SYSTÉMOVÁ hodnota (technický list)
```

Mechanicky se to řeší **na hranici endpointu, ne uvnitř `_calc_*`
funkcí** - `_coef()` z předchozí sekce zůstává BEZE ZMĚNY (pořád jen
`inputs.get(key, default)`), protože `inputs` dict, který do `calc_fn`
vstupuje, se **před voláním** sestaví jako:

```python
def _effective_inputs(craftsman_id, calculator_type_id, body_inputs):
    """Slozi kaskadu: telo pozadavku PREPISUJE remeslnikovu vychozi
    hodnotu, ktera PREPISUJE systemovou (tu uz zna az samotna _calc_*
    funkce jako svuj default - tady se nedotycne, pokud remeslnik
    nemá ulozenou vlastni)."""
    craftsman_defaults = _fetch_craftsman_coef_defaults(craftsman_id, calculator_type_id)  # {input_key: hodnota}
    return {**craftsman_defaults, **body_inputs}
```

Tím zůstává `_calc_*` funkce nadále **čistá funkce jednoho dictu** -
žádná z 14 funkcí se kaskády vůbec nemusí dotýkat, žádné DB volání
uvnitř, žádná ztráta dnešní testovatelnosti ("zavolej funkci napřímo s
pevnými čísly", jak se testuje celou noc). Kaskáda je čistě otázka
call-site (v `remeslo_calculation_create`/`remeslo_calculation_recompute`),
ne architektury výpočtu.

#### Nová tabulka: `remeslo_craftsman_coef_defaults`

```sql
-- lazy vznik radku (jen kdyz remeslnik neco skutecne ulozi), stejny
-- vzor jako remeslo_invoicing_settings.
CREATE TABLE IF NOT EXISTS remeslo_craftsman_coef_defaults (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    craftsman_id        INT NOT NULL,
    calculator_type_id  INT NOT NULL,
    input_key           VARCHAR(80) NOT NULL,
    hodnota              DECIMAL(12,4) NOT NULL,
    created_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_craftsman_coef (craftsman_id, calculator_type_id, input_key),
    CONSTRAINT fk_remeslo_coef_def_craftsman FOREIGN KEY (craftsman_id) REFERENCES remeslo_craftsmen(id) ON DELETE CASCADE,
    CONSTRAINT fk_remeslo_coef_def_type FOREIGN KEY (calculator_type_id) REFERENCES remeslo_calculator_types(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**Proč `calculator_type_id` v klíči, ne jen `craftsman_id +
input_key`**: `input_key` je dnes navržený jako jedinečný jen V RÁMCI
JEDNÉ `_calc_*` funkce (např. `rezerva_percent` se stejným jménem
vyskytuje u Betonáže i Zdění s jinak vhodnou hodnotou pro každou) -
bez rozlišení kalkulačky by nastavení jedné tiše přetékalo do druhé.

#### Aplikace v UI — viditelnost systémového zdroje i po přepsání

Manifest koeficientu (z `_coef()`, vrácený spolu s položkami) se
rozšiřuje ze dvou hodnot na čtyři, aby šlo přesně to, co Robert chce -
**systémový zdroj zůstává vidět, i když je přepsaný**:

```python
{
    "input_key": "cihly_ks_m2",
    "label": "Spotřeba cihel",
    "jednotka": "ks/m²",
    "hodnota": 18.0,                        # EFEKTIVNÍ - po celé kaskádě, použitá v TÉTO kalkulaci
    "systemova_hodnota": 16.0,               # VŽDY vyplněné, natvrdo v _calc_* funkci
    "systemovy_zdroj": "Wienerberger Porotherm 30 Profi (technický list)",
    "remeslnik_ma_vychozi": True,            # ma radek v remeslo_craftsman_coef_defaults?
    "remeslnik_hodnota": 18.0,               # jen kdyz remeslnik_ma_vychozi
}
```

V panelu (`#remesloCalcCoefPanel`) se u řádku, kde `hodnota !=
systemova_hodnota`, vypíše malým písmem "systémová hodnota: 16 ks/m²
(Wienerberger Porotherm 30 Profi)" - přesně "ať vidí, od čeho se
odchyluje a proč", natrvalo, ne jen při první editaci.

Dvě samostatné akce u KAŽDÉHO koeficientu (záměrně oddělené, ne
automatický vedlejší efekt "Přepočítat" - přepsat číslo pro JEDNU
zakázku a natrvalo změnit svoje nastavení jsou dvě různé věci, jedna
by neměla tiše dělat druhou):

- **💾 Uložit jako moji výchozí hodnotu** - upsert do
  `remeslo_craftsman_coef_defaults` (`PUT
  /api/remeslo/craftsmen/<id>/calculator-types/<type_id>/coef-defaults`,
  body `{"input_key": ..., "hodnota": ...}`).
- **↺ Vrátit na systémovou** - `DELETE` řádku (funguje, i když
  řemeslník žádnou výchozí hodnotu nemá - no-op).

Volitelný doplněk (menší priorita, nezavádí nový mechanismus, jen
přehled): "Nastavení → Moje výchozí hodnoty kalkulaček" - jednoduchý
seznam všech řádků `remeslo_craftsman_coef_defaults` napříč
kalkulačkami s tlačítkem "Vrátit na systémovou" u každého, pro případ
že řemeslník zapomene, co všechno si kdy přenastavil.

#### Skryté položky ("trvale skrýt systémovou, kterou nikdy nepoužívá")

**Řešeno jako FÁZE 1** (malá, stejný vzor jako koeficienty výš - jedna
další lazy tabulka, žádný nový koncept):

```sql
CREATE TABLE IF NOT EXISTS remeslo_craftsman_item_prefs (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    craftsman_id        INT NOT NULL,
    calculator_type_id  INT NOT NULL,
    item_klic           VARCHAR(80) NOT NULL,   -- odkazuje na `klic` z _calc_* polozky
    hidden              TINYINT NOT NULL DEFAULT 1,
    created_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_craftsman_item (craftsman_id, calculator_type_id, item_klic),
    CONSTRAINT fk_remeslo_item_pref_craftsman FOREIGN KEY (craftsman_id) REFERENCES remeslo_craftsmen(id) ON DELETE CASCADE,
    CONSTRAINT fk_remeslo_item_pref_type FOREIGN KEY (calculator_type_id) REFERENCES remeslo_calculator_types(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

Na hranici endpointu (stejné místo jako `_effective_inputs`), po
zavolání `calc_fn`, se položky, jejichž `klic` je v tabulce pro
tohohle řemeslníka+typ, **z výstupu úplně vynechají** (ne jen
`is_used=0` - "trvale skrýt" má znamenat, že se řádek příště vůbec
neobjeví, ne že se objeví odškrtnutý a řemeslník ho musí pokaždé znovu
přehlédnout).

**Reverzibilita je povinná součást, ne budoucí vylepšení**: skrytí bez
cesty zpět by bylo past ("omylem jsem skryl povinnou položku a nevím
proč mi kalkulace nesedí"). Malá sekce "Nastavení → Skryté položky
kalkulaček" - seznam `nazev` (poslední známý text z doby skrytí,
uložený jako snapshot při skrytí) + tlačítko "Zobrazit znovu" (DELETE
řádku). Ovládací prvek skrytí samotné: v rozbalitelném řádku položky
(vedle "Výpočet:"/"Zdroj:" z předchozí sekce) tlačítko "🚫 Trvale
skrýt tuhle položku u mých budoucích kalkulací".

#### Vlastní položky navíc — FÁZE 2, vědomě odložena

Robert žádal "zvaž" - zvážila jsem a navrhuju to NEZAHRNOVAT do
stejného kola jako kaskáda koeficientů a skrývání, z konkrétního
důvodu: skrytí i výchozí koeficient jsou **atribut nad EXISTUJÍCÍ
položkou/koeficientem** (jednoduchý přepínač/číslo). Vlastní položka
navíc potřebuje navíc **vlastní pravidlo škálování** - je pevné
množství bez ohledu na velikost zakázky (např. "1× sada přesných
kotev"), nebo roste s plochou, s obvodem, s jinou veličinou? To je
vlastní malé UI (výběr vazby + jednotka + případně koeficient) a
vlastní návrh sám o sobě, ne jednořádkové rozšíření tabulky.

Necháno jako otevřený, NEBLOKUJÍCÍ bod pro příští kolo - pokud ho
Robert chce v tomhle kole taky, řekni a rozšířím návrh o něj zvlášť
(datový model beze zbytku sedí do stejné rodiny tabulek
`remeslo_craftsman_*`, jen s víc poli).

#### Příklad end-to-end (konkrétní čísla, pro srozumitelnost)

1. Systémová hodnota "Spotřeba cihel" u Zdění = 16 ks/m² (Wienerberger
   Porotherm Profi).
2. Řemeslník Novák staví jen z Porothermu 30 AKU (jiná cihla, hutnější
   spára) - u první kalkulace přepíše na 18 ks/m² a klikne "💾 Uložit
   jako moji výchozí hodnotu" → vznikne řádek v
   `remeslo_craftsman_coef_defaults` (craftsman_id=Novák,
   calculator_type=zdeni, input_key=cihly_ks_m2, hodnota=18).
3. Příští kalkulace Zdění od Nováka: `_effective_inputs()` najde jeho
   řádek → `calc_fn` dostane `cihly_ks_m2=18` už BEZ toho, aby cokoli
   zadával - v panelu vidí "18 ks/m² (systémová hodnota: 16 ks/m²,
   Wienerberger Porotherm 30 Profi)".
4. Jednorázová zakázka výjimečně s jinou cihlou → přepíše na 20 jen
   pro TUHLE kalkulaci (nic neukládá) → příští kalkulace se vrátí na
   jeho 18, ne na 20 ani na systémových 16.
5. Novák nikdy nepoužívá "Zakládací malta" (u něj vždy dělá zednický
   parťák jinou technologií) → v rozbalitelném řádku klikne "🚫 Trvale
   skrýt" → od příští kalkulace Zdění se mu položka vůbec negeneruje,
   dokud ji sám nevrátí v Nastavení.

#### Dopad na rollout (žádná zásadní změna pořadí)

Kaskáda i skryté položky se zavádí jako SOUČÁST kroku 1 (infrastruktura)
z původního rollout plánu výš - dvě další malé tabulky + rozšíření
call-site o `_effective_inputs()`/filtr skrytých, žádný zásah do
jednotlivých `_calc_*` funkcí navíc oproti tomu, co už bylo
naplánováno. Pilotní kalkulačka (Betonáž) demo ukáže rovnou i kaskádu
(uložení výchozí hodnoty, návrat na systémovou), ne jen odvození/zdroj.

#### Stav rozhodnutí

Robert schvaluje přímo bez dalšího kola recenzí (dvě nezávislé
recenze/druhý návrh už proběhly na základní verzi výš, princip kaskády
na ně navazuje beze změny architektury). K implementaci tedy jde:

- **SCHVÁLENO K IMPLEMENTACI**: odvození + zdroj + editovatelné
  koeficienty (`klic`/`mnozstvi_formula`/`is_orphaned`, `/recompute`,
  generický panel) + kaskáda výchozích hodnot řemeslníka
  (`remeslo_craftsman_coef_defaults`) + trvale skryté položky
  (`remeslo_craftsman_item_prefs`), pilot na Betonáži.
- **VĚDOMĚ ODLOŽENO na příští kolo** (ne zamítnuto): vlastní položky
  navíc s vlastní vazbou škálování (Fáze 2 výš) - vyžaduje samostatný
  malý návrh (výběr vazby fixní/na plochu/na obvod), není
  jednořádkové rozšíření stejné rodiny tabulek.

## Vlastní položky navíc — FÁZE 2, NÁVRH + ROVNOU IMPLEMENTACE (bot9, 2026-08-20)

Robert (2026-08-20): "vezmi si tu odloženou část - VLASTNÍ POLOŽKY
NAVÍC... potřebuji vlastní pravidlo skalování (pevné množství vs. na
plochu vs. na obvod)... napiš návrh a rovnou implementuj, už máš vzor
z Betonáže i důvěru z dvou nezávislých recenzí." Souvislost: produktový
slib "řešení na míru zdarma" - vlastní položka je přesně místo, kde si
řemeslník přizpůsobí kalkulačku něčemu, co jsme vůbec nepředpokládali.

### Rozdíl od koeficientů (proč je to samostatná tabulka, ne rozšíření `remeslo_craftsman_coef_defaults`)

Koeficient (Fáze 1) mění ČÍSLO uvnitř existujícího vzorce, který napsal
systém. Vlastní položka je NOVÝ ŘÁDEK, který systém vůbec nezná - nemá
"systémovou hodnotu" k porovnání, protože žádná neexistuje. Kaskáda
3 úrovní (kalkulace > řemeslník > systém) tu proto nedává smysl -
existuje jen 1 autoritativní místo: definice vlastní položky samotná.
Jednorázová odchylka pro JEDNU zakázku nepotřebuje nový mechanismus -
řemeslník po vygenerování prostě přepíše `mnozstvi` v tabulce přímo,
přesně jako u dnešního "+ Přidat vlastní položku" (to zůstává funkční
beze změny pro čistě jednorázové položky bez trvalého pravidla).

### Pravidlo škálování - 2 režimy, ne víc

- **`fixed`** - pevné množství bez ohledu na velikost zakázky (Robertův
  příklad "1× sada přesných kotev"). `coef` = přímo to množství.
- **`per_input`** - `mnozstvi = coef × inputs[input_key] × (1 +
  rezerva_percent/100)`. `input_key` NENÍ pevný seznam ("na plochu",
  "na obvod") - je to libovolný klíč z `inputs` AKTUÁLNĚ OTEVŘENÉ
  kalkulace (`remesloCalcEditorInputs` na frontendu, `detail.inputs`
  z API) - žádný nový registr "jaké vstupy má který typ kalkulačky"
  není potřeba, protože přesně tenhle seznam už existuje a je vidět v
  okamžiku, kdy řemeslník položku přidává.

Žádný 3. režim (např. "na obvod I na plochu zároveň") - kdyby to někdo
potřeboval, přidá dvě vlastní položky. Jednodušší než rozšiřovat
gramatiku pravidla.

### Datový model

```sql
CREATE TABLE remeslo_craftsman_custom_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    craftsman_id INT NOT NULL,
    calculator_type_id INT NOT NULL,
    nazev VARCHAR(255) NOT NULL,
    jednotka VARCHAR(40) NOT NULL,
    is_mandatory TINYINT NOT NULL DEFAULT 0,
    rule_mode ENUM('fixed','per_input') NOT NULL DEFAULT 'fixed',
    rule_input_key VARCHAR(80) NULL,
    rule_input_label VARCHAR(120) NULL,
    coef DECIMAL(12,4) NOT NULL DEFAULT 1,
    rezerva_percent DECIMAL(6,2) NOT NULL DEFAULT 0,
    poznamka VARCHAR(300) NULL,
    active TINYINT NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    ...FK na remeslo_craftsmen/remeslo_calculator_types...
);
```

`active` místo `DELETE` - stejná "nikdy nemazat, jen vypnout" politika
jako u skrytých položek. Vypnutí definice neovlivní kalkulace, kde už
položka je (ty mají svůj vlastní `klic`/`mnozstvi` uložené jako
snapshot) - jen ji přestane nabízet NOVÝM kalkulacím.

`klic` generovaného řádku = `custom_<id>` - jmenný prostor oddělený od
systémových klíčů (ty jsou vždy prosté slovo typu `beton`), takže
kolize nehrozí ani náhodou.

### Kam se napojuje výpočet

Nový čistý helper `_evaluate_custom_items(cur, craftsman_id,
calculator_type_id, inputs) -> list[dict]` - stejný tvar výstupu jako
`_calc_*` (přes `_item()`), jen čte z nové tabulky místo z hardcoded
vzorce. Zapojuje se na 2 místech:

1. **`remeslo_calculation_create`** - `proposed = calc_fn(...) +
   _evaluate_custom_items(...)`. Bezpečné vždy - `create` nemá žádné
   existující řádky k mergování, jen uloží, co dostane.
2. **`/recompute`** - stejné spojení `proposed`, ale objevil se tu
   latentní bug, který bych bez vlastních položek nikdy nenarazila:
   merge smyčka dnes pro položku BEZ `klic` (existuje jen u
   needretrofitovaných kalkulaček) omylem vkládá NOVÝ řádek navíc k
   tomu, co už beztak prochází nedotčené přes `manual` passthrough →
   při potvrzení `confirm_legacy` by se legacy položky zdvojily. Dokud
   `proposed` byl vždy 100% s klíčem NEBO 100% bez (jedna kalkulačka,
   jeden stav), na tenhle case nikdy nedošlo - vlastní položka (vždy
   MÁ klíč) poprvé vytváří SMÍŠENÝ seznam. Oprava: merge smyčka teď
   přeskočí položky bez `klic` (ty zůstávají výhradně v gesci
   `manual` passthrough, přesně podle původního komentáře "recompute
   se jich nikdy nedotkne") - jednořádková podmínka, žádná změna
   chování pro už otestované případy (ověřeno regresní sadou znovu).

### Endpointy (stejný vzor jako coef-defaults/item-prefs)

- `GET /api/remeslo/craftsmen/<id>/custom-items?calculator_type_id=X`
- `POST /api/remeslo/craftsmen/<id>/custom-items`
- `PUT /api/remeslo/craftsmen/<id>/custom-items/<item_id>` (včetně
  přepnutí `active` - žádný samostatný DELETE, konzistentní s "nikdy
  nemazat" politikou celé téhle rodiny tabulek)

### UI

Rozšíření existujícího "+ Přidat vlastní položku" (dnes: jednorázová
položka jen do TÉTO kalkulace) o checkbox "Pamatovat si i pro příští
kalkulace tohoto typu" - po zaškrtnutí se zobrazí výběr pravidla
(Pevné množství / Na hodnotu vstupu... s dropdownem naplněným
AKTUÁLNÍMI klíči `remesloCalcEditorInputs`) + koeficient + rezerva +
poznámka (řemeslníkův vlastní "zdroj" - proč tuhle položku přidává).
Množství pro TUTO kalkulaci se počítá rovnou v JS (stejný vzorec,
žádná závislost na `/recompute`) - funguje identicky bez ohledu na to,
jestli je kalkulačka retrofitovaná. Trvalá definice (přes API) se
uloží nezávisle, projeví se samo od příští `create`/`recompute`.
Správa (deaktivace/reaktivace) v Nastavení → podzáložka "Kalkulačky"
(rozšíření dnešní "Skryté položky" o druhou sekci "Vlastní položky").

### Stav rozhodnutí

Robert schválil rovnou, bez dalšího kola recenzí ("už máš vzor z
Betonáže i důvěru"). Implementuje se ihned po zápisu tohoto návrhu.

**HOTOVO A OVĚŘENO** (bot9, 2026-08-20): backend (`_evaluate_custom_items`,
napojení do create/recompute vč. opravy latentního bugu v merge smyčce,
endpointy `/custom-items`) + frontend ("pamatovat si i pro příští
kalkulace" v editoru, Nastavení -> Kalkulačky -> Vlastní položky).
Ověřeno 24/24 + 28/28 e2e kontrol (`test_client` + reálná DB) a živě
přes nginx. Funguje napříč VŠEMI 14 kalkulačkami (i neretrofitovanými
a čistě zákaznickými bez `_calc_*` vzorce), ne jen na pilotu Betonáž.
