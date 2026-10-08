-- Řemeslo - pilot modulu 1 (srovnávač cen materiálu, dle profese) -
-- bot10, 2026-08-17. Viz REMESLO_KONCEPT.md pro celý kontext/zdůvodnění
-- (Robert, přes bot3: priorita č.1 ze všech modulů Řemesla, pilotní
-- profese = instalatér/voda-topení, zdroj dat na start = pilotní
-- scraping + ruční zadání, NE AI-crowdsourcing z faktur - ten je
-- odložen na později).
--
-- Minimální jádro databáze řemeslníků (jen sloupce, které modul 1
-- potřebuje - profese, poloha pro vzdálenost) + materiálová/cenová
-- data. Materiál je JEDNA sdílená tabulka BEZ profession_id sloupce -
-- profese je filtr přes M:N vazební tabulku
-- (remeslo_material_category_professions), NE duplicitní kopie dat
-- pro každou profesi (Robert: "hodně materiálu se prolíná napříč
-- profesemi... nesmí se to duplikovat v DB").
--
-- Číslování řemeslníka: prefix podle profese, řada od 0001 ZVLÁŠŤ
-- pro každý prefix (Robert) - `remeslo_professions.next_seq` +
-- `SELECT ... FOR UPDATE` v api/remeslo.py přiřazuje kód atomicky.
--
-- Použití: python api/db_migrate.py sql/2026-08-17_remeslo_pricing_pilot.sql

CREATE TABLE IF NOT EXISTS remeslo_professions (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(100) NOT NULL UNIQUE,
    slug          VARCHAR(100) NOT NULL UNIQUE,
    code_prefix   VARCHAR(10) NOT NULL UNIQUE,
    next_seq      INT NOT NULL DEFAULT 1,
    active        TINYINT(1) NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS remeslo_craftsmen (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    code            VARCHAR(20) NOT NULL UNIQUE,
    name            VARCHAR(255) NOT NULL,
    company_name    VARCHAR(255) NULL,
    profession_id   INT NOT NULL,
    address         TEXT NULL,
    city            VARCHAR(255) NULL,
    zip_code        VARCHAR(10) NULL,
    latitude        DECIMAL(10,7) NULL,
    longitude       DECIMAL(10,7) NULL,
    email           VARCHAR(255) NULL,
    phone           VARCHAR(50) NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'candidate',
    note            TEXT NULL,
    active          TINYINT(1) NOT NULL DEFAULT 1,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_remeslo_craftsmen_profession
        FOREIGN KEY (profession_id) REFERENCES remeslo_professions(id),
    KEY idx_profession (profession_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS remeslo_material_categories (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    unit            VARCHAR(20) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS remeslo_material_category_professions (
    category_id     INT NOT NULL,
    profession_id   INT NOT NULL,
    PRIMARY KEY (category_id, profession_id),
    CONSTRAINT fk_remeslo_mcp_category
        FOREIGN KEY (category_id) REFERENCES remeslo_material_categories(id) ON DELETE CASCADE,
    CONSTRAINT fk_remeslo_mcp_profession
        FOREIGN KEY (profession_id) REFERENCES remeslo_professions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS remeslo_price_sources (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    supplier_name   VARCHAR(255) NOT NULL UNIQUE,
    website         VARCHAR(255) NULL,
    address         TEXT NULL,
    latitude        DECIMAL(10,7) NULL,
    longitude       DECIMAL(10,7) NULL,
    origin          VARCHAR(20) NOT NULL DEFAULT 'scrape_pilot',
    scrape_config   JSON NULL,
    active          TINYINT(1) NOT NULL DEFAULT 1,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS remeslo_material_prices (
    id                           INT AUTO_INCREMENT PRIMARY KEY,
    category_id                  INT NOT NULL,
    source_id                    INT NOT NULL,
    product_name                 VARCHAR(255) NOT NULL,
    price_czk                    DECIMAL(10,2) NOT NULL,
    product_url                  VARCHAR(500) NULL,
    contributed_by_craftsman_id  INT NULL,
    source_photo_analysis_id     INT NULL,
    scraped_at                   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_remeslo_mp_category
        FOREIGN KEY (category_id) REFERENCES remeslo_material_categories(id) ON DELETE CASCADE,
    CONSTRAINT fk_remeslo_mp_source
        FOREIGN KEY (source_id) REFERENCES remeslo_price_sources(id) ON DELETE CASCADE,
    CONSTRAINT fk_remeslo_mp_craftsman
        FOREIGN KEY (contributed_by_craftsman_id) REFERENCES remeslo_craftsmen(id) ON DELETE SET NULL,
    KEY idx_category (category_id),
    KEY idx_source (source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Pilotní profese (Robert, přes bot3, 2026-08-17): instalatér (voda/topení).
INSERT INTO remeslo_professions (name, slug, code_prefix, next_seq)
VALUES ('Instalatér (voda, topení)', 'instalater', 'INST', 1)
ON DUPLICATE KEY UPDATE name=VALUES(name);

-- 2 kurátorovaně vybraní dodavatelé (kritéria viz REMESLO_KONCEPT.md
-- Modul 1: velikost firmy, celostátní dosah, strukturovaný veřejný
-- ceník, relevance k instalatérské profesi, šíře sortimentu) -
-- ověřeno živě (WebSearch/WebFetch, 2026-08-17), oba mají veřejně
-- viditelné ceny bez přihlášení:
--   - Ptáček-shop.cz - retail e-shop největšího velkoobchodu voda/
--     topení/plyn v ČR+SR (140+ poboček/instalatércenter, mateřská
--     firma Ptáček - velkoobchod, a.s.), tisíce položek skladem.
--   - Aquatopshop.cz - specializovaný e-shop voda/topení/plyn,
--     18 let v oboru, 5000+ položek, veřejné ceny (ověřeno na PPR
--     trubkách - 31 Kč s DPH).
-- website/address/lat/lon se doplní/zpřesní ve scraper skriptu -
-- tady jen základní založení zdroje.
INSERT INTO remeslo_price_sources (supplier_name, website, origin)
VALUES
    ('Ptáček-shop.cz', 'https://www.ptacek-shop.cz/', 'scrape_pilot'),
    ('Aquatopshop.cz', 'https://www.aquatopshop.cz/', 'scrape_pilot')
ON DUPLICATE KEY UPDATE website=VALUES(website);
