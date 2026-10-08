-- Explicitni vazebni sloupec Vandr karta <-> vandrawee_work.stored_models
-- (Robert pres bot3, 2026-09-25: "musí se to normálně na sebe napárovat" -
-- ne parsovani SKU za behu, ale jednou naplneny sloupec pouzivany jako
-- skutecny vazebni klic). NULL = karta bez protejsku v adminu (5 znamych
-- pripadu - 4 nasi vlastni testovaci VD-EXPORT-*/VD-TEST-* artefakty +
-- 1 skutecne osirela karta #4277, viz backfill skript).
ALTER TABLE shop_products
    ADD COLUMN vandr_stored_model_uuid CHAR(36) NULL
        COMMENT 'vandrawee_work.stored_models.uuid (dashed lowercase string) - jen kdyz overene existuje, jinak NULL',
    ADD UNIQUE KEY uq_vandr_stored_model_uuid (vandr_stored_model_uuid);
