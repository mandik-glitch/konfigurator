-- Rezny plan: zasoba ZBYTKU vznikajicich rezanim profilu (Robert 2026-08-06:
-- "bude se kalkulovat skladova zasoba profilu (delka vzdy 3000mm) a
-- zasoba zbytku vznikajicich rezanim, tzn bude se drzet databaze zbytku,
-- sila rezu (ztrata) je 4mm"). Rozhodnuti z doprovodnych otazek:
--   - zbytek se zaeviduje AUTOMATICKY, jakmile admin na dilne odskrtne
--     tyc jako "hotovo" (delka odpadu je z vypoctu planu presne znama
--     predem, zadny rucni zasah neni potreba)
--   - min. delka zbytku hodna skladovani: 50 mm (kratsi jde rovnou do
--     odpadu, nikdy se do shop_cutting_remnants nezaloz)
--   - kerf 4mm plati JEN pro profily (desky zustavaji na 3mm)
--   - zbytky se resi jen pro cut_kind='profil' (2D zbytky z desek NEJSOU
--     v teto iteraci v rozsahu pozadavku)
--
-- Pouziti (na DB instance "Configurator", xebyhtfeaj @ 80.211.73.226):
--   mysql -h 80.211.73.226 -u <user> -p xebyhtfeaj < 2026-08-06_cutting_remnants.sql

CREATE TABLE IF NOT EXISTS shop_cutting_remnants (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    cut_kind        VARCHAR(10) NOT NULL DEFAULT 'profil',
    material_key    VARCHAR(40) NOT NULL,
    length_mm       DECIMAL(8,1) NOT NULL,
    status          VARCHAR(10) NOT NULL DEFAULT 'available',  -- available | used
    source_unit_id  INT NULL,  -- shop_cutting_plan_units.id, z jake tyce zbytek vznikl (audit)
    used_by_unit_id INT NULL,  -- shop_cutting_plan_units.id, kde byl zbytek spotrebovan
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    used_at         DATETIME NULL,
    KEY idx_scr_material_status (cut_kind, material_key, status),
    CONSTRAINT fk_scr_source_unit FOREIGN KEY (source_unit_id) REFERENCES shop_cutting_plan_units(id) ON DELETE SET NULL,
    CONSTRAINT fk_scr_used_unit FOREIGN KEY (used_by_unit_id) REFERENCES shop_cutting_plan_units(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Vazba na jednotku, ktera vznikla ze ZBYTKU (misto cerstve tyce) - NULL
-- = bezna cerstva tyc (drivejsi/beznyy pripad, beze zmeny chovani).
ALTER TABLE shop_cutting_plan_units
    ADD COLUMN remnant_id INT NULL AFTER stock_id,
    ADD CONSTRAINT fk_scpu_remnant FOREIGN KEY (remnant_id) REFERENCES shop_cutting_remnants(id) ON DELETE SET NULL;

UPDATE shop_cutting_settings SET kerf_mm = 4.0 WHERE material_key = '30x30';
