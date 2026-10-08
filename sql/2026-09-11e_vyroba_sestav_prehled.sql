-- "Přehled postupu v adminu" (Robert 2026-09-11, přes bot3 koordinace):
-- "ten plán je potreba prepracovat na tu přehledovou tabulku kde se bude
-- moci odškrtávat hotové a uvidi se stav práce na vsech sestavach."
--
-- Řádek obrazovky = KARTA (vozidlo × typologie), rozbalitelný na
-- jednotlivé sestavy. Pět fázových sloupců (scéna/schváleno/karta/
-- rendery/web) a sloupec "profil vyplněný" se NEUKLÁDAJÍ - dopočítávají
-- se live z product_assemblies/product_turntable_frames/shop_products
-- (PLAN_TVORBY_SESTAV.md, "stav se nezadává, dopočítává se"). Tady
-- vznikají jen ty tři věci, které data sama poznat neumí:
--
--   1. production_step_defs   - číselník ručních kroků (roste v čase,
--      proto číselník, ne ENUM v kódu - už dnes se čeká přírůstek
--      "razítka po zařazení do složky", zadáno bot8).
--   2. production_step_checks - dvoustavové zaškrtnutí kroku
--      (hlášeno kýmkoli se staff oprávněním / ověřeno JEDINĚ bot4 přes
--      servisní token, ne přes app_users - bot3 2026-09-11: "Nezakládej
--      účet... zakládat admin účty pro boty je přesně to, co dnes
--      vyplavalo jako kritický nález"). Kroky mají dva rozsahy: většina
--      na SESTAVĚ (assembly_id), "první otočka schválena" na KARTĚ
--      (car_model_id + typologie_id) - bot3: "jako vlastnost každé
--      sestavy je to špatně škálované... na kartě, ne na sestavě."
--   3. production_card_blockers - "blokace" s historií (bot3: "jedna
--      přepisovaná poznámka ztratí, PROČ karta stála"), na obrazovce se
--      ukazuje jen poslední nevyřešená (resolved_at IS NULL).

CREATE TABLE production_step_defs (
  step_key VARCHAR(64) NOT NULL PRIMARY KEY,
  label VARCHAR(200) NOT NULL,
  phase VARCHAR(20) NOT NULL,
  scope ENUM('sestava','karta') NOT NULL DEFAULT 'sestava',
  sort_order INT NOT NULL DEFAULT 0,
  active TINYINT(1) NOT NULL DEFAULT 1
);

INSERT INTO production_step_defs (step_key, label, phase, scope, sort_order) VALUES
  ('scene_geometry_checked', 'Geometrie zkontrolována ve scéně', '1', 'sestava', 10),
  ('cleaned_legacy_parts', 'Vyčištěno od starých horních bloků a kolizních úhelníků', '1', 'sestava', 20),
  ('rebuilt_per_template', 'Přestavěno podle schváleného vzoru (Doblo C)', '1', 'sestava', 30),
  ('robert_confirmed_placement', 'Robert potvrdil umístění dílů přímo ve scéně', '2', 'sestava', 40),
  ('texts_done', 'Texty a popis hotové', '3', 'sestava', 50),
  ('first_turntable_approved', 'První otočka schválena', '4', 'karta', 60);

-- Dvoustavové zaškrtnutí. reported_* = "hlášeno hotovo" (staff opravneni,
-- kdokoli). verified_* = "ověřeno" (jedine bot4, gatovano servisnim
-- tokenem v api endpointu, NE timhle schematem - viz production_overview.py).
-- verified_by je TEXT ('bot4'), ne FK na app_users - bot4 neni prihlaseny
-- uzivatel v prohlizeci, je to session volajici API primo.
--
-- Presne jeden z (assembly_id) / (car_model_id+typologie_id) je vyplneny
-- podle production_step_defs.scope pro dany step_key - nevynucuje DB
-- (prenositelnost/jednoduchost), hlida to api/production_overview.py.
CREATE TABLE production_step_checks (
  id INT AUTO_INCREMENT PRIMARY KEY,
  step_key VARCHAR(64) NOT NULL,
  assembly_id INT NULL,
  car_model_id INT NULL,
  typologie_id INT NULL,
  reported_by VARCHAR(100) NULL,
  reported_at DATETIME NULL,
  verified_by VARCHAR(100) NULL,
  verified_at DATETIME NULL,
  verify_verdict VARCHAR(20) NULL,
  verify_note VARCHAR(300) NULL,
  CONSTRAINT fk_psc_step FOREIGN KEY (step_key) REFERENCES production_step_defs(step_key),
  UNIQUE KEY uniq_assembly_step (assembly_id, step_key),
  UNIQUE KEY uniq_karta_step (car_model_id, typologie_id, step_key)
);

-- Historie blokací karty. Zadna PK na (car_model_id, typologie_id) -
-- schvalne umoznuje vic radku, na obrazovce se ctou jen ty s
-- resolved_at IS NULL (typicky jeden, nejnovejsi). Pri zapisu nove
-- blokace se stara oteviena zavre (resolved_at=NOW()).
CREATE TABLE production_card_blockers (
  id INT AUTO_INCREMENT PRIMARY KEY,
  car_model_id INT NOT NULL,
  typologie_id INT NOT NULL,
  text VARCHAR(500) NOT NULL,
  author VARCHAR(100) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  resolved_at DATETIME NULL,
  KEY idx_karta_open (car_model_id, typologie_id, resolved_at)
);
