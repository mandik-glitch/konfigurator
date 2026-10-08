-- GPS povinna u obou typu zastavky (Robert 2026-08-05: "takze zastavka
-- je bud tankovani, nebo Zakaznik. u obou se vyzaduje GPS"). Zadna data
-- v tabulce zatim nejsou (funkce nasazena dnes, jeste nepouzivana) -
-- NOT NULL jde nastavit primo bez backfillu.
ALTER TABLE fleet_trip_stops
  MODIFY COLUMN lat DECIMAL(10,7) NOT NULL,
  MODIFY COLUMN lng DECIMAL(10,7) NOT NULL;
