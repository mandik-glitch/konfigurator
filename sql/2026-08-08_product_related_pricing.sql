-- Zalozka "Souvisejici" + rozsireni "Cenotvorba" na skladove karte -
-- bot3, 2026-08-08. Robert: "potom zalozka nova Souvisejici, tam budou
-- presunuty jiz existuji souvis.produkty, dale souvisejici dokumenty
-- napr pdf a videa. zalozka Cenotvorba nove dostane: dealerska sleva...
-- kuponovy system... akcni cena s casovou platnosti".

-- Souvisejici dokumenty (PDF/video) - VLASTNI jednoducha tabulka misto
-- rozsirovani sdileneho content_gallery_items (ten je napojen na
-- fotogalerie napric cely appkou - kategorie/produkty/capture/CRM - a
-- rozsirovat ho o PDF/video by riskovalo regresi tam, kde se nechce).
-- Primy FK na shop_products (ne polymorfni owner_type/owner_id jako
-- gallery_items) - ON DELETE CASCADE resi uklid pri smazani produktu
-- automaticky, bez nutnosti rucniho uklidu v shop_products_delete.
CREATE TABLE shop_product_documents (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    product_id    INT NOT NULL,
    filename      VARCHAR(255) NOT NULL,
    original_name VARCHAR(255) NULL,
    doc_type      ENUM('pdf','video') NOT NULL,
    caption       VARCHAR(255) NULL,
    sort_order    INT NOT NULL DEFAULT 0,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES shop_products(id) ON DELETE CASCADE,
    KEY idx_product (product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Dealerska sleva (Robert, po upresneni: "prihlaseny ktery ma
-- schvalenou dealerskou slevu, vidi ceny rovnou ponizene") - procento
-- se nastavuje PO PRODUKTU (admin), schvaleni dealerskeho statusu PO
-- ZAKAZNIKOVI (admin). Obe pole editovatelna jen adminem (vynuceno v
-- API, ne jen skryto v UI - stejny vzor jako "Testovaci data"
-- generator drive tuhle session).
ALTER TABLE shop_products
    ADD COLUMN dealer_discount_percent DECIMAL(5,2) NULL COMMENT 'Dealerska sleva v % - jen pro schvalene dealery';

ALTER TABLE shop_customers
    ADD COLUMN is_dealer_approved TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Schvalena dealerska sleva (admin)';

-- Akcni cena s casovou platnosti.
ALTER TABLE shop_products
    ADD COLUMN sale_price_czk DECIMAL(10,2) NULL COMMENT 'Akcni cena bez DPH',
    ADD COLUMN sale_price_from DATETIME NULL COMMENT 'Akcni cena plati od',
    ADD COLUMN sale_price_until DATETIME NULL COMMENT 'Akcni cena plati do';

-- Kuponovy system - Robert upresnil: "jen konkretni produkt" (ne cely
-- kosik) + "jeden sdileny kod" (ne jednorazove kody na osobu). Jeden
-- produkt muze mit vice kuponu v case (historie), ale realne pouzitelny
-- je vzdy jen ten s active=1 a platnym datem.
CREATE TABLE shop_product_coupons (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    product_id      INT NOT NULL,
    code            VARCHAR(40) NOT NULL,
    discount_type   ENUM('percent','fixed') NOT NULL DEFAULT 'percent',
    discount_value  DECIMAL(10,2) NOT NULL,
    valid_from      DATETIME NULL,
    valid_until     DATETIME NULL,
    active          TINYINT(1) NOT NULL DEFAULT 1,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES shop_products(id) ON DELETE CASCADE,
    UNIQUE KEY uq_code (code),
    KEY idx_product (product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
