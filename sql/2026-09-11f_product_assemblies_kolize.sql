-- Příznak kolize z geometrického sweepu (bot16, scripts/2026-09-11_sweep_kolizni_uhelniky.cjs,
-- pravidlo v3 "kolize se rozhoduje na síti, ne na Box3"). Domluveno s
-- bot10 2026-09-11 pro "Přehled postupu v adminu" (sloupec "Kolize").
--
-- kolize_pocet: NULL = nikdy nezměřeno, 0 = změřeno a čisto, >0 = počet
-- nálezů. KRITICKÉ (bot16): NULL v UI NESMÍ vypadat jako zelená - tatáž
-- kontrola už 3x ohlásila "0 kolizí" z důvodu nesouvisejícího s čistotou
-- (chybějící GLB, záměrně přeskakovaný partner, natvrdo psaná mapa) a
-- "0 nalezeno" bylo nerozlišitelné od "nic jsem neporovnal".
--
-- kolize_detail: JSON, zapisuje se VŽDY (i pro čistou sestavu), nese
-- PODLE ČEHO se měřilo (pravidlo/režim/nástroj) - bez toho nejde poznat,
-- které řádky se musí přeměřit, až se pravidlo změní znovu (v2->v3 už se
-- to jednou stalo). Režim "verdikt" (levný, 0,16s, synchronní při uložení
-- sestavy) NEMÁ mm-pole, protože je nepočítá - nikdy nemíchat čerstvý
-- počet se starým detailem.
--
-- Rozsah dnešního sweepu je JEN úhelníky proti ostatním dílům, ne
-- všechny dvojice - sloupec proto v adminu popisuje "počet kolizních
-- úhelníků", ne kolize obecně, dokud bot16 nedoměří cenu plného pokrytí
-- všech dvojic dílů.
ALTER TABLE product_assemblies
  ADD COLUMN kolize_pocet INT NULL AFTER technicky_ok_by,
  ADD COLUMN kolize_detail JSON NULL AFTER kolize_pocet,
  ADD COLUMN kolize_checked_at DATETIME NULL AFTER kolize_detail;
