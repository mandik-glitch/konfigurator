-- SEO audit (bot6, 2026-08-03) - sitemap.xml potreboval <lastmod> pro
-- kategorie (konkurent do-dodavky.cz ho ma u kazde URL, my jsme ho nemeli
-- k dispozici vubec - content_categories na rozdil od shop_products
-- nemela zadny casovy sloupec). ON UPDATE CURRENT_TIMESTAMP se sam
-- udrzuje pri kazdem UPDATE, zadna zmena v aplikacnim kodu potreba.
ALTER TABLE content_categories
  ADD COLUMN updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;
