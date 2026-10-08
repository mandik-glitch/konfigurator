-- Remeslo modul 9 - dalsi remeslna profese: Strechy (bot11, 2026-08-19).
-- ORIENTACNI MATERIALOVY ODHAD KRYTINY, ne navrh krovu/statiky - nosnou
-- konstrukci (krov) musi navrhnout opravnena osoba, kalkulacka pocita
-- jen kryci material z plochy. Krov (rezivo krokvi/pozednic) VEDOME
-- mimo v1 - viz api/remeslo.py _calc_strechy() docstring pro citovane
-- zdroje koeficientu (Bramac/Tondach pres krytiny-strechy.cz +
-- technicke listy, late/kontralate strechy-vyzlovka.cz +
-- stavimbydlim.cz, hrebenace dek.cz produktove listy).
-- Cenik kategorie "Strechy" uz existuje
-- (sql/2026-08-19_remeslo_pricelist.sql), tady jen typ kalkulacky.
--
-- Pouziti: python api/db_migrate_remeslo.py sql/2026-08-19_remeslo_calculator_strechy.sql

INSERT IGNORE INTO remeslo_calculator_types (code, name, is_system) VALUES
    ('strechy', 'Střechy', 1);
