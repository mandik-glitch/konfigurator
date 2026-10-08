-- bot5 2026-08-10 (Robert: navrh vylepseni frontendu -> filtrace v
-- kategorii podle prurezu profilu a drazkove rodiny) - nove sloupce pro
-- filtrovani, hodnoty se dopocitaji backfill skriptem ze struktury SKU
-- (1.1.GG.XXXYYY.NN, GG=kod drazky 06/08/10, XXXYYY=prurez), viz
-- scripts/2026-08-10_product_cross_section_groove_backfill.py.
--
-- Zamerne oddelene od cfg_dily (3D model pro scenu) - stejny duvod jako
-- u is_profile_material (sql/2026-08-09_is_profile_material.sql): jen
-- 22 ze 101 profilovych produktu ma cfg_dily_id, jako jediny zdroj by
-- pokryl min nez ctvrtinu filtrovatelnych produktu.
ALTER TABLE shop_products
    ADD COLUMN cross_section_label VARCHAR(16) NULL AFTER is_profile_material,
    ADD COLUMN groove_family VARCHAR(4) NULL AFTER cross_section_label;
