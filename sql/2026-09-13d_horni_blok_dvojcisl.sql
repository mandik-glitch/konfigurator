-- Rozsireni horni_blok_varianty.kod na dvojcislo (bot9, 2026-09-13,
-- Robert primo v chatu: "dej mu dvojcifernost, varianty pribudou").
--
-- Dnesnich sedm provedeni (0-6) se jen zleva doplni nulou (0 -> 00,
-- 3 -> 03, ...), aby bylo od zacatku misto na dalsi provedeni bez
-- dalsi zmeny sirky sloupce/formatu kodu.
-- MODIFY sam o sobe zachova puvodni UNIQUE index na sloupci (jen se
-- zmeni sirka), overeno pred zapisem pres SHOW INDEX.
ALTER TABLE horni_blok_varianty MODIFY kod CHAR(2) NOT NULL;

UPDATE horni_blok_varianty SET kod = LPAD(kod, 2, '0');
