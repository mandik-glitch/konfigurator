-- SEO audit (bot6, 2026-08-03) - "Yoast-styl" nastroje primo v adminu:
-- 1) focus_keyword - cilove klicove slovo kategorie, kontroluje se proti
--    title/popisu/slugu/textu (viz admin.html cem-seo-checklist).
-- 2) content_category_redirects - kdyz nekdo v adminu zmeni slug
--    existujici kategorie, stara URL by jinak zacala vracet 404 a
--    Google by prisel o cely dosavadni index/odkazy na ni. Zaznamena se
--    stary slug -> kategorie, /kategorie/<stary-slug> pak vraci 301 na
--    aktualni URL misto 404.
ALTER TABLE content_categories
  ADD COLUMN focus_keyword VARCHAR(255) DEFAULT NULL COMMENT 'Cilove klicove slovo pro SEO kontrolu - Pokrocile';

CREATE TABLE content_category_redirects (
  old_slug VARCHAR(255) NOT NULL PRIMARY KEY,
  category_id INT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_cat_redirect_category FOREIGN KEY (category_id) REFERENCES content_categories(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
