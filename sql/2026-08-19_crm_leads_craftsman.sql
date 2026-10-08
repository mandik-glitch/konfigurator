-- Řemeslo - modul 3 (bot11, 2026-08-19, na zadání Roberta přes bot3):
-- Jednoduché CRM - viz REMESLO_KONCEPT.md "Modul 3 — Jednoduché CRM",
-- Robertovo výslovné zadání: znovupoužít stávající crm_leads, NE
-- stavět paralelní systém. NULL = původní význam (náš vlastní
-- e-shopový lead, beze změny chování stávajícího kódu). Vyplněné =
-- lead patří KONKRÉTNÍMU řemeslníkovi jako JEHO vlastní "mini-CRM"
-- záznam, ne náš.
--
-- ON DELETE SET NULL - smazání řemeslníka nemá smazat lead, jen ho
-- odpojit (stejný princip jako remeslo_jobs.collaborator_id).
--
-- Použití: python api/db_migrate.py sql/2026-08-19_crm_leads_craftsman.sql

ALTER TABLE crm_leads
    ADD COLUMN craftsman_id INT NULL AFTER customer_id,
    ADD CONSTRAINT fk_crm_leads_craftsman
        FOREIGN KEY (craftsman_id) REFERENCES remeslo_craftsmen(id) ON DELETE SET NULL,
    ADD KEY idx_craftsman (craftsman_id);
