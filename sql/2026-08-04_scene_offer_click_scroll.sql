-- Rozsireni sledovani online nabidek o kliky a hloubku scrollu (Robert
-- 2026-08-04, navazuje na sql/2026-08-04_scene_offer_online.sql).
-- event_type rozlisuje 2 druhy radku ve stejne tabulce:
--   'page_view' (puvodni chovani, vsechny dosavadni radky) - dwell_ms +
--     ted navic scroll_pct (max dosazeny scroll v ramci navstevy stranky,
--     0-100, NULL kdyz stranka neprtekala/nescrollovalo se).
--   'click' - target popisuje CO bylo kliknuto (nazev z pevneho
--     seznamu na backendu, ne volny text - viz CLICK_TARGETS v
--     api/scene_offers.py), dwell_ms/scroll_pct se u click radku
--     nepouzivaji (zustavaji NULL/0).
ALTER TABLE scene_offer_page_events
  ADD COLUMN event_type VARCHAR(20) NOT NULL DEFAULT 'page_view' AFTER page_key,
  ADD COLUMN target VARCHAR(50) NULL AFTER event_type,
  ADD COLUMN scroll_pct TINYINT NULL AFTER dwell_ms,
  ADD KEY idx_sope_type (event_type);
