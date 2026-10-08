-- Priprava na import realnych zakazniku z customers.xml (bot3, 2026-07-25).
--
-- 1) Sjednoceni nazvu startovacich slevovych skupin se skutecnou
--    terminologii z puvodniho systemu (zjisteno az z realnych dat -
--    puvodni placeholder nazvy "Standardni"/"Velkoobchod"/"VIP" byly jen
--    odhad pred tim, nez existovala realna data). Zadny zakaznik zatim
--    zadnou skupinu nema prirazenou, takze bezpecne prejmenovat/pridat.
UPDATE shop_customer_groups SET name='Koncový zákazník' WHERE name='Standardní';
UPDATE shop_customer_groups SET name='Prodejce sleva 10%' WHERE name='Velkoobchod';
UPDATE shop_customer_groups SET name='Prodejce sleva 15%' WHERE name='VIP';
INSERT INTO shop_customer_groups (name, discount_percent, active, sort_order)
    VALUES ('Autosalon', 5, 1, 4);

-- 2) Nova pole na shop_customers pro import historickych zakazniku:
--    - note: volny text (mapuje se z REMARK)
--    - legacy_guid: GUID z puvodniho systemu - UNIQUE, aby se pri
--      pripadnem opakovanem spusteni importu stejny zaznam nevytvoril
--      dvakrat (idempotence)
--    - legacy_order_count / legacy_order_value_czk: historicke statistiky
--      z puvodniho systemu (NEJSOU napojene na skutecne radky shop_orders
--      v tomto systemu - jde jen o informativni kontext "kolikrat/za kolik
--      uz u nas tenhle zakaznik drive nakoupil")
ALTER TABLE shop_customers
    ADD COLUMN note TEXT NULL,
    ADD COLUMN legacy_guid VARCHAR(64) NULL,
    ADD COLUMN legacy_order_count INT NULL,
    ADD COLUMN legacy_order_value_czk DECIMAL(12,2) NULL,
    ADD UNIQUE KEY uq_shop_customers_legacy_guid (legacy_guid);
