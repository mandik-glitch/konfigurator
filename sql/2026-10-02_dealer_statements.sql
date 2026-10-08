-- Dealersky program, etapa 1, krok 3: MESICNI VYUCTOVANI provizi (bot5, 2026-10-02; zadani Robert pres bot3, TASKS.md "ZADANO 2026-10-02 ... dealersky program").
-- Vyuctovani = podklad, podle ktereho dealer vystavi nam fakturu (my zadnou fakturu nevystavujeme). Radky vyuctovani jsou SNIMEK provize v okamziku generovani
-- (provize se jinak pocita z dat, viz api/dealer_commissions.py). Nic se nemaze: FK RESTRICT, zruseny koncept se jen oznaci (status 'zrusen') a vznikne novy.
-- Aplikace: python api/db_migrate.py sql/2026-10-02_dealer_statements.sql (CREATE TABLE IF NOT EXISTS je opakovatelne).

CREATE TABLE IF NOT EXISTS dealer_statements (
  id INT NOT NULL AUTO_INCREMENT,
  dealer_id INT NOT NULL,
  period CHAR(7) NOT NULL COMMENT 'obdobi YYYY-MM',
  period_active CHAR(7) GENERATED ALWAYS AS (IF(status = 'zrusen', NULL, period)) STORED COMMENT 'jen pro unikatnost: jedno ZIVE vyuctovani na dealera a mesic, zrusene se nepocita',
  status ENUM('navrh','schvaleno','zaplaceno','zrusen') NOT NULL DEFAULT 'navrh',
  seq_year INT DEFAULT NULL,
  seq_number INT DEFAULT NULL,
  statement_number VARCHAR(30) DEFAULT NULL COMMENT 'cislo vyuctovani, prideluje se pri schvaleni (DV-RRRR-NNN)',
  total_czk DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT 'castka k fakturaci dealerem BEZ DPH',
  lines_count INT NOT NULL DEFAULT 0,
  period_end DATETIME NOT NULL COMMENT 'hranice (vcetne): zahrnute provize, jejichz lhuta na vraceni skoncila do tohoto okamziku',
  note TEXT,
  dealer_snapshot JSON NOT NULL COMMENT 'nazev, ICO, DIC, adresa a ucet dealera v okamziku generovani/schvaleni',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_by INT DEFAULT NULL,
  approved_at DATETIME DEFAULT NULL,
  approved_by INT DEFAULT NULL,
  paid_at DATETIME DEFAULT NULL,
  paid_note VARCHAR(255) DEFAULT NULL,
  cancelled_at DATETIME DEFAULT NULL,
  cancelled_note VARCHAR(255) DEFAULT NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_dealer_statements_period (dealer_id, period_active),
  UNIQUE KEY uq_dealer_statements_number (seq_year, seq_number),
  KEY idx_dealer_statements_status (status, period),
  CONSTRAINT fk_dealer_statements_dealer FOREIGN KEY (dealer_id) REFERENCES dealers (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS dealer_statement_lines (
  id INT NOT NULL AUTO_INCREMENT,
  statement_id INT NOT NULL,
  order_id INT NOT NULL COMMENT 'mekky odkaz na shop_orders (objednavka se muze v predprovoznim obdobi smazat, radek vyuctovani zustava)',
  line_type ENUM('commission','adjustment') NOT NULL DEFAULT 'commission',
  order_number VARCHAR(32) NOT NULL,
  order_created_at DATETIME DEFAULT NULL,
  base_net_czk DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  commission_czk DECIMAL(12,2) NOT NULL COMMENT 'se znamenkem: zaporna = korekce (vraceni nebo storno po vyplate)',
  detail_json JSON DEFAULT NULL COMMENT 'snimek radku: polozky, sazby, vratky, dosud vyuctovano',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_dealer_statement_lines_statement (statement_id),
  KEY idx_dealer_statement_lines_order (order_id),
  CONSTRAINT fk_dealer_statement_lines_statement FOREIGN KEY (statement_id) REFERENCES dealer_statements (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
