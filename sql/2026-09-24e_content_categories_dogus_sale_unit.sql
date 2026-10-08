-- Pevna, jednou schvalena klasifikace prodejni jednotky podle Dogus
-- sekce (Robert pres bot3, 2026-09-24, FINALNI rozhodnuti - "podle
-- DOGUSICH SEKCI, zadne odvozovani"). Skript
-- scripts/2026-08-09_dogus_price_recompute.py uz tenhle sloupec jen
-- CTE, nikdy nedopocitava za behu (nahrazuje jak puvodni "lišta v
-- nazvu" heuristiku, tak jednodenni pokus o zivy signal ze stranky
-- hdnStockQuantityUnitValue - overeno bot3, ze to pole neni obecne
-- spolehlive, chybi/je 0 i u casti polozek, ktere Robert vyslovne
-- oznacil za metraz).
--
--   tyc_3m  - Dogus skupina 9 "aluminium-profiles" (6/8/10-slot,
--             surface-coating, conveyor, special-series) + 2 dalsi
--             kategorie hlinikovych profilu mimo tuhle skupinu, ktere
--             Robert vyslovne potvrdil jako tyce (215 Vodici hlinikove
--             profily, 192 Hlinikove profily Dynamic). cena_za_ks =
--             round(usd x kurz x koef x 3), unit='ks', "1 ks=3000mm".
--   metraz  - Dogus sekce 84 "profile-seals" (nase kategorie 196).
--             cena_za_m = usd x kurz x koef (BEZ x3), unit='m'.
--   kus     - vsechno ostatni (DEFAULT). ceil(usd x kurz x koef), unit='ks'.
ALTER TABLE content_categories
    ADD COLUMN dogus_sale_unit ENUM('tyc_3m','metraz','kus') NOT NULL DEFAULT 'kus'
        COMMENT 'Robert 2026-09-24: pevna klasifikace prodejni jednotky podle Dogus sekce, viz komentar v migraci';

UPDATE content_categories SET dogus_sale_unit='tyc_3m'
    WHERE id IN (154, 169, 198, 262, 264, 168, 215, 192);

UPDATE content_categories SET dogus_sale_unit='metraz'
    WHERE id = 196;
