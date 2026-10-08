-- Robert: "rozdel text dulezity nad mrizku podkategorií a zbylý do
-- spodni casti" - dosavadni jeden text kategorie (content_pages.
-- body_html, mezi vypisem podkategorii a produkty) se rozdeluje na
-- dve casti: kratky "dulezity" uvod (intro_html, nove pole) hned pod
-- nadpisem PRED mrizkou podkategorii (SEO/GEO - AI vyhledavace casto
-- beru prvni odstavec jako shrnuti stranky), a zbytek (puvodni
-- body_html) presunuty NIZ, za vypis produktu (viz webapp/category.html).
ALTER TABLE content_pages
  ADD COLUMN intro_html MEDIUMTEXT NULL AFTER title;
