-- Předávací zápisník flotily botů (scripts/handover.py). Jeden řádek = jedno téma jednoho bota.
CREATE TABLE IF NOT EXISTS bot_handover (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  bot VARCHAR(32) NOT NULL,
  project VARCHAR(64) NOT NULL,
  topic VARCHAR(160) NOT NULL,
  status ENUM('open','done','blocked','info') NOT NULL DEFAULT 'open',
  body MEDIUMTEXT NOT NULL,
  KEY ix_project_status (project, status),
  KEY ix_bot (bot)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
