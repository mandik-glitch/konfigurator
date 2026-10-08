-- Strom kategorii pro Vlastni tvary ve 3D scene (Robert 2026-08-05:
-- "ve 3D scene potrebujeme upravit strukturu vlastnich tvaru nekam na
-- urovne, stromeckove jako leve menu, vlastnich tvaru tam bude hodne
-- stovky a desitky podkategorii"). Zamerne SAMOSTATNY strom, ne napojeni
-- na `content_categories` (e-shopove kategorie produktu) - jina domena
-- (sablony sestav pro stavbu ve scene, ne prodejni katalog), stejny
-- princip jako ma projekt uz jinde (Sdileny disk/Nabidky - kazda
-- domena vlastni strom, ne sdileny).
CREATE TABLE custom_shape_categories (
  id INT AUTO_INCREMENT PRIMARY KEY,
  parent_id INT NULL,
  name VARCHAR(150) NOT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  created_by INT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_csc_parent (parent_id),
  CONSTRAINT fk_csc_parent FOREIGN KEY (parent_id) REFERENCES custom_shape_categories(id) ON DELETE CASCADE,
  CONSTRAINT fk_csc_user FOREIGN KEY (created_by) REFERENCES app_users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- NULL = "Nezarazene" (vychozi/dosavadni chovani, zadny tvar dosud
-- kategorii nema - zadny backfill nutny).
ALTER TABLE custom_shapes
  ADD COLUMN category_id INT NULL AFTER name,
  ADD CONSTRAINT fk_cs_category FOREIGN KEY (category_id) REFERENCES custom_shape_categories(id) ON DELETE SET NULL;
