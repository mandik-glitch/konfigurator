-- Řemeslo - modul 2 rozšíření: náklady na zakázku (finanční dashboard,
-- viz REMESLO_PRUZKUM_WORKFLOW_APPS.md sekce C - detailní rozbor
-- PROFIDAT). Profit/marže/Kč-hod se NEUKLÁDAJÍ - počítají se za běhu
-- v SQL z price_czk/costs_czk/hours_worked (čistá funkce, žádný důvod
-- duplikovat stav).
--
-- Použití: python api/db_migrate.py sql/2026-08-18_remeslo_jobs_costs.sql

ALTER TABLE remeslo_jobs
    ADD COLUMN costs_czk DECIMAL(10,2) NULL AFTER price_czk;
