-- bot8 2026-09-17, Robert: "davej mi sestavy aktualne ktere resime vzdy nahoru"
-- Casove razitko "aktualne resime": NULL = neresi se, jinak kdy byla sestava
-- oznacena. Scena (panel Produktove sestavy) z nej sklada skupinu
-- "Aktualne resime" uplne nahore, nejnovejsi prvni. Nastavuje bot pri praci
-- na sestave, admin ho zrusi ve scene (📌).
ALTER TABLE product_assemblies
  ADD COLUMN resi_se_at DATETIME NULL DEFAULT NULL AFTER mezera_checked_at,
  ADD KEY idx_pa_resi_se_at (resi_se_at);
