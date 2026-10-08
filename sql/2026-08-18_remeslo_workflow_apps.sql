-- Řemeslo - srovnávač appek pro řízení denní práce řemeslníka.
-- Robert (přes bot3): strategický posun - první služba Řemesla je
-- srovnávač EXISTUJÍCÍCH appek, ne další appka do konkurence.
-- Viz REMESLO_APPKY_SROVNANI.md (sloučený podklad ze 3 průzkumů).
--
-- M:N vazba appka<->funkce, stejný vzor jako
-- remeslo_material_category_professions. ZJEDNODUŠENÍ (schváleno):
-- existence řádku v remeslo_workflow_app_features = funkce POTVRZENA
-- průzkumem; chybějící řádek = "nemá NEBO neověřeno" (2 stavy, ne 3).
--
-- Použití: python api/db_migrate.py sql/2026-08-18_remeslo_workflow_apps.sql

CREATE TABLE IF NOT EXISTS remeslo_workflow_apps (
    id                     INT AUTO_INCREMENT PRIMARY KEY,
    name                   VARCHAR(255) NOT NULL,
    publisher              VARCHAR(255) NULL,
    category               VARCHAR(30) NOT NULL,
    play_store_package     VARCHAR(255) NULL UNIQUE,
    app_store_id           VARCHAR(50) NULL UNIQUE,
    rating_play            DECIMAL(3,2) NULL,
    rating_count_play      INT NULL,
    rating_appstore        DECIMAL(3,2) NULL,
    rating_count_appstore  INT NULL,
    price_note             TEXT NULL,
    target_audience_note   TEXT NULL,
    language_cs            TINYINT(1) NOT NULL DEFAULT 0,
    not_found_on_stores    TINYINT(1) NOT NULL DEFAULT 0,
    source_doc             VARCHAR(255) NULL,
    researched_at          DATE NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS remeslo_workflow_features (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    slug       VARCHAR(50) NOT NULL UNIQUE,
    name       VARCHAR(255) NOT NULL,
    sort_order INT NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS remeslo_workflow_app_features (
    app_id     INT NOT NULL,
    feature_id INT NOT NULL,
    PRIMARY KEY (app_id, feature_id),
    CONSTRAINT fk_rwaf_app FOREIGN KEY (app_id) REFERENCES remeslo_workflow_apps(id) ON DELETE CASCADE,
    CONSTRAINT fk_rwaf_feature FOREIGN KEY (feature_id) REFERENCES remeslo_workflow_features(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
