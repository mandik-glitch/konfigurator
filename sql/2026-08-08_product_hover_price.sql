-- "Hover okno produktu" (bot4, 2026-08-08).
--
-- Robert: "změna zobrazování ceny v přehledu produktů.... dej do
-- skladových karet zatržítka, Cena je videt, cena není vidět. Cena je
-- vidět, znamená standardní stávající zobrazení produktu. Když není
-- vidět, znamená to druhou cestu zobrazení a sice po najetí myší na
-- okno produktu. Pojmenujme to Hover okno produktu ... Bude jako nová
-- záložka ve skladových kartách a tam si zatržítkama vydefinujeme co
-- je vidět, např cena, dostupnost".
--
-- price_visible_default: hlavni prepinac "Cena je vidět" (1, vychozi -
-- beze zmeny puvodniho chovani pro vsechny stavajici produkty) /
-- "Cena není vidět" (0 - cena/dostupnost na karte v mrizce kategorie
-- zmizi z trvaleho zobrazeni a presunou se do hover panelu).
-- hover_show_price/hover_show_availability: co presne se ma v hover
-- panelu zobrazit, kdyz je price_visible_default=0 - samostatne
-- zatrzitka, at jde v budoucnu pridat dalsi bez dalsi migrace.
ALTER TABLE shop_products ADD COLUMN price_visible_default TINYINT(1) NOT NULL DEFAULT 1 AFTER availability_text;
ALTER TABLE shop_products ADD COLUMN hover_show_price TINYINT(1) NOT NULL DEFAULT 1 AFTER price_visible_default;
ALTER TABLE shop_products ADD COLUMN hover_show_availability TINYINT(1) NOT NULL DEFAULT 0 AFTER hover_show_price;
