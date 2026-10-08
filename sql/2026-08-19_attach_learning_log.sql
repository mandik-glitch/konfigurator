-- bot8 2026-08-19: trvala DB evidence uceni napojovani (Robert: "ja hlavne
-- chci aby se to uceni ukladalo do DB").
--
-- Motivace (incident 18.8.-19.8.): hromadny precompute prepsal Robertovy
-- rucne naucene attach_pose (parallel_side) vzorcem jine rodiny a zapsal
-- nekolika dilum absurdni pozy (az 74 m mimo) - NIC v DB nerozlisovalo
-- "rucne nauceno a overeno Robertem" od "automaticky dopocteno", a verdikt
-- zadneho overeni se nikam trvale nezapisoval (zil jen v logu session).
--
-- 1) shop_products.attach_pose_source: puvod aktualni attach_pose.
--    'robert' = rucni uceni ve scene (🎯 Ulozit pozici) NEBO Robertem
--               vizualne potvrzena hodnota - hromadny skript ji NIKDY
--               nesmi prepsat bez vyslovneho pokynu.
--    'auto'   = automaticky dopocet/odvozeni (merenim overene, ale bez
--               vizualniho potvrzeni Robertem).
--    NULL     = neznamy puvod (historicke hodnoty pred zavedenim).
ALTER TABLE shop_products
  ADD COLUMN attach_pose_source VARCHAR(10) NULL DEFAULT NULL
  COMMENT 'puvod attach_pose: robert=rucni/potvrzene (neprepisovat), auto=dopocet';

-- 2) attach_learning_log: kazde overeni/zmena uceni napojeni = 1 radek,
--    trvale. Zadne mazani (append-only) - historie uceni je dohledatelna
--    v DB, ne v AGENTS_LOG/session.
CREATE TABLE IF NOT EXISTS attach_learning_log (
  id INT AUTO_INCREMENT PRIMARY KEY,
  product_id INT NOT NULL,
  sku VARCHAR(64) NULL,
  event VARCHAR(32) NOT NULL COMMENT 'verified_ok | pose_written | pose_restored | mode_changed | offset_cleared | geo_faces_cleared | verified_fail',
  attach_mode VARCHAR(20) NULL COMMENT 'attach_mode v okamziku zaznamu',
  detail JSON NULL COMMENT 'zmerene hodnoty (gap/overlap per osa), pouzity profil, stara/nova hodnota',
  verified_by VARCHAR(16) NOT NULL DEFAULT 'auto' COMMENT 'auto (headless mereni) | robert (vizualni potvrzeni)',
  created_by VARCHAR(16) NULL COMMENT 'bot id / admin',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_product (product_id),
  INDEX idx_event (event)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_czech_ci;
