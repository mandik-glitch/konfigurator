-- Objednani (Robert: "Souhlasim / objednavam") - kazdy radek = 1
-- kliknuti (append-only, stejny princip jako scene_offer_views).
-- guest_id = trvala anonymni identita (session cookie, mirror
-- support.py::_support_identity), NE view_id (ten se meni pri kazdem
-- nacteni stranky).
CREATE TABLE scene_offer_acceptances (
  id INT AUTO_INCREMENT PRIMARY KEY,
  offer_id INT NOT NULL,
  guest_id VARCHAR(64) NOT NULL,
  name VARCHAR(255) NOT NULL,
  ip_address VARCHAR(45) NOT NULL,
  accepted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_soa_offer (offer_id),
  CONSTRAINT fk_soa_offer FOREIGN KEY (offer_id) REFERENCES scene_offers(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Dotaz/poznamka ke strance nebo konkretni polozce (Robert: "ke
-- konkretni polozce nebo strance"). page_key/item_name NULLable -
-- obecny dotaz nema ani jedno vyplnene.
CREATE TABLE scene_offer_notes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  offer_id INT NOT NULL,
  guest_id VARCHAR(64) NOT NULL,
  page_key VARCHAR(30) NULL,
  item_name VARCHAR(500) NULL,
  body TEXT NOT NULL,
  ip_address VARCHAR(45) NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_son_offer (offer_id),
  CONSTRAINT fk_son_offer FOREIGN KEY (offer_id) REFERENCES scene_offers(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
