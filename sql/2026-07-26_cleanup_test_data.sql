-- Uklid testovacich dat na zadost Roberta 2026-07-26 ("smažme všechny
-- testovací data, nechme jen zákazníky"). Upresneno pres AskUserQuestion:
-- ucty/zakaznici (app_users + shop_customers, vc. testovacich uctu
-- qatest-admin/skladnik/ucetni/zakaznik) ZUSTAVAJI - mazeme jen jejich
-- (v tuto chvili prazdnou) aktivitu + 4 DEMO objednavky pro rezne plany
-- + rezne plany k nim + auditni log. Fotogalerie (230 fotek, import
-- z logiman.cz) a Shoptet katalog (2559 produktu) NEDOTCENO - Robert
-- potvrdil, ze jde o realna produkcni data.
START TRANSACTION;

-- 1) DEMO objednavky pro rezne plany (DEMO-REZNY-01..04, id 22-25)
DELETE FROM shop_order_items WHERE order_id IN (22,23,24,25);
DELETE FROM shop_orders WHERE id IN (22,23,24,25);

-- 2) Rezne plany navazane na tyto DEMO objednavky (potvrzeno: vsechny
--    existujici plany/jednotky referencuji DEMO-REZNY-xx v pieces_json)
DELETE FROM shop_cutting_plan_units;
DELETE FROM shop_cutting_plans;

-- 3) Auditni log (historie akci behem dnesniho testovani)
DELETE FROM audit_log;

COMMIT;
