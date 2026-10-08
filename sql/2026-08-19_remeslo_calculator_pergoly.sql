-- Remeslo modul 9 - posledni z 5 dalsich remeslnych profesi: Pergoly
-- (bot11, 2026-08-19). Viz api/remeslo.py _calc_pergoly() pro
-- vypocetni logiku a citovane zdroje koeficientu (hornbach.cz +
-- ispas.cz navody, nezavisle potvrzeno planstavby.cz kalkulackou
-- materialu pergoly; spotreba impregnace Lazurol/Herbol/PNZ/Remmers).
-- Ceník kategorie "Pergoly" uz existuje
-- (sql/2026-08-19_remeslo_pricelist.sql), tady jen pridavame typ
-- kalkulacky.
--
-- Pouziti: python api/db_migrate_remeslo.py sql/2026-08-19_remeslo_calculator_pergoly.sql

INSERT IGNORE INTO remeslo_calculator_types (code, name, is_system) VALUES
    ('pergoly', 'Pergoly', 1);
