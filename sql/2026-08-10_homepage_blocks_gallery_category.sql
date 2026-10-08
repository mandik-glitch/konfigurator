-- bot5 2026-08-10
-- Robert: "ted pridej do další nové dlaždice totéž, fotogaleriei, ale
-- budou rozdělené tato nová bude pouze pro stoly, a z predeslé pro
-- vestvaby ty fotky stolů přesuneš"
--
-- Navazuje na gallery_preview (viz 2026-08-10_homepage_blocks_gallery_preview.sql).
-- gallery_category umoznuje kazde "gallery_preview" dlazdici omezit
-- karusel i cilovy odkaz jen na jednu kategorii fotogalerie
-- (shop_gallery_images.category - "vestavby_dodavek"/"realizace_stolu",
-- viz api/gallery.py GALLERY_CATEGORIES). NULL = bez filtru (vsechny
-- kategorie michane, puvodni chovani).
ALTER TABLE homepage_blocks
  ADD COLUMN gallery_category VARCHAR(32) NULL AFTER gallery_preview;
