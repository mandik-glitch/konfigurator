-- bot16 2026-09-13
-- Robert upresnil: "má zde být výpis uložených souborů záloh z
-- uloziste S3, ne samotne soubory, jen seznam" - puvodni
-- offsite_backup_log (viz 2026-09-13_offsite_backup_log.sql) je log
-- POKUSU o upload, tohle je AKTUALNI SEZNAM souboru, ktere na S3
-- opravdu jsou (zrcadlo `rclone lsjson`, zapisuje daily_backup.py po
-- kazdem uspesnem uploadu - DELETE + znovu-INSERT cele tabulky, at
-- odrazi i pripadne rucni smazani na strane S3, ne jen pridavani).
CREATE TABLE offsite_backup_files (
  soubor VARCHAR(255) NOT NULL PRIMARY KEY,
  velikost_b BIGINT NOT NULL,
  zmeneno_at DATETIME NULL,
  aktualizovano_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
