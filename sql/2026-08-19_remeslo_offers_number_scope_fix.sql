-- Řemeslo - oprava reálného bugu nalezeného vlastním testováním (bot13,
-- 2026-08-19): remeslo_offers.number měl GLOBÁLNÍ UNIQUE constraint,
-- ale číselná řada (remeslo_numbering_sequences) je per-craftsman se
-- SDÍLENÝM výchozím prefixem ("NAB"/"FAK") - dva různí řemeslníci bez
-- vlastního přizpůsobení prefixu tak nevyhnutelně kolidují na prvním
-- vlastním čísle ("NAB-2026-0001" pro oba), druhý dostane
-- IntegrityError při vytvoření nabídky. Číslo dokladu má být unikátní
-- jen V RÁMCI JEDNOHO řemeslníka (nezávislé číselné řady per firma,
-- přesně jak je řada navržená v REMESLO_KONCEPT.md modul 8b), ne
-- napříč celou platformou.
--
-- Použití: python api/db_migrate.py sql/2026-08-19_remeslo_offers_number_scope_fix.sql

ALTER TABLE remeslo_offers
    DROP INDEX uq_number,
    ADD UNIQUE KEY uq_craftsman_number (craftsman_id, number);
