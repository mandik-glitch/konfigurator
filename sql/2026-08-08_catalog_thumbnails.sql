-- Automaticky generovane 3D nahledy katalogovych dilu (Robert 2026-08-08:
-- "chce to vymyslet jak to efektivne dostat na co nejmensi plochu... obrazky
-- jako tlacitka") - novy obrazkovy plovouci panel katalogu (vedle stavajiciho
-- stromu) potrebuje pro kazdy dil miniaturu. Generuje se dávkově adminem ve
-- scene.html (screenshot izolovaneho GLB, stejny princip jako generator
-- nahledu produktovych sestav), uklada se jako staticky soubor do
-- webapp/katalog/thumbnails/ (stejna slozka/nginx alias jako GLB modely,
-- viz KATALOG_GLB_DIR v api/app.py) - sloupec nese jen relativni cestu.

ALTER TABLE cfg_dily
  ADD COLUMN thumbnail_file VARCHAR(255) NULL AFTER glb_file;

ALTER TABLE shop_products
  ADD COLUMN thumbnail_file VARCHAR(255) NULL AFTER glb_file;
