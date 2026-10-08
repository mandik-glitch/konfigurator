-- bot16 2026-09-03: oprava cargo_length v karoserie_model_reference (odhalil audit
-- scripts/2026-09-03_audit_regal_jen_k_podbehu.py - GLB vs. oficialni ložná délka).
-- Zaloha puvodnich radku: backups/karoserie_model_reference_crew_cargo_length_20260903.json
--
-- 1) PSA Crew Cab L2 (celk. 4959) a L3 (celk. 5309) maji cargo_text PROHOZENY:
--    objem 3.2 m3 (L2) / 4.0 m3 (L3) i GLB (1575 / 1927 mm) sedi jen na prohozene hodnoty.
UPDATE karoserie_model_reference SET cargo_text='1700mm (L) 1618mm (W) 1339mm (H)', cargo_length_mm=1700, cargo_height_mm=1339, updated_at=NOW() WHERE legacy_vendor_code IN ('TO12','PE21','CI18') AND cargo_length_mm=2017;
UPDATE karoserie_model_reference SET cargo_text='2017mm (L) 1618mm (W) 1337mm (H)', cargo_length_mm=2017, cargo_height_mm=1337, updated_at=NOW() WHERE legacy_vendor_code IN ('TO17','PE20','CI19') AND cargo_length_mm=1700;
-- 2) FO29 "Transit Custom L1 DCiV 12-" mel zkopirovane hodnoty bezne L1 (FO10: 2554/1406, 4.0 m3).
--    DCiV L1: ložná délka u podlahy 1604 mm (vanshelves.co.uk; GLB meri 1616), vyska jako L2 DCiV (FO28 1324), objem 3.5 m3.
UPDATE karoserie_model_reference SET cargo_text='1604mm (L) 1775mm (W) 1324mm (H)', cargo_length_mm=1604, cargo_height_mm=1324, cargo_volume_m3=3.50, updated_at=NOW() WHERE legacy_vendor_code='FO29' AND cargo_length_mm=2554;
-- RE28/RE29 (novy Trafic Van E-Tech Electric 2026, celk. 4870/5270) zustavaji 0 - Renault
-- ložné rozmery zatim nezverejnil (vyroba az konec 2026); GLB meri 2604/3004 mm.
