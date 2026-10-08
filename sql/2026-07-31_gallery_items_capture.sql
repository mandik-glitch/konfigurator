-- Robert: prenest "foceni a ukladani" z projektu Photosss do konfiguratoru -
-- kamera primo z prohlizece, volitelna zvukova poznamka, volitelne video,
-- volitelna GPS poloha. Cile: produkty (dopnkova fotka do stavajici
-- galerie), doklady, skladove pohyby, polozky nakupni objednavky (u
-- poslednich tri zatim zadny foto mechanismus).
--
-- Rozsireni existujiciho obecneho "pripojitelneho" fotogalerie modulu
-- (content_gallery_items, viz sql/2026-07-26_gallery_items.sql), ne
-- stavba paralelniho mechanismu.
--
-- media_type = video/foto priznak na existujicim sloupci filename
-- (video nepotrebuje vlastni sloupec, jen priznak jak soubor prehrat).
-- audio_filename je VZDY jen doplnek k foto/videu (nikdy samostatny
-- zaznam), proto vlastni nullable sloupec misto dalsi hodnoty media_type.
-- latitude/longitude - zadna nova "lokacni" tabulka (Photosss model
-- per-account kategorii sem nesedi, tihle vlastnici zadny kategorie/
-- ucet koncept nemaji) - jen souradnice primo na radku, "blizke
-- zaznamy" se pripadne dopocitaji za behu (viz GET /api/gallery-items/nearby).
--
-- owner_type rozsiren o 3 nove vlastniky - vsichni maji INT AUTO_INCREMENT
-- PK, zadna zmena typu owner_id neni potreba:
--   document       -> shop_documents
--   stock_movement -> shop_stock_movements
--   po_item        -> shop_purchase_order_items
--
-- Cistě aditivni/nullable zmena - media_type default 'image' = zadna
-- regrese u stavajicich category/product radku.

ALTER TABLE content_gallery_items
  MODIFY COLUMN owner_type ENUM('category','product','document','stock_movement','po_item') NOT NULL,
  ADD COLUMN media_type ENUM('image','video') NOT NULL DEFAULT 'image' AFTER filename,
  ADD COLUMN audio_filename VARCHAR(255) DEFAULT NULL AFTER media_type,
  ADD COLUMN latitude DECIMAL(9,6) DEFAULT NULL AFTER caption,
  ADD COLUMN longitude DECIMAL(9,6) DEFAULT NULL AFTER latitude,
  ADD INDEX idx_geo (latitude, longitude);
