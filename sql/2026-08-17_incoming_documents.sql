-- Prijate ucetni doklady z e-mailu (mandik@logiman.cz) - bot8, 2026-08-17.
--
-- Kontext (Robert pres bot3): "nastavte potrebne k tomu, aby se emaily
-- analyzovali na spam a opravdu doklady, ktere musime zavadet do
-- ucetnictvi" - rozsireni existujiciho e-mail-sync tridiciho bodu
-- (api/support_email_sync.py, viz jeho docstring) o TRETI kategorii
-- vedle "poptavka"/"jine": "doklad" (faktura/dokladovy PDF prijaty od
-- dodavatele).
--
-- Robert pak upresnil (2026-08-17, tyz den): "predpokladam, ze to
-- ukladani dokladu budeme jeste upresnovat, konkretne: nez se tam
-- ulozi, musim je odsouhlasit" - proto NENI zalozeny primo do Sdileneho
-- disku (shared_drive_files) automaticky, ale nejdriv do TETO
-- schvalovaci fronty (approval_status, stejny vzor jako
-- shop_documents.approval_status/crm_quotes.approval_status, viz
-- sql/2026-08-01_approvals.sql a api/approvals.py) - teprve po
-- rucnim schvaleni (POST /api/admin/incoming-documents/<id>/approve)
-- se soubor PRESUNE ze stagingu do Sdileneho disku, do slozky
-- "Faktury a doklady prijate" / <rok> / <cesky nazev mesice>, podle
-- data PRIJETI e-mailu (ne data vystaveni na fakture) - podslozky se
-- zakladaji LINE za chodu, kdyz prijde prvni doklad daneho mesice, ne
-- predem vsechny.
--
-- Soubor pred schvalenim NENI v shared-drive adresari (mimo nginx
-- docroot uplne stejne, jen jiny podadresar - viz
-- api/incoming_documents.py INCOMING_DOCS_DIR), aby ho nesel nikdo
-- omylem stahnout/pouzit driv, nez ho Robert schvali.

CREATE TABLE incoming_documents (
  id INT AUTO_INCREMENT PRIMARY KEY,
  source_email VARCHAR(255) NOT NULL,
  source_name VARCHAR(255) NULL,
  subject VARCHAR(500) NULL,
  body_text MEDIUMTEXT NULL,
  received_at DATETIME NOT NULL,
  -- filename/stored_filename/content_type/size_bytes NULL = doklad bez
  -- prilohy (napr. faktura jen v textu e-mailu) - porad se zalozi
  -- zaznam k rucnimu prehlednuti, jen bez souboru ke stazeni.
  filename VARCHAR(255) NULL,
  stored_filename VARCHAR(255) NULL,
  content_type VARCHAR(150) NULL,
  size_bytes INT NULL,
  approval_status VARCHAR(20) NOT NULL DEFAULT 'ceka_schvaleni',
  supplier_name VARCHAR(255) NULL,
  amount_czk DECIMAL(12,2) NULL,
  note TEXT NULL,
  drive_file_id INT NULL,
  reviewed_by INT NULL,
  reviewed_at DATETIME NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_incdoc_status (approval_status),
  KEY idx_incdoc_received (received_at),
  CONSTRAINT fk_incdoc_drive_file FOREIGN KEY (drive_file_id) REFERENCES shared_drive_files(id) ON DELETE SET NULL,
  CONSTRAINT fk_incdoc_reviewed_by FOREIGN KEY (reviewed_by) REFERENCES app_users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Rozsireni existujiciho slovnikoveho klasifikatoru (crm_classifier_words,
-- viz sql/2026-07-31_crm_classifier_words.sql) o treti pocitadlo -
-- stejny "skore = soucet rozdilu pres slova" princip jako
-- poptavka_count/jine_count, jen navic tretí kategorie misto ciste
-- binarniho rozhodnuti. Admin oprava spatne kategorie (kdykoli pribyde
-- UI pro to) zavola crm.train_words() se stejnym mechanismem.
ALTER TABLE crm_classifier_words ADD COLUMN doklad_count INT NOT NULL DEFAULT 0;

-- Bezpecnostni "studeny start" - bez tohohle by prvni desitky dokladovych
-- e-mailu klasifikator vubec nepoznal (doklad_count=0 u vsech slov =
-- skore vzdy 0 = nikdy nevyhraje nad poptavka/jine). Skromne pocatecni
-- vahy (5) - nekolik shodujicich se slov v predmetu/tele proto sice da
-- rozumny signal, ale realne pouzivani/uceni (train_words) casem
-- prevazi at jiz spravnym, nebo opravenym smerem.
INSERT INTO crm_classifier_words (word, poptavka_count, jine_count, doklad_count) VALUES
  ('faktura', 0, 0, 5), ('fakturu', 0, 0, 5), ('fakturou', 0, 0, 5),
  ('fakturace', 0, 0, 5), ('dokladu', 0, 0, 5), ('dokladem', 0, 0, 5),
  ('vyuctovani', 0, 0, 5), ('vyuctovana', 0, 0, 5),
  ('variabilni', 0, 0, 4), ('symbol', 0, 0, 3), ('splatnost', 0, 0, 4),
  ('splatnosti', 0, 0, 4), ('dodavatel', 0, 0, 3), ('odberatel', 0, 0, 3),
  ('castka', 0, 0, 3), ('uhrady', 0, 0, 3), ('uhradu', 0, 0, 3),
  ('bankovni', 0, 0, 3), ('ucet', 0, 0, 2), ('dph', 0, 0, 4),
  ('zaklad', 0, 0, 2), ('sazba', 0, 0, 2)
ON DUPLICATE KEY UPDATE
  doklad_count = doklad_count + VALUES(doklad_count);
