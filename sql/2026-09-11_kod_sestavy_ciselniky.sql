-- Ciselniky pro KOD SESTAVY (bot9, 2026-09-11, Robert pres bot8).
--
-- NAHRAZUJE sql/2026-09-09_boxy_kombinace_ciselnik.sql, ktery se nikdy
-- neaplikoval (git rm ve stejnem commitu). Duvod nahrazeni: Robert
-- 2026-09-11 rozsiril kod o dve slozky, ktere puvodni navrh mlcky
-- predpokladal jako konstantu - TYPOLOGII regalu a VELIKOST PROFILU:
--   "bude mnoho typu regalu, na euroboxy je jen jeden z nich, mame
--    zakladni 3 velikosti profilu 30, 40, 45"
-- a zaroven preobsadil ciselnik variant horniho bloku na sest provedeni
-- cislovanych vzestupne ("kody variant horniho bloku budou cisla,
-- postupne po sobe"), protoze puvodnich pet kodu neznalo osu
-- "jedno / dve pasma" a dve ruzna provedeni by dostala tentyz kod.
--
-- FORMAT KODU (Robert 2026-09-11, priklad K-075-E30A72):
--   K-075  karoserie      (pripona "e" = JINE vozidlo, ne varianta - pravidlo 25)
--   E      typologie      E euroboxy / U universal / S ocelove supliky / V euroboxy na vysuvech
--   30     profil         skutecna velikost 30/40/45, NE zkratka; urcuje admin
--   A7     varianta typologie  2 znaky, ciselnik ZVLAST pro kazdou typologii
--   2      horni blok     0 = bez, 1-6 provedeni
--   [0]    dodatek        pise se, jen kdyz neni nula (zajistuje jednoznacnost)
--
-- ZASADA (plan bot8 "Od sceny na web", sekce 1b): PRAVDOU JSOU POLE, KOD
-- JE JEN ZAPIS. Kazda slozka ma vlastni sloupec/ciselnik na sestave a kod
-- se z nich GENERUJE - nikdy se zpetne neparsuje. Diky tomu je pridani
-- dalsi typologie novy RADEK v ciselniku, ne preformatovani vsech
-- dosavadnich kodu.

-- 1) Typologie regalu -------------------------------------------------
-- POZOR: seznam NENI uzavreny (plan bot8, sekce 6 "Co ceka na Roberta":
-- "padly ctyri, seznam nebyl uzavreny"). Ctyri nize jsou ty, ktere Robert
-- vyjmenoval; dalsi se pridava jako novy radek, bez zmeny schematu.
CREATE TABLE regal_typologie (
  id INT AUTO_INCREMENT PRIMARY KEY,
  kod CHAR(1) NOT NULL UNIQUE,
  klic VARCHAR(32) NOT NULL UNIQUE,
  nazev VARCHAR(128) NOT NULL,
  popis TEXT,
  aktivni TINYINT(1) NOT NULL DEFAULT 1,
  sort_order INT NOT NULL DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

INSERT INTO regal_typologie (kod, klic, nazev, popis, sort_order) VALUES
  ('E', 'euroboxy',          'Regál na euroboxy',            'Sloupcová konstrukce s patry pro euroboxy 400x300. Varianta typologie = rozpis boxů.', 10),
  ('U', 'universal',         'Univerzální regál',            'Zatím jen pojmenováno, obsah neurčen (Robert 2026-09-11).', 20),
  ('S', 'ocelove_supliky',   'Ocelové šuplíky',              'Zatím jen pojmenováno, obsah neurčen (Robert 2026-09-11).', 30),
  ('V', 'euroboxy_vysuvy',   'Euroboxy na výsuvech',         'Zatím jen pojmenováno, obsah neurčen (Robert 2026-09-11).', 40);

-- 2) Rozpis boxu (detail, plati JEN pro typologii E) ------------------
-- Vlastni tabulka, ne sloupce v typologie_varianty: ciselny rozpad
-- (n120..n320) ma smysl vyhradne u euroboxu a u ostatnich typologii by
-- zustal prazdny. Zaroven umoznuje dotazovat "vsechny sestavy s aspon
-- jednim boxem 270" bez parsovani retezce.
--
-- ZDROJ DAT: product_assemblies.data (JSON), NIKDY nazev sestavy. U 25
-- z 262 sestav byl rozpis v nazvu zastaraly (sestava se po pojmenovani
-- editovala, nazev ne) - generovani z nazvu by tyhle chyby zabetonovalo
-- do trvalych identifikatoru. Overeno 2026-09-09.
CREATE TABLE boxy_kombinace (
  id INT AUTO_INCREMENT PRIMARY KEY,
  -- Kanonicky tvar "H1xN1-H2xN2-...", SESTUPNE podle vysky, jedna vyska =
  -- prave jedna dvojice. Diky normalizaci je "270x1-120x6" a "120x6-270x1"
  -- tataz kombinace. N = pocet KUSU, ne pocet pater.
  spec_kanonicky VARCHAR(64) NOT NULL UNIQUE,
  n120 SMALLINT NOT NULL DEFAULT 0,
  n170 SMALLINT NOT NULL DEFAULT 0,
  n220 SMALLINT NOT NULL DEFAULT 0,
  n270 SMALLINT NOT NULL DEFAULT 0,
  n320 SMALLINT NOT NULL DEFAULT 0,
  boxu_celkem SMALLINT NOT NULL DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3) Varianta typologie (obecny ciselnik, kod ZVLAST pro kazdou typologii)
-- Robert: "varianta 3 znamena u euroboxu neco jineho nez u ocelovych
-- supliku" - proto UNIQUE az na dvojici (typologie_id, kod) a FK na
-- typologii. U typologie E odkazuje kazdy radek na svuj rozpis boxu;
-- u ostatnich typologii zustane boxy_kombinace_id NULL a vyznam varianty
-- ponese nazev/popis.
CREATE TABLE typologie_varianty (
  id INT AUTO_INCREMENT PRIMARY KEY,
  typologie_id INT NOT NULL,
  kod CHAR(2) NOT NULL,
  nazev VARCHAR(128) NOT NULL,
  popis TEXT,
  boxy_kombinace_id INT NULL,
  aktivni TINYINT(1) NOT NULL DEFAULT 1,
  sort_order INT NOT NULL DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_typologie_kod (typologie_id, kod),
  UNIQUE KEY uq_typologie_box (typologie_id, boxy_kombinace_id),
  FOREIGN KEY (typologie_id) REFERENCES regal_typologie(id),
  FOREIGN KEY (boxy_kombinace_id) REFERENCES boxy_kombinace(id)
);

-- 4) Provedeni horniho bloku ------------------------------------------
-- UZAVRENY seznam sesti provedeni + nulty radek "bez bloku". Zdroj pravdy:
-- shape_geometry_methods.id=9 verze 12, klic varianty_provedeni (zapsal
-- bot8 2026-09-11 z Robertova vzoru na Doblu C, sestavy 332-337).
--
-- Nulty radek je zamerne RADEK, ne NULL: drtiva vetsina sestav blok nema
-- a FK tim zustane vzdy vyplnene, takze generovani kodu nemusi resit
-- zvlastni pripad.
--
-- STARE horni bloky v jinych sestavach NEPLATI (Robert 2026-09-11: "stare
-- horni bloky neplati, vzorovy horni blok delame na Doblu C") - proto se
-- jim kod neprideluje a v seedu zustavaji NULL, dokud se neprestavi.
CREATE TABLE horni_blok_varianty (
  id INT AUTO_INCREMENT PRIMARY KEY,
  kod CHAR(1) NOT NULL UNIQUE,
  klic VARCHAR(32) NOT NULL UNIQUE,
  nazev VARCHAR(128) NOT NULL,
  lisi_se TEXT,
  slozeni JSON,
  prepinace VARCHAR(255),
  sestava_vzoru INT NULL,
  aktivni TINYINT(1) NOT NULL DEFAULT 1,
  sort_order INT NOT NULL DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

INSERT INTO horni_blok_varianty (kod, klic, nazev, lisi_se, slozeni, prepinace, sestava_vzoru, sort_order) VALUES
  ('0', 'bez', 'Bez horního bloku',
   'Sestava horní blok nemá. Týká se drtivé většiny sestav v katalogu.',
   NULL, NULL, NULL, 0),
  ('1', 'jedno_pasmo_ram', 'Jedno pásmo - jen rám',
   'Základní, nejchudší provedení. Jen jedno (spodní) pásmo rámu, žádné desky.',
   '{"pricka-spodni-*": 3, "podelnik-celni-spodni-*": 2, "podelnik-zadni-spodni-*": 2}',
   '--jedno-pasmo --bez-vyplni', 332, 10),
  ('2', 'jedno_pasmo_ram_dna', 'Jedno pásmo - rám + dna [ZÁKLAD]',
   'Proti 1 přibyla dvě dna (MDF desky) do spodního pásma. Robertem označeno jako ZÁKLADNÍ provedení.',
   '{"vypln-dno-*": 2, "pricka-spodni-*": 3, "podelnik-celni-spodni-*": 2, "podelnik-zadni-spodni-*": 2}',
   '--jedno-pasmo', 333, 20),
  ('3', 'dve_pasma_ram', 'Dvě pásma - jen rám, bez police',
   'Proti 1 přibylo DRUHÉ (horní) pásmo: 2 podélníky + 3 horní příčky. Žádná police, žádné desky.',
   '{"pricka-horni-*": 3, "pricka-spodni-*": 3, "podelnik-celni-horni": 1, "podelnik-zadni-horni": 1, "podelnik-celni-spodni-*": 2, "podelnik-zadni-spodni-*": 2}',
   '--bez-police --bez-vyplni', 334, 30),
  ('4', 'dve_pasma_police_pricky', 'Dvě pásma - police jen příčky, bez horních příček',
   'Proti 3 jsou horní příčky NAHRAZENY příčkami police (v polovině výšky). Police nemá vlastní podélníky ani desku.',
   '{"pricka-police-*": 3, "pricka-spodni-*": 3, "podelnik-celni-horni": 1, "podelnik-zadni-horni": 1, "podelnik-celni-spodni-*": 2, "podelnik-zadni-spodni-*": 2}',
   '--bez-hornich-pricek --police-bez-podelniku --bez-vyplni', 335, 40),
  ('5', 'dve_pasma_plne_bez_police', 'Dvě pásma - plné výplně, bez police, horní příčka jen u přepážky',
   'Proti 3 přibylo plné opláštění (záda, čelo, bok u přepážky, dna) a horních příček zbyla JEDINÁ - u přepážky, kde slouží jako doraz. Police pořád žádná.',
   '{"vypln-dno-*": 2, "vypln-celo-*": 2, "vypln-zada-*": 2, "pricka-horni-*": 1, "pricka-spodni-*": 3, "vypln-bok-prepazka": 1, "podelnik-celni-horni": 1, "podelnik-zadni-horni": 1, "podelnik-celni-spodni-*": 2, "podelnik-zadni-spodni-*": 2}',
   '--bez-police --horni-pricka-jen-prepazka', 336, 50),
  ('6', 'dve_pasma_plne_s_polici', 'Dvě pásma - plné výplně, s policí, horní příčka jen u přepážky',
   'Proti 5 přibyla POLICE jako plnohodnotné patro: vlastní podélníky (čelní i zadní), příčky a deska. Svislé výplně se tím DĚLÍ na dvě části nad a pod policí - proto sufixy -a/-b u zad, čela i boku. Nejbohatší provedení.',
   '{"vypln-dno-*": 2, "pricka-horni-*": 1, "vypln-celo-*": 4, "vypln-police-*": 2, "vypln-zada-*": 4, "pricka-police-*": 3, "pricka-spodni-*": 3, "podelnik-celni-horni": 1, "podelnik-zadni-horni": 1, "vypln-bok-prepazka-*": 2, "podelnik-celni-police-*": 2, "podelnik-zadni-police-*": 2, "podelnik-celni-spodni-*": 2, "podelnik-zadni-spodni-*": 2}',
   '--horni-pricka-jen-prepazka', 337, 60);

-- 5) Slozky kodu na sestave -------------------------------------------
-- karoserie_kod se zapisuje jako VLASTNI POLE, ne pres car_model_id.
-- Duvod (WORKFLOW.md pravidlo 25): doplneni car_model_id shodi pojistku
-- verejnych storefrontu (car_storefronts.py:196 pousti sestavu ven pri
-- is_public + active + car_model_id, a dnes to drzi jen to, ze
-- car_model_id je vsude NULL). Kod karoserie do DB patri, tahle cesta ho
-- tam dostane bez toho vedlejsiho ucinku.
--
-- profil_mm zamerne NEMA default ani odvozeni z dat: Robert 2026-09-11
-- "velikost profilu je jen pro orientaci, profil urcuje admin". Seed ho
-- necha NULL a kod se u takove sestavy nevygeneruje - radsi chybejici kod
-- nez uhodnuty.
ALTER TABLE product_assemblies
  ADD COLUMN karoserie_kod VARCHAR(8) NULL AFTER car_model_id,
  ADD COLUMN typologie_id INT NULL AFTER karoserie_kod,
  ADD COLUMN profil_mm SMALLINT NULL AFTER typologie_id,
  ADD COLUMN typologie_varianta_id INT NULL AFTER profil_mm,
  ADD COLUMN horni_blok_varianta_id INT NULL AFTER typologie_varianta_id,
  ADD COLUMN dodatek SMALLINT NOT NULL DEFAULT 0 AFTER horni_blok_varianta_id,
  ADD COLUMN kod_sestavy VARCHAR(32) NULL AFTER dodatek,
  ADD KEY idx_pa_kod_sestavy (kod_sestavy),
  ADD CONSTRAINT fk_pa_typologie FOREIGN KEY (typologie_id) REFERENCES regal_typologie(id),
  ADD CONSTRAINT fk_pa_typologie_varianta FOREIGN KEY (typologie_varianta_id) REFERENCES typologie_varianty(id),
  ADD CONSTRAINT fk_pa_horni_blok_varianta FOREIGN KEY (horni_blok_varianta_id) REFERENCES horni_blok_varianty(id);
