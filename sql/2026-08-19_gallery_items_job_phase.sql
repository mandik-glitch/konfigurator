-- Řemeslo - fotodokumentace zakázky před/po (bot14, 2026-08-19).
--
-- Úkol z TASKS.md: fotky ke stavu zakázky (PŘED zahájením, průběžně,
-- PO dokončení) jako důkaz odvedené práce pro klienta i pro případný
-- spor. Zadání výslovně říká NESTAVĚT OD NULY - polymorfní
-- content_gallery_items už existuje a Řemeslo ho pro zakázky používá
-- (owner_type='remeslo_job', viz api/gallery_items.py OWNER_TYPES a
-- REMESLO_KONCEPT.md "Foto-dokumentace zakázky"). Chybí jediná věc:
-- rozlišení FÁZE, ve které fotka vznikla.
--
-- Proto jen nový sloupec, žádná nová tabulka ani nový owner_type.
--
-- POZOR - tahle migrace patří do HLAVNÍ DB (content_gallery_items tam
-- zůstala i po přesunu Řemesla na vlastní DB "Remeslnik" - vlastník
-- řádku se ověřuje přes get_remeslo_conn() v _validate_owner()).
-- Aplikovat tedy:  python api/db_migrate.py sql/2026-08-19_gallery_items_job_phase.sql
--
-- NULL = fotka bez zařazení do fáze. Je to VÝCHOZÍ a legitimní stav, ne
-- chybějící údaj:
--   - všechny fotky nahrané před touhle migrací (zpětně nevíme, do jaké
--     fáze patřily - dopisovat by znamenalo si to vymyslet),
--   - fotky u ostatních owner_type (kategorie, produkt, doklad...), kde
--     fáze nedává smysl - sloupec je pro ně trvale NULL,
--   - a fotky u zakázky, kterým řemeslník fázi prostě nepřiřadil.
ALTER TABLE content_gallery_items
    ADD COLUMN job_phase ENUM('pred', 'prubeh', 'po') NULL AFTER caption;

-- Výpis fotek zakázky se řadí podle fáze a pak podle sort_order (viz
-- gallery_items_list) - index drží ten dotaz rychlý i u zakázky s
-- desítkami fotek.
CREATE INDEX idx_gallery_owner_phase
    ON content_gallery_items (owner_type, owner_id, job_phase);
