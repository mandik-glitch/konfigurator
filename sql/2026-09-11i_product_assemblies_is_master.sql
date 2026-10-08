-- Zastupce karty pro prehled produktu v eshopu (Robert 2026-09-11):
-- "v prehledu produktů v eshopu bude obrazek a cena sestavy kterou vzdy
-- urcim ja u kazde karty." Byla to otevrena otazka z PLAN_TVORBY_SESTAV.md
-- ("Vyslovny priznak nositele karty (is_master)?" - "nejstarsi = zakladni"
-- se rozpadne, jakmile se zakladni sestava prestavi a ulozi znovu) - ted
-- ma konkretni duvod: bez nej neni jednoznacne, ktery obrazek/cena
-- reprezentuje kartu v prehledu, kdyz karta ma vic navazanych sestav.
--
-- NEVYNUCUJE se "prave jedna is_master=1 na shop_product_id" v DB (MySQL
-- partial/filtered UNIQUE index by potreboval generovany sloupec) -
-- hlida to appka pri zapisu (nastaveni is_master=1 u jedne sestavy
-- vynuluje is_master u ostatnich se stejnym shop_product_id, viz
-- api/product_assemblies.py).
ALTER TABLE product_assemblies
  ADD COLUMN is_master TINYINT(1) NOT NULL DEFAULT 0 AFTER technicky_ok_by;
