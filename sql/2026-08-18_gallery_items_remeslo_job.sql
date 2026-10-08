-- Řemeslo - modul 2 (evidence zakázek): rozšíření ENUM sloupce
-- content_gallery_items.owner_type o novou hodnotu 'remeslo_job'
-- (foto-dokumentace zakázky, viz api/gallery_items.py, api/remeslo.py).
--
-- Použití: python api/db_migrate.py sql/2026-08-18_gallery_items_remeslo_job.sql

ALTER TABLE content_gallery_items
    MODIFY COLUMN owner_type ENUM(
        'category','product','document','stock_movement','po_item',
        'order','inbox','lead','homepage_block','sidebar_block','remeslo_job'
    ) NOT NULL;
