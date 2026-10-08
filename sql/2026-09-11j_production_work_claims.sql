-- Zabrani prace pro watchdog automat (bot9 2026-09-11, navrh bot10,
-- schvaleno bot3/Robert po dotazu "dela nekdo na watchdogovi pro hlidani
-- botu aby si sami z tabulky vybrali praci").
--
-- UCEL: bota, ktery chce udelat jeden krok produkce (napr. doplnit
-- kusovnik/cenu jedne sestavy), musi jit ATOMICKY zjistit, jestli tenhle
-- krok uz nedela jiny bot/automat, aniz by potreboval globalni zamek
-- (DEPLOY_LOCK.json resi neco jineho - guardovane soubory pri commitu,
-- ne "kdo prave pocita cenu sestavy 334").
--
-- NENI TO DEPLOY_LOCK. DEPLOY_LOCK.json = jeden zamek pro cely git commit
-- do webapp/*|api/*.py. Tahle tabulka = zabrani PO JEDNOM CILI (sestava +
-- krok), muze jich byt zabranych soucasne libovolne mnoho. Nezamenovat.
--
-- PRINCIP ZABRANI (jeden atomicky dotaz, zadna transakce/SELECT FOR UPDATE
-- potreba):
--   INSERT INTO production_work_claims (...)
--   VALUES (...)
--   ON DUPLICATE KEY UPDATE
--     held_by     = IF(result IS NOT NULL OR released_at IS NOT NULL OR expires_at < NOW(), VALUES(held_by), held_by),
--     held_at     = IF(result IS NOT NULL OR released_at IS NOT NULL OR expires_at < NOW(), VALUES(held_at), held_at),
--     expires_at  = IF(result IS NOT NULL OR released_at IS NOT NULL OR expires_at < NOW(), VALUES(expires_at), expires_at),
--     released_at = IF(result IS NOT NULL OR released_at IS NOT NULL OR expires_at < NOW(), NULL, released_at),
--     result      = IF(result IS NOT NULL OR released_at IS NOT NULL OR expires_at < NOW(), NULL, result),
--     result_note = IF(result IS NOT NULL OR released_at IS NOT NULL OR expires_at < NOW(), NULL, result_note);
--   -- pak SELECT held_by ... - kdo tam je, ten vyhral (i kdyz to byl uz drivejsi radek).
--
-- Rad je RECLAIMOVATELNY, kdyz uz NENI aktivne drzeny (dokoncen/vzdan/
-- vyprsel) - ne jen kdyz vyprsel. Diky tomu jde tutez sestavu+krok znovu
-- zpracovat pozdeji (napr. geometricka oprava znovu vyprazdni bom), aniz
-- by rad zustaval navzdy "hotovo" a blokoval reklaim.
--
-- fail_count SE V CLAIM KROKU NEDOTYKA (neni v UPDATE seznamu vyse, MySQL
-- ho tedy necha byt) - inkrementuje ho az release s result='chyba',
-- resetuje release s result='hotovo'. Automat PRED pokusem o zabrani musi
-- sam zkontrolovat fail_count < 3 (SELECT), jinak sestavu nechava bublat
-- do watchdog badge jako "vyzaduje pohled cloveka" - viz
-- scripts/production_work_claims.py.
--
-- VIDITELNOST (ne "watchdog proces"): zadny samostatny sledovaci proces
-- neni potreba - "abandoned" radek (expires_at < NOW() AND released_at IS
-- NULL AND result IS NULL, tedy bot/automat spadl uprostred prace) se proste
-- da najit dotazem kdykoli, typicky primo v /api/admin/vyroba-sestav/prehled.
CREATE TABLE IF NOT EXISTS production_work_claims (
  target_type  VARCHAR(20)  NOT NULL COMMENT 'napr. assembly, karta',
  target_id    INT          NOT NULL,
  step_key     VARCHAR(40)  NOT NULL COMMENT 'napr. bom_backfill, kolizni_sweep',
  held_by      VARCHAR(80)  NOT NULL COMMENT 'BOT_ID (rucne) nebo automat:<step_key>',
  held_at      DATETIME     NOT NULL,
  expires_at   DATETIME     NOT NULL,
  released_at  DATETIME     NULL,
  result       VARCHAR(20)  NULL COMMENT 'hotovo | chyba | vzdano',
  result_note  VARCHAR(300) NULL,
  fail_count   INT          NOT NULL DEFAULT 0,
  PRIMARY KEY (target_type, target_id, step_key),
  KEY idx_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
