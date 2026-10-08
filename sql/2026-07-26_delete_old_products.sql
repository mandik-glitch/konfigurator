-- Smazani 294 puvodnich (pre-Shoptet) produktu na vyslovnou zadost
-- Roberta 2026-07-26 ("smaž staré původní produkty, včetně pohybů").
-- Vsechny nalezene navazane objednavky jsou testovaci (customer_name
-- zacina "TEST"), Robert explicitne potvrdil smazani i techto objednavek
-- pres AskUserQuestion.
START TRANSACTION;

-- 1) Odvazat self-referencujici doklady (faktura/danovy doklad -> proforma)
UPDATE shop_documents SET related_document_id = NULL WHERE order_id IN (12,13,14,30,31);

-- 2) Smazat doklady, historii stavu, e-maily a polozky pro tyto testovaci objednavky
DELETE FROM shop_documents WHERE order_id IN (12,13,14,30,31);
DELETE FROM shop_order_status_history WHERE order_id IN (12,13,14,30,31);
DELETE FROM shop_emails WHERE order_id IN (12,13,14,30,31);
DELETE FROM shop_order_items WHERE order_id IN (12,13,14,30,31);
DELETE FROM shop_orders WHERE id IN (12,13,14,30,31);

-- 3) Smazat samotne stare produkty (shoptet_id IS NULL = puvodni katalog
--    pred importem). FK CASCADE automaticky smaze navazane radky:
--    shop_stock_movements (pohyby), shop_reorder_items, shop_cart_items,
--    shop_product_images.
DELETE FROM shop_products WHERE shoptet_id IS NULL;

COMMIT;
