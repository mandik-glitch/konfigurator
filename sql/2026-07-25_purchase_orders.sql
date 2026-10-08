-- Nakupni objednavky (smerem K DODAVATELUM) - bot3, 2026-07-25, v7.
--
-- Kontext: Robert "pridejme jeste Nákupní objednávky" - NA ROZDIL od
-- shop_orders (objednavky OD zakazniku), tohle jsou objednavky, ktere
-- LOGIMAN zadava svym dodavatelum (nakup materialu/zbozi na sklad).
-- Rozsah potvrzen pres AskUserQuestion (2026-07-25, multiSelect - vsechny
-- 3 zvoleny):
--   1. Evidence dodavatelu (zakladni karta - nazev/adresa/ICO/DIC/kontakt)
--   2. Polozky napojene na sklad (shop_products) - prijem zbozi zvysi
--      stock_qty automaticky (stejny princip jako prijem/vydej u
--      shop_orders v orders.py::admin_orders_update)
--   3. Stavy/schvalovani - navrh -> odeslano -> (castecne) prijato,
--      s auditni historii (stejny vzor jako shop_order_status_history)
--
-- Cislovani: vlastni rada "NO-YYYY-NNNNN" (analogicky k "OBJ-YYYY-NNNNN"
-- u shop_orders) - NENI to stejny typ cisla jako RRMMxxxx doklady
-- (zalohova faktura/faktura z v6) - nakupni objednavka neni danovy doklad
-- vuci zakaznikovi, je to interni/dodavatelsky doklad.
--
-- Pouziti: mysql -h 80.211.73.226 -u <db_user> -p xebyhtfeaj < 2026-07-25_purchase_orders.sql

CREATE TABLE IF NOT EXISTS shop_suppliers (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    ico             VARCHAR(20) NULL,
    dic             VARCHAR(20) NULL,
    address         TEXT NULL,
    contact_name    VARCHAR(255) NULL,
    email           VARCHAR(255) NULL,
    phone           VARCHAR(50) NULL,
    note            TEXT NULL,
    active          TINYINT(1) NOT NULL DEFAULT 1,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Stavy: navrh (pripravuje se, jeste neodeslano) -> odeslano (poslano
-- dodavateli) -> castecne_prijato / prijato (podle poctu prijatych kusu
-- napric polozkami - dopocitava se AUTOMATICKY z shop_purchase_order_items,
-- viz api/purchase_orders.py::_recompute_status_after_receive) -> zruseno
-- (kdykoli z aktivniho stavu, koncovy stav jako u shop_orders).
CREATE TABLE IF NOT EXISTS shop_purchase_orders (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    po_number           VARCHAR(32) NOT NULL DEFAULT '' UNIQUE,
    status              VARCHAR(20) NOT NULL DEFAULT 'navrh',
    supplier_id         INT NULL,
    -- Snapshot udaju dodavatele v okamziku vytvoreni (stejny princip jako
    -- billing_* na shop_orders) - pozdejsi zmena karty dodavatele
    -- nezmeni historickou nakupni objednavku.
    supplier_name       VARCHAR(255) NOT NULL,
    supplier_ico        VARCHAR(20) NULL,
    supplier_dic         VARCHAR(20) NULL,
    supplier_address    TEXT NULL,
    supplier_contact_name VARCHAR(255) NULL,
    supplier_email       VARCHAR(255) NULL,
    supplier_phone       VARCHAR(50) NULL,
    note                TEXT NULL,
    admin_note          TEXT NULL,
    total_czk           DECIMAL(12,2) NOT NULL DEFAULT 0,
    created_by          INT NULL,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_shop_po_supplier FOREIGN KEY (supplier_id) REFERENCES shop_suppliers(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS shop_purchase_order_items (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    purchase_order_id   INT NOT NULL,
    product_id          INT NOT NULL,
    product_name_snapshot VARCHAR(255) NOT NULL,
    sku_snapshot        VARCHAR(50) NULL,
    unit_price_czk      DECIMAL(12,2) NOT NULL DEFAULT 0,  -- nakupni cena za kus, BEZ DPH
    qty_ordered         INT NOT NULL,
    qty_received        INT NOT NULL DEFAULT 0,            -- bezi nahoru s kazdym prijmem (podpora castecnych dodavek)
    line_total_czk       DECIMAL(12,2) NOT NULL DEFAULT 0,
    CONSTRAINT fk_shop_po_items_po FOREIGN KEY (purchase_order_id) REFERENCES shop_purchase_orders(id),
    CONSTRAINT fk_shop_po_items_product FOREIGN KEY (product_id) REFERENCES shop_products(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS shop_purchase_order_status_history (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    purchase_order_id   INT NOT NULL,
    status              VARCHAR(20) NOT NULL,
    changed_by          INT NULL,
    changed_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    note                TEXT NULL,
    CONSTRAINT fk_shop_po_history_po FOREIGN KEY (purchase_order_id) REFERENCES shop_purchase_orders(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
