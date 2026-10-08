-- Kompletni infrastruktura kategorii (Robert, dle screenshotu Shoptet
-- "Upravit kategorii" - zalozky Obecne informace/Pokrocile/Viditelnost,
-- bez "Doplnkova nastaveni" - Robert vyslovne "bez doplnku").

ALTER TABLE content_categories
  ADD COLUMN slug VARCHAR(255) DEFAULT NULL AFTER name,
  ADD UNIQUE KEY uq_content_categories_slug (slug),
  ADD COLUMN nav_label VARCHAR(255) DEFAULT NULL COMMENT 'Text odkazu (v menu) - Pokrocile',
  ADD COLUMN meta_title VARCHAR(255) DEFAULT NULL COMMENT 'Nazev (tag title) - Pokrocile',
  ADD COLUMN meta_description VARCHAR(500) DEFAULT NULL COMMENT 'Popis (meta tag description) - Pokrocile',
  ADD COLUMN og_image_filename VARCHAR(255) DEFAULT NULL COMMENT 'Nahledovy obrazek pro socialni site - Pokrocile',
  ADD COLUMN is_visible TINYINT(1) NOT NULL DEFAULT 1 COMMENT 'Viditelnost stranky - Viditelnost',
  ADD COLUMN menu_expanded TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Zobrazit rozbalene v menu kategorii - Viditelnost',
  ADD COLUMN image_filename VARCHAR(255) DEFAULT NULL COMMENT 'Obrazek kategorie - Obecne informace';

ALTER TABLE content_pages
  ADD COLUMN bottom_body_html MEDIUMTEXT DEFAULT NULL COMMENT 'Spodni popis kategorie - Obecne informace';
