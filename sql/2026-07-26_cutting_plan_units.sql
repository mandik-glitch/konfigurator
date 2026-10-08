-- Perzistentni rezne plany s odskrtavanim hotovych kusu (bot4, "optimizer").
-- Robert 2026-07-25/26: "měly by se asi odklikávat, které jsou hotové" +
-- potvrzeni navrhu (NAVRH_REZNE_PLANY.md sekce 6): jednotka odskrtnuti =
-- cela tyc/deska, hotove jednotky se nikdy neprepocitavaji zpetne, vazba
-- na stav objednavky je jen informativni (zadna automaticka zmena stavu).
--
-- Pouziti (na DB instance "Configurator", xebyhtfeaj @ 80.211.73.226):
--   mysql -h 80.211.73.226 -u <user> -p xebyhtfeaj < 2026-07-26_cutting_plan_units.sql

CREATE TABLE IF NOT EXISTS shop_cutting_plans (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    generated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    generated_by    INT NULL,
    statuses_filter VARCHAR(100) NOT NULL DEFAULT 'nova,potvrzena,ve_vyrobe',
    CONSTRAINT fk_shop_cutting_plans_user
        FOREIGN KEY (generated_by) REFERENCES app_users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS shop_cutting_plan_units (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    plan_id         INT NOT NULL,
    cut_kind        VARCHAR(10) NOT NULL,
    material_key    VARCHAR(40) NOT NULL,
    stock_id        INT NOT NULL,
    unit_index      INT NOT NULL,
    pieces_json     JSON NOT NULL,
    used_amount     DECIMAL(14,1) NULL,   -- profil: used_mm, deska: used_area_mm2 (jen pro zobrazeni bez prepoctu)
    waste_amount    DECIMAL(14,1) NULL,
    status          VARCHAR(10) NOT NULL DEFAULT 'pending',
    done_at         DATETIME NULL,
    done_by         INT NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_scpu_status (status),
    KEY idx_scpu_material (cut_kind, material_key),
    CONSTRAINT fk_scpu_plan FOREIGN KEY (plan_id) REFERENCES shop_cutting_plans(id) ON DELETE CASCADE,
    CONSTRAINT fk_scpu_stock FOREIGN KEY (stock_id) REFERENCES shop_cutting_stock(id),
    CONSTRAINT fk_scpu_done_by FOREIGN KEY (done_by) REFERENCES app_users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
