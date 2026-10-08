-- Řemeslo - "Denní zásobník" hlasových poznámek (bot13, 2026-08-19).
-- Viz REMESLO_KONCEPT.md "Denní zásobník" -> "Návrh (bot13...)" pro
-- plné zdůvodnění (schváleno Robertem přes bot3).
--
-- Cutover na DB "Remeslnik" dokončen bot14 (91af721) - APLIKOVÁNO
-- bot13, 2026-08-19 přes api/db_migrate_remeslo.py (REMESLO_DB_*).
--
-- Rozšiřuje remeslo_voice_notes (NE nová tabulka - viz zdůvodnění v
-- KONCEPTu: každá nahrávka prochází stejným cyklem upload->fronta->
-- přepis, volná poznámka jen potřebuje krok navíc). Nové sloupce jsou
-- NULL-friendly / mají bezpečný default, takže stávající řádky
-- (všechny dnes 'wizard_step') zůstanou beze změny chování.
--
-- `reviewed_by` NEMÁ FK constraint na app_users (na rozdíl o návrhu
-- před cutoverem) - `app_users` žije ve sdílené hlavní DB, "Remeslnik"
-- je JINÁ databáze na stejném hostu, cross-database FOREIGN KEY v
-- MySQL/InnoDB nejde (chyba 1824, ověřeno při pokusu). Stejný případ
-- jako už existující `created_by` na tomhle stole - bot14 ho při
-- cutoveru (91af721) z FK constraintu vypustila, sloupec zůstal jako
-- obyčejný nevynucený INT (viz `SHOW CREATE TABLE`). `reviewed_by`
-- jde stejnou cestou pro konzistenci, jen s indexem místo constraintu.
--
-- Použití: python api/db_migrate_remeslo.py sql/2026-08-19_remeslo_voice_notes_inbox.sql

ALTER TABLE remeslo_voice_notes
    ADD COLUMN capture_mode ENUM('wizard_step','free_note') NOT NULL DEFAULT 'wizard_step' AFTER craftsman_id,
    ADD COLUMN proposed_type ENUM('job_note','invoice_draft','unclear') NULL AFTER transcript,
    ADD COLUMN proposed_job_id INT NULL AFTER proposed_type,
    ADD COLUMN proposed_reasoning VARCHAR(255) NULL AFTER proposed_job_id,
    ADD COLUMN review_status ENUM('pending','approved','rejected') NULL AFTER proposed_reasoning,
    ADD COLUMN reviewed_by INT NULL AFTER review_status,
    ADD COLUMN reviewed_at DATETIME NULL AFTER reviewed_by,
    ADD CONSTRAINT fk_rvn_proposed_job
        FOREIGN KEY (proposed_job_id) REFERENCES remeslo_jobs(id) ON DELETE SET NULL,
    ADD KEY idx_rvn_reviewed_by (reviewed_by),
    ADD KEY idx_rvn_capture_mode (capture_mode),
    ADD KEY idx_rvn_review_status (review_status);
