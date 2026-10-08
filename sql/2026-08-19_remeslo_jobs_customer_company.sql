-- Řemeslo - modul 2 rozšíření: firemní údaje zákazníka (IČO/DIČ/adresa),
-- doplnitelné přes ARES podle IČO (inspirace appkou iDoklad - viz
-- REMESLO_APPKY_VIDEO_SCREENSHOTY.md, živé ARES našeptávání). Znovupoužívá
-- existující veřejný endpoint GET /api/public/ares/<ico> (api/scene_offers.py),
-- žádný nový ARES proxy kód. customer_name zůstává (řemeslník nemusí znát
-- IČO fyzické osoby) - tohle jsou jen VOLITELNÁ doplňková pole.
--
-- Toto NENÍ fakturace/doklad (viz REMESLO_KONCEPT.md - fakturace se
-- záměrně nestaví) - čistě identifikační evidence zákazníka k zakázce.
--
-- Použití: python api/db_migrate.py sql/2026-08-19_remeslo_jobs_customer_company.sql

ALTER TABLE remeslo_jobs
    ADD COLUMN customer_ico VARCHAR(20) NULL AFTER customer_name,
    ADD COLUMN customer_dic VARCHAR(20) NULL AFTER customer_ico,
    ADD COLUMN customer_address VARCHAR(500) NULL AFTER customer_dic;
