-- Taxonomie TYPU VESTAVBY v aute (Robert, 2026-09-06): "jedna karoserie
-- mohla obsahovat vice typu vestaveb" - regal levy/pravy/na prepazku/
-- spojeny levy+prepazka/vysuvny modul/druha podlaha, kazdy typ muze mit
-- vic VERZI (napr. regal levy: euroboxy / univerzalni / dalsi pribudou).
--
-- Dve vrstvy, ktere se NESMI zamenit:
--   vestavby_typy/vestavby_verze (TATO migrace) = "co to JE a KAM v aute
--     patri" - nejvyssi uroven, viditelna napr. v e-shopove kategorizaci.
--   komponenty/komponenty_varianty (JIZ EXISTUJE, bot16 2026-08-31) = jemnejsi
--     stavebni VZOR pouzity UVNITR nejake verze (dnes jen "Regal na
--     euroboxy" s 3 rozmerovymi variantami luzka) - NEROZSIRUJE se touto
--     migraci, zustava svym vlastnim ucelem.
--
-- shape_geometry_method_id na verzi je NULLABLE a je to "hlavni/kotevni"
-- recept, ne uplny vycet - eurobox regal napr. pouziva SOUCASNE nekolik
-- receptu (id=3/5/6/7/8/9), viz poznamka u dane verze pro uplny seznam.

CREATE TABLE vestavby_typy (
  id INT AUTO_INCREMENT PRIMARY KEY,
  kod VARCHAR(64) NOT NULL UNIQUE,
  nazev VARCHAR(128) NOT NULL,
  popis TEXT,
  sort_order INT NOT NULL DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE vestavby_verze (
  id INT AUTO_INCREMENT PRIMARY KEY,
  vestavba_typ_id INT NOT NULL,
  kod VARCHAR(64) NOT NULL,
  nazev VARCHAR(128) NOT NULL,
  popis TEXT,
  shape_geometry_method_id INT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_typ_kod (vestavba_typ_id, kod),
  FOREIGN KEY (vestavba_typ_id) REFERENCES vestavby_typy(id),
  FOREIGN KEY (shape_geometry_method_id) REFERENCES shape_geometry_methods(id)
);

-- product_assemblies dostava tagovaci FK - CO tahle konkretni sestava JE
-- (analogicky k jiz existujicimu car_model_id = PRO KTERE auto je).
-- Obe NULL = stare sestavy pred touto migraci, netaguji se retroaktivne
-- automaticky (viz navazny python skript pro rucni/poloautomaticke otagovani).
ALTER TABLE product_assemblies
  ADD COLUMN vestavba_typ_id INT NULL AFTER car_model_id,
  ADD COLUMN vestavba_verze_id INT NULL AFTER vestavba_typ_id,
  ADD FOREIGN KEY (vestavba_typ_id) REFERENCES vestavby_typy(id),
  ADD FOREIGN KEY (vestavba_verze_id) REFERENCES vestavby_verze(id);

INSERT INTO vestavby_typy (kod, nazev, popis, sort_order) VALUES
  ('regal_levy', 'Regál levý', 'Regál na levé straně nákladového prostoru (podél boku vozidla).', 10),
  ('regal_pravy', 'Regál pravý', 'Regál na pravé straně nákladového prostoru.', 20),
  ('regal_prepazka', 'Regál na přepážku', 'Regál na přední přepážce (u kabiny řidiče).', 30),
  ('regal_levy_prepazka_spojeny', 'Regál levý + přepážka (spojený)', 'Jedna kontinuální konstrukce spojující levou stranu s přepážkou přes roh - NENÍ bundle dvou samostatných regálů, je to vlastní geometrický vzor s vlastním rohovým spojem (viz PRAVIDLA_SPOJU.md, "dvě topologie rohu").', 40),
  ('vysuvny_modul', 'Výsuvný modul', 'Vysouvací modul, např. z bočních dveří.', 50),
  ('druha_podlaha', 'Druhá podlaha', 'Uložný prostor v podlaze, typicky velké šuplíky. Verze se liší přístupem (zadní dveře / boční dveře / obojí).', 60);

INSERT INTO vestavby_verze (vestavba_typ_id, kod, nazev, popis, shape_geometry_method_id, sort_order) VALUES
  ((SELECT id FROM vestavby_typy WHERE kod='regal_levy'), 'euroboxy', 'Regál na euroboxy',
   'Sloupcová konstrukce s patry pro euroboxy, volitelný horní blok pro dlouhé předměty. Recepty: shape_geometry_methods id=3 (ukladani-euroboxu-do-luzek), 5 (regal-sloupcova-struktura), 6 (protazeni-zadni-svislice-vyrezove-nohy), 7 (uhelniky-na-spoje-nohy), 8 (prizpusobeni-vysky-nohy-vysce-dveri), 9 (horni-blok-pro-dlouhe-predmety, volitelny doplnek).',
   3, 10);
