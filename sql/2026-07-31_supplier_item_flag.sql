-- Priznak "dodavatelska polozka" na produktove karte (bot6, 2026-07-31).
--
-- Robert: hromadny import ~50-60 nakupnich polozek (material/spojovaci
-- soucastky/prepravky) od dodavatelu zjistenych z PDF seznamu - jde o
-- INTERNI nakupni material pro vyrobu, NE zbozi urcene k prodeji
-- zakaznikum v e-shopu. "Zavedeme na produktovych kartach priznaky,
-- bude to databazova promenna" - Robert vyslovne potvrdil, ze ma jit o
-- novy sloupec (ne jen skryti pres active=0, ktere uz existuje ale
-- nerozlisuje DUVOD neaktivity).
--
-- shop_products.active zustava beze zmeny (rizeni viditelnosti v
-- e-shopu) - novy sloupec je DOPLNKOVY vyznam ("proc je to tady"), ne
-- nahrada za active.
ALTER TABLE shop_products
  ADD COLUMN is_supplier_item TINYINT(1) NOT NULL DEFAULT 0
  COMMENT 'Interni nakupni polozka od dodavatele (material/soucastka pro vyrobu) - NE zbozi k prodeji zakaznikum';
