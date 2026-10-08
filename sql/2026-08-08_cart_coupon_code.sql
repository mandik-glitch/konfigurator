-- Kupon ulozeny na radku kosiku - bot3, 2026-08-08. Doplnek k
-- sql/2026-08-08_product_related_pricing.sql (shop_product_coupons).
--
-- Cena v kosiku se (stejne jako u ostatnich poli - viz api/cart.py
-- docstring "_cut_service_price_czk se NEUKLADA, dopocitava se ZIVA")
-- vzdy dopocita ziva z aktualnich dat produktu, ne snapshotuje pri
-- pridani do kosiku - aby zmena ceny/kuponu v adminu platila i pro uz
-- rozpracovany kosik. Kod kuponu samotny se ale ULOZIT MUSI (na rozdil
-- od ceny), protoze jinak by si system po zavreni/znovuotevreni kosiku
-- nepamatoval, ktery kupon zakaznik zadal.
ALTER TABLE shop_cart_items
    ADD COLUMN coupon_code VARCHAR(40) NULL;
