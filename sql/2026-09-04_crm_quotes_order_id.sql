-- Formalni vazba nabidka -> objednavka (bot18, 2026-09-04, Robert pres
-- bot3 - schvalene doporuceni z hloubkoveho rozboru Dolibarr/ERPNext).
--
-- crm_quotes dnes NEMA zadnou vazbu na shop_orders (potvrzeno ctenim
-- api/quotes.py i teto tabulky) - prevod nabidka->objednavka je 100%
-- rucni a netrasovany, admin nema jak dotazem zjistit, ktera nabidka
-- vedla k jake objednavce. Zrcadli JIZ EXISTUJICI vzor lead_id na tehle
-- tabulce (sql/2026-08-01_crm_quotes.sql) - nullable FK, ON DELETE SET
-- NULL (smazani objednavky nesmi smazat/rozbit nabidku, jen odpojit
-- vazbu), zadna zmena existujicich radku.
--
-- POZOR na skutecny datovy model: crm_quotes je adresarova struktura
-- (crm_quote_folders/crm_quote_files, PDF prilohy), NE polozkovy
-- dokument s cenami/mnozstvim - proto se vazba dela jako RUCNI odkaz na
-- uz existujici/nove zalozenou objednavku (admin vybere/zalozi), ne
-- jako automaticky prevod polozek (zadne polozky k prevodu neexistuji).

ALTER TABLE crm_quotes
    ADD COLUMN order_id INT NULL DEFAULT NULL AFTER customer_id,
    ADD KEY idx_crm_quotes_order (order_id),
    ADD CONSTRAINT fk_crm_quotes_order FOREIGN KEY (order_id) REFERENCES shop_orders(id) ON DELETE SET NULL;
