-- Řemeslo - modul 8a (bot13, 2026-08-19, na zadání Roberta přes bot3,
-- po živém průzkumu remeslnik.online): Nastavení -> Firemní profil.
-- Viz REMESLO_KONCEPT.md "Modul 8a" pro plný kontext.
--
-- Rozšíření existující remeslo_craftsmen (ne nová tabulka - řemeslník
-- v ní už má jméno/firmu/adresu/kontakty, tohle jen doplňuje
-- identifikační údaje podle typu subjektu + "vzhled dokumentů").
--
-- subject_type mění, která identifikační pole jsou POVINNÁ na
-- frontendu/API (viz REMESLO_KONCEPT.md) - žádná DB-level validace
-- navíc.
--
-- Použití: python api/db_migrate.py sql/2026-08-19_remeslo_craftsman_profile.sql

ALTER TABLE remeslo_craftsmen
    ADD COLUMN subject_type ENUM('osvc','firma','jiny') NOT NULL DEFAULT 'osvc' AFTER company_name,
    ADD COLUMN ico VARCHAR(20) NULL AFTER subject_type,
    ADD COLUMN dic VARCHAR(20) NULL AFTER ico,
    ADD COLUMN subject_type_other_label VARCHAR(120) NULL AFTER dic,
    ADD COLUMN doc_accent_color VARCHAR(7) NULL AFTER note,
    ADD COLUMN doc_footer_note TEXT NULL AFTER doc_accent_color;
