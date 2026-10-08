-- Ciselnik UMISTENI regalu - druha, nezavisla osa vedle typologie
-- (bot9, 2026-09-13, Robert primo v chatu).
--
-- Doposud `regal_typologie` (EB/UN/OS/EV, viz
-- sql/2026-09-11_kod_sestavy_ciselniky.sql) popisovala jen SYSTEM/OBSAH
-- regalu (co je uvnitr - euroboxy, supliky...). Robert 2026-09-13 dal
-- dalsi seznam ("hlavni typologie": regal leva/prava strana, regal na
-- prepazce, dvojita podlaha, vysuvne bloky ze zadnich/bocnich dveri,
-- vysuvna podlaha) + druhy seznam ("dalsi regaly": suplikova
-- stena/regal, vysuvne euroboxy jako supliky, upinaci police, police
-- organizery, police vany, police sklopne dvirka).
--
-- Po rozkryti (Robert: "mas tu hrusky s jablkama") vysly dve NEZAVISLE
-- osy, ne jeden plochy seznam:
--   - Osa "system/obsah"  = existujici regal_typologie (EB/UN/OS/EV).
--     Druhy seznam Roberta obsah puvodnich placeholderu UN/OS/EV jen
--     UPRESNIL (viz UPDATE nize), nejsou to nove polozky.
--   - Osa "umisteni"      = prvni seznam Roberta, TOHLE je genuinne
--     nova osa - tabulka nize.
--
-- Realny produkt = kombinace JEDNE polozky umisteni x JEDNE polozky
-- typologie (dnes rozpracovano jen RB x EB, vzor Doblo C).
--
-- "Leva/prava strana" u RB NENI samostatny radek ciselniku - je to
-- orientace/zrcadleni konkretni sestavy, ne jiny typ umisteni. Kam presne
-- se strana zapise (novy sloupec na product_assemblies, nebo az bude
-- potreba), Robert zatim neurcil - nezavadi se tu spekulativne.
--
-- U "RP" (prepazka) plati vyjimka: nema horni blok jako bocni regaly,
-- misto toho u nekterych aut existuje SPODNI blok (Robert 2026-09-13).
-- `horni_blok_varianty` bude nutne zobecnit (pridat "pozice"), az se RP
-- zacne stavet - dnes zustava beze zmeny, tyka se jen EB.
CREATE TABLE regal_umisteni (
  id INT AUTO_INCREMENT PRIMARY KEY,
  kod CHAR(2) NOT NULL UNIQUE,
  klic VARCHAR(32) NOT NULL UNIQUE,
  nazev VARCHAR(128) NOT NULL,
  popis TEXT,
  aktivni TINYINT(1) NOT NULL DEFAULT 1,
  sort_order INT NOT NULL DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

INSERT INTO regal_umisteni (kod, klic, nazev, popis, sort_order) VALUES
  ('RB', 'bocni_strana',        'Regál — boční strana (levá/pravá)',
   'Regál podél boční stěny nákladového prostoru. Kombinace RB × EB (euroboxy) je dnes jediná rozpracovaná - vzor Doblo C. Strana levá/pravá je orientace konkrétní sestavy, ne samostatný kód číselníku.', 10),
  ('RP', 'prepazka',            'Regál na přepážce',
   'Regál na přepážce (oddělovací stěna kabina/náklad). Nemá horní blok jako boční regály - u některých vozidel místo toho spodní blok (Robert 2026-09-13, koncept zatím nerozpracován).', 20),
  ('DP', 'dvojita_podlaha',     'Dvojitá podlaha',
   'Úložný prostor pod zvýšenou podlahou nákladového prostoru. Obsah/detaily zatím neurčeny.', 30),
  ('VZ', 'vysuvne_bloky_zadni', 'Výsuvné bloky ze zadních dveří',
   'Výsuvný blok přístupný zadními dveřmi vozidla. Obsah/detaily zatím neurčeny.', 40),
  ('VB', 'vysuvne_bloky_bocni', 'Výsuvné bloky z bočních dveří',
   'Výsuvný blok přístupný bočními dveřmi vozidla. Obsah/detaily zatím neurčeny.', 50),
  ('VP', 'vysuvna_podlaha',     'Výsuvná podlaha',
   'Celá podlaha nákladového prostoru jako výsuvný díl. Obsah/detaily zatím neurčeny.', 60);

-- Upresneni obsahu puvodnich placeholderu (Robert 2026-09-13) - PRIDANO
-- k puvodni poznamce z 2026-09-11, nemazano (historicky kontext zustava).
UPDATE regal_typologie SET popis = CONCAT(popis,
  ' Upřesněno 2026-09-13: zahrnuje upínací police, police organizéry, police vany, police sklopné dvířka - jednotlivé podtypy zatím nemají vlastní rozpad.')
  WHERE klic = 'universal';
UPDATE regal_typologie SET popis = CONCAT(popis,
  ' Upřesněno 2026-09-13: = šuplíková stěna/regál. Detaily konstrukce zatím neurčeny.')
  WHERE klic = 'ocelove_supliky';
UPDATE regal_typologie SET popis = CONCAT(popis,
  ' Upřesněno 2026-09-13: = výsuvné euroboxy jako šuplíky. Detaily konstrukce zatím neurčeny.')
  WHERE klic = 'euroboxy_vysuvy';

-- Druhy sloupec na sestave, stejny princip jako typologie_id
-- (sql/2026-09-11_kod_sestavy_ciselniky.sql: "PRAVDOU JSOU POLE, KOD JE
-- JEN ZAPIS"). NULL dnes u vsech - zadna sestava zatim RB oficialne
-- nema prirazeno, kod_sestavy se generuje bez teto slozky, dokud se
-- nerozhodne, jak presne vstoupi do formatu kodu.
ALTER TABLE product_assemblies
  ADD COLUMN umisteni_id INT NULL AFTER typologie_id,
  ADD CONSTRAINT fk_pa_umisteni FOREIGN KEY (umisteni_id) REFERENCES regal_umisteni(id);
