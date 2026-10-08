-- 2026-07-26 bot2: smazani neceskych/neanglickych nazvu z 1321 produktu
-- bez kategorie (Shoptet import). Robert: "ceske nazvy ponechej, anglicke
-- taky, proved" - smazano jen 15 polozek s tureckymi/ruskymi nazvy
-- (zadne objednavky/kosiky/PO na ne neodkazuji, jen shop_product_images
-- CASCADE).
START TRANSACTION;
DELETE FROM shop_products WHERE id IN (397,538,1219,1575,1576,1577,1578,1579,1580,1581,1710,1711,1712,2889,2890);
COMMIT;
