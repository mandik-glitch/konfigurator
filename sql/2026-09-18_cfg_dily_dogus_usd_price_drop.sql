-- Robert 2026-09-18: "ja neco rucne opisu? blazne, kazdy tyden jede
-- smycka na stahovaáí ceny z dogusu, najdi to a aplikuj do sloupce, musi
-- se to udrzovat zive" - puvodni rucne-zadavane sloupce (viz
-- 2026-09-18_cfg_dily_dogus_usd_price.sql, jeste tentyz den) byly spatny
-- napad, nikdy nezustaly pouzite. "Cena USD (Dogus)" ted cte ZIVE ze
-- shop_products.dogus_list_price_usd / price_last_refreshed_at (JOIN pres
-- shop_products.cfg_dily_id, viz api/admin_profily.py) - stejna data,
-- ktera uz tydne aktualizuje scripts/2026-08-09_dogus_price_recompute.py.
ALTER TABLE cfg_dily
  DROP COLUMN dogus_price_usd,
  DROP COLUMN dogus_price_usd_fetched_at;
