-- Stitek umisteni v aute pro shop_products (WORKFLOW.md pravidlo 51,
-- Robert 2026-09-24 pres bot3: "kazda sestava do auta musi nest stitek
-- na jakou stranu auta je navrzena: leva / prava / prepazka / podlaha /
-- vysuv z auta"). Mapuje se 1:1 na existujici cislenik regal_umisteni
-- (RL/RP/RK/DP/VZ/VB/VP), zadny novy se nezavadi - viz
-- sql/2026-09-13_regal_umisteni.sql. Stejne jmeno sloupce jako
-- product_assemblies.umisteni_id (sql/2026-09-13_regal_umisteni.sql,
-- radek 77-78), pro konzistenci napric obema vetvemi.
--
-- Duvod, proc na shop_products (ne jen na Vandr): rule 51 plati pro OBE
-- vetve; nativni sestavy uz maji product_assemblies.umisteni_id, ale
-- Vandr karty (shop_products.sku LIKE 'VD-%') zadnou vazbu na
-- product_assemblies nemaji (viz scripts/2026-09-22_vandr_fbx_watcher.py
-- docstring: "Vandr karty product_assemblies vubec nemaji").
--
-- NULL = zatim neurceno (napr. u Vandr karty ambiguous left_part_id +
-- right_part_id soucasne, nebo zadna shoda ve vandrawee_work) - NIKDY
-- tichy default, viz backfill scripts/2026-09-24_vandr_umisteni_backfill.py.
ALTER TABLE shop_products
  ADD COLUMN umisteni_id INT NULL,
  ADD CONSTRAINT fk_sp_umisteni FOREIGN KEY (umisteni_id) REFERENCES regal_umisteni(id);
