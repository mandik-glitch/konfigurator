-- bot5, 2026-09-17 - Robert primo (pres bot7): "kategorie eshopu je
-- potreba osadit sestavama, at je to videt, takze 1 sestava muze byt
-- na vice kategoriich." `shop_products.category_id` (jediny FK) na to
-- nestaci - zustava PRIMARNI/hlavni kategorie (breadcrumb/canonical),
-- tahle tabulka nese DALSI (sekundarni) kategorie navic. Stejny vzor
-- jako uz existujici `content_photo_library_categories` (zadny
-- DB-level FK, jen slozeny PRIMARY KEY + index - zavedena konvence
-- projektu, viz i `bots`/`bot_ukoly`).
CREATE TABLE shop_product_categories (
  product_id INT NOT NULL,
  category_id INT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (product_id, category_id),
  KEY idx_category (category_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
