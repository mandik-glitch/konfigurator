-- Modul 11 (bot13, 2026-08-19) - REMESLO_KONCEPT.md
-- Samoobsluzna registrace remeslnika: vazba na app_users, profese
-- navazana na remeslo_calculator_types (14 typu), personalizace
-- vychozich/eminentnich kalkulacek per profese. Idempotentni -
-- IF NOT EXISTS / INSERT IGNORE, ale FK/UNIQUE ADD COLUMN nejde
-- IF NOT EXISTS v teto verzi MySQL - spustit jen jednou (stejna
-- disciplina jako ostatni sql/2026-08-19_remeslo_*.sql soubory).
--
-- Kratky lock_wait_timeout (bot13, 2026-08-19, po zivem incidentu):
-- prvni pokus o tenhle ALTER visel 280+s na "Waiting for table
-- metadata lock" a blokoval frontu za sebou (mj. verejnou stranku
-- remeslnik.pro - "SELECT ... FROM remeslo_craftsmen JOIN remeslo_
-- professions" cekala tez). Radeji rychle selhat a zkusit znovu, nez
-- drzet frontu dlouho.
SET SESSION lock_wait_timeout = 10;

-- remeslo_craftsmen.app_user_id uz aplikovano (prvni beh 2026-08-19,
-- ktery pak zaseknul frontu na druhem ALTERu nize - viz komentar u
-- lock_wait_timeout) - NEOPAKOVAT, "Duplicate column name" by presly
-- v cyklu az sem znova.

ALTER TABLE remeslo_professions
  ADD COLUMN calculator_type_id INT NULL UNIQUE,
  ADD CONSTRAINT fk_profession_calc_type FOREIGN KEY (calculator_type_id)
      REFERENCES remeslo_calculator_types(id);

-- Existujici radek "Instalater (voda, topeni)" napojit na
-- calculator_type 'voda_topeni' - kodova rada (prefix INST,
-- next_seq) zustava beze zmeny.
UPDATE remeslo_professions p
JOIN remeslo_calculator_types t ON t.code = 'voda_topeni'
SET p.calculator_type_id = t.id
WHERE p.code_prefix = 'INST';

-- Zbylych 13 profesi - jedna na kazdy dalsi calculator_type. Prefixy
-- rucne zvoleny (kolize by auto-zkraceni nazvu snadno zpusobilo -
-- "Zamkova dlazba" / "Zemni prace" by se srazily na stejnou zkratku).
INSERT INTO remeslo_professions (name, slug, code_prefix, calculator_type_id)
SELECT 'Dlaždič (zámková dlažba)', 'dlazdic-dlazba', 'DLA', id FROM remeslo_calculator_types WHERE code = 'zamkova_dlazba';
INSERT INTO remeslo_professions (name, slug, code_prefix, calculator_type_id)
SELECT 'Obkladač', 'obkladac', 'OBK', id FROM remeslo_calculator_types WHERE code = 'obklady_dlazby';
INSERT INTO remeslo_professions (name, slug, code_prefix, calculator_type_id)
SELECT 'Malíř', 'malir', 'MAL', id FROM remeslo_calculator_types WHERE code = 'malovani';
INSERT INTO remeslo_professions (name, slug, code_prefix, calculator_type_id)
SELECT 'Sádrokartonář', 'sadrokartonar', 'SDK', id FROM remeslo_calculator_types WHERE code = 'sadrokarton';
INSERT INTO remeslo_professions (name, slug, code_prefix, calculator_type_id)
SELECT 'Podlahář', 'podlahar', 'POD', id FROM remeslo_calculator_types WHERE code = 'podlahy';
INSERT INTO remeslo_professions (name, slug, code_prefix, calculator_type_id)
SELECT 'Fasádník (zateplení)', 'fasadnik', 'FAS', id FROM remeslo_calculator_types WHERE code = 'fasada_zatepleni';
INSERT INTO remeslo_professions (name, slug, code_prefix, calculator_type_id)
SELECT 'Betonář', 'betonar', 'BET', id FROM remeslo_calculator_types WHERE code = 'betonaz';
INSERT INTO remeslo_professions (name, slug, code_prefix, calculator_type_id)
SELECT 'Zemní práce', 'zemni-prace', 'ZEM', id FROM remeslo_calculator_types WHERE code = 'zemni_prace';
INSERT INTO remeslo_professions (name, slug, code_prefix, calculator_type_id)
SELECT 'Univerzální řemeslník', 'univerzalni-remeslnik', 'UNIV', id FROM remeslo_calculator_types WHERE code = 'univerzalni';
INSERT INTO remeslo_professions (name, slug, code_prefix, calculator_type_id)
SELECT 'Zedník', 'zednik', 'ZED', id FROM remeslo_calculator_types WHERE code = 'zdeni';
INSERT INTO remeslo_professions (name, slug, code_prefix, calculator_type_id)
SELECT 'Elektrikář', 'elektrikar', 'ELE', id FROM remeslo_calculator_types WHERE code = 'elektroinstalace';
INSERT INTO remeslo_professions (name, slug, code_prefix, calculator_type_id)
SELECT 'Pokrývač (střechy)', 'pokryvac', 'POK', id FROM remeslo_calculator_types WHERE code = 'strechy';
INSERT INTO remeslo_professions (name, slug, code_prefix, calculator_type_id)
SELECT 'Truhlář/tesař (pergoly)', 'truhlar-tesar', 'TRU', id FROM remeslo_calculator_types WHERE code = 'pergoly';

CREATE TABLE remeslo_profession_calculator_defaults (
    profession_id       INT NOT NULL,
    calculator_type_id  INT NOT NULL,
    is_default           TINYINT(1) NOT NULL DEFAULT 0,
    prominence           INT NOT NULL DEFAULT 0,
    PRIMARY KEY (profession_id, calculator_type_id),
    CONSTRAINT fk_pcd_profession FOREIGN KEY (profession_id) REFERENCES remeslo_professions(id),
    CONSTRAINT fk_pcd_calc_type FOREIGN KEY (calculator_type_id) REFERENCES remeslo_calculator_types(id)
);

-- Seed: kazda profese ma vlastni 1:1 kalkulacku jako vychozi/eminentni.
INSERT INTO remeslo_profession_calculator_defaults (profession_id, calculator_type_id, is_default, prominence)
SELECT p.id, p.calculator_type_id, 1, 100
FROM remeslo_professions p
WHERE p.calculator_type_id IS NOT NULL;

-- Seed: univerzalni kalkulacka eminentni (ale ne pripnuta jako
-- vychozi) pro VSECHNY profese, i tu, jejiz vlastni typ uz univerzalni
-- je (tam UNIQUE PRIMARY KEY konflikt - proto NOT IN podminka nize).
INSERT INTO remeslo_profession_calculator_defaults (profession_id, calculator_type_id, is_default, prominence)
SELECT p.id, t.id, 0, 50
FROM remeslo_professions p
JOIN remeslo_calculator_types t ON t.code = 'univerzalni'
WHERE p.calculator_type_id IS NULL OR p.calculator_type_id != t.id;
