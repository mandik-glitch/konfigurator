-- Řemeslo - Modul 4 (ověřování řemeslníka), 1. iterace - bot14, 2026-08-19.
-- Viz REMESLO_KONCEPT.md "Modul 4" + "Návrh implementace 1. iterace"
-- (schváleno bot3/Robertem, vč. platnosti per check_type - DPH check
-- kratší revalidace než ostatní).
--
-- !!! DB "Remeslnik" - aplikovat VYHRADNE pres:
--     python api/db_migrate_remeslo.py sql/2026-08-19_remeslo_verification_checks.sql
-- (db_migrate.py remeslo_* migrace odmitne - miri na hlavni DB).
--
-- check_type - pásmo A (automatické, plní worker):
--   'ares_existence' | 'rzp_zivnost' | 'isir_insolvence' | 'dph_nespolehlivy'
-- check_type - pásmo B (evidence doložení, plní admin ručně):
--   'bezuhonnost' | 'bezdluznost_fu' | 'bezdluznost_cssz' | 'bezdluznost_zp'
--   | 'pojisteni_odpovednosti' | 'odborna_zpusobilost'
--
-- status: 'ceka' (fronta/registr zatím neodpověděl - selhání dotazu
--   NENÍ 'neproslo', zásada 3) / 'proslo' / 'neproslo' / 'netyka_se'
--   (např. DPH check u neplátce) / 'dolozeno' (pásmo B - záměrně
--   odlišené od 'proslo': appka NEověřila obsah, jen eviduje doložení).
--
-- UNIQUE (craftsman_id, check_type) - 1 aktuální stav na kontrolu,
-- historie běhů se v 1. iteraci nearchivuje. VÝJIMKA 'odborna_
-- zpusobilost' (více certifikátů na osobu) se řeší v aplikační logice
-- sloupcem seq (0 pro všechny unikátní typy, inkrement jen u odborné
-- způsobilosti) - unique klíč je proto trojice s seq.
--
-- checked_by je obyčejný INT bez FK (app_users žije v hlavní DB,
-- cross-database FK nejde - stejný vzor jako author_user_id jinde).

CREATE TABLE IF NOT EXISTS remeslo_verification_checks (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    craftsman_id     INT NOT NULL,
    check_type       VARCHAR(50) NOT NULL,
    seq              INT NOT NULL DEFAULT 0,
    status           VARCHAR(20) NOT NULL DEFAULT 'ceka',
    source           VARCHAR(20) NOT NULL DEFAULT 'auto',
    result_detail    TEXT NULL,
    evidence_note    TEXT NULL,
    attempts         INT NOT NULL DEFAULT 0,
    last_attempt_at  DATETIME NULL,
    checked_by       INT NULL,
    checked_at       DATETIME NULL,
    valid_until      DATETIME NULL,
    created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_remeslo_verif_craftsman
        FOREIGN KEY (craftsman_id) REFERENCES remeslo_craftsmen(id) ON DELETE CASCADE,
    UNIQUE KEY uq_craftsman_check (craftsman_id, check_type, seq),
    KEY idx_status (status),
    KEY idx_valid_until (valid_until)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
