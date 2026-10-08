-- Robert 2026-08-10: "1x tydne se nacte kompletne novy cenik z Dogus,
-- ulozi se cena USD u nas aby ji jen admin videl na kazde karte.
-- Automaticky se okamzite podle koeficientu a podle rovnice cena dogus
-- x 3 x kurz = cena za 1ks tyce 3m, s kurzem Fio banka devize prodej."
--
-- Dosud se USD cena z Dogus (List Price) nikam neuklada - pouzila se
-- jen v pameti pri prepoctu (scripts/2026-08-09_dogus_price_recompute.py)
-- a zahodila. Nove 2 sloupce na shop_products:
--   dogus_list_price_usd  - posledni nactena cena z Dogus (USD/m)
--   dogus_price_rate_used - kurz CZK/USD pouzity pri poslednim prepoctu
--                            (Fio banka, "Prodej") - ulozeno kvuli
--                            transparentnosti/auditu vypoctu na karte
--                            produktu, ne jen samotny vysledek.
ALTER TABLE shop_products
  ADD COLUMN dogus_list_price_usd DECIMAL(10,4) NULL AFTER price_czk_placeholder,
  ADD COLUMN dogus_price_rate_used DECIMAL(10,5) NULL AFTER dogus_list_price_usd;
