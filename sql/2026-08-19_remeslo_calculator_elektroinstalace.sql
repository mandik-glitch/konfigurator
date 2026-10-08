-- Remeslo modul 9 - dalsi remeslna profese: Elektroinstalace (bot11, 2026-08-19).
-- ORIENTACNI MATERIALOVY ODHAD, ne navrh elektroinstalace - dimenzovani/
-- jisteni/revize dela opravnena osoba dle CSN, viz api/remeslo.py
-- _calc_elektroinstalace() docstring pro citovane zdroje koeficientu
-- (CSN 33 2130 ed. 3 pres elektroprumysl.cz + naradilibochovice.cz,
-- delka trasy na bod odvozena ze 2 nezavislych praktickych zdroju).
-- Cenik kategorie "Elektroinstalace" uz existuje
-- (sql/2026-08-19_remeslo_pricelist.sql), tady jen typ kalkulacky.
--
-- Pouziti: python api/db_migrate_remeslo.py sql/2026-08-19_remeslo_calculator_elektroinstalace.sql

INSERT IGNORE INTO remeslo_calculator_types (code, name, is_system) VALUES
    ('elektroinstalace', 'Elektroinstalace', 1);
