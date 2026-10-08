-- Oprava: PUT /api/admin/theme-colors padal s "Data too long for
-- column 'setting_value'" (1406) - app_settings.setting_value byl
-- VARCHAR(255), navrzeny pro drobne skalarni hodnoty (joint_price_czk
-- apod.), ale JSON paleta 24 barev ma ~620 znaku. Robert nahlasil
-- screenshotem ("Nelze ukladat barvy"), bot6 2026-07-26.

ALTER TABLE app_settings MODIFY COLUMN setting_value TEXT DEFAULT NULL;
