-- Řemeslo - vlastní položky navíc (Fáze 2 individualizace kalkulaček) -
-- bot9, 2026-08-20. Viz REMESLO_KONCEPT.md "Vlastní položky navíc —
-- FÁZE 2, NÁVRH + ROVNOU IMPLEMENTACE" (schváleno Robertem přímo).
--
-- Na rozdíl od remeslo_craftsman_coef_defaults (mění ČÍSLO v existujícím
-- vzorci) je tohle NOVÝ ŘÁDEK, který systém vůbec nezná - žádná
-- "systémová hodnota" k porovnání, proto samostatná tabulka, ne
-- rozšíření té stávající.
--
-- Použití: python api/db_migrate_remeslo.py sql/2026-08-20_remeslo_custom_items.sql

CREATE TABLE IF NOT EXISTS remeslo_craftsman_custom_items (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    craftsman_id        INT NOT NULL,
    calculator_type_id  INT NOT NULL,
    nazev               VARCHAR(255) NOT NULL,
    jednotka            VARCHAR(40) NOT NULL,
    is_mandatory        TINYINT NOT NULL DEFAULT 0,
    -- 'fixed'     -> mnozstvi = coef (bez ohledu na velikost zakazky,
    --                napr. "1x sada presnych kotev")
    -- 'per_input' -> mnozstvi = coef * inputs[rule_input_key] *
    --                (1 + rezerva_percent/100). rule_input_key je
    --                libovolny klic z `inputs` AKTUALNI kalkulace
    --                (zadny pevny seznam "na plochu"/"na obvod") -
    --                rule_input_label je jen snapshot popisku pro
    --                citelnost (rule_input_key sam o sobe muze byt
    --                technicky nazev jako "plocha_m2").
    rule_mode           ENUM('fixed','per_input') NOT NULL DEFAULT 'fixed',
    rule_input_key      VARCHAR(80) NULL,
    rule_input_label    VARCHAR(120) NULL,
    coef                DECIMAL(12,4) NOT NULL DEFAULT 1,
    rezerva_percent     DECIMAL(6,2) NOT NULL DEFAULT 0,
    poznamka            VARCHAR(300) NULL,
    -- Nikdy nemazat, jen vypnout - stejna politika jako
    -- remeslo_craftsman_item_prefs. Vypnuti definice neovlivni
    -- kalkulace, kde uz polozka je (maji svuj vlastni snapshot v
    -- remeslo_calculation_items), jen ji prestane nabizet NOVYM.
    active              TINYINT NOT NULL DEFAULT 1,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_remeslo_custom_item_craftsman FOREIGN KEY (craftsman_id) REFERENCES remeslo_craftsmen(id) ON DELETE CASCADE,
    CONSTRAINT fk_remeslo_custom_item_type FOREIGN KEY (calculator_type_id) REFERENCES remeslo_calculator_types(id) ON DELETE CASCADE,
    KEY idx_craftsman_type (craftsman_id, calculator_type_id, active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
