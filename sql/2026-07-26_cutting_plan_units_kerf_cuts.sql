-- Doplneni shop_cutting_plan_units o kerf_mm a cuts_count (bot4).
-- Robert ukazal referencni nahled profesionalniho CAM softwaru (Truhlar/
-- Aptechsoftware) - hlavicka tabule ukazuje "Sirka rezu [mm]" a
-- "Pocet rezu", ktere se pocitaji v case generovani planu (zavisi na
-- tehdejsim nastaveni kerf) - je potreba je ULOZIT na jednotku, ne
-- dopocitavat znovu pri kazdem cteni (kdyby se kerf v nastaveni pozdeji
-- zmenil, historicky plan by se tise prepocital jinak, coz nechceme -
-- viz NAVRH_REZNE_PLANY.md sekce 6, "hotove jednotky se nikdy
-- neprepocitavaji").
--
-- Pouziti (na DB instance "Configurator", xebyhtfeaj @ 80.211.73.226):
--   mysql -h 80.211.73.226 -u <user> -p xebyhtfeaj < 2026-07-26_cutting_plan_units_kerf_cuts.sql

ALTER TABLE shop_cutting_plan_units
  ADD COLUMN kerf_mm    DECIMAL(5,2) NULL COMMENT 'sirka rezu pouzita pri generovani teto jednotky',
  ADD COLUMN cuts_count INT NULL COMMENT 'pocet rezu potrebnych k vyrobeni teto tyce/desky';
