-- Robert: "na homepage vytvoř system sudeho poctu oken, ktere lze
-- pridavat a odebirat... mozaika... pozitivni vliv na SEO/GEO...
-- funkce jakoby mala web stranka zmensena, kde lze menit nazev, meta
-- popis, obrazek, telo textu"
--
-- Kazdy "blok" je administrovatelna dlazdice na homepage (nazev +
-- obrazek + kratky vytah z telo_html) ktera odkazuje na VLASTNI
-- samostatnou stranku (/blok/<slug>) se skutecnym <title>/<meta
-- description> - realny SEO prinos (vic indexovatelnych stranek), ne
-- jen kosmeticky prvek na jedne URL. AskUserQuestion 2026-08-09:
-- "Vlastní stránka pro každou dlaždici (doporučeno)" + "Stejný styl
-- jako karty produktů (doporučeno)".
CREATE TABLE homepage_blocks (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(255) NOT NULL,
  slug VARCHAR(255) NOT NULL,
  meta_description VARCHAR(500) NULL,
  image_filename VARCHAR(255) NULL,
  body_html MEDIUMTEXT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  is_visible TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_homepage_blocks_slug (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
