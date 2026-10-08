-- bot5, 2026-09-26 (Robert: "nesmí vzniknout díra v číslování žádné
-- číselné řady" - incident objednávka 191). order_number uz nesmi byt
-- odvozeny z shop_orders.id (smazani radku = navzdy ztracene cislo).
--
-- Rocni reset (stejna rodina jako novy format dokladu - Robert 2026-09-26,
-- pres bot3), format zustava OBJ-{rok}-{poradi:05d} beze zmeny.
--
-- shop_order_number_released: cisla uvolnena smazanim TESTOVACI objednavky
-- (Robert: "jen testovací objednávky budeme mazat... vrátí se k dispozici
-- číslo") - _next_order_number() je vzdy nejdriv NABIZI odsud (nejmensi
-- uvolnene cislo), pak teprve sahne na prubezny citac nize. Normalni
-- objednavky se nemazou (jen stav 'zrusena'), takze sem nikdy nic
-- neprijde z jejich strany.
CREATE TABLE IF NOT EXISTS shop_order_number_sequence (
  seq_year SMALLINT NOT NULL PRIMARY KEY,
  next_number INT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS shop_order_number_released (
  seq_year SMALLINT NOT NULL,
  seq_number INT NOT NULL,
  released_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (seq_year, seq_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Seed: Robert rucne nastavil jedinou zbyvajici realnou objednavku (id=187)
-- na "OBJ-2026-00001" - dalsi vydane cislo musi navazovat AZ ZA touhle 1,
-- ne za starym id=187/191 (viz AGENTS_LOG.md 2026-09-26).
INSERT INTO shop_order_number_sequence (seq_year, next_number) VALUES (2026, 2)
  ON DUPLICATE KEY UPDATE next_number = next_number;
