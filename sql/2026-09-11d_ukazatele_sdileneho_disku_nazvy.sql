-- Doplneni NAZVU k ukazatelum na Sdileny disk (bot9, 2026-09-11, pres bot8).
--
-- Nastaveni `render_template_file_id` / `render_hdri_file_id` drzela jen
-- `id` radku v `shared_drive_files`. Robert pri kazde uprave soubor SMAZE
-- a nahraje novy, takze ukazatel visel do prazdna a render TISE spadl na
-- vestavene vychozi hodnoty (2026-09-10 dvakrat za vecer: 1784 -> 2058 ->
-- 2064). Nove se vedle id uklada i nazev a podle nej se soubor dohleda -
-- viz api/shared_drive_pointer.py.
--
-- Tahle migrace jen BACKFILLUJE nazvy k hodnotam, ktere uz v nastaveni
-- jsou (zapsal je clovek/skript, ne setter). Dal je udrzuje kod.
-- Idempotentni: kdyz ukazatel neexistuje nebo uz nazev ma, nic se nestane.
INSERT INTO app_settings (setting_key, setting_value)
SELECT 'render_template_file_name', f.filename
  FROM shared_drive_files f
  JOIN app_settings s ON s.setting_key='render_template_file_id'
                     AND s.setting_value = CAST(f.id AS CHAR)
 ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value);

INSERT INTO app_settings (setting_key, setting_value)
SELECT 'render_hdri_file_name', f.filename
  FROM shared_drive_files f
  JOIN app_settings s ON s.setting_key='render_hdri_file_id'
                     AND s.setting_value = CAST(f.id AS CHAR)
 ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value);
