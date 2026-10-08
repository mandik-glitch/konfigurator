-- Robert (pres toscanaccio-0b, 2026-08-30 noc): hub karty (Doblò/Ducato/
-- Scudo) musi byt serazene podle velikosti vozu (male->velke, zleva
-- doprava pro vizualni narativ "prujezd auta rostouci velikosti"), ne
-- abecedne. Stejna konvence jako car_makes.sort_order/car_models.
-- sort_order/content_categories.sort_order jinde v projektu.

ALTER TABLE car_storefronts
    ADD COLUMN sort_order INT NOT NULL DEFAULT 0;
