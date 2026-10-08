-- bot5 2026-08-10 (Robert: "navrhni kam to na eshop umistime... jsou
-- to ilustracni nahledy pouziti nasich prvku v praxi" -> vybral
-- "Obojí + navíc na kategorii profilu") - ilustracni obrazky z Dogus
-- PDF katalogu (montaz/pouziti spojek a prislusenstvi), napojene na
-- konkretni produkt. Zamerne SAMOSTATNA tabulka, ne rozsireni
-- content_gallery_items (jeho owner_type je ENUM bez "product_usage"
-- hodnoty + tyhle obrazky jsou vyznamove jine nez produktova fotka -
-- ukazuji SPOJ/POUZITI, ne izolovany produkt).
--
-- Jeden fyzicky obrazek muze mit VICE radku (ruzne product_id) - v
-- PDF katalogu casto 1 obrazek ukazuje 2 varianty stejneho spoje
-- (napr. "Slot 8"/"Slot 10"), takze se napoji na oba produkty zvlast.
CREATE TABLE product_usage_images (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    filename VARCHAR(255) NOT NULL,
    source_page INT,
    sort_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_product_usage_images_product (product_id),
    FOREIGN KEY (product_id) REFERENCES shop_products(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
