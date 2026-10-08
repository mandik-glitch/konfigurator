-- bot5 2026-08-10 (Robert: "uhelniky nemaji zobaky... dej jim vsechny
-- 3 ikony") - groove_family nove pripousti CSV seznam vice hodnot
-- ("6,8,10") u prislusenstvi bez fyzicke vazby na konkretni sirku
-- drazky (viz _groove_badges_html/_category_products_with_images v
-- api/app.py). Puvodni VARCHAR(4) stacil jen na jednu hodnotu ("10"),
-- "6,8,10" ma 6 znaku - VARCHAR(16) s rezervou pro budoucnost.
ALTER TABLE shop_products
    MODIFY COLUMN groove_family VARCHAR(16) NULL;
