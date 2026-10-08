-- Interaktivni online nabidky (Robert 2026-08-04): druha, interaktivni
-- forma evidence nabidky vedle uz existujiciho statickeho PDF
-- (api/scene_offers.py, bot6). Klient otevre odkaz bez prihlaseni,
-- listuje "slidy" (stejny obsah jako PDF), sleduje se pocet shlednuti
-- podle IP, podle stranky, a cas straveny cetenim celkove i po
-- strankach. Zatim BEZ vazby na CRM Nabidky (crm_quotes) - Robertovo
-- rozhodnuti, propojeni je budouci krok.

-- Trvala kopie obsahu nabidky (dnes se po vyrenderovani PDF zahazuje) +
-- verejny pristupovy token. Token samotny (secrets.token_urlsafe) se
-- NIKDY neuklada - jen jeho SHA-256 hash (view_token_hash), stejny
-- princip jako app_users.magic_token_hash (sql/2026-07-31_magic_login_token.sql).
CREATE TABLE scene_offers (
  id INT AUTO_INCREMENT PRIMARY KEY,
  offer_number VARCHAR(4) NOT NULL UNIQUE,        -- sdileni s quotes._next_quote_number, jiz existuje
  drive_file_id INT NULL,                          -- odkaz na uz existujici PDF na Sdilenem disku
  items JSON NOT NULL,                             -- snapshot kusovniku (stejna struktura jako dnes posila scene.html)
  total_price INT NOT NULL,
  view_narys VARCHAR(255) NOT NULL,                -- stored_filename na disku, NE cesta
  view_bokorys VARCHAR(255) NOT NULL,
  view_pudorys VARCHAR(255) NOT NULL,
  view_3d_a VARCHAR(255) NOT NULL,
  view_3d_b VARCHAR(255) NOT NULL,
  editable_text_popis TEXT NOT NULL,               -- snapshot _load_editable_text() v okamziku generovani
  editable_text_patka TEXT NOT NULL,
  customer_name VARCHAR(255) NULL,
  view_token_hash CHAR(64) NOT NULL UNIQUE,
  expires_at DATETIME NOT NULL,                    -- created_at + 30 dni, pocitano pri vytvoreni
  is_active TINYINT(1) NOT NULL DEFAULT 1,          -- rucni deaktivace administratorem
  created_by INT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_scene_offers_token (view_token_hash),
  CONSTRAINT fk_scene_offers_drive_file FOREIGN KEY (drive_file_id) REFERENCES shared_drive_files(id) ON DELETE SET NULL,
  CONSTRAINT fk_scene_offers_created_by FOREIGN KEY (created_by) REFERENCES app_users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Jedno "shlednuti" = jedno nacteni verejne stranky (bez deduplikace
-- podle IP - "pocet shlednuti podle IP adresy" se pak pocita agregaci
-- COUNT(*)/COUNT(DISTINCT ip_address) GROUP BY ip_address nad touhle
-- tabulkou, ne rucnim slucovanim pri zapisu).
CREATE TABLE scene_offer_views (
  id INT AUTO_INCREMENT PRIMARY KEY,
  offer_id INT NOT NULL,
  ip_address VARCHAR(45) NOT NULL,                 -- IPv6-safe delka
  user_agent VARCHAR(500) NULL,
  started_at DATETIME NOT NULL,
  last_seen_at DATETIME NOT NULL,                  -- aktualizovano pri kazde /event beacon (fallback pro celkovy cas)
  KEY idx_sov_offer (offer_id),
  CONSTRAINT fk_sov_offer FOREIGN KEY (offer_id) REFERENCES scene_offers(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Jeden radek = jedna navsteva jedne stranky behem jednoho shlednuti
-- (pri opakovanem listovani zpet vznikaji dalsi radky - zamerne, "pocet
-- shlednuti podle stranky" i "cas podle stranky" se pak pocitaji SUM/
-- COUNT nad touhle tabulkou). page_key je citelny nazev (ne jen index),
-- aby zmena poctu/poradi slidu v budoucnu nerozbila historicka data.
CREATE TABLE scene_offer_page_events (
  id INT AUTO_INCREMENT PRIMARY KEY,
  view_id INT NOT NULL,
  page_index TINYINT NOT NULL,
  page_key VARCHAR(30) NOT NULL,                   -- cover|intro|drawings_1|drawings_2|view_3d|pricing|closing
  entered_at DATETIME NOT NULL,
  dwell_ms INT NOT NULL DEFAULT 0,                  -- cas straveny na strance, dopocitano na klientovi
  KEY idx_sope_view (view_id),
  KEY idx_sope_page (page_key),
  CONSTRAINT fk_sope_view FOREIGN KEY (view_id) REFERENCES scene_offer_views(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
