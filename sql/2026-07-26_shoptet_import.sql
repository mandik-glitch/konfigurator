
-- Dodatecna oprava behem importu: nektere Shoptet CODE hodnoty presahovaly
-- puvodnich 50 znaku (max pozorovano 57), UPDATE selhal na 1000. radku s
-- "Data too long for column sku". Rozsireno a import bezpecne dobehl
-- (idempotentni skript, jiz vlozene radky jen aktualizoval).
ALTER TABLE shop_products MODIFY sku VARCHAR(150) NOT NULL;
