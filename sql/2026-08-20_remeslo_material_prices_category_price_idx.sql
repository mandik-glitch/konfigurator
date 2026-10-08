-- Řemeslo - výkonová prohlídka Srovnávače (Robert 2026-08-20, navazuje
-- na dřívější opravu /compare - "500 jednotlivých zápisů místo
-- jednoho hromadného"). GET /api/remeslo/compare řadí
-- remeslo_material_prices podle price_czk v rámci jedné category_id
-- (EXPLAIN ukázal "Using temporary; Using filesort" - existující
-- idx_category(category_id) neobsahuje price_czk, takže MySQL musí
-- filtrované řádky nejdřív materializovat a pak zvlášť seřadit).
-- U dnešního maxima (521 řádků) je to bez efektu, ale s rostoucím
-- katalogem (bot9ovo "dohledání položky na vyžádání") a s LIMIT 1000
-- v /compare (viz api/remeslo.py) tenhle index umožní MySQL číst
-- rovnou v seřazeném pořadí a zastavit se po LIMIT řádcích, místo
-- řadit celou (rostoucí) sadu předem.
--
-- Použití: python api/db_migrate_remeslo.py sql/2026-08-20_remeslo_material_prices_category_price_idx.sql

ALTER TABLE remeslo_material_prices
    ADD INDEX idx_category_price (category_id, price_czk);
