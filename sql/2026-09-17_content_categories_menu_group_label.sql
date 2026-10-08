-- bot16, 2026-09-17 (Robert pres bot7, screenshot leveho menu kategorii:
-- "s tim stejnym podkladem tmava to je spatne pro orientaci cloveka" +
-- "udelat to nejak v duchu tveho navrhu" - viz KATEGORIE_VESTAVBY_
-- ARCHITEKTURA.md pro plny kontext prestavby kategorie 184).
--
-- Skupinovy nadpis NAD konkretnim uzlem stromu kategorii ("PODLE
-- VOZIDLA" nad uzlem 267, "PODLE TYPU ULOZISTE" nad uzlem 247) - cistě
-- vizualni popisek v menu, NENI to vlastni klikatelna kategorie/URL.
-- Datove rizeny sloupec (ne hardcoded ID v kodu), aby bot7 mohl skupiny
-- pridavat/menit i jinde ve stromu bez zasahu do kodu.
ALTER TABLE content_categories
  ADD COLUMN menu_group_label VARCHAR(60) NULL AFTER nav_label;

UPDATE content_categories SET menu_group_label = 'PODLE VOZIDLA' WHERE id = 267;
UPDATE content_categories SET menu_group_label = 'PODLE TYPU ÚLOŽIŠTĚ' WHERE id = 247;
