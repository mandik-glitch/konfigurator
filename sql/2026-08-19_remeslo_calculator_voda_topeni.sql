-- Remeslo modul 9 - dalsi remeslna profese: Voda/topeni (bot11, 2026-08-19).
-- Zamereno na podlahove topeni (jednodussi/lepe zdrojovatelne nez
-- kompletni rozvod vody se vsemi fitinky - viz api/remeslo.py
-- _calc_voda_topeni() docstring pro citovane zdroje koeficientu
-- (Wavin + REHAU-kompatibilni vypocet z kolikmaterialu.cz). Cenik
-- kategorie "Voda/topení" uz existuje (sql/2026-08-19_remeslo_pricelist.sql),
-- tady jen pridavame typ kalkulacky.
--
-- Pouziti: python api/db_migrate_remeslo.py sql/2026-08-19_remeslo_calculator_voda_topeni.sql

INSERT IGNORE INTO remeslo_calculator_types (code, name, is_system) VALUES
    ('voda_topeni', 'Voda/topení', 1);
