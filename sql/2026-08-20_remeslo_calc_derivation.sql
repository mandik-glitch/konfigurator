-- Řemeslo - zviditelnění odvození/zdroje u položek kalkulaček +
-- individualizace (per-řemeslník výchozí hodnoty koeficientů, trvale
-- skryté položky) - bot9, 2026-08-20. Viz REMESLO_KONCEPT.md
-- "Zviditelnění odvození a zdroje" + "ROZŠÍŘENO o individualizaci"
-- (schváleno Robertem, dvě nezávislé recenze + druhý nezávislý návrh
-- proběhly PŘED implementací).
--
-- Kaskáda hodnot: hodnota v TÉTO kalkulaci > výchozí hodnota
-- ŘEMESLNÍKA (remeslo_craftsman_coef_defaults) > SYSTÉMOVÁ hodnota
-- (natvrdo v _calc_* funkci, z technického listu).
--
-- Použití: python api/db_migrate.py sql/2026-08-20_remeslo_calc_derivation.sql

-- Všechny nové sloupce jsou nullable/výchozí 0 - staré řádky (stovky
-- už uložených kalkulací) fungují beze změny, žádný backfill.
ALTER TABLE remeslo_calculation_items
    ADD COLUMN klic              VARCHAR(80)   NULL AFTER pricelist_item_id,
    ADD COLUMN mnozstvi_formula  DECIMAL(12,4) NULL AFTER mnozstvi,
    ADD COLUMN odvozeni          VARCHAR(500)  NULL AFTER mnozstvi_formula,
    ADD COLUMN zdroj             VARCHAR(300)  NULL AFTER odvozeni,
    ADD COLUMN koeficienty_json  JSON          NULL AFTER zdroj,
    ADD COLUMN is_orphaned       TINYINT NOT NULL DEFAULT 0 AFTER is_used,
    ADD KEY idx_klic (calculation_id, klic);

-- Řemeslníkova trvalá výchozí hodnota koeficientu. Scoped i podle
-- calculator_type_id, NE jen craftsman_id+input_key - input_key je
-- jedinečný jen v rámci JEDNÉ _calc_* funkce (např. "rezerva_percent"
-- existuje u víc kalkuláček s jinak vhodnou hodnotou pro každou), bez
-- rozlišení kalkulačky by nastavení jedné tiše přetékalo do druhé.
-- Lazy vznik řádku (jen když řemeslník skutečně něco uloží), stejný
-- vzor jako remeslo_invoicing_settings.
CREATE TABLE IF NOT EXISTS remeslo_craftsman_coef_defaults (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    craftsman_id        INT NOT NULL,
    calculator_type_id  INT NOT NULL,
    input_key           VARCHAR(80) NOT NULL,
    hodnota              DECIMAL(12,4) NOT NULL,
    created_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_craftsman_coef (craftsman_id, calculator_type_id, input_key),
    CONSTRAINT fk_remeslo_coef_def_craftsman FOREIGN KEY (craftsman_id) REFERENCES remeslo_craftsmen(id) ON DELETE CASCADE,
    CONSTRAINT fk_remeslo_coef_def_type FOREIGN KEY (calculator_type_id) REFERENCES remeslo_calculator_types(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Trvale skryté položky ("nikdy nepoužívám tuhle systémovou položku").
-- nazev_snapshot je text položky V OKAMŽIKU skrytí - slouží jen pro
-- čitelnost v seznamu "Nastavení -> Skryté položky", NENÍ zdroj pravdy
-- (ten je pořád `klic`, `nazev` se může časem přejmenovat).
CREATE TABLE IF NOT EXISTS remeslo_craftsman_item_prefs (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    craftsman_id        INT NOT NULL,
    calculator_type_id  INT NOT NULL,
    item_klic           VARCHAR(80) NOT NULL,
    nazev_snapshot       VARCHAR(255) NULL,
    hidden               TINYINT NOT NULL DEFAULT 1,
    created_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_craftsman_item (craftsman_id, calculator_type_id, item_klic),
    CONSTRAINT fk_remeslo_item_pref_craftsman FOREIGN KEY (craftsman_id) REFERENCES remeslo_craftsmen(id) ON DELETE CASCADE,
    CONSTRAINT fk_remeslo_item_pref_type FOREIGN KEY (calculator_type_id) REFERENCES remeslo_calculator_types(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
