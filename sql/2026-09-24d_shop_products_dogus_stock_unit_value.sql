-- Zjisteny udaj OD DODAVATELE (Dogus), NE nase klasifikace (bot3, Robert
-- 2026-09-24: "teď si určíme pevně co je na kusy a co je na tyče 3m",
-- pevna klasifikace se ma zapsat AZ po jeho schvaleni a bude samostatna
-- - tenhle sloupec jen drzi surovy fakt z jejich stranky (skryte pole
-- hdnStockQuantityUnitValue), at jde kdykoli zpetne overit, na cem se
-- klasifikace zakladala).
ALTER TABLE shop_products
    ADD COLUMN dogus_stock_unit_value INT NULL COMMENT 'hdnStockQuantityUnitValue z dogusi stranky (3000=3m jednotka, 0=kus, NULL=nezjisteno)',
    ADD COLUMN dogus_stock_unit_checked_at DATETIME NULL COMMENT 'kdy byl dogus_stock_unit_value naposledy zjisten crawlem';
