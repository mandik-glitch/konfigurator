-- Řemeslo - Modul 9 (Kalkulačky + Ceník), ČÁST 2: Kalkulačky - bot11, 2026-08-19.
-- Viz REMESLO_KONCEPT.md "Modul 9" sekce "Kalkulačky - schéma" pro plné
-- zdůvodnění (schváleno bot3/Robertem před implementací). Ceník (část 1,
-- sql/2026-08-19_remeslo_pricelist.sql) musí být aplikovaný první -
-- remeslo_calculation_items odkazuje na remeslo_pricelist_items.
--
-- Revize kalkulace = nová řádka s vyplněným parent_calculation_id
-- (řetěz, ne verzovací sloupec). Položky/vrstvy kalkulace mají SNAPSHOT
-- názvu i ceny v okamžiku přidání (nazev/cena_jednotka_czk) - stará
-- kalkulace se nesmí tiše přepočítat, když se později změní Ceník.
--
-- FAKTURACE/DOKLADY SE NESTAVÍ - kalkulačky počítají MNOŽSTVÍ a
-- orientační NÁKUPNÍ cenu materiálu pro vlastní potřebu řemeslníka.
--
-- Použití: python api/db_migrate.py sql/2026-08-19_remeslo_calculators.sql

CREATE TABLE IF NOT EXISTS remeslo_calculator_types (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    code        VARCHAR(50) NOT NULL,
    name        VARCHAR(255) NOT NULL,
    is_system   TINYINT NOT NULL DEFAULT 1,
    UNIQUE KEY uq_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS remeslo_calculations (
    id                      INT AUTO_INCREMENT PRIMARY KEY,
    calculator_type_id     INT NOT NULL,
    craftsman_id            INT NOT NULL,
    job_id                  INT NULL,
    parent_calculation_id  INT NULL,
    name                    VARCHAR(255) NOT NULL,
    status                  VARCHAR(20) NOT NULL DEFAULT 'koncept',
    author_user_id          INT NOT NULL,
    inputs_json             JSON NULL,
    created_at               DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at               DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_remeslo_calc_type
        FOREIGN KEY (calculator_type_id) REFERENCES remeslo_calculator_types(id),
    CONSTRAINT fk_remeslo_calc_craftsman
        FOREIGN KEY (craftsman_id) REFERENCES remeslo_craftsmen(id),
    CONSTRAINT fk_remeslo_calc_job
        FOREIGN KEY (job_id) REFERENCES remeslo_jobs(id) ON DELETE SET NULL,
    CONSTRAINT fk_remeslo_calc_parent
        FOREIGN KEY (parent_calculation_id) REFERENCES remeslo_calculations(id) ON DELETE CASCADE,
    KEY idx_craftsman (craftsman_id),
    KEY idx_parent (parent_calculation_id),
    KEY idx_job (job_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS remeslo_calculation_items (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    calculation_id      INT NOT NULL,
    pricelist_item_id   INT NULL,
    nazev               VARCHAR(255) NOT NULL,
    mnozstvi             DECIMAL(10,2) NOT NULL,
    jednotka             VARCHAR(20) NULL,
    cena_jednotka_czk   DECIMAL(10,2) NULL,
    is_mandatory        TINYINT NOT NULL DEFAULT 0,
    is_used              TINYINT NOT NULL DEFAULT 1,
    sort_order           INT NOT NULL DEFAULT 0,
    CONSTRAINT fk_remeslo_calc_items_calc
        FOREIGN KEY (calculation_id) REFERENCES remeslo_calculations(id) ON DELETE CASCADE,
    CONSTRAINT fk_remeslo_calc_items_pricelist
        FOREIGN KEY (pricelist_item_id) REFERENCES remeslo_pricelist_items(id) ON DELETE SET NULL,
    KEY idx_calculation (calculation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Seed: vsech 9 systemovych typu + univerzalni kalkulacka. Jen
-- 'zamkova_dlazba' ma v teto fazi vlastni vypocetni funkci
-- (_calc_zamkova_dlazba v api/remeslo.py) - zbyle typy existuji uz
-- ted v tabulce (pro stabilni FK/vyber v UI), vypocetni funkce
-- pribudou v dalsich kolech (viz REMESLO_KONCEPT.md "Pořadí implementace").
-- INSERT IGNORE + UNIQUE KEY uq_code = idempotentni bez fragilniho
-- "UNION ALL ... WHERE NOT EXISTS" vzoru (ten pouziva derived-table
-- sloupce bez aliasu na vetsine vetvi, coz u dvojice 'podlahy'/'Podlahy'
-- spadlo na "Duplicate column name" - MySQL derived-table nazvy
-- sloupcu jsou case-insensitive).
INSERT IGNORE INTO remeslo_calculator_types (code, name, is_system) VALUES
    ('zamkova_dlazba', 'Zámková dlažba', 1),
    ('obklady_dlazby', 'Obklady a dlažby', 1),
    ('malovani', 'Malování', 1),
    ('sadrokarton', 'Sádrokarton', 1),
    ('podlahy', 'Podlahy', 1),
    ('fasada_zatepleni', 'Fasáda a zateplení', 1),
    ('betonaz', 'Betonáž', 1),
    ('zemni_prace', 'Zemní práce', 1),
    ('univerzalni', 'Univerzální kalkulace', 1);
