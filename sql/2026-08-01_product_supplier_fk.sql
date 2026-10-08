-- Propojeni produktovych karet s dodavateli (bot6, 2026-08-01).
--
-- Robert: "az to doddelas je potreba ty produkty k tem dodavatelum
-- priradit aby se predbnabizeli kdyz dam do objednavky dodavatele
-- muzou se mi rovnou ty produkty nabidnout a nemusime hledat" - navazuje
-- na hromadny import ~67 nakupnich polozek + 41 dodavatelu z PDF
-- (shop_products.is_supplier_item, viz 2026-07-31_supplier_item_flag.sql).
--
-- shop_products.supplier_name (volny text) dosud nemel zadnou FK vazbu
-- na shop_suppliers.id - novy sloupec supplier_id tohle opravuje, stejna
-- konvence jako shop_purchase_orders.supplier_id (ON DELETE SET NULL).
-- supplier_name zustava beze zmeny (fallback popisek/historie), supplier_id
-- je nova strukturovana vazba pouzita pro filtrovani v adminu.
ALTER TABLE shop_products
  ADD COLUMN supplier_id INT NULL,
  ADD CONSTRAINT fk_shop_products_supplier FOREIGN KEY (supplier_id) REFERENCES shop_suppliers(id) ON DELETE SET NULL;

CREATE INDEX idx_shop_products_supplier ON shop_products(supplier_id);
