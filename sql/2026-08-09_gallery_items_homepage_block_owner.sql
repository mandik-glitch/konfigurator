-- Robert: "na dlaždici mozaiky homepage, chceme umět vložit obrazek,
-- video, apd takze je potreba jednoduchý editor"
--
-- Homepage-block editor (Quill, viz webapp/admin.html hpbQuillImageHandler)
-- nahrava vlozene obrazky pres stejny obecny content_gallery_items
-- mechanismus jako kategorie (owner_type/owner_id), jen s novym
-- owner_type "homepage_block" - ten je treba pridat do ENUM sloupce,
-- jinak MySQL vraci "Data truncated for column 'owner_type'".
ALTER TABLE content_gallery_items
  MODIFY owner_type ENUM('category','product','document','stock_movement','po_item','order','inbox','lead','homepage_block') NOT NULL;
