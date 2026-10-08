-- Řemeslo split (bot14, 2026-09-03, nález bot5 v journalu): fk_crm_leads_craftsman
-- (viz sql/2026-08-19_crm_leads_craftsman.sql) odkazovala PŮVODNĚ na
-- remeslo_craftsmen(id), platné, dokud tahle tabulka žila v HLAVNÍ DB.
-- Po přesunu skutečných dat řemeslníků do REMESLO_DB (samostatná
-- databáze) byla stará tabulka v hlavní DB přejmenována na archiv
-- _zzz_remeslo_craftsmen_20260902 (1 zbytkový řádek) - FK constraint
-- "táhla" přejmenování s sebou a teď ukazuje na archivovanou tabulku.
--
-- Důsledek: JAKÝKOLI reálný craftsman_id z Řemesla (žije výhradně v
-- REMESLO_DB.remeslo_craftsmen) spolehlivě selže na FK constraint při
-- INSERT do crm_leads (1452 IntegrityError) - zjištěno bot5 v žívém
-- journalu, POST /api/internal/crm-leads (crm_internal_lead_create)
-- selhával VŽDY, tiše (volání z Řemesla je best-effort/non-blocking na
-- jejich straně, takže to vypadalo jako úspěch). Ověřeno: 0 řádků
-- crm_leads.source='remeslo' existovalo v okamžiku nálezu.
--
-- Oprava: FK constraint pryč (craftsman_id teď odkazuje do JINÉ fyzické
-- databáze, cross-DB FK v rámci jednoho MySQL constraintu nedává smysl
-- a stejně by ho MySQL nedovolil, kdyby REMESLO_DB nebyla na stejném
-- serveru). Index idx_craftsman a samotný sloupec ZŮSTÁVAJÍ (pořád
-- užitečné pro filtrování/dotazy, viz crm_admin_leads_list). Validaci
-- "existuje tenhle craftsman_id opravdu v Řemeslu" (pokud vůbec
-- potřeba) by musela dělat aplikační vrstva, ne DB FK - Řemeslo je teď
-- oddělený projekt/DB.
--
-- Použití: python api/db_migrate.py sql/2026-09-03_crm_leads_craftsman_fk_drop.sql

ALTER TABLE crm_leads
    DROP FOREIGN KEY fk_crm_leads_craftsman;
