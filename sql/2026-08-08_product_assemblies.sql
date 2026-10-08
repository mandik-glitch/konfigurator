-- "Produktové sestavy" - novy panel ve 3D scene, prakticky kopie
-- "Vlastni tvary" (viz custom_shapes/custom_shape_categories), ale s
-- jednim zasadnim rozdilem: kazda ulozena sestava se rovnou "propise"
-- (bot7, 2026-08-08, Robert: "Vytvoř ve scéně nový panel prakticky
-- kopii panelu vlastní tvary... rozdílem že uložené sestavy se budou
-- propisovat jako e-shopové položky k prodeji") jako NAVRH e-shopove
-- polozky (shop_products, active=0 - admin dodela cenu/foto/kategorii
-- a rucne aktivuje, viz AskUserQuestion "Rovnou navrh, admin dodela").
--
-- Struktura zamerne 1:1 kopiruje custom_shapes/custom_shape_categories
-- (viz `SHOW CREATE TABLE custom_shapes`), AZ NA:
-- - product_assemblies.shop_product_id (FK na shop_products, SET NULL
--   pri smazani produktu - smazani navazaneho produktu sestavu
--   nezniči, jen ztrati odkaz).
-- - ZADNE zrcadleni na Sdileny disk (drive_file_id/drive_folder_id) -
--   vedomne vynechano pro prvni verzi (custom_shapes ma tenhle
--   mechanismus navic, neni to nutna soucast zakladni funkce).

CREATE TABLE product_assembly_categories (
  id INT NOT NULL AUTO_INCREMENT,
  parent_id INT DEFAULT NULL,
  name VARCHAR(150) NOT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  created_by INT DEFAULT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_pac_parent (parent_id),
  KEY fk_pac_user (created_by),
  CONSTRAINT fk_pac_parent FOREIGN KEY (parent_id) REFERENCES product_assembly_categories (id) ON DELETE CASCADE,
  CONSTRAINT fk_pac_user FOREIGN KEY (created_by) REFERENCES app_users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE product_assemblies (
  id INT NOT NULL AUTO_INCREMENT,
  name VARCHAR(255) NOT NULL,
  category_id INT DEFAULT NULL,
  data LONGTEXT NOT NULL,
  created_by INT DEFAULT NULL,
  is_public TINYINT(1) NOT NULL DEFAULT 0,
  shop_product_id INT DEFAULT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_pa_created_by (created_by),
  KEY fk_pa_category (category_id),
  KEY fk_pa_shop_product (shop_product_id),
  CONSTRAINT fk_pa_created_by FOREIGN KEY (created_by) REFERENCES app_users (id) ON DELETE SET NULL,
  CONSTRAINT fk_pa_category FOREIGN KEY (category_id) REFERENCES product_assembly_categories (id) ON DELETE SET NULL,
  CONSTRAINT fk_pa_shop_product FOREIGN KEY (shop_product_id) REFERENCES shop_products (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
