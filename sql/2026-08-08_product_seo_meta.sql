-- SEO meta pole pro produkty e-shopu - bot3, 2026-08-08.
--
-- Robert: "vlastni zalozky nech ma take ceno tvorba, GEO/SEO(udelat)" -
-- skladova karta dostava novou zalozku "GEO/SEO" (viz admin.html).
-- Stejny nazev/typ sloupcu jako uz existujici content_categories.meta_title/
-- meta_description (viz sql/2026-07-26_category_infrastructure.sql) -
-- zachovana konvence napric projektem misto vymyslet novy nazev.
ALTER TABLE shop_products
    ADD COLUMN meta_title VARCHAR(255) NULL COMMENT 'Nazev (tag title) - SEO',
    ADD COLUMN meta_description VARCHAR(500) NULL COMMENT 'Popis (meta tag description) - SEO';
