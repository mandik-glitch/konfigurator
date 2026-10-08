-- VYPNUTI renderovani podle tabulky materialu katalogu (okamzity navrat k dnesnimu chovani; data v tabulkach zustanou).
--   !/opt/konfigurator/scripts/2026-09-03_bot16_mysql_apply.sh /opt/konfigurator/sql/2026-10-01_render_materialy_flag_vypnout.sql
INSERT INTO app_settings (setting_key, setting_value) VALUES ('render_materialy_katalogu_aktivni', '0')
ON DUPLICATE KEY UPDATE setting_value = '0';
SELECT setting_key, setting_value FROM app_settings WHERE setting_key = 'render_materialy_katalogu_aktivni';
