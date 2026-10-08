-- Grace period pro stare davky otocneho nahledu (bot3/Robert 2026-09-02,
-- pres bot16): commit nove davky uz starou davku nesmaze hned (navstevnik
-- s otevrenou strankou uprostred otacky by dostal 404 na dalsi snimek) -
-- jen ji DEAKTIVUJE (is_active=0, jak uz delal) a k tomu ted navic
-- zaznamena kdy. Fyzicke smazani (radky + soubory) az po 24 h bez
-- aktivity - viz api/turntable.py _sweep_expired_batches, volana z
-- commit endpointu i ze scripts/turntable_cleanup.py (budouci cron).
-- NULL = davka jeste nebyla nikdy deaktivovana (aktivni, nebo nedokonceny
-- upload, ktery se aktivnim nikdy nestal).

ALTER TABLE product_turntable_frames
    ADD COLUMN deactivated_at DATETIME NULL DEFAULT NULL AFTER is_active;
