-- Remeslo modul 9 - dalsi remeslna profese: Zdeni (bot11, 2026-08-19).
-- Viz api/remeslo.py _calc_zdeni() pro vypocetni logiku a citovane
-- zdroje koeficientu (Wienerberger/Porotherm + nezavisle overeno
-- Xella/Ytong). Ceník kategorie "Zdění" uz existuje
-- (sql/2026-08-19_remeslo_pricelist.sql), tady jen pridavame typ
-- kalkulacky.
--
-- Pouziti: python api/db_migrate.py sql/2026-08-19_remeslo_calculator_zdeni.sql

INSERT IGNORE INTO remeslo_calculator_types (code, name, is_system) VALUES
    ('zdeni', 'Zdění', 1);
