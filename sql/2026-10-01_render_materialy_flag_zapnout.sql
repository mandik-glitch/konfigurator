-- ZAPNUTI renderovani podle tabulky materialu katalogu (bot10, 2026-10-01). NESPOUSTET driv, nez:
--   1) bezelo sql/2026-10-01_render_materialy.sql a scripts/2026-10-01_render_materialy_predvyplneni.py --apply,
--   2) je zapojena render_material_key() do resolve_parts() (zvlast s bot4) a Robert prosel tabulku v adminu,
--   3) existuji knihovny .blend vsech pouzitych materialu na Sdilenem disku (cub_seda.blend, bila.blend!).
-- Pravidlo 50: do app_settings nezapisuje bot, pousti Robert pres '!':
--   !/opt/konfigurator/scripts/2026-09-03_bot16_mysql_apply.sh /opt/konfigurator/sql/2026-10-01_render_materialy_flag_zapnout.sql
-- Vypnuti = soubor 2026-10-01_render_materialy_flag_vypnout.sql (nebo DELETE radku; chybejici radek = vypnuto).
INSERT INTO app_settings (setting_key, setting_value) VALUES ('render_materialy_katalogu_aktivni', '1')
ON DUPLICATE KEY UPDATE setting_value = '1';
SELECT setting_key, setting_value FROM app_settings WHERE setting_key = 'render_materialy_katalogu_aktivni';
