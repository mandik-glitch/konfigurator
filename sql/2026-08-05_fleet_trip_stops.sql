-- Zastavky behem jizdy (Robert 2026-08-05, navazuje na Knihu jizd):
-- "ty tabulky knihy jizd musi sedet s cerpanim PHM, koupi se benzin/
-- nafta, doklad se naskenuje ve fotoapce, vlozi se do spravne slozky
-- disku a zaroven se nacte do knihy jizd, tzn bude to vzdy jako
-- zastavka v prehledu jizd" + "dale potrebujeme evidovat Zakazniky a
-- mesta kam se jelo jako cilova destinace".
--
-- Dva typy zastavky ve stejne tabulce (misto dvou zvlast) - obe jsou
-- casove razene udalosti BEHEM jedne jizdy, admin prehled je chce
-- videt spolecne v jedne casove ose:
-- 'fuel'     - doklad o tankovani, ulozeny jako soubor ve Sdilenem
--              disku (slozka "Tankovani/<vozidlo>", zalozena
--              automaticky) - viz drive_file_id.
-- 'customer' - cilova destinace jizdy (Robert: "jen fotka dokladu" u
--              tankovani, zadna castka/litry - viz AGENTS_LOG). Zakaznik
--              bud nalezen v existujici kartotece (customer_id), nebo
--              volny text (customer_name_freetext), mesto vzdy volny
--              text (nemusi odpovidat fakturacni adrese zakaznika).
CREATE TABLE fleet_trip_stops (
  id INT AUTO_INCREMENT PRIMARY KEY,
  trip_id INT NOT NULL,
  stop_type VARCHAR(20) NOT NULL,
  recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  lat DECIMAL(10,7) NULL,
  lng DECIMAL(10,7) NULL,
  drive_file_id INT NULL,
  customer_id INT NULL,
  customer_name_freetext VARCHAR(200) NULL,
  city VARCHAR(120) NULL,
  KEY idx_fts_trip (trip_id),
  CONSTRAINT fk_fts_trip FOREIGN KEY (trip_id) REFERENCES fleet_trips(id) ON DELETE CASCADE,
  CONSTRAINT fk_fts_drive_file FOREIGN KEY (drive_file_id) REFERENCES shared_drive_files(id) ON DELETE SET NULL,
  CONSTRAINT fk_fts_customer FOREIGN KEY (customer_id) REFERENCES shop_customers(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
