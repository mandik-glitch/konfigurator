-- bot16 2026-09-13
-- Robert (pres bot3): chce v adminu (Přehledy) videt otisk/stav offsite
-- S3 zalohy, at se kvuli tomu nemusi prihlasovat na Contabo. Zapisuje
-- scripts/daily_backup.py (bezi jako root, ma pristup k rclone.conf -
-- viz upload_offsite()) po KAZDEM pokusu o upload (ne jen po uspesnem),
-- at je v prehledu videt i selhani, ne jen posledni uspech. Cte novy
-- GET /api/admin/offsite-backup (api/bots.py nebo vlastni modul).
--
-- remote_objektu_celkem/remote_bytu_celkem = "rclone size" snapshot
-- REMOTE uloziste jako celku (ne jen tehle davky) - zapsany JEN pri
-- uspesnem uploadu (rclone size je dalsi sitovy pozadavek navic, ma
-- smysl jen kdyz uz vime, ze pripojeni funguje).
CREATE TABLE offsite_backup_log (
  id INT AUTO_INCREMENT PRIMARY KEY,
  soubor VARCHAR(255) NOT NULL,
  velikost_b BIGINT NULL,
  remote_cesta VARCHAR(500) NULL,
  stav ENUM('ok','preskoceno','chyba') NOT NULL,
  detail TEXT NULL,
  remote_objektu_celkem INT NULL,
  remote_bytu_celkem BIGINT NULL,
  nahrano_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX idx_offsite_backup_log_nahrano ON offsite_backup_log (nahrano_at);
