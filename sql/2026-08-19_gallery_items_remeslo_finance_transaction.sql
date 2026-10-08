-- Řemeslo - modul 10b Finance (viz sql/2026-08-19_remeslo_finance_
-- transactions.sql): rozšíření ENUM sloupce content_gallery_items.
-- owner_type o novou hodnotu 'remeslo_finance_transaction' (foto
-- dokladu -> náklad, stejný "připojitelný" vzor jako u ostatních
-- Řemeslo typů).
--
-- Nalezeno vlastním testem (bot14, 2026-08-19): přidání owner_type do
-- api/gallery_items.py OWNER_TYPES samo o sobě NESTAČÍ - sloupec je v
-- DB skutečný ENUM, ne jen validovaný v Pythonu, takže bez týhle
-- migrace insert spadne na "Data truncated for column 'owner_type'"
-- (MySQL potichu neroste ENUM podle Python kódu).
--
-- Použití: python api/db_migrate.py sql/2026-08-19_gallery_items_remeslo_finance_transaction.sql

ALTER TABLE content_gallery_items
    MODIFY COLUMN owner_type ENUM(
        'category','product','document','stock_movement','po_item',
        'order','inbox','lead','homepage_block','sidebar_block',
        'remeslo_job','remeslo_job_material','remeslo_craftsman_public',
        'remeslo_finance_transaction'
    ) NOT NULL;
