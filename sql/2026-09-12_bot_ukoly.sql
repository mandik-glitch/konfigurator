-- bot16 2026-09-12
-- Robert (chat): "tabulka botů musí obsahovat mnou zadané ukoly a
-- pravidla které v chatu oznacim jako: ukol na zed" - trvaly "nastenkovy"
-- seznam ukolu/pravidel, ktere Robert v kterekoli chat session oznaci
-- frazi "ukol na zed", aby se neztratily mezi sessions (stejny problem,
-- kvuli kteremu ma tenhle projekt AGENTS_LOG.md - viz CLAUDE.md).
--
-- Samostatna tabulka (ne sloupec v `bots`) - Robert upresnil hned
-- dvakrat v chatu za sebou: "s kompletni historii" a "priradi se jen
-- k tomu spravnemu botovi" - proto bot_id NOT NULL (kazdy ukol MUSI
-- mit prave jednoho bota, api/bots.py navic overuje, ze bot v `bots`
-- opravdu existuje, nez zapis dovoli) a zadny radek se natvrdo
-- nemaze pres UI (jen `hotovo` priznak) - "historii" drzi hlavne
-- existujici log_audit()/#tab-auditlog mechanismus, stejny jako u
-- zbytku administrace, ne vlastni verzovani navic.
--
-- `bot_id` je VOLNY text jako uz v `bots.bot_id` (sql/2026-09-12_bots.sql)
-- - zadny DB-level FK (stejna neformalni konvence jako jinde v projektu),
-- validace existence bota resena v api vrstve.
CREATE TABLE bot_ukoly (
  id INT AUTO_INCREMENT PRIMARY KEY,
  text TEXT NOT NULL,
  bot_id VARCHAR(40) NOT NULL,
  hotovo TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
