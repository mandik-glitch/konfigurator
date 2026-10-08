-- Rezne plany (bot4, "optimizer") - datovy model, viz NAVRH_REZNE_PLANY.md.
-- Vsechny zmeny jsou ADITIVNI a NULLable / maji vychozi hodnotu - stavajici
-- kod (orders.py, cart.py) se stimhle souborem NEMENI a dal funguje beze
-- zmeny chovani, protoze zadny existujici SELECT/INSERT tyhle sloupce
-- nezmiňuje. Bezpecne spustit i behem toho, co jiny bot pracuje na
-- nesouvisejicich casteh appky.
--
-- Pouziti (na DB instance "Configurator", xebyhtfeaj @ 80.211.73.226):
--   mysql -h 80.211.73.226 -u <user> -p xebyhtfeaj < 2026-07-25_cutting_plans.sql

ALTER TABLE shop_order_items
  ADD COLUMN cut_kind        VARCHAR(10)  NULL COMMENT 'profil | deska | NULL=bezny produkt',
  ADD COLUMN material_key    VARCHAR(40)  NULL COMMENT 'napr. 30x30 (profil) nebo mdf_8 (deska)',
  ADD COLUMN length_mm       DECIMAL(8,1) NULL COMMENT 'profil: rezana delka',
  ADD COLUMN width_mm        DECIMAL(8,1) NULL COMMENT 'deska: sirka kusu',
  ADD COLUMN height_mm       DECIMAL(8,1) NULL COMMENT 'deska: vyska/hloubka kusu',
  ADD COLUMN grain_locked    TINYINT(1)   NOT NULL DEFAULT 0 COMMENT 'deska: nesmi se otocit o 90 stupnu',
  ADD COLUMN source_scene_id VARCHAR(64)  NULL COMMENT 'volitelna vazba na ulozenou scenu/sestavu';

CREATE TABLE IF NOT EXISTS shop_cutting_stock (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    cut_kind        VARCHAR(10)  NOT NULL,
    material_key    VARCHAR(40)  NOT NULL,
    label           VARCHAR(100) NOT NULL,
    stock_length_mm DECIMAL(8,1) NULL,
    stock_width_mm  DECIMAL(8,1) NULL,
    stock_height_mm DECIMAL(8,1) NULL,
    price_czk       DECIMAL(12,2) NOT NULL DEFAULT 0,
    active          TINYINT(1) NOT NULL DEFAULT 1,
    sort_order      INT NOT NULL DEFAULT 0,
    KEY idx_shop_cutting_stock_material (cut_kind, material_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS shop_cutting_settings (
    material_key       VARCHAR(40) PRIMARY KEY,
    kerf_mm             DECIMAL(5,2) NOT NULL DEFAULT 3.0,
    orientation_locked  TINYINT(1) NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Pocatecni sada - POTVRZENO Robertem 2026-07-25 (viz NAVRH_REZNE_PLANY.md
-- sekce 5). Ceny zatim placeholder 0 Kc, dokud Robert nedoda cenik.
INSERT INTO shop_cutting_stock (cut_kind, material_key, label, stock_length_mm, price_czk, sort_order) VALUES
    ('profil', '30x30', 'Tyč 30×30, 3000 mm (reálná délka 3005 mm, rezerva)', 3000.0, 0, 10);

INSERT INTO shop_cutting_stock (cut_kind, material_key, label, stock_width_mm, stock_height_mm, price_czk, sort_order) VALUES
    ('deska', 'preklizka_10', 'Překližka 10 mm, 2500×1250 mm', 2500.0, 1250.0, 0, 20),
    ('deska', 'mdf_8',        'MDF 8 mm, 2800×2070 mm',        2800.0, 2070.0, 0, 30);

INSERT INTO shop_cutting_settings (material_key, kerf_mm) VALUES
    ('30x30', 3.0),
    ('preklizka_10', 3.0),
    ('mdf_8', 3.0);
