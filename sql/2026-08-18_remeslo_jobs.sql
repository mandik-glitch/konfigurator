-- Řemeslo - modul 2 (evidence zakázek řemeslníka) - bot10, 2026-08-18.
-- Viz REMESLO_KONCEPT.md "Modul 2" pro celý kontext/zdůvodnění.
--
-- hours_worked je VOLITELNÉ (jen pro řemeslníky fakturující hodinovkou,
-- ne paušálem/položkově - viz REMESLO_PRUZKUM_WORKFLOW_APPS.md).
-- Foto-dokumentace zakázky (před/po) NENÍ tady - řeší se znovupoužitím
-- api/gallery_items.py (owner_type='remeslo_job'), žádný nový sloupec/
-- tabulka pro to potřeba.
--
-- Použití: python api/db_migrate.py sql/2026-08-18_remeslo_jobs.sql

CREATE TABLE IF NOT EXISTS remeslo_jobs (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    craftsman_id    INT NOT NULL,
    customer_name   VARCHAR(255) NOT NULL,
    description     TEXT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'planovano',
    start_date      DATE NULL,
    due_date        DATE NULL,
    price_czk       DECIMAL(10,2) NULL,
    hours_worked    DECIMAL(6,2) NULL,
    note            TEXT NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_remeslo_jobs_craftsman
        FOREIGN KEY (craftsman_id) REFERENCES remeslo_craftsmen(id),
    KEY idx_craftsman (craftsman_id),
    KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
