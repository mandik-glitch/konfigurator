-- Robert: "kazdy uzivatel vidi jen svoje vlastni tvary, a ja admin kdyz
-- udelam vlastni tvary uvidi je vsichni" - vlastni tvary (custom_shapes)
-- byly dosud jedna plne sdilena knihovna bez rozliseni autora (kazdy
-- prihlaseny videl/mazal uplne vse).
--
-- is_public = snapshot role tvurce V OKAMZIKU ULOZENI (ne live JOIN na
-- app_users.role, ktera se muze pozdeji zmenit) - shoda admin -> 1,
-- kdokoli jiny -> 0. Zadne existujici radky v produkci (tabulka byla
-- prazdna pred timto zasahem), takze zadny backfill neni potreba.
ALTER TABLE custom_shapes
  ADD COLUMN is_public TINYINT(1) NOT NULL DEFAULT 0 AFTER created_by;
