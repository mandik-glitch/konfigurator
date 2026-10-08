-- Robert (2026-09-23, ostre pres bot3): "zakazoval jsem pri sestavach
-- pouzivat slovo Dogus a bot5 vesele dal pracuje nejakym dogus
-- souborem!" - sloupec `dogus_specs_json` je OBECNY mechanismus
-- (pohani renderMetaTable/"tabulka specifikaci" na product.html),
-- pojmenovany podle PUVODNIHO Dogus importu, ale od bot7ova Vandr
-- importu (2026-09-18) uz ho pouziva i Vandr vetev pres stejny
-- sloupec. Zadne mixovani dat mezi vetvemi (kazdy produkt ma svuj
-- vlastni radek/JSON), jen NAZEV sloupce nese Dogus branding, ktery
-- Robert u sestav/obecne nechce videt ani v kodu.
--
-- Ostatni dogus_* sloupce (dogus_url, dogus_stock_code, dogus_image_*,
-- dogus_matched_at, dogus_list_price_usd, dogus_price_rate_used)
-- ZUSTAVAJI beze zmeny - ty jsou skutecne Dogus-specificke (sledovani
-- puvodu dat od dodavatele Dogus), tenhle prejmenovani se jich netyka.
ALTER TABLE shop_products
  CHANGE COLUMN dogus_specs_json product_specs_json JSON NULL;
