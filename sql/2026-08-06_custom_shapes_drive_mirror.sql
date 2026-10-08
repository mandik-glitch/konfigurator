-- Zrcadleni JEDNOTLIVYCH tvaru (custom_shapes) do Sdileneho disku, nejen
-- kategorii jako slozek (viz 2026-08-06_custom_shape_categories_drive_mirror.sql).
--
-- Robert 2026-08-06 (screenshot + "ve scene toho synchronizovaneho stromu
-- s tim ve sdilenem disku jsou nasledujici soubory"): ocekava, ze kazdy
-- tvar viditelny ve stromu "Vlastni tvary" ve scene ma zrcadlenej odpovidajici
-- SOUBOR v parove slozce na Sdilenem disku - ne jen prazdnou slozku.
-- Dosavadni mirror (2026-08-06_custom_shape_categories_drive_mirror.sql)
-- zrcadlil jen STRUKTURU slozek, nikdy obsah - proto byla "Nohy FBX 349"
-- prazdna i kdyz tvary uvnitr existuji.
--
-- drive_file_id: parovy radek v shared_drive_files (JSON export dat tvaru,
-- stazitelny z administrace stejne jako kterykoli jiny soubor na disku).
-- ON DELETE SET NULL - smazani souboru na Sdilenem disku rucne admin-em
-- tvar samotny neznici (jen prijde o zrcadleny soubor, dopocita se znovu
-- pri dalsi zmene).
ALTER TABLE custom_shapes
  ADD COLUMN drive_file_id INT NULL AFTER category_id,
  ADD CONSTRAINT fk_cs_drive_file FOREIGN KEY (drive_file_id) REFERENCES shared_drive_files(id) ON DELETE SET NULL;
