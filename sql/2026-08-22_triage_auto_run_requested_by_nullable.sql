-- Automaticke zakladani behu trideni e-mailu (Robert, 2026-08-22, pres
-- bot3 - navazuje na zaseknuty beh id=6): periodicky systemd timer
-- (triage-auto-check, konfigurator-triage-auto-check.timer) kontroluje
-- pocet netridenych konverzaci a sam zalozi novy support_email_triage_
-- runs beh, kdyz jich je >= 6. Na rozdil od tlacitka "Tridit" v adminu
-- tenhle beh NENI vyzadan konkretnim adminem - `requested_by` bylo
-- NOT NULL s FK na app_users(id), coz by vynutilo vymyslet/predstirat
-- konkretniho "zadatele" (misleading atribuce). NULL jasne rika
-- "systemove zalozeno automatikou", ne "admin X kliknul".
ALTER TABLE support_email_triage_runs
  MODIFY requested_by INT NULL;
