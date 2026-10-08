-- Robert 2026-08-11: "nechci ukladat rendery kam nevidim, ale do
-- sdileneho disku, kde je muzu kdykoli smazat" - obrazek renderu zije
-- jako soubor Sdileneho disku (shared_drive_files), tabulka
-- scene_offer_renders na nej jen odkazuje.
ALTER TABLE scene_offer_renders MODIFY stored_filename VARCHAR(255) NULL;
ALTER TABLE scene_offer_renders ADD COLUMN drive_file_id INT NULL AFTER stored_filename
