-- bot5 2026-08-10 (Robert: "udelej novou sekci v adminu, a dlazdici
-- tam prenes, prekopiruj" - postranni panel jako plnohodnotna,
-- samostatna obdoba homepage_blocks/"dlazdic", jen s jinym umistenim
-- (levy sidebar na vsech strankach, ne homepage mozaika) a vlastni
-- admin sekci, ne sdileny s homepage_blocks).
--
-- Schema 1:1 podle homepage_blocks (sql/2026-08-09_homepage_blocks.sql),
-- navic video_filename (Robert: "to video tam vloží admin" - vlastni
-- upload tlacitko pro video, ne jen pro nahledovy obrazek/poster).
CREATE TABLE sidebar_blocks (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(255) NOT NULL,
  slug VARCHAR(255) NOT NULL,
  meta_description VARCHAR(500) NULL,
  image_filename VARCHAR(255) NULL,
  video_filename VARCHAR(255) NULL,
  body_html MEDIUMTEXT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  is_visible TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_sidebar_blocks_slug (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
