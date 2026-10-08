-- Robert (pres bot16), 2026-09-13, doslova: "vyber montáže klientem:
-- v Praze nebo ve Slavičíně, povinný výběr." - kdyz zakaznik zaskrtne
-- montaz (viz sql/2026-09-13h_...sql), MUSI navic vybrat MISTO montaze.
-- Dve pevne hodnoty (kody 'praha'/'slavicin', popisky viz
-- api/product_assemblies.py::MONTAZ_MISTA) - zadna nova admin-editovatelna
-- tabulka, Robert dal dve konkretni jmena, ne obecny koncept "seznam
-- provozoven".

ALTER TABLE shop_cart_items
  ADD COLUMN montaz_misto VARCHAR(20) NULL COMMENT 'misto montaze (praha/slavicin) - povinne kdyz montaz_zvolena=1';

ALTER TABLE shop_order_items
  ADD COLUMN montaz_misto_snapshot VARCHAR(20) NULL COMMENT 'misto montaze v okamziku objednani';
