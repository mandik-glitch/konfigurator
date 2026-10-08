-- Zakaznicky text pro katalogove dimenze regalu (bot5, 2026-09-13).
--
-- TEXT_FILTR.md pravidlo 13 (Robert, doslova): "Popis v detailu produktové
-- sestavě musí korespondovat s vybranou variantou, tzn. popisy jsou
-- dynamické podle vybrané sestavy."
--
-- KDE TEXT BYDLI, A PROC NE NA product_assemblies: per-variantni popis se
-- neuklada na jednotlivou sestavu (to by znamenalo rucne psat text pro
-- KAZDOU kombinaci na KAZDE karte - 7 dnes, az 18 na kartu, krat N
-- budoucich vozidel). Misto toho se pise JEDNOU na katalogovou dimenzi
-- (horni_blok_varianty / typologie_varianty) - stejna filozofie jako
-- `kod_sestavy` ("pravdou jsou pole, kod je jen zapis"): text se sklada
-- serverem podle toho, ktere `horni_blok_varianta_id`/`typologie_varianta_id`
-- ma konkretni sestava, a funguje automaticky na kazde budouci karte, co
-- tu kombinaci pouzije.
--
-- Sloupce jsou NULLable a nic nevynucuji - dokud text nekdo nenapise,
-- dynamicka cast se proste nezobrazi (stejny bezpecny vzor jako
-- `sestavit_kod_sestavy()`, ktery pri chybejicim vstupu vraci None misto
-- pádu).

ALTER TABLE horni_blok_varianty
  ADD COLUMN popis_zakaznicky TEXT NULL
  COMMENT 'Zakaznicka veta popisujici tuto katalogovou variantu (TEXT_FILTR.md pravidlo 13) - NE interni text z lisi_se, ktery zminuje jmena/interni kody';

ALTER TABLE typologie_varianty
  ADD COLUMN popis_zakaznicky TEXT NULL
  COMMENT 'Zakaznicka veta popisujici konfiguraci boxu teto varianty (TEXT_FILTR.md pravidlo 13)';
