-- Volby objednavky klienta v online nabidce (Robert 2026-08-05:
-- "interaktivni radky: doprava vlastni nebo Toptrans, platba: dobirka,
-- zalohova platba 70-100%, Dodani ve stavu: smontovano/demont") -
-- 1 radek na (offer_id, guest_id), posledni volba vyhrava (UPSERT pres
-- UNIQUE klic) - na rozdil od append-only acceptances/notes tady
-- historie jednotlivych prepnuti nema hodnotu, admin chce videt
-- AKTUALNI prani klienta.
CREATE TABLE scene_offer_order_prefs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  offer_id INT NOT NULL,
  guest_id VARCHAR(64) NOT NULL,
  shipping_method VARCHAR(20) NULL,   -- 'vlastni' | 'toptrans'
  payment_method VARCHAR(20) NULL,    -- 'dobirka' | 'zaloha'
  deposit_pct TINYINT NULL,           -- 70-100, jen pro payment_method='zaloha'
  delivery_state VARCHAR(20) NULL,    -- 'smontovano' | 'demontovano'
  ip_address VARCHAR(45) NOT NULL,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_sop_offer_guest (offer_id, guest_id),
  CONSTRAINT fk_sop_offer FOREIGN KEY (offer_id) REFERENCES scene_offers(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
