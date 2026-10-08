-- bot16, 2026-09-17
-- Robert (primo, Prehledy > Boti): sloupec "skutecne aktualni model a
-- effort" - stejny duch jako "Tokeny" (skutecna hodnota z OTel, ne
-- odhad/self-report). Zdroj: stejny scrape jako
-- scripts/2026-09-12_bot_token_usage_sync.py, konkretne radky s
-- `query_source="main"` (hlavni konverzacni smycka bota, ne
-- subagenti/auxiliary) - viz "PROC JEN main" v komentari sync skriptu.
--
-- Ulozeno primo na `bots` (ne samostatna tabulka) - stejna kategorie
-- dat jako `aktualni_cinnost`/`aktualni_soubor` (živý stav jednoho
-- bota, ne historie). `current_model_updated_at` je VLASTNI razitko
-- (ne spolehnuti na `bots.updated_at`, ten uz bezi kvuli
-- /api/bots/checkin prakticky nepretrzite pro kazdy aktivni bot a
-- neznamenal by nic specifickeho o modelu).
ALTER TABLE bots
  ADD COLUMN current_model VARCHAR(80) NULL AFTER proces_checked_at,
  ADD COLUMN current_effort VARCHAR(20) NULL AFTER current_model,
  ADD COLUMN current_model_updated_at DATETIME NULL AFTER current_effort;
