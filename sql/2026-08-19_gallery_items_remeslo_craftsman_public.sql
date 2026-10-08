-- Řemeslo - Modul 7 část A (viz sql/2026-08-19_remeslo_public_profile.sql):
-- rozšíření ENUM sloupce content_gallery_items.owner_type o novou
-- hodnotu 'remeslo_craftsman_public' (ukázky práce na veřejném
-- profilu řemeslníka, nahrávané PŘÍMO pro profil, ne z fotek zakázek).
--
-- Použití: python api/db_migrate.py sql/2026-08-19_gallery_items_remeslo_craftsman_public.sql

ALTER TABLE content_gallery_items
    MODIFY COLUMN owner_type ENUM(
        'category','product','document','stock_movement','po_item',
        'order','inbox','lead','homepage_block','sidebar_block',
        'remeslo_job','remeslo_job_material','remeslo_craftsman_public'
    ) NOT NULL;
