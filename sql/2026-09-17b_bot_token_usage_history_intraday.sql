-- bot16, 2026-09-17 (Robert pres bot3, po prvnim zivem screenshotu grafu)
-- Puvodni bot_token_usage_history (sql/2026-09-17_bot_token_usage_
-- history.sql, PK bot_id+den DATE) delala jen JEDEN prepisovany radek
-- za den - graf pak mel jen 1 tecku na bota za dnesek, plochou caru,
-- zadny vnitrodenni pohyb. Robert chce meritka 5min az 1 mesic +
-- "aktualizaci kazdych 5 minut" - reseno radkem za KAZDY beh syncu
-- (~2min timer, jemnejsi nez pozadovanych 5 min "zadarmo").
--
-- Puvodni tabulka mela v tuhle chvili jen par hodin dat (7 radku,
-- vznikla ten samy den) - zahodit je bezpecne, DROP+CREATE misto
-- slozite migrace mala hodnoty dat na novy tvar PK.
DROP TABLE IF EXISTS bot_token_usage_history;
CREATE TABLE bot_token_usage_history (
  bot_id VARCHAR(40) NOT NULL,
  ts DATETIME NOT NULL,
  tokens_total_snapshot BIGINT NOT NULL DEFAULT 0,
  cost_usd_total_snapshot DECIMAL(12,4) NOT NULL DEFAULT 0,
  PRIMARY KEY (bot_id, ts)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX idx_bot_token_usage_history_ts ON bot_token_usage_history (ts);
