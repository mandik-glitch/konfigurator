-- Obecny "pripojitelny" fotogalerie modul (Robert: "vytvor modul
-- fotogalerie tak aby se to dalo pridavat kdykoliv pozdeji ... do
-- kategorii ... nebo k samotnym produktum katalogu"). Polymorfni
-- (owner_type/owner_id) - BEZ FK na content_categories/shop_products,
-- protoze jeden sloupec nemuze mit FK na dve ruzne tabulky podle
-- hodnoty owner_type. Uklid osamocenych radku pri mazani vlastnika
-- resi api/gallery_items.py (delete_items_for_owner), volano z
-- categories_delete/shop_products_delete v app.py.

CREATE TABLE IF NOT EXISTS content_gallery_items (
  id INT NOT NULL AUTO_INCREMENT,
  owner_type ENUM('category','product') NOT NULL,
  owner_id INT NOT NULL,
  filename VARCHAR(255) NOT NULL,
  source_url VARCHAR(500) DEFAULT NULL,
  caption VARCHAR(255) DEFAULT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_owner (owner_type, owner_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
