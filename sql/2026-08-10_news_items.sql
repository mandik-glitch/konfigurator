-- bot5 2026-08-10
-- Robert: "udelej pro homepage jednoduchý typ dlazdice povedle mozaiky,
-- pro ohlašování nových zpráv novinek tzn jen text plnohodnotně pro seo,
-- design jako dlazdice mozaiky, jen s možností menit barvy okrajů" +
-- "podobne jako dlazdice s fotogalerií" (crossfade karusel poslednich 3
-- novinek na homepage, klik vede na plny seznam) + "stare zprávy se řadí
-- dolu... při zavrenem okne kolujují poslední 3 novinky".
--
-- Vlastni tabulka (ne rozsireni homepage_blocks) - jina sada poli (zadny
-- obrazek, navic border_color), jine razeni (vzdy chronologicky podle
-- created_at, ne rucni sort_order), jina verejna stranka (/novinky.html
-- seznam + /novinka/<slug> jednotlive polozky, misto /blok/<slug>).
CREATE TABLE news_items (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(255) NOT NULL,
  slug VARCHAR(255) NOT NULL,
  meta_description VARCHAR(500) NULL,
  body_html MEDIUMTEXT NULL,
  border_color VARCHAR(7) NULL,
  is_visible TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_news_items_slug (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
