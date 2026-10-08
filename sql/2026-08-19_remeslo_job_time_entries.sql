-- Řemeslo - modul 2 rozšíření: itemizovaný "work log" (průběžné
-- záznamy odpracovaného času na zakázce), bot11, 2026-08-19, na
-- zadání Roberta přes bot3 - inspirace appkou PROFIDAT (viz
-- REMESLO_PRUZKUM_WORKFLOW_APPS.md sekce C): "workLogHours" - během
-- práce na zakázce (ne až na konci) se přidávají dílčí záznamy s
-- odpracovanými hodinami, systém je průběžně sčítá. Žádná jiná
-- zkoumaná appka (mezinárodní ani česká) tohle nemá takhle explicitně.
--
-- Stejný vzor jako sql/2026-08-19_remeslo_job_materials.sql (jen čas
-- místo materiálu) - remeslo_jobs.hours_worked se AUTOMATICKY
-- přepočítává součtem záznamů, jakmile aspoň jeden existuje (viz
-- api/remeslo.py _recalc_job_hours) - jedna cesta pravdy.
--
-- FAKTURACE/DOKLADY SE NESTAVÍ (Robert, 2026-08-19, REMESLO_KONCEPT.md)
-- - čistě INTERNÍ evidence odpracovaného času, ne fakturační podklad
-- (žádná hodinová sazba/cena tady, jen hodiny).
--
-- ON DELETE CASCADE na job_id - záznam práce nemá smysl nezávislý na
-- zakázce (stejné zdůvodnění jako u remeslo_job_materials).
--
-- Použití: python api/db_migrate.py sql/2026-08-19_remeslo_job_time_entries.sql

CREATE TABLE IF NOT EXISTS remeslo_job_time_entries (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    job_id      INT NOT NULL,
    datum       DATE NOT NULL,
    popis       VARCHAR(255) NULL,
    hodiny      DECIMAL(5,2) NOT NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_remeslo_job_time_entries_job
        FOREIGN KEY (job_id) REFERENCES remeslo_jobs(id) ON DELETE CASCADE,
    KEY idx_job (job_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
