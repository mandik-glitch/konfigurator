-- Robert 2026-08-10: 3 vylepseni online nabidek navrzena po diskuzi o
-- panelu "Profily v rezu" -
--   1) odmitnuti/pripominka (zakaznik nema jen "Souhlasim / objednavam",
--      muze taky rict "nemam zajem" nebo napsat pripominku)
--   2) upominka pred vyprsenim (e-mail zakaznikovi, pokud znamy)
--   3) plne editovani nabidky v adminu + historie verzi

-- 1) Odmitnuti - stejny append-only vzor jako scene_offer_acceptances
-- (sql/2026-08-05_scene_offer_accept_notes.sql), duvod nepovinny.
CREATE TABLE scene_offer_declines (
  id INT AUTO_INCREMENT PRIMARY KEY,
  offer_id INT NOT NULL,
  guest_id VARCHAR(64) NOT NULL,
  reason TEXT NULL,
  ip_address VARCHAR(45) NOT NULL,
  declined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_sod_offer (offer_id),
  CONSTRAINT fk_sod_offer FOREIGN KEY (offer_id) REFERENCES scene_offers(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2) Upominka pred vyprsenim - customer_email volitelny (zadava se pri
-- vytvoreni nabidky ve scene.html vedle jmena), reminder_sent_at brani
-- opakovanemu odeslani stejne upominky pri kazdem behu cronu.
ALTER TABLE scene_offers
  ADD COLUMN customer_email VARCHAR(255) NULL AFTER customer_name,
  ADD COLUMN reminder_sent_at DATETIME NULL AFTER expires_at;

-- 3) Editace nabidky adminem + historie verzi. scene_offer_revisions
-- uklada PUVODNI stav TESNE PRED kazdou upravou (ne po) - pri editaci
-- se nejdriv aktualni radek scene_offers zkopiruje sem jako dalsi
-- revize, az pak se scene_offers prepise novymi hodnotami. Nikdy
-- editovana nabidka tak ma 0 radku zde (nic se neztraci, jen se nikdy
-- needitovalo).
CREATE TABLE scene_offer_revisions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  offer_id INT NOT NULL,
  revision_number INT NOT NULL,          -- 1, 2, 3... poradi PRED editaci, ktera ho vytvorila
  items JSON NOT NULL,
  total_price INT NOT NULL,
  editable_text_popis TEXT NOT NULL,
  editable_text_patka TEXT NOT NULL,
  offer_options JSON NULL,
  edited_by INT NULL,                    -- kdo provedl NASLEDUJICI editaci (tim vznikla tahle archivni revize)
  edited_at DATETIME NOT NULL,
  change_note VARCHAR(500) NULL,         -- volitelny popis "co se zmenilo", vyplnuje admin pri ulozeni
  KEY idx_sor_offer (offer_id),
  CONSTRAINT fk_sor_offer FOREIGN KEY (offer_id) REFERENCES scene_offers(id) ON DELETE CASCADE,
  CONSTRAINT fk_sor_edited_by FOREIGN KEY (edited_by) REFERENCES app_users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE scene_offers
  ADD COLUMN revision_number INT NOT NULL DEFAULT 1 AFTER offer_options,
  ADD COLUMN last_edited_at DATETIME NULL AFTER revision_number,
  ADD COLUMN last_edited_by INT NULL AFTER last_edited_at,
  ADD CONSTRAINT fk_scene_offers_last_edited_by FOREIGN KEY (last_edited_by) REFERENCES app_users(id) ON DELETE SET NULL;
