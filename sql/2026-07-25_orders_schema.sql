-- Zavedeni objednavkoveho systemu (e-shop checkout) nad existujicim
-- katalogem shop_products. Autor: bot3 (Claude / Cowork), 2026-07-25.
--
-- DULEZITE: spustit na DB instance "Configurator" (databaze xebyhtfeaj na
-- 80.211.73.226, viz PREHLED_ROZHODNUTI.md) - NE na databazi appky Sklad.
-- Predpoklada existujici tabulky app_users a shop_products (uz bezi).
--
-- Pouziti (na serveru, s pristupem k DB definovanym v /opt/konfigurator/api/.env):
--   mysql -h 80.211.73.226 -u <db_user> -p xebyhtfeaj < 2026-07-25_orders_schema.sql
--
-- Po spusteni migrace je potreba na konec api/app.py pridat radek
-- `import orders` (viz DEPLOY.md v teto slozce) a restartovat systemd
-- sluzbu `konfigurator`.

CREATE TABLE IF NOT EXISTS shop_orders (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    order_number        VARCHAR(32) NOT NULL DEFAULT '',
    status              VARCHAR(20) NOT NULL DEFAULT 'nova',
    is_urgent           TINYINT(1) NOT NULL DEFAULT 0,
    user_id             INT NULL,
    customer_name       VARCHAR(255) NOT NULL,
    customer_email      VARCHAR(255) NOT NULL,
    customer_phone      VARCHAR(50) NULL,
    delivery_address    TEXT NULL,
    note                TEXT NULL,
    admin_note          TEXT NULL,
    total_czk           DECIMAL(12,2) NOT NULL DEFAULT 0,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_shop_orders_order_number (order_number),
    KEY idx_shop_orders_user (user_id),
    KEY idx_shop_orders_status (status),
    KEY idx_shop_orders_urgent (is_urgent),
    KEY idx_shop_orders_created (created_at),
    CONSTRAINT fk_shop_orders_user
        FOREIGN KEY (user_id) REFERENCES app_users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS shop_order_items (
    id                      INT AUTO_INCREMENT PRIMARY KEY,
    order_id                INT NOT NULL,
    product_id              INT NULL,
    product_name_snapshot   VARCHAR(255) NOT NULL,
    unit_price_czk          DECIMAL(12,2) NOT NULL DEFAULT 0,
    qty                     INT NOT NULL,
    line_total_czk          DECIMAL(12,2) NOT NULL DEFAULT 0,
    KEY idx_shop_order_items_order (order_id),
    CONSTRAINT fk_shop_order_items_order
        FOREIGN KEY (order_id) REFERENCES shop_orders(id) ON DELETE CASCADE,
    CONSTRAINT fk_shop_order_items_product
        FOREIGN KEY (product_id) REFERENCES shop_products(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS shop_order_status_history (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    order_id    INT NOT NULL,
    status      VARCHAR(20) NOT NULL,
    changed_by  INT NULL,
    changed_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    note        TEXT NULL,
    KEY idx_shop_order_status_history_order (order_id),
    CONSTRAINT fk_shop_order_status_history_order
        FOREIGN KEY (order_id) REFERENCES shop_orders(id) ON DELETE CASCADE,
    CONSTRAINT fk_shop_order_status_history_user
        FOREIGN KEY (changed_by) REFERENCES app_users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
