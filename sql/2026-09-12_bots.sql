-- bot16 2026-09-12
-- Robert: "musime ustálit boty, každý bude mít svou specializaci" +
-- "editovatelná tabulka botů, včetně jejich popisu práce" - první
-- tabulka v nové sekci "Přehledy" administrace.
--
-- Vedomě SAMOSTATNÁ nová tabulka, ne rozšíření `bot_handover`
-- (sql/2026-09-02_bot_handover.sql) - ten je LOG jednotlivých
-- předávek/úkolů (řádek na událost, napříč všemi 6 projekty na VPS),
-- tenhle je REGISTR (jeden řádek na bota, aktuální stav specializace,
-- ručně udržovaný). Různý účel, různý tvar dat.
--
-- `bot_id` je ta neformální nálepka používaná už dnes v BOT_ID env
-- proměnné pro git commity a v `scripts/lock.sh` (viz WORKFLOW.md) -
-- boti dosud NEMĚLI žádný záznam v DB (žádná role v `app_users`,
-- žádná tabulka je neevidovala). Tahle tabulka je první místo, kde
-- "bot3"/"bot16"/... dostává vlastní řádek.
CREATE TABLE bots (
  id INT AUTO_INCREMENT PRIMARY KEY,
  bot_id VARCHAR(40) NOT NULL,
  specializace TEXT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_bots_bot_id (bot_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
