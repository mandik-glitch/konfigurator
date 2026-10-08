-- Uzivatelsky nastavitelne barevne schema (Robert 2026-07-26, task #66),
-- admin panel i zakaznicky web nastavuji NEZAVISLE na sobe (potvrzeno
-- pres AskUserQuestion: "Obojí odděleně").
ALTER TABLE app_users
  ADD COLUMN theme_admin VARCHAR(10) NOT NULL DEFAULT 'dark',
  ADD COLUMN theme_shop VARCHAR(10) NOT NULL DEFAULT 'dark';
