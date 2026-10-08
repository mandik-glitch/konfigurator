-- Archivace poptavek (bot4, Robert 2026-08-06: "testovaci poptavky
-- automaticky archivujme"). Novy priznak archived - archivovana
-- poptavka zmizi z beznych zalozek (Vse/Nova/...) do vlastni zalozky
-- "Archiv" v adminu. Automaticky se archivuji nove prichozi poptavky,
-- jejichz PREDMET vypada testovaci (slovo zacinajici na "test" -
-- test/testovaci/[TEST...], viz _looks_like_test_lead v api/crm.py);
-- admin muze archivovat/obnovit rucne v detailu poptavky.
ALTER TABLE crm_leads
  ADD COLUMN archived TINYINT(1) NOT NULL DEFAULT 0,
  ADD KEY idx_crm_leads_archived (archived);
