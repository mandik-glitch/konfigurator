-- Centralni fotogalerie (Robert 2026-09-12, pres bot3): "budeme mit
-- centralni fotogalerii na jednom miste v adminu... z teto fotogalerie
-- se budou prirazovat do kategorii ruzne fotky". Nahrazuje TRI dosavadni
-- nezavisle mechanismy (shop_gallery_images, content_gallery_items
-- owner_type='category', obrazky vlozene primo do content_pages.body_html
-- pod content-files/kategorie-popisy/) - dnesni is_public dira vznikla
-- prave z jejich nezavislosti.
--
-- KRITICKE: `file_path` u migrovanych radku NIKDY nemeni fyzickou cestu
-- souboru na disku - image_watermark_manifest.rel_path je na tuhle
-- cestu PRIMARY KEY, presun by rozbil rozliseni "uz orazitkovano" vs
-- "nove". Tabulka je nejdriv DATABAZOVA vrstva nad existujicimi soubory,
-- ne reorganizace disku (viz backfill skript scripts/2026-09-12_photo_
-- library_backfill.py).
CREATE TABLE IF NOT EXISTS content_photo_library (
  id INT AUTO_INCREMENT PRIMARY KEY,
  file_path VARCHAR(500) NOT NULL COMMENT 'relativni k webapp/, stejny format jako image_watermark_manifest.rel_path - NEMENIT pri migraci',
  title VARCHAR(255) NULL,
  alt_text VARCHAR(300) NULL,
  caption VARCHAR(255) NULL,
  is_public TINYINT(1) NOT NULL DEFAULT 0,
  -- Nahrazuje stare pevne buckety shop_gallery_images.category
  -- ('vestavby_dodavek'/'realizace_stolu') - NENI to kategorie eshopu,
  -- je to jen stitek pro puvodni dve statické sekce /realizace.html.
  realizace_tag VARCHAR(30) NULL,
  legacy_source VARCHAR(30) NOT NULL COMMENT 'shop_gallery_images|content_gallery_items|kategorie_popisy|upload - auditni stopa migrace',
  legacy_id INT NULL COMMENT 'puvodni id v puvodni tabulce, pro dohledatelnost/rollback (NULL u kategorie_popisy - tam zadne id nikdy nebylo)',
  sort_order INT NOT NULL DEFAULT 0,
  created_by INT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_file_path (file_path),
  KEY idx_realizace_tag (realizace_tag),
  KEY idx_legacy (legacy_source, legacy_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- M:N - Robert vyslovne potvrdil "jedna fotka muze byt v libovolnem
-- poctu sub-fotogalerii (v eshopu v kategoriich)", ne 1:1 jako dnes.
CREATE TABLE IF NOT EXISTS content_photo_library_categories (
  photo_id INT NOT NULL,
  category_id INT NOT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  PRIMARY KEY (photo_id, category_id),
  KEY idx_category (category_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
