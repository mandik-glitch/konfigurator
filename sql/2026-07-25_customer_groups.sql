-- Skupiny zakazniku s ramcovou slevou (bot3, 2026-07-25, v3).
--
-- Robert: "skupiny zákazníků, potřebujeme jim přiřadit různou rámcovou
-- slevu." -> Explicitne receno "zatím nenasazuj" - tenhle soubor je
-- PRIPRAVENY, ale NEAPLIKOVANY na produkcni DB. Nasazeni az na dalsi
-- pokyn (viz AGENTS_LOG.md, zaznam bot3 2026-07-25 (4) pro presny postup
-- shodny s predchozimi migracemi - SQL -> soubory na server -> import v
-- app.py -> restart, vse pod DEPLOY_LOCK.json).
--
-- Navazuje na 2026-07-25_orders_v2_customers_cart_shipping.sql (musi byt
-- uz aplikovana - potrebuje tabulku shop_customers).
--
-- Pouziti (az bude dano svoleni k nasazeni):
--   mysql -h 80.211.73.226 -u <db_user> -p xebyhtfeaj < 2026-07-25_customer_groups.sql

CREATE TABLE IF NOT EXISTS shop_customer_groups (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    name                VARCHAR(100) NOT NULL,
    discount_percent    DECIMAL(5,2) NOT NULL DEFAULT 0,
    note                TEXT NULL,
    active              TINYINT(1) NOT NULL DEFAULT 1,
    sort_order          INT NOT NULL DEFAULT 0,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_shop_customer_groups_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Startovaci placeholder skupiny - stejna konvence jako u dopravy/platby,
-- admin si je muze kdykoli prejmenovat/upravit slevu pres
-- /api/admin/customer-groups (zatim jen API, bez UI).
INSERT INTO shop_customer_groups (name, discount_percent, active, sort_order) VALUES
    ('Standardní', 0,  1, 1),
    ('Velkoobchod', 10, 1, 2),
    ('VIP', 15,        1, 3);

-- Zakaznik muze (ale nemusi) patrit do prave jedne skupiny - prirazuje
-- VYHRADNE admin (viz customers.py: admin_customers_update prijima
-- group_id, samoobsluzny PUT /api/customer/profile ho ZAMERNE
-- nepodporuje - zakaznik si sam slevovou skupinu nastavit nemuze).
ALTER TABLE shop_customers
    ADD COLUMN group_id INT NULL,
    ADD CONSTRAINT fk_shop_customers_group
        FOREIGN KEY (group_id) REFERENCES shop_customer_groups(id) ON DELETE SET NULL;

-- Snapshot na objednavce - jaka skupina/sleva byla aplikovana v okamziku
-- objednani (stejny princip jako billing_*/shipping_*/payment_* v
-- predchozi migraci - pozdejsi zmena slevy skupiny nezmeni historickou
-- objednavku). Sleva se aplikuje PRIMO do unit_price_czk polozek
-- (shop_order_items) - tady je jen pro dohledatelnost "proc byla cena
-- nizsi".
ALTER TABLE shop_orders
    ADD COLUMN customer_group_name VARCHAR(100) NULL,
    ADD COLUMN customer_discount_percent DECIMAL(5,2) NOT NULL DEFAULT 0;
