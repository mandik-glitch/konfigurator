-- Robert 2026-09-18: "chci pridat sloupec, primo cenu v USD z Dogus s
-- datem stazeni" - novy sloupec v admin > Ceny profilů (cfg_dily), vedle
-- uz existujiciho price_czk_approx (prepocitana CZK cena). Rucne zadavana
-- hodnota (admin ji opise z katalogu Dogus Kalip), datum stazeni se
-- nastavuje automaticky pri ulozeni (viz api/admin_profily.py), zadny
-- samostatny date picker.
ALTER TABLE cfg_dily
  ADD COLUMN dogus_price_usd DECIMAL(10,2) NULL AFTER price_source_url,
  ADD COLUMN dogus_price_usd_fetched_at DATETIME NULL AFTER dogus_price_usd;
