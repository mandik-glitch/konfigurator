-- Řemeslo - itemizovaná evidence materiálu (viz sql/2026-08-19_remeslo_
-- job_materials.sql): rozšíření ENUM sloupce content_gallery_items.
-- owner_type o novou hodnotu 'remeslo_job_material' (foto k jednotlivé
-- položce materiálu, stejný "připojitelný" vzor jako u zakázky samotné
-- - owner_type='remeslo_job').
--
-- Použití: python api/db_migrate.py sql/2026-08-19_gallery_items_remeslo_job_material.sql

ALTER TABLE content_gallery_items
    MODIFY COLUMN owner_type ENUM(
        'category','product','document','stock_movement','po_item',
        'order','inbox','lead','homepage_block','sidebar_block',
        'remeslo_job','remeslo_job_material'
    ) NOT NULL;
