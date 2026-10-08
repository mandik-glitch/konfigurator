-- Vandr (vanDrawee) FBX fronta - SAMOSTATNA od product_assemblies/
-- card_auto_link/card_auto_activate (Robert, 2026-09-22, durazne:
-- "Vandr je jiny vetev sestav, maji jine karty", viz
-- PLAN_TVORBY_SESTAV.md sekce "Vandr sestavy na eshopu").
--
-- Spoustec cele Vandr vetve = novy .fbx soubor na Sdilenem disku
-- (shared_drive_files) pod stromem korenove slozky "vanDrawee sestavy"
-- (Robert primo: "uz tim ze sestavu fbx nahraju na sdileny disk, tim
-- je sestava technicky schvalena"). Tenhle radek = jedno zpracovani
-- jednoho FBX souboru, idempotence pres UNIQUE(shared_drive_file_id).
CREATE TABLE vandr_fbx_queue (
  id INT AUTO_INCREMENT PRIMARY KEY,
  shared_drive_file_id INT NOT NULL,
  vandrawee_uuid VARCHAR(36) NULL,
  shop_product_id INT NULL,
  -- 'karta_existovala' = UUID uz mel kartu z puvodniho CSV importu
  -- (bot7, 321 karet) - jen zaznamenano, karta se nemenila.
  -- 'karta_zalozena' = nova draft karta zalozena timhle automatem
  -- (active=0, bez ceny - ceka na Roberta, viz bot_ukoly).
  -- 'chyba' = filename neni platne UUID.fbx, nezpracovano.
  stav ENUM('karta_existovala','karta_zalozena','chyba') NOT NULL,
  poznamka TEXT NULL,
  processed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_vfq_file (shared_drive_file_id),
  KEY idx_vfq_product (shop_product_id),
  CONSTRAINT fk_vfq_file FOREIGN KEY (shared_drive_file_id) REFERENCES shared_drive_files(id) ON DELETE CASCADE,
  CONSTRAINT fk_vfq_product FOREIGN KEY (shop_product_id) REFERENCES shop_products(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
