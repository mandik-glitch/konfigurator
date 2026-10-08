-- Modul 1 (bot13, 2026-08-20) - REMESLO_KONCEPT.md "Doplnek: jednotny
-- seznam dodavatelu napric Srovnavacem a Cenikem". remeslo_price_sources
-- se stava jedinym zdrojem pravdy o dodavatelich - Cenik prestava mit
-- vlastni volny text 'supplier', misto toho FK na tuhle tabulku (0
-- radku Ceniku melo supplier vyplnene - overeno zive 2026-08-20, zadna
-- migrace historickych dat neni potreba).

SET SESSION lock_wait_timeout = 10;

-- NULL = sdileny/oficialni dodavatel (prosel 5 kriterii, pouziva se
-- ve Srovnavaci), hodnota = VLASTNI dodavatel prave tohoto remeslnika
-- (mistni prodejna mimo velke site - Robertuv koncept pocita s tim,
-- ze remeslnik nakupuje i mimo overene retezce).
ALTER TABLE remeslo_price_sources
  ADD COLUMN craftsman_id INT NULL AFTER id;

-- UNIQUE(supplier_name) by kolidovalo, kdyz dva ruzni remeslnici
-- pridaji vlastniho dodavatele se stejnym nazvem - nahrazeno slozenym
-- klicem (NULL craftsman_id = porad globalne unikatni nazev mezi
-- oficialnimi dodavateli).
ALTER TABLE remeslo_price_sources
  DROP INDEX supplier_name,
  ADD UNIQUE KEY uq_source_name_per_craftsman (craftsman_id, supplier_name);

ALTER TABLE remeslo_pricelist_items
  ADD COLUMN supplier_source_id INT NULL AFTER supplier;
