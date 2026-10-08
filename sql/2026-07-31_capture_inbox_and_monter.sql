-- Robert 2026-07-31: mobilni fotoapka (PWA /capture.html) - "kazda role
-- bude mit v mobilu instanci... fotka od kazdeho pujde ulozit podle jeho
-- role". Osobni sberny kos fotek per uzivatel + atribuce autora/role u
-- kazde fotky. "Manazer bude fotit k objednavkam" -> novy owner_type
-- 'order'. "Jeste pridame roli monter" -> nova role v app_users.

-- 1) Nova role monter (mobilni foceni v terenu - montaze).
ALTER TABLE app_users
  MODIFY COLUMN role ENUM('admin','manager','user','skladnik','ucetni','monter') NOT NULL DEFAULT 'user';

-- 2) Galerie: novy vlastnik 'order' (shop_orders) a 'inbox' (osobni
--    sberny kos - owner_id = app_users.id). Atribuce autora kazde fotky
--    (created_by/created_role - snapshot role v okamziku porizeni).
ALTER TABLE content_gallery_items
  MODIFY COLUMN owner_type ENUM('category','product','document','stock_movement','po_item','order','inbox') NOT NULL,
  ADD COLUMN created_by INT DEFAULT NULL AFTER longitude,
  ADD COLUMN created_role VARCHAR(20) DEFAULT NULL AFTER created_by;

-- 3) Opravneni: manazer bude pripojovat fotky k objednavkam (Robert) ->
--    objednavky/upravit pro roli manager. Nova role monter zatim BEZ
--    admin sekci (jen mobilni kos pres vlastni logiku, ne role_permissions).
UPDATE role_permissions SET allowed=1 WHERE role='manager' AND section='objednavky' AND action='upravit';
