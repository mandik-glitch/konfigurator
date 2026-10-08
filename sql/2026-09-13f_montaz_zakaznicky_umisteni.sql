-- Zakaznicky text pro montaz, navazany na UMISTENI, ne na horni blok/typologii.
--
-- TEXT_FILTR.md pravidlo 12 (montaz jako oddelena cast) + doplneni pravidla
-- 13 (Robert pres bot9, 2026-09-13, doslova): "Stejné pravidlo platí i pro
-- popis ohledně montáže."
--
-- PROC NA regal_umisteni, NE na horni_blok_varianty/typologie_varianty (kam
-- putuje `popis_zakaznicky`, viz 2026-09-13e): montaz se fyzicky lisi tim,
-- KAM se regal kotvi (bocnice+podlaha u RL/RP, jinam u RK/DP/VZ/VB/VP), ne
-- tim, co je postavene NAD euroboxy. Zavest to na horni_blok_varianty by
-- vyzadovalo tvrdit, jestli vyssi/tezsi provedeni potrebuje jine kotevni
-- body - to neni overene, tedy fabrikace (TEXT_FILTR pravidlo 3).
--
-- Sloupec je NULLable a nic nevynucuje - u umisteni bez urceneho obsahu
-- (DP/VZ/VB/VP maji v `regal_umisteni.popis` doslova "obsah/detaily zatim
-- neurceny") zustava prazdny, dokud nekdo napise overeny text.

ALTER TABLE regal_umisteni
  ADD COLUMN montaz_zakaznicky TEXT NULL
  COMMENT 'Zakaznicka veta o montazi pro tohle umisteni (TEXT_FILTR.md pravidla 12+13) - fyzicky zavisi na tom, KAM se regal kotvi, ne na obsahu horniho bloku';
