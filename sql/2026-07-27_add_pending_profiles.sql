-- Robert vybral 17 dalsich profilu z logiman.cz (z tabulky pripravene v
-- artefaktu "Dalsi profily z logiman.cz" - drazka 6mm/8mm/10mm), ktere
-- se maji pridat do cenikove tabulky (admin "Ceny profilu") stejnym
-- zpusobem jako existujicich 5 (Object_1/2/7/11/14) - cross-section,
-- material, price_source_url, cena+hmotnost se dotahnou stejnym scraperem
-- (scrape_logiman_price_weight / refresh_price_for_row).
--
-- Robert: "fbx model jim priradime pozdeji" - glb_file je NOT NULL sloupec,
-- proto placeholder "_PENDING_<id>.glb". Bezpecne: scene.html filtruje
-- 3D katalog pro stavbu sceny pres vlastni VISIBLE_CATALOG_IDS allowlist
-- (jen Object_1/2/7/11/14), takze tyhle radky se v 3D stavebnici NEUKAZI
-- a jejich neplatny glb_file se nikdy nebude nacitat - az dorazi realny
-- FBX/GLB export, jen se prepise glb_file a pripadne id se prida do
-- VISIBLE_CATALOG_IDS ve scene.html (samostatny krok).
--
-- id NEpouziva schema "Object_N" (to je vyhrazene pro skutecne FBX-exportovane
-- mesh objekty), aby nedoslo ke kolizi az se budou realne modely priradovat.
--
-- dim_y_mm=1000 = referencni delka 1m (stejna konvence jako u existujicich
-- 5 radku - "Ceny profilu" a currentWeightPrice() pak prepocitavaji linearne
-- na jinou delku). weight_kg_approx/price_czk_approx se NEplni tady (NULL),
-- doplni je nasledny scrape skript (stejna cesta jako noc. refresh timer).

INSERT INTO cfg_dily
  (id, name, layer, material_label, dim_x_mm, dim_y_mm, dim_z_mm,
   density_kg_m3, price_per_kg_czk_placeholder, glb_file, price_source_url)
VALUES
  ('profil_20x20', 'Profil 20x20mm', 'alu', 'Hlinik (elox)', 20.00, 1000.00, 20.00,
   2700.00, 250.00, '_PENDING_profil_20x20.glb',
   'https://www.logiman.cz/hlinikove-profily-s-drazkou-6mm/hlinikovy-stavebnicovy-profil-20x20/'),

  ('profil_20x20_radius', 'Profil 20x20mm (radius)', 'alu', 'Hlinik (elox)', 20.00, 1000.00, 20.00,
   2700.00, 250.00, '_PENDING_profil_20x20_radius.glb',
   'https://www.logiman.cz/hlinikove-profily-s-drazkou-6mm/hlinikovy-stavebnicovy-profil-20x20-radius/'),

  ('profil_20x40', 'Profil 20x40mm', 'alu', 'Hlinik (elox)', 20.00, 1000.00, 40.00,
   2700.00, 250.00, '_PENDING_profil_20x40.glb',
   'https://www.logiman.cz/hlinikove-profily-s-drazkou-6mm/hlinikovy-stavebnicovy-profil-20x40/'),

  ('profil_20x80', 'Profil 20x80mm', 'alu', 'Hlinik (elox)', 20.00, 1000.00, 80.00,
   2700.00, 250.00, '_PENDING_profil_20x80.glb',
   'https://www.logiman.cz/hlinikove-profily-s-drazkou-6mm/hlinikovy-stavebnicovy-profil-20x80/'),

  ('profil_25x25', 'Profil 25x25mm', 'alu', 'Hlinik (elox)', 25.00, 1000.00, 25.00,
   2700.00, 250.00, '_PENDING_profil_25x25.glb',
   'https://www.logiman.cz/hlinikove-profily-s-drazkou-6mm/hlinikovy-stavebnicovy-profil-25x25/'),

  ('profil_30x30_radius', 'Profil 30x30mm (radius)', 'alu', 'Hlinik (elox)', 30.00, 1000.00, 30.00,
   2700.00, 250.00, '_PENDING_profil_30x30_radius.glb',
   'https://www.logiman.cz/hlinikove-profily-s-drazkou-8mm/hlinikovy-stavebnicovy-profil-30x30-radius/'),

  ('profil_30x30_uzavreny', 'Profil 30x30mm (uzavřený)', 'alu', 'Hlinik (elox)', 30.00, 1000.00, 30.00,
   2700.00, 250.00, '_PENDING_profil_30x30_uzavreny.glb',
   'https://www.logiman.cz/hlinikove-profily-s-drazkou-8mm/hlinikovy-stavebnicovy-profil-30x30-uzavreny/'),

  ('profil_35x35', 'Profil 35x35mm', 'alu', 'Hlinik (elox)', 35.00, 1000.00, 35.00,
   2700.00, 250.00, '_PENDING_profil_35x35.glb',
   'https://www.logiman.cz/hlinikove-profily-s-drazkou-8mm/hlinikovy-stavebnicovy-profil-35-x-35-x-3000-mm/'),

  ('profil_40x40_zkoseny_s10', 'Profil 40x40mm (zkosený S10)', 'alu', 'Hlinik (elox)', 40.00, 1000.00, 40.00,
   2700.00, 250.00, '_PENDING_profil_40x40_zkoseny_s10.glb',
   'https://www.logiman.cz/hlinikove-profily-s-drazkou-8mm/hlinikovy-stavebnicovy-profil-40-x-40-x-3000-mm-zkoseny-s10/'),

  ('profil_40x40_light_s10', 'Profil 40x40mm (Light S10)', 'alu', 'Hlinik (elox)', 40.00, 1000.00, 40.00,
   2700.00, 250.00, '_PENDING_profil_40x40_light_s10.glb',
   'https://www.logiman.cz/hlinikove-profily-s-drazkou-10mm/hlinikovy-stavebnicovy-profil-40x40-light-s10/'),

  ('profil_40x40_uzavreny_s10', 'Profil 40x40mm (Uzavřený S10)', 'alu', 'Hlinik (elox)', 40.00, 1000.00, 40.00,
   2700.00, 250.00, '_PENDING_profil_40x40_uzavreny_s10.glb',
   'https://www.logiman.cz/hlinikove-profily-s-drazkou-10mm/hlinikovy-stavebnicovy-profil-40-x-40-x-3000-mm-uzavreny-s10/'),

  ('profil_40x80_light_s10', 'Profil 40x80mm (Light S10)', 'alu', 'Hlinik (elox)', 40.00, 1000.00, 80.00,
   2700.00, 250.00, '_PENDING_profil_40x80_light_s10.glb',
   'https://www.logiman.cz/hlinikove-profily-s-drazkou-10mm/hlinikovy-stavebnicovy-profil-40-x-80-x-3000-mm-light-s10/'),

  ('profil_45x45_radius', 'Profil 45x45mm (radius)', 'alu', 'Hlinik (elox)', 45.00, 1000.00, 45.00,
   2700.00, 250.00, '_PENDING_profil_45x45_radius.glb',
   'https://www.logiman.cz/hlinikove-profily-s-drazkou-10mm/hlinikovy-stavebnicovy-profil-45-x-45-x-3000-mm-radius/'),

  ('profil_45x45_light_s10', 'Profil 45x45mm (Light S10)', 'alu', 'Hlinik (elox)', 45.00, 1000.00, 45.00,
   2700.00, 250.00, '_PENDING_profil_45x45_light_s10.glb',
   'https://www.logiman.cz/hlinikove-profily-s-drazkou-10mm/hlinikovy-stavebnicovy-profil-45x45-light-s10/'),

  ('profil_45x45_uzavreny_s10', 'Profil 45x45mm (uzavřený S10)', 'alu', 'Hlinik (elox)', 45.00, 1000.00, 45.00,
   2700.00, 250.00, '_PENDING_profil_45x45_uzavreny_s10.glb',
   'https://www.logiman.cz/hlinikove-profily-s-drazkou-10mm/hlinikovy-stavebnicovy-profil-45x45-uzavreny-s10/'),

  ('profil_45x90_superlight_s10', 'Profil 45x90mm (Super Light S10)', 'alu', 'Hlinik (elox)', 45.00, 1000.00, 90.00,
   2700.00, 250.00, '_PENDING_profil_45x90_superlight_s10.glb',
   'https://www.logiman.cz/hlinikove-profily-s-drazkou-10mm/hlinikovy-stavebnicovy-profil-45x90-superlight-s10/'),

  ('profil_45x90_light_s10', 'Profil 45x90mm (Light S10)', 'alu', 'Hlinik (elox)', 45.00, 1000.00, 90.00,
   2700.00, 250.00, '_PENDING_profil_45x90_light_s10.glb',
   'https://www.logiman.cz/hlinikove-profily-s-drazkou-10mm/hlinikovy-stavebnicovy-profil-45-x-90-x-3000-mm-light-s10/');
