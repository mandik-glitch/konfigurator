-- bot16 2026-09-12
-- Robert (pres bot3): sloupec "Tokeny" v administraci (Přehledy > Boti)
-- se skutečnou spotřebou tokenů/nákladů botů. Viz /opt/bot-telemetry
-- (otel-collector, běží od 2026-09-12) a
-- scripts/2026-09-12_bot_token_usage_sync.py. Skutečná data začnou
-- chodit až po cutover 2026-09-16 22:00 (viz
-- /opt/bot-telemetry/RUNBOOK_CUTOVER.md) - do té doby tabulka existuje,
-- ale zůstává prázdná/nulová (žádná bot session ještě neposílá metriky).
--
-- `bot_token_usage` - agregovany kumulativni soucet za bota (co cte
-- admin Boti tabulka). `bot_token_usage_series` - pomocna tabulka pro
-- SPRAVNY vypocet delt pres restarty session (Prometheus Counter po
-- restartu klesne na 0 - bez sledovani "posledni videne hodnoty" per
-- konkretni casova rada by naivni prepis bud ztratil historii, nebo
-- zapocital zaporne delty). `series_key` je CELY radek popisku z
-- Prometheus expozice (nazev metriky + vsechny labely) - robustni vuci
-- tomu, ze presny label-set (model, dalsi dimenze) nebyl pri navrhu
-- jeste znamy (zadna bot session jeste nic neposilala).
CREATE TABLE bot_token_usage (
  bot_id VARCHAR(40) NOT NULL PRIMARY KEY,
  tokens_total BIGINT NOT NULL DEFAULT 0,
  cost_usd_total DECIMAL(12,4) NOT NULL DEFAULT 0,
  last_synced_at DATETIME NULL,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE bot_token_usage_series (
  series_key VARCHAR(191) NOT NULL PRIMARY KEY,
  bot_id VARCHAR(40) NOT NULL,
  metric VARCHAR(20) NOT NULL,  -- "tokens" nebo "cost"
  last_seen_value DECIMAL(20,4) NOT NULL DEFAULT 0,
  last_seen_at DATETIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX idx_bot_token_usage_series_bot ON bot_token_usage_series (bot_id);
