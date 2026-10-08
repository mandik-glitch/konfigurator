-- Vratny uklid opustenych remeslo_* tabulek v HLAVNI DB (bot13, 2026-09-02).
--
-- Kontext: Remeslo se presunulo do vlastni DB (REMESLO_DB_*) uz 2026-08-19
-- (viz api/remeslo.py::get_remeslo_conn, api/db_migrate_remeslo.py), ale
-- 30 puvodnich remeslo_* tabulek v hlavni DB nikdy nebylo smazano/
-- prejmenovano - zjisteno jako CRITICAL/info nalez v scripts/qa/
-- db_integrity.py (bot13). Analyza (viz AGENTS_LOG.md tento datum):
--   - zadna z 30 tabulek nema v hlavni DB novejsi data nez odpovidajici
--     tabulka v Remeslo DB (COUNT(*) i MAX(created_at/updated_at)
--     porovnano zive, read-only)
--   - jedina zjistena zivota pouzivana cesta pres hlavni spojeni byla
--     api/system_pipeline.py:227 (dlazdice "Prehled systemu") - OPRAVENO
--     PRED touhle migraci (commit f1489f2, _check_remeslo_module() si
--     ted otevira vlastni spojeni na Remeslo DB)
--   - vsech 30 tabulek jinak pouzivaji jen scraper skripty a api/remeslo.py
--     + pomocne moduly, vsechny overene pres get_remeslo_conn()/REMESLO_DB_*
--
-- RENAME (ne DROP) - nic se nemaze, jen se tabulky odsunou stranou at
-- je jasne, ze jsou mrtve (prefix _zzz_..._20260902, sedi abecedne az
-- na konec SHOW TABLES). Revert viz
-- sql/2026-09-02_remeslo_main_db_rename_REVERT.sql (presny opak, jeden
-- prikaz).

RENAME TABLE
  remeslo_calculation_items TO _zzz_remeslo_calculation_items_20260902,
  remeslo_calculations TO _zzz_remeslo_calculations_20260902,
  remeslo_calculator_types TO _zzz_remeslo_calculator_types_20260902,
  remeslo_collaborators TO _zzz_remeslo_collaborators_20260902,
  remeslo_craftsmen TO _zzz_remeslo_craftsmen_20260902,
  remeslo_finance_transactions TO _zzz_remeslo_finance_transactions_20260902,
  remeslo_invoice_items TO _zzz_remeslo_invoice_items_20260902,
  remeslo_invoices TO _zzz_remeslo_invoices_20260902,
  remeslo_invoicing_settings TO _zzz_remeslo_invoicing_settings_20260902,
  remeslo_job_materials TO _zzz_remeslo_job_materials_20260902,
  remeslo_job_time_entries TO _zzz_remeslo_job_time_entries_20260902,
  remeslo_jobs TO _zzz_remeslo_jobs_20260902,
  remeslo_material_categories TO _zzz_remeslo_material_categories_20260902,
  remeslo_material_category_professions TO _zzz_remeslo_material_category_professions_20260902,
  remeslo_material_prices TO _zzz_remeslo_material_prices_20260902,
  remeslo_numbering_sequences TO _zzz_remeslo_numbering_sequences_20260902,
  remeslo_offer_acceptances TO _zzz_remeslo_offer_acceptances_20260902,
  remeslo_offer_declines TO _zzz_remeslo_offer_declines_20260902,
  remeslo_offer_items TO _zzz_remeslo_offer_items_20260902,
  remeslo_offers TO _zzz_remeslo_offers_20260902,
  remeslo_photo_analyses TO _zzz_remeslo_photo_analyses_20260902,
  remeslo_price_sources TO _zzz_remeslo_price_sources_20260902,
  remeslo_pricelist_categories TO _zzz_remeslo_pricelist_categories_20260902,
  remeslo_pricelist_item_price_history TO _zzz_remeslo_pricelist_item_price_history_20260902,
  remeslo_pricelist_items TO _zzz_remeslo_pricelist_items_20260902,
  remeslo_professions TO _zzz_remeslo_professions_20260902,
  remeslo_voice_notes TO _zzz_remeslo_voice_notes_20260902,
  remeslo_workflow_app_features TO _zzz_remeslo_workflow_app_features_20260902,
  remeslo_workflow_apps TO _zzz_remeslo_workflow_apps_20260902,
  remeslo_workflow_features TO _zzz_remeslo_workflow_features_20260902;
