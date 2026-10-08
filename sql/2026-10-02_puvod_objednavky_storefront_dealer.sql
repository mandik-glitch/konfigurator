-- Puvod objednavky (domena, jazyk) a prirazeni mini-shopu dealerovi (bot5, 2026-10-02; navrh A-D schvalil bot3, pravidla Roberta v TASKS.md "dealersky program").
-- Pravidlo: mini-shop muze bezet BEZ dealera, objednavka bez dealera (dealer_id NULL) je nase. Dealer se zapisuje na objednavku PRI JEJIM VZNIKU z prirazeni platneho v tu chvili
-- (storefront_dealers), nikdy zpetne z domeny, takze pozdejsi prirazeni domeny dealerovi stare objednavky nedotkne. Zpetna provize je samostatna akce jen na Robertuv pokyn (zatim jen navrh).
-- Migrace JEN PRIDAVA nullable sloupce a novou tabulku, nic nemeni ani nemaze. Aplikace: python api/db_migrate.py sql/2026-10-02_puvod_objednavky_storefront_dealer.sql
-- POZOR: db_migrate deli prikazy podle strednikuv, v COMMENT retezcich proto zadne strednik. ALTER neni opakovatelny (MySQL 8 nezna ADD COLUMN IF NOT EXISTS), CREATE TABLE IF NOT EXISTS ano.

ALTER TABLE shop_orders
  ADD COLUMN order_host VARCHAR(255) NULL COMMENT 'nemenny snimek: normalizovany Host (male pismena, bez portu a www) pri vzniku zakaznicke objednavky, NULL = starsi nebo rucne zadana',
  ADD COLUMN order_lang VARCHAR(8) NULL COMMENT 'nemenny snimek: jazyk mini-shopu podle DOMENY pri vzniku objednavky (cs, en, de ...), NULL = starsi objednavka (hlavni e-shop, cesky)',
  ADD COLUMN dealer_source ENUM('click','storefront','retro','api') NULL COMMENT 'jak se objednavka pripsala dealerovi: click = cookie z prokliku, storefront = prirazeni mini-shopu, retro = zpetna atribuce na pokyn Roberta, api = cesta b (zatim nezapisuje)';

ALTER TABLE car_storefronts
  ADD COLUMN lang VARCHAR(8) NOT NULL DEFAULT 'cs' COMMENT 'jazyk mini-shopu urcuje DOMENA (cs, en, de ...), z nej se plni shop_orders.order_lang';

CREATE TABLE IF NOT EXISTS storefront_dealers (
  id INT NOT NULL AUTO_INCREMENT,
  storefront_id INT NOT NULL,
  dealer_id INT NOT NULL,
  valid_from DATETIME NOT NULL COMMENT 'od kdy se NOVE objednavky mini-shopu pripisuji dealerovi, objednavky pred timto okamzikem zustavaji nase a zpetne se nic neprepisuje',
  valid_to DATETIME DEFAULT NULL COMMENT 'NULL = prirazeni bez konce, jinak od kdy uz ne',
  active_storefront INT GENERATED ALWAYS AS (IF(valid_to IS NULL, storefront_id, NULL)) STORED COMMENT 'jen pro unikatnost: nejvyse jedno prirazeni bez konce na mini-shop',
  note VARCHAR(255) DEFAULT NULL,
  created_by INT DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_storefront_dealers_active (active_storefront),
  KEY idx_storefront_dealers_storefront (storefront_id, valid_from),
  KEY idx_storefront_dealers_dealer (dealer_id),
  CONSTRAINT fk_storefront_dealers_storefront FOREIGN KEY (storefront_id) REFERENCES car_storefronts (id) ON DELETE RESTRICT,
  CONSTRAINT fk_storefront_dealers_dealer FOREIGN KEY (dealer_id) REFERENCES dealers (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
