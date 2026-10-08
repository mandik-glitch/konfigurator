-- Řemeslo - "Dohledání položky na vyžádání" (Modul 1, bot9, 2026-08-20).
-- Robert: "každý registrovaný si může přidat položky ke srovnání, které
-- tam nemáme, a my mu je automaticky doplníme - databáze poroste podle
-- skutečné poptávky, ne podle našeho odhadu." Zpracování je VEČERNÍ
-- DÁVKA spouštěná ručně z terminálu (ne cron, ne worker na pozadí,
-- žádné externí vyhledávací API) - viz REMESLO_KONCEPT.md.
--
-- Použití: python api/db_migrate_remeslo.py sql/2026-08-20_remeslo_material_requests.sql

CREATE TABLE IF NOT EXISTS remeslo_material_requests (
    id                    INT AUTO_INCREMENT PRIMARY KEY,
    craftsman_id          INT NOT NULL,
    requested_name        VARCHAR(255) NOT NULL,
    unit                  VARCHAR(20) NOT NULL,
    poznamka              VARCHAR(300) NULL,
    -- pending = ceka na vecerni davku, done = nalezeno aspon u 1
    -- dodavatele (i castecne pokryti se publikuje - viz Robert),
    -- not_found = davka probehla, nikde se nenaslo.
    status                ENUM('pending','done','not_found') NOT NULL DEFAULT 'pending',
    matched_category_id   INT NULL,
    suppliers_tried       INT NULL,
    suppliers_found       INT NULL,
    batch_note            VARCHAR(500) NULL,
    created_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at          DATETIME NULL,
    CONSTRAINT fk_remeslo_material_request_craftsman
        FOREIGN KEY (craftsman_id) REFERENCES remeslo_craftsmen(id) ON DELETE CASCADE,
    CONSTRAINT fk_remeslo_material_request_category
        FOREIGN KEY (matched_category_id) REFERENCES remeslo_material_categories(id) ON DELETE SET NULL,
    KEY idx_craftsman (craftsman_id),
    KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
