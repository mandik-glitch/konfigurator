-- Technické schválení produktové sestavy (Robert 2026-09-11).
--
-- Doslova: "zatržítko na každý řádek, které znamená moje schválení sestavy
-- po technické stránce jak vypadá, cena se bude řešit zvlášť."
--
-- POZOR, JSOU TO DVĚ RŮZNÁ SCHVÁLENÍ - nezaměňovat:
--
--   1. `technicky_ok` (tenhle sloupec) = Robert potvrzuje SKLADBU FYZICKÝCH
--      DÍLŮ, tedy že sestava vypadá, jak má. Zaškrtává se přímo ve scéně,
--      v panelu Produktové sestavy, na řádku sestavy. Netýká se ceny.
--
--   2. `category_id IS NOT NULL` = sestava je přeřazená ze složky
--      "Nezařazená" a tím schválená k renderům a publikaci
--      (WORKFLOW.md pravidlo 24). To zůstává beze změny.
--
-- Sestava tedy může být technicky schválená a přitom ještě nezařazená -
-- a to je normální mezistav: geometrie sedí, ale ještě se neposílá dál.

ALTER TABLE product_assemblies
  ADD COLUMN technicky_ok TINYINT(1) NOT NULL DEFAULT 0 AFTER is_public,
  ADD COLUMN technicky_ok_at DATETIME NULL AFTER technicky_ok,
  ADD COLUMN technicky_ok_by INT NULL AFTER technicky_ok_at;
