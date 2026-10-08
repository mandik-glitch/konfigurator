-- bot16, 2026-09-17
-- Robert (pres bot3): liniovy graf spotreby tokenu v case v admin
-- Prehledy > Boti, vedle stavajici tabulky se sloupcem "Tokeny".
--
-- `bot_token_usage` (viz sql/2026-09-12_bot_token_usage.sql) drzi jen
-- JEDEN kumulativni radek na bota - zadna historie, kazdy sync ho
-- prepisuje. Tahle tabulka je DENNI SNAPSHOT te kumulativni hodnoty -
-- ne novy radek za kazdy beh syncu (ten bezi kazde ~2 min, to by
-- narostlo na stovky radku/den zbytecne), ale UPSERT "dnesniho" radku
-- (PRIMARY KEY bot_id+den) - kazdy dalsi beh stejneho dne prepise
-- hodnotu na aktualnejsi, misledni beh dne tak zustane platny snapshot.
--
-- Cumulative, ne denni delta (rozhodnuti bot16, doporuceno i bot3):
-- jednodussi na vykresleni (sklon primky = tempo spotreby, zadne
-- zaporne hodnoty k reseni), a nemusi resit reset pri restartu session
-- znovu - `bot_token_usage.tokens_total` uz to reseni ma (viz komentar
-- v scripts/2026-09-12_bot_token_usage_sync.py, "PROC DELTY").
CREATE TABLE bot_token_usage_history (
  bot_id VARCHAR(40) NOT NULL,
  den DATE NOT NULL,
  tokens_total_snapshot BIGINT NOT NULL DEFAULT 0,
  cost_usd_total_snapshot DECIMAL(12,4) NOT NULL DEFAULT 0,
  PRIMARY KEY (bot_id, den)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
