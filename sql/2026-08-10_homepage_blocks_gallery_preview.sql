-- bot5 2026-08-10
-- Robert: "v další dlaždici mozaiky na homepage, pridal jsem dlaždici, je
-- prázdná, z této udeláme fotogalerii... v náhledu tam bude carusel prvních
-- 10ti fotek, po kliknutí se vstupuje rovnou na fotogalerii, nejdříve sem
-- přesuneme tu co už máme hotovou" + "myslím tím tuto [Foto realizací
-- v horní liště], z horní lišty zmizí a bude součástí dlaždice"
--
-- Priznak na existujici tabulce homepage_blocks (ne nova tabulka/typ enum -
-- jde jen o jednu konkretni dlazdici odkazujici na jiz hotovou fotogalerii
-- realizaci, viz webapp/realizace.html + /api/gallery). Kdyz je nastaveno,
-- SSR render mozaiky (_render_homepage_mosaic_html v api/app.py) misto
-- vlastniho obrazku dlazdice vykresli karusel prvnich 10 aktivnich fotek z
-- shop_gallery_images a odkaz vede na /realizace.html misto /blok/<slug>.
ALTER TABLE homepage_blocks
  ADD COLUMN gallery_preview TINYINT(1) NOT NULL DEFAULT 0 AFTER image_filename;
