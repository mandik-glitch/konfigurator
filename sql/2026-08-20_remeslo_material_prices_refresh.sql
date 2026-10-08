-- Modul 1 (bot10, 2026-08-20) - REMESLO_KONCEPT.md "Obnova cen - dve
-- URL cesty s oddelenou politikou aktualizace" (TRVALE PRAVIDLO,
-- Robert). Cena na vyzadani: obnovuje se JEN price_source_url
-- (levne, per polozka), product_url (drahe dohledavani) se resi jen
-- pri chybe. last_requested_at rizeni prioritu obnovy na pozadi
-- (nejcasteji dotazovane + nejstarsi napred), last_refresh_attempt_at
-- na remeslo_price_sources drzi per-dodavatel cooldown, at obnova
-- jednu polozky nezpusobi navalu pozadavku na stejny server.

SET SESSION lock_wait_timeout = 10;

ALTER TABLE remeslo_material_prices
  ADD COLUMN price_source_url VARCHAR(500) NULL AFTER product_url,
  ADD COLUMN last_requested_at DATETIME NULL AFTER scraped_at;

-- Backfill: dokud nemame overeny odlehceny zdroj (viz tabulka stavu v
-- REMESLO_KONCEPT.md), price_source_url = product_url - stejna URL,
-- jen priznane slabsi mechanismus (zapsano tam, ne tise predstirano).
UPDATE remeslo_material_prices SET price_source_url = product_url WHERE price_source_url IS NULL;

ALTER TABLE remeslo_price_sources
  ADD COLUMN last_refresh_attempt_at DATETIME NULL AFTER created_at;
