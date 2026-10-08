-- Rozsireni objednavkoveho systemu (bot3, 2026-07-25, v2):
--   1) objednavku uz jde zadat jen po prihlaseni (Robert 2026-07-25: "objednávka
--      nelze zadat bez přihlášení") - tahle migrace sama o sobe zadnou zmenu
--      chovani nevyzaduje, ale nasledujici tabulky na prihlaseneho uzivatele
--      pocitaji (cart, customers jsou vzdy vazane na user_id, ne na guest).
--   2) evidence zakazniku - fakturacni/dodaci adresa, ICO/DIC, kontakt.
--   3) kosik (persistentni, per prihlaseny uzivatel).
--   4) doprava a platba jako volitelne polozky s cenou (bez platebni brany).
--
-- DULEZITE: spustit na DB instance "Configurator" (databaze xebyhtfeaj na
-- 80.211.73.226) - NE na databazi appky Sklad. Navazuje na
-- 2026-07-25_orders_schema.sql (musi byt uz aplikovana).
--
-- Pouziti:
--   mysql -h 80.211.73.226 -u <db_user> -p xebyhtfeaj < 2026-07-25_orders_v2_customers_cart_shipping.sql

-- ---------------------------------------------------------------------------
-- 1) Evidence zakazniku (1 fakturacni profil na 1 uzivatelsky ucet)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS shop_customers (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    user_id             INT NOT NULL,
    customer_type       VARCHAR(10) NOT NULL DEFAULT 'osoba',   -- 'osoba' | 'firma'
    full_name           VARCHAR(255) NOT NULL DEFAULT '',       -- fyzicka osoba, nebo kontaktni osoba u firmy
    company_name        VARCHAR(255) NULL,                      -- nazev firmy / zivnostnika (jen kdyz 'firma')
    ico                 VARCHAR(20) NULL,
    dic                 VARCHAR(20) NULL,
    email               VARCHAR(255) NOT NULL DEFAULT '',
    phone               VARCHAR(50) NULL,
    billing_address     TEXT NULL,
    delivery_address     TEXT NULL,                              -- prazdne = stejna jako fakturacni
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_shop_customers_user (user_id),
    CONSTRAINT fk_shop_customers_user
        FOREIGN KEY (user_id) REFERENCES app_users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- 2) Kosik (persistentni, jen pro prihlasene uzivatele - 1 radek = 1
--    produkt v kosiku daneho uzivatele, mnozstvi se pri opakovanem pridani
--    stejneho produktu jen zvysi)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS shop_cart_items (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT NOT NULL,
    product_id  INT NOT NULL,
    qty         INT NOT NULL,
    added_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_shop_cart_user_product (user_id, product_id),
    CONSTRAINT fk_shop_cart_items_user
        FOREIGN KEY (user_id) REFERENCES app_users(id) ON DELETE CASCADE,
    CONSTRAINT fk_shop_cart_items_product
        FOREIGN KEY (product_id) REFERENCES shop_products(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- 3) Doprava a platba - vyberove polozky s cenou (zadna platebni brana,
--    jen evidence volby a jejiho poplatku)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS shop_shipping_methods (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    price_czk   DECIMAL(12,2) NOT NULL DEFAULT 0,
    active      TINYINT(1) NOT NULL DEFAULT 1,
    sort_order  INT NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS shop_payment_methods (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    price_czk   DECIMAL(12,2) NOT NULL DEFAULT 0,
    active      TINYINT(1) NOT NULL DEFAULT 1,
    sort_order  INT NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Startovaci placeholder data - stejna konvence jako placeholder produkty
-- ze skladapp; admin si je muze kdykoli upravit pres /api/admin/shipping-methods
-- resp. /api/admin/payment-methods (UI zatim neni, jen API).
INSERT INTO shop_shipping_methods (name, price_czk, active, sort_order) VALUES
    ('Osobní odběr', 0, 1, 1),
    ('Kurýr', 120, 1, 2),
    ('Česká pošta', 90, 1, 3);

INSERT INTO shop_payment_methods (name, price_czk, active, sort_order) VALUES
    ('Bankovní převod předem', 0, 1, 1),
    ('Dobírka', 40, 1, 2),
    ('Platba kartou při převzetí', 0, 1, 3);

-- ---------------------------------------------------------------------------
-- 4) shop_orders - snapshot fakturacnich udaju + zvolene dopravy/platby
--    (stejny princip jako u shop_order_items - snapshot v okamziku
--    objednani, aby pozdejsi zmena profilu zakaznika nebo ceniku dopravy
--    nezmenila historickou objednavku)
-- ---------------------------------------------------------------------------
ALTER TABLE shop_orders
    ADD COLUMN billing_name        VARCHAR(255) NULL      AFTER delivery_address,
    ADD COLUMN billing_ico         VARCHAR(20) NULL       AFTER billing_name,
    ADD COLUMN billing_dic         VARCHAR(20) NULL       AFTER billing_ico,
    ADD COLUMN billing_address     TEXT NULL              AFTER billing_dic,
    ADD COLUMN shipping_method_name VARCHAR(100) NULL     AFTER billing_address,
    ADD COLUMN shipping_price_czk  DECIMAL(12,2) NOT NULL DEFAULT 0 AFTER shipping_method_name,
    ADD COLUMN payment_method_name VARCHAR(100) NULL      AFTER shipping_price_czk,
    ADD COLUMN payment_price_czk   DECIMAL(12,2) NOT NULL DEFAULT 0 AFTER payment_method_name;
