-- Mini-shop, katalog patri RODINE shopu (bot5, 2026-10-02): kategorie dostane family, shopy se stejnou family (jazykove verze) sdili jeden katalog a shop jine rodiny (napr. pracovni stoly) vidi jen sve.
-- Bez toho by kazdy mini-shop videl kategorie a produkty vsech rodin. Produkt dedi rodinu pres kategorii. Slug kategorie je unikatni v ramci rodiny, ne globalne.
-- Migrace upravuje JEN nove (prazdne, dosud nenasazene) tabulky miniweb_categories z migrace sql/2026-10-02_miniweb.sql. ALTER neni opakovatelny (MySQL 8 nezna ADD COLUMN IF NOT EXISTS).
-- Aplikace: python api/db_migrate.py sql/2026-10-02_miniweb_family.sql
-- POZOR: db_migrate deli prikazy podle strednikuv, v COMMENT retezcich proto zadne strednik.

ALTER TABLE miniweb_categories
  ADD COLUMN family VARCHAR(40) NOT NULL DEFAULT 'default' COMMENT 'rodina mini-shopu (stejna hodnota jako miniweb_shops.family), shop vidi jen kategorie sve rodiny' AFTER parent_id,
  DROP INDEX uq_miniweb_categories_slug,
  ADD UNIQUE KEY uq_miniweb_categories_family_slug (family, slug),
  ADD KEY idx_miniweb_categories_family (family);
