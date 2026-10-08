-- Party model, faze 5 - most k Remeslu (bot18, 2026-09-05, Robert pres
-- bot3). `party_id` NENI a NEMUZE byt vynucena cizi klic - MySQL
-- nedovoluje FK pres hranici databazi (tahle tabulka zije v DB
-- "Remeslnik", `parties` v hlavni DB Konfiguratoru). Hodnota se sem
-- dostava jednosmernym idempotentnim sync skriptem
-- (scripts/2026-09-05_remeslo_party_sync.py), stejny princip jako uz
-- existujici `remeslo_craftsmen.app_user_id` (taky bez vynucene FK,
-- viz REMESLO_KONCEPT.md).
--
-- POZOR (stejna pojistka jako u ostatnich remeslo_* migraci): spoustet
-- VYHRADNE pres api/db_migrate_remeslo.py, NE db_migrate.py - jinak by
-- se sloupec tise pridal do nepouzivane kopie v hlavni DB.

ALTER TABLE remeslo_craftsmen
  ADD COLUMN party_id INT NULL AFTER app_user_id,
  ADD KEY idx_remeslo_craftsmen_party (party_id);
