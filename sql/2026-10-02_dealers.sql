-- Dealersky program, etapa 1, krok 1 (bot5, 2026-10-02; zadani Robert pres bot3, TASKS.md "ZADANO 2026-10-02 ... dealersky program").
-- Entita dealera, rady dealera (dealerska sleva / provize podle kategorie), klice (widget/api/feed), povolene domeny, proklik (atribuce
-- 30 dni) a 4 nullable sloupce na shop_orders. Nic se nemaze: FK jsou RESTRICT (financni data, pravidlo 11), is_active je soft-delete.
-- Aplikace: python api/db_migrate.py sql/2026-10-02_dealers.sql (CREATE TABLE IF NOT EXISTS je opakovatelne, ALTER ne - pustit JEDNOU).
-- Novy kod (api/dealers.py) pocita s existenci tabulek; stary kod nove sloupce shop_orders nezna a nevadi mu (nullable, vsechny INSERTy
-- maji explicitni seznam sloupcu).

CREATE TABLE IF NOT EXISTS dealers (
  id INT NOT NULL AUTO_INCREMENT,
  ref_code VARCHAR(16) NOT NULL COMMENT 'kratky kod v odkazu /api/dealer/go/<ref_code>',
  name VARCHAR(255) NOT NULL,
  contact_name VARCHAR(255) DEFAULT NULL,
  contact_email VARCHAR(255) DEFAULT NULL,
  contact_phone VARCHAR(50) DEFAULT NULL,
  ico VARCHAR(20) DEFAULT NULL,
  dic VARCHAR(20) DEFAULT NULL,
  billing_street VARCHAR(255) DEFAULT NULL,
  billing_city VARCHAR(120) DEFAULT NULL,
  billing_zip VARCHAR(6) DEFAULT NULL,
  bank_account VARCHAR(64) DEFAULT NULL COMMENT 'ucet pro vyplaceni provize',
  party_id INT DEFAULT NULL COMMENT 'CRM adresar (parties)',
  user_id INT DEFAULT NULL COMMENT 'ucet dealera (role user) pro partnersky panel',
  status ENUM('pending','active','suspended') NOT NULL DEFAULT 'pending',
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  order_path ENUM('our','dealer') NOT NULL DEFAULT 'our' COMMENT 'our = objednavka u nas + provize, dealer = objednavka na webu dealera za dealerskou cenu',
  default_discount_pct DECIMAL(5,2) DEFAULT NULL COMMENT 'dealerska sleva pro cestu dealer, NULL = nema nastavenu, nemuze objednavat',
  default_commission_pct DECIMAL(5,2) DEFAULT NULL COMMENT 'provize, NULL = vychozi z app_settings dealer_commission_default_pct (10)',
  note TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_dealers_ref_code (ref_code),
  UNIQUE KEY uq_dealers_user (user_id),
  KEY idx_dealers_status (status, is_active),
  CONSTRAINT fk_dealers_user FOREIGN KEY (user_id) REFERENCES app_users (id) ON DELETE RESTRICT,
  CONSTRAINT fk_dealers_party FOREIGN KEY (party_id) REFERENCES parties (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS dealer_rates (
  id INT NOT NULL AUTO_INCREMENT,
  dealer_id INT NOT NULL,
  category_id INT NOT NULL COMMENT 'content_categories.id, sazba se dedi i na podkategorie, nejblizsi nadrazena vyhrava',
  discount_pct DECIMAL(5,2) DEFAULT NULL COMMENT 'NULL = zdedit',
  commission_pct DECIMAL(5,2) DEFAULT NULL COMMENT 'NULL = zdedit',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_dealer_rates (dealer_id, category_id),
  CONSTRAINT fk_dealer_rates_dealer FOREIGN KEY (dealer_id) REFERENCES dealers (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS dealer_keys (
  id INT NOT NULL AUTO_INCREMENT,
  dealer_id INT NOT NULL,
  kind ENUM('widget','api','feed') NOT NULL,
  public_id VARCHAR(40) NOT NULL COMMENT 'widget: cely pk_ klic (verejny), api/feed: predpona sk_xxxxxxxx / ft_xxxxxxxx (neni tajna)',
  secret_hash CHAR(64) DEFAULT NULL COMMENT 'sha256 tajne casti (jen api/feed), samotna tajna se ukaze jednou a nikde se neuklada',
  scopes VARCHAR(100) DEFAULT NULL COMMENT 'carkou: feed,quote,orders',
  allowed_ips TEXT COMMENT 'volitelny seznam IP (po radcich/carkach) jen pro api',
  label VARCHAR(100) DEFAULT NULL,
  rate_per_min INT NOT NULL DEFAULT 120,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  expires_at DATETIME DEFAULT NULL COMMENT 'rotace s prekryvem: stary klic plati jen do tohoto casu',
  revoked_at DATETIME DEFAULT NULL,
  last_used_at DATETIME DEFAULT NULL,
  last_used_ip VARCHAR(45) DEFAULT NULL,
  created_by INT DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_dealer_keys_public (public_id),
  KEY idx_dealer_keys_dealer (dealer_id, kind, is_active),
  CONSTRAINT fk_dealer_keys_dealer FOREIGN KEY (dealer_id) REFERENCES dealers (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS dealer_domains (
  id INT NOT NULL AUTO_INCREMENT,
  dealer_id INT NOT NULL,
  domain VARCHAR(255) NOT NULL COMMENT 'mala pismena, punycode, *.example.cz = jen subdomeny',
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_dealer_domains (dealer_id, domain),
  CONSTRAINT fk_dealer_domains_dealer FOREIGN KEY (dealer_id) REFERENCES dealers (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS dealer_clicks (
  id INT NOT NULL AUTO_INCREMENT,
  dealer_id INT NOT NULL,
  token CHAR(32) NOT NULL COMMENT 'hodnota cookie dlr (128 bit nahodne), atribuce se overuje tady v DB',
  product_id INT DEFAULT NULL,
  landing VARCHAR(255) DEFAULT NULL,
  ip_hash CHAR(16) DEFAULT NULL COMMENT 'sha256 se soli, ne IP',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_dealer_clicks_token (token),
  KEY idx_dealer_clicks_dealer (dealer_id, created_at),
  CONSTRAINT fk_dealer_clicks_dealer FOREIGN KEY (dealer_id) REFERENCES dealers (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

ALTER TABLE shop_orders
  ADD COLUMN dealer_id INT DEFAULT NULL,
  ADD COLUMN dealer_click_id INT DEFAULT NULL,
  ADD COLUMN order_path VARCHAR(10) DEFAULT NULL COMMENT 'our (z odkazu dealera, provize) | dealer (objednavka z API dealera)',
  ADD COLUMN dealer_external_ref VARCHAR(64) DEFAULT NULL COMMENT 'cislo objednavky u dealera - idempotence API',
  ADD KEY idx_shop_orders_dealer (dealer_id),
  ADD UNIQUE KEY uq_shop_orders_dealer_ref (dealer_id, dealer_external_ref),
  ADD CONSTRAINT fk_shop_orders_dealer FOREIGN KEY (dealer_id) REFERENCES dealers (id) ON DELETE RESTRICT;
