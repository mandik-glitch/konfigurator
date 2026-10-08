-- Strom geometrickych pravidel (Robert 2026-09-21: "udelej to jako strom,
-- podle vyznamu ty pravidla" + "at se stejne shlukuji do jedne vetve").
--
-- Zarazeni je DATA, ne zadratovana struktura v kodu - aby sel strom kdykoli
-- prerovnat ze stejne obrazovky jako zneni pravidel. Format je CESTA
-- oddelena lomitkem, max 2 urovne: "Horni blok/Rozmery a pasma".
-- Prazdna/NULL kategorie = vetev "Nezarazene" (nic se neztrati).
ALTER TABLE shape_geometry_methods
  ADD COLUMN kategorie VARCHAR(120) NULL COMMENT 'cesta ve stromu, lomitko = uroven',
  ADD COLUMN poradi INT NOT NULL DEFAULT 100 COMMENT 'razeni uvnitr vetve';

ALTER TABLE car_body_placement_methods
  ADD COLUMN kategorie VARCHAR(120) NULL COMMENT 'cesta ve stromu, lomitko = uroven',
  ADD COLUMN poradi INT NOT NULL DEFAULT 100 COMMENT 'razeni uvnitr vetve';
