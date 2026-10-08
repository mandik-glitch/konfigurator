-- Řemeslo Srovnávač - vzdálenost k NEJBLIŽŠÍ pobočce místo k sídlu
-- (Robert 2026-08-20, návazný úkol na bot13in audit vzdálenostního
-- filtru - "vzdálenost k sídlu je pro řetězce jako DEK/OBI/Hornbach
-- zavádějící, mají desítky poboček po celé ČR").
--
-- Jen 3 dodavatelé jsou skutečné celostátní řetězce s víc pobočkami
-- (DEK.cz, OBI.cz, HORNBACH.cz) - proto se plní jen pro ně. Zbylých
-- 5 dodavatelů (HECKL, Aquatopshop.cz, TZBeshop.cz, Ptáček-shop.cz,
-- Mereo.cz) žádné řádky nemají a chovají se v distance calc přesně
-- jako dnes (fallback na remeslo_price_sources.latitude/longitude).
--
-- Naplňuje `scripts/2026-08-20_remeslo_supplier_branches_import.py`
-- (DEK.cz a OBI.cz automatizovaně z jejich vlastních webů, HORNBACH.cz
-- ručně kurátorovaný seznam - jejich web blokuje i headless Playwright
-- stejnou bot-challenge stránkou jako u vyhledávání cen, viz
-- api/remeslo_price_search.py). Import je SAMOSTATNÝ re-spustitelný
-- skript mimo živou cestu /compare - pobočky se otvírají řádově
-- jednou za rok, žádný pravidelný cron pro v1 není potřeba.
CREATE TABLE IF NOT EXISTS remeslo_supplier_branches (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_id INT NOT NULL,
    branch_name VARCHAR(255) NOT NULL,
    address VARCHAR(255),
    city VARCHAR(255),
    latitude DECIMAL(10,7) NOT NULL,
    longitude DECIMAL(10,7) NOT NULL,
    origin VARCHAR(20) NOT NULL, -- 'own_site_scrape' | 'manual_curated'
    active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_remeslo_supplier_branches_source
        FOREIGN KEY (source_id) REFERENCES remeslo_price_sources(id),
    INDEX idx_remeslo_supplier_branches_source (source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
