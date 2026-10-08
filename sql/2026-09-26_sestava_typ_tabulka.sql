-- Nova osa "typ sestavy" (AUTO / STUL_SKLAD / do budoucna dalsi) - Robert
-- pres bot3, 2026-09-26 (PLAN_TVORBY_SESTAV.md, "Nová osa: typ sestavy").
-- Chce centralne spravovany text/sluzby PER TYP na JEDNOM miste v adminu,
-- misto dnesniho ad-hoc rozlisovani pres nullable car_model_id +
-- Vandr-specifickou logiku.
--
-- Konzultovano pred navrhem (bot16): bot8 (product_assemblies, vlastnik),
-- bot5 (volitelne sluzby/pricing/sklad), bot10 (stolova linie, realny
-- druhy spotrebitel - dnes bez vlastniho mechanismu, viz jeho odpoved).
-- Schema+UI schvalil bot3 bez podminek jako "cistě aditivni a nic
-- neriskuje". DVE VECI ZAMERNE NEJSOU soucasti tohohle souboru, jsou to
-- SAMOSTATNE kroky s povinnym dry-run pred spustenim:
--   1) migrace existujicich ~530 product_assemblies radku na
--      sestava_typ_id=AUTO (sestava_typ_id tu zustava NULL u vsech)
--   2) presunuti Vandr-specifickeho textu/logiky do noveho systemu
--
-- Bot8: sestava_typ_id musi byt VYSLOVNE nastavovano pri ulozeni sestavy
-- ve scene, NIKDY odvozovano z nullability car_model_id (262/532
-- existujicich radku ma car_model_id NULL jen z historicke diry v datech,
-- ne proto ze nejsou AUTO).
CREATE TABLE sestava_typ (
  id INT AUTO_INCREMENT PRIMARY KEY,
  kod VARCHAR(32) NOT NULL UNIQUE,
  nazev VARCHAR(128) NOT NULL,
  -- bot10: vychozi text NESMI obsahovat vozidlovou terminologii ("vhodne
  -- pro vozidlo X") - jinak se to jednou bude muset zpetne chytat pres
  -- TEXT_FILTR.md jako spatne pouzity Vandr/car boilerplate.
  popis_sablona TEXT,
  aktivni TINYINT(1) NOT NULL DEFAULT 1,
  sort_order INT NOT NULL DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO sestava_typ (kod, nazev, sort_order) VALUES
  ('AUTO', 'Vestavby do vozidel', 10),
  ('STUL_SKLAD', 'Stolové a skladové sestavy', 20);

-- NULL u VSECH radku dnes - vyslovne prirazeni existujicich ~530 sestav
-- na AUTO je samostatny krok (dry-run pred spustenim, viz bot3).
ALTER TABLE product_assemblies
  ADD COLUMN sestava_typ_id INT NULL AFTER car_model_id,
  ADD CONSTRAINT fk_pa_sestava_typ FOREIGN KEY (sestava_typ_id) REFERENCES sestava_typ(id);

-- Generalizace "volitelnych sluzeb" (bot5) - dnes zadna obecna tabulka
-- neexistuje, jedina implementace je natvrdo zadratovana montaz
-- (montaz_mista + literalni sloupce na shop_cart_items/shop_order_items,
-- viz api/product_assemblies.py::_montaz_mista_map). Tahle tabulka je
-- NOVY, oddeleny katalog - NEnahrazuje montaz_mista rovnou (presun je az
-- posledni krok s dry-run), jen pripravuje misto pro budouci sluzby
-- scoped podle typu sestavy.
--
-- sestava_typ_id NULL = sluzba plati pro VSECHNY typy (bot5 klic, pres
-- ktery se filtruje "montaz na miste dava smysl u stolu, instalace do
-- vozidla ne").
-- pricing_mode: informativni (jen text, zadna cena), procento_z_ceny
-- (hodnota = %, pocita se z ceny sestavy), pevna_castka (hodnota = Kc).
-- vyzaduje_dalsi_pole: generalizace dnesniho "montaz vyzaduje
-- montazni_misto" patternu - konkretni dalsi pole (napr. ktery
-- montaz_mista.klic) se resi az pri realnem propojeni, tady je jen
-- priznak "tahle sluzba jedno potrebuje".
--
-- "Boxy" pricing (bot5) zustava MIMO tuhle tabulku - je geometrii
-- odvozene, ne typova konfigurace, sem nepatri.
CREATE TABLE sestava_typ_sluzba (
  id INT AUTO_INCREMENT PRIMARY KEY,
  sestava_typ_id INT NULL,
  klic VARCHAR(32) NOT NULL,
  nazev VARCHAR(128) NOT NULL,
  pricing_mode ENUM('informativni','procento_z_ceny','pevna_castka') NOT NULL DEFAULT 'informativni',
  hodnota DECIMAL(10,2) NULL,
  vyzaduje_dalsi_pole TINYINT(1) NOT NULL DEFAULT 0,
  aktivni TINYINT(1) NOT NULL DEFAULT 1,
  sort_order INT NOT NULL DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_sts_typ_klic (sestava_typ_id, klic),
  CONSTRAINT fk_sts_typ FOREIGN KEY (sestava_typ_id) REFERENCES sestava_typ(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
