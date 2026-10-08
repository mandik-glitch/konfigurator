-- Mini-shop (Packstations a dalsi tema mini-shopy), faze 1: tabulky pro serverove API /api/miniweb/* (bot5, 2026-10-02; navrh schvalil bot3, kostra shopu bot16 9c5992a2).
-- Mini-shop = storefront (car_storefronts, host a jazyk podle DOMENY, aliasy hostu v storefront_hosts) + radek v miniweb_shops. Katalog je language-neutral (kategorie, produkty) a TEXTY jsou po jazycich
-- se stavem draft/approved (verejnosti se servi jen approved, texty schvaluje Robert, dodava bot7). Klonovani dalsiho jazyka = novy storefront + novy miniweb_shops radek + texty v jazyce, bez zasahu do kodu.
-- Ceny se zatim NEUKLADAJI: price_mode 'hidden' (jen poptavka), mena a orientacni cena az po rozhodnuti Roberta. Znacka (Logiman, dodavatel) v textech zakazana, server ji filtruje a QA hlida.
-- Migrace JEN PRIDAVA nove tabulky (CREATE TABLE IF NOT EXISTS, opakovatelne). Aplikace: python api/db_migrate.py sql/2026-10-02_miniweb.sql
-- POZOR: db_migrate deli prikazy podle strednikuv, v COMMENT retezcich proto zadne strednik. Sloupec nesmi mit nazev product_id (QA product_duplicate_unclassified_table), proto miniweb_product_id.

CREATE TABLE IF NOT EXISTS miniweb_shops (
  storefront_id INT NOT NULL,
  family VARCHAR(40) NOT NULL DEFAULT 'default' COMMENT 'rodina mini-shopu (napr. packstations), shopy se stejnou rodinou a jinym jazykem jsou jazykove verze (hreflang alternates)',
  price_mode ENUM('hidden','indicative') NOT NULL DEFAULT 'hidden' COMMENT 'hidden = bez ceny (jen poptavka), indicative = orientacni cena od (az po rozhodnuti o mene)',
  currency CHAR(3) DEFAULT NULL COMMENT 'mena zobrazeni (EUR ...), NULL dokud neni rozhodnuto',
  locale VARCHAR(16) DEFAULT NULL COMMENT 'napr. en-IE, formatovani cisel a men na strance',
  accent CHAR(7) DEFAULT NULL COMMENT 'barva zvyrazneni #rrggbb',
  countries VARCHAR(100) DEFAULT NULL COMMENT 'cilove zeme (ISO 3166-1 alpha-2, oddelene carkou)',
  contact_json JSON DEFAULT NULL COMMENT 'neutralni kontakt shopu (email, phone, hours) bez znacky',
  inquiry_enabled TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (storefront_id),
  KEY idx_miniweb_shops_family (family),
  CONSTRAINT fk_miniweb_shops_storefront FOREIGN KEY (storefront_id) REFERENCES car_storefronts (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS miniweb_categories (
  id INT NOT NULL AUTO_INCREMENT,
  parent_id INT DEFAULT NULL,
  slug VARCHAR(100) NOT NULL COMMENT 'jazykove neutralni adresa kategorie',
  sort_order INT NOT NULL DEFAULT 0,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_miniweb_categories_slug (slug),
  KEY idx_miniweb_categories_parent (parent_id),
  CONSTRAINT fk_miniweb_categories_parent FOREIGN KEY (parent_id) REFERENCES miniweb_categories (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS miniweb_category_texts (
  miniweb_category_id INT NOT NULL,
  lang VARCHAR(8) NOT NULL COMMENT 'jazyk textu (en, de ...), stejny tvar jako car_storefronts.lang',
  name VARCHAR(200) NOT NULL,
  status ENUM('draft','approved') NOT NULL DEFAULT 'draft' COMMENT 'verejnosti se servi jen approved, staff v nahledu i draft',
  approved_by INT DEFAULT NULL,
  approved_at DATETIME DEFAULT NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (miniweb_category_id, lang),
  CONSTRAINT fk_miniweb_category_texts_category FOREIGN KEY (miniweb_category_id) REFERENCES miniweb_categories (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS miniweb_products (
  id INT NOT NULL AUTO_INCREMENT,
  category_id INT NOT NULL,
  slug VARCHAR(120) NOT NULL COMMENT 'jazykove neutralni adresa produktu',
  public_sku VARCHAR(50) NOT NULL COMMENT 'verejny kod produktu na webu, NENI interni SKU',
  shop_product_id INT DEFAULT NULL COMMENT 'karta konfigurovatelne sestavy v shop_products pro konfigurator, NULL bez konfiguratoru',
  configurator_available TINYINT(1) NOT NULL DEFAULT 0,
  default_view VARCHAR(20) NOT NULL DEFAULT 'configurator',
  sort_order INT NOT NULL DEFAULT 0,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_miniweb_products_slug (slug),
  KEY idx_miniweb_products_category (category_id),
  CONSTRAINT fk_miniweb_products_category FOREIGN KEY (category_id) REFERENCES miniweb_categories (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS miniweb_product_texts (
  miniweb_product_id INT NOT NULL,
  lang VARCHAR(8) NOT NULL COMMENT 'jazyk textu (en, de ...), stejny tvar jako car_storefronts.lang',
  name VARCHAR(200) NOT NULL,
  summary VARCHAR(500) DEFAULT NULL,
  description TEXT,
  delivery VARCHAR(255) DEFAULT NULL,
  specs_json JSON DEFAULT NULL COMMENT 'seznam parametru, kazdy objekt s poli name a value',
  status ENUM('draft','approved') NOT NULL DEFAULT 'draft' COMMENT 'verejnosti se servi jen approved, staff v nahledu i draft',
  approved_by INT DEFAULT NULL,
  approved_at DATETIME DEFAULT NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (miniweb_product_id, lang),
  CONSTRAINT fk_miniweb_product_texts_product FOREIGN KEY (miniweb_product_id) REFERENCES miniweb_products (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
