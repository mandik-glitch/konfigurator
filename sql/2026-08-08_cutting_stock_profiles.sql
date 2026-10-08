-- Doplneni chybejicich prurezu profilu do shop_cutting_stock/shop_cutting_settings
-- (bot4, 2026-08-08).
--
-- Robert: "nahraju ti testovací objednávku profily s přířezy a desky,
-- uchop to napoj reálně funkčně na řezné plány" - pri priprave se
-- zjistilo, ze jen prurez 30x30 ma zalozenou skladovou variantu (viz
-- puvodni sql/2026-07-25_cutting_plans.sql seed) - u ostatnich 10
-- prurezu z VLASTNOSTI_PROFILU.md by testovaci objednavka skoncila
-- chybou "zadna aktivni skladova varianta" v api/cutting.py.
--
-- stock_length_mm=3000 - stejna konvence jako PROFILE_MAX_LENGTH_MM
-- (api/app.py) a jiz existujici 30x30 radek.
-- kerf_mm=4.00 - Robert potvrdil: "rezna ztrata ostatnich je vzdy
-- stejna, rezeme na stejne pile" - stejna hodnota jako uz ma 30x30.
INSERT INTO shop_cutting_stock (cut_kind, material_key, label, stock_length_mm, price_czk, active, sort_order) VALUES
  ('profil', '10x40', 'Tyč 10×40, 3000 mm', 3000, 0.00, 1, 11),
  ('profil', '20x20', 'Tyč 20×20, 3000 mm', 3000, 0.00, 1, 12),
  ('profil', '20x40', 'Tyč 20×40, 3000 mm', 3000, 0.00, 1, 13),
  ('profil', '20x80', 'Tyč 20×80, 3000 mm', 3000, 0.00, 1, 14),
  ('profil', '30x60', 'Tyč 30×60, 3000 mm', 3000, 0.00, 1, 15),
  ('profil', '35x35', 'Tyč 35×35, 3000 mm', 3000, 0.00, 1, 16),
  ('profil', '40x40', 'Tyč 40×40, 3000 mm', 3000, 0.00, 1, 17),
  ('profil', '40x80', 'Tyč 40×80, 3000 mm', 3000, 0.00, 1, 18),
  ('profil', '45x45', 'Tyč 45×45, 3000 mm', 3000, 0.00, 1, 19),
  ('profil', '45x90', 'Tyč 45×90, 3000 mm', 3000, 0.00, 1, 20);

INSERT INTO shop_cutting_settings (material_key, kerf_mm, orientation_locked) VALUES
  ('10x40', 4.00, 0),
  ('20x20', 4.00, 0),
  ('20x40', 4.00, 0),
  ('20x80', 4.00, 0),
  ('30x60', 4.00, 0),
  ('35x35', 4.00, 0),
  ('40x40', 4.00, 0),
  ('40x80', 4.00, 0),
  ('45x45', 4.00, 0),
  ('45x90', 4.00, 0);
