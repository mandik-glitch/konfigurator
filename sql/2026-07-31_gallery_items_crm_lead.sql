-- Fotky u CRM poptavek - bot5, 2026-07-31.
--
-- Robert: "Udělej implementaci fotek i do všech sekcí crm" - misto
-- vlastniho uploadu se rozsiruje uz existujici polymorfni modul
-- content_gallery_items (api/gallery_items.py, "pripojitelny k
-- libovolnemu vlastnikovi") o dalsi owner_type - presne stejny vzor,
-- jakym uz byly pridany 'document', 'stock_movement', 'po_item',
-- 'order' a 'inbox' pred timto.

ALTER TABLE content_gallery_items
  MODIFY COLUMN owner_type ENUM('category','product','document','stock_movement','po_item','order','inbox','lead') NOT NULL;
