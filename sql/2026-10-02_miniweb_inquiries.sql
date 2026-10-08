-- Mini-shop (Packstations a dalsi tema mini-shopy), faze 2: poptavka z mini-shopu (bot5, 2026-10-02; navrh schvalil bot3).
-- POST /api/miniweb/inquiry zaklada CRM poptavku (crm_leads + crm_lead_messages, source miniweb) jako storefront_lead_create a potvrzeni zakaznikovi jen do schvalovaci fronty (system_emails, pravidlo 16).
-- Osobni udaje (jmeno, e-mail, telefon, firma, text zpravy) zustavaji JEN v CRM, tady je nepersonalni snimek: shop, host a jazyk v dobe poptavky, zeme, souhlas se zpracovanim a polozky.
-- Polozky drzi snimek verejneho kodu a nazvu v jazyce shopu a konfiguraci z konfiguratoru (neoverenou, jen k dohledani a zobrazeni). Ceny se NEUKLADAJI, cenu urci nabidka.
-- Migrace JEN PRIDAVA nove tabulky (CREATE TABLE IF NOT EXISTS, opakovatelne). Aplikace: python api/db_migrate.py sql/2026-10-02_miniweb_inquiries.sql
-- POZOR: db_migrate deli prikazy podle strednikuv, v COMMENT retezcich proto zadne strednik. Sloupec nesmi mit nazev product_id (QA product_duplicate_unclassified_table), proto miniweb_product_id.

CREATE TABLE IF NOT EXISTS miniweb_inquiries (
  id INT NOT NULL AUTO_INCREMENT,
  storefront_id INT NOT NULL,
  shop_host VARCHAR(255) NOT NULL COMMENT 'nemenny snimek: normalizovany Host, na kterem poptavka vznikla',
  lang VARCHAR(8) NOT NULL COMMENT 'nemenny snimek: jazyk shopu v dobe poptavky',
  crm_lead_id INT DEFAULT NULL COMMENT 'poptavka v CRM (crm_leads), po jejim smazani NULL a snimek zustane bez osobnich udaju',
  system_email_id INT DEFAULT NULL COMMENT 'potvrzeni cekajici ve fronte ke schvaleni (system_emails), NULL kdyz pro jazyk shopu neni sablona',
  country CHAR(2) DEFAULT NULL COMMENT 'zeme zakaznika (ISO 3166-1 alpha-2), nepovinne',
  consent_at DATETIME NOT NULL COMMENT 'kdy zakaznik odsouhlasil zpracovani udaju k vyrizeni poptavky',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_miniweb_inquiries_storefront (storefront_id, created_at),
  KEY idx_miniweb_inquiries_lead (crm_lead_id),
  CONSTRAINT fk_miniweb_inquiries_storefront FOREIGN KEY (storefront_id) REFERENCES car_storefronts (id) ON DELETE RESTRICT,
  CONSTRAINT fk_miniweb_inquiries_lead FOREIGN KEY (crm_lead_id) REFERENCES crm_leads (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS miniweb_inquiry_items (
  id INT NOT NULL AUTO_INCREMENT,
  inquiry_id INT NOT NULL,
  miniweb_product_id INT NOT NULL,
  public_sku VARCHAR(50) NOT NULL COMMENT 'snimek verejneho kodu produktu',
  product_name VARCHAR(200) NOT NULL COMMENT 'snimek nazvu v jazyce shopu',
  qty SMALLINT UNSIGNED NOT NULL DEFAULT 1,
  config_code VARCHAR(60) DEFAULT NULL COMMENT 'kod konfigurace z konfiguratoru',
  config_hash VARCHAR(128) DEFAULT NULL COMMENT 'otisk konfigurace z konfiguratoru, neoverovany',
  config_json JSON DEFAULT NULL COMMENT 'konfigurace z prohlizece, neoverena, jen k dohledani a zobrazeni',
  summary_json JSON DEFAULT NULL COMMENT 'seznam parametru konfigurace (label a value) ke zobrazeni',
  PRIMARY KEY (id),
  KEY idx_miniweb_inquiry_items_inquiry (inquiry_id),
  KEY idx_miniweb_inquiry_items_product (miniweb_product_id),
  CONSTRAINT fk_miniweb_inquiry_items_inquiry FOREIGN KEY (inquiry_id) REFERENCES miniweb_inquiries (id) ON DELETE RESTRICT,
  CONSTRAINT fk_miniweb_inquiry_items_product FOREIGN KEY (miniweb_product_id) REFERENCES miniweb_products (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
