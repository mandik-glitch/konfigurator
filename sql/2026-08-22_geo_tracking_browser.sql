-- Doplneni k sql/2026-08-22_geo_tracking_daily_device_dwell.sql -
-- Robert pres bot3 (dodatecne, behem prace na predchozim kroku): vedle
-- typu zarizeni (mobil/desktop/tablet) chce i PROHLIZEC (Chrome/
-- Safari/Firefox/...). Stejny zdroj dat jako zarizeni -
-- _classify_device_type() uz cte User-Agent hlavicku serverove,
-- analogicka _classify_browser() (viz api/tracking.py) vedle ni.

ALTER TABLE page_views ADD COLUMN browser VARCHAR(20) NULL AFTER device_type;
ALTER TABLE product_views ADD COLUMN browser VARCHAR(20) NULL AFTER device_type;
ALTER TABLE category_views ADD COLUMN browser VARCHAR(20) NULL AFTER device_type;

-- Denni bucket tabulky: browser NOT NULL DEFAULT '' (stejny duvod jako
-- u country/city/device_type - MySQL UNIQUE KEY bere kazdy NULL jako
-- odlisny od jineho NULL), musi byt i soucasti UNIQUE KEY (jinak by se
-- ruzne prohlizece tise slevaly do jednoho radku misto rozpadu).

ALTER TABLE page_views_daily
  DROP INDEX uq_page_views_daily,
  ADD COLUMN browser VARCHAR(20) NOT NULL DEFAULT '' AFTER device_type,
  ADD UNIQUE KEY uq_page_views_daily (path, den, country, city, device_type, browser);

ALTER TABLE product_views_daily
  DROP INDEX uq_product_views_daily,
  ADD COLUMN browser VARCHAR(20) NOT NULL DEFAULT '' AFTER device_type,
  ADD UNIQUE KEY uq_product_views_daily (product_id, den, country, city, device_type, browser);

ALTER TABLE category_views_daily
  DROP INDEX uq_category_views_daily,
  ADD COLUMN browser VARCHAR(20) NOT NULL DEFAULT '' AFTER device_type,
  ADD UNIQUE KEY uq_category_views_daily (category_id, den, country, city, device_type, browser);
