-- CRM/poptavky - klasifikace na klicova slova s ucenim - bot5, 2026-07-31.
--
-- Robert po nalezu, ze ANTHROPIC_API_KEY je neplatny (viz AGENTS_LOG,
-- klasifikace pres Anthropic API tedy vzdy fail-open vracela "jine" a
-- CRM zatim nic nezachytilo): "nechme to zatim na klicovych slovech,
-- spatne zarazene e-maily oznacim kam patri a system se to bude ucit".
--
-- Misto volani Anthropic API pocita crm.classify_incoming_email() skore
-- souctem (poptavka_count - jine_count) pres slova nalezena v predmetu+
-- textu e-mailu. Tabulka je zaroven "pametí" uceni: kdyz admin oznaci
-- spatne zarazeny e-mail (CRM tlacitko "Toto neni poptavka" / Podpora
-- tlacitko "Toto je poptavka"), crm.train_words() zvysi pocitadla podle
-- skutecneho spravneho zarazeni - dalsi podobne e-maily uz se klasifikuji
-- lip, bez zasahu do kodu.
--
-- Seed radky nize jsou jen POCATECNI odhad (aby klasifikace fungovala i
-- pred prvni rucni opravou) - dalsim pouzivanim se vahy preváží podle
-- skutecnych dat.

CREATE TABLE IF NOT EXISTS crm_classifier_words (
  word VARCHAR(64) NOT NULL PRIMARY KEY,
  poptavka_count INT NOT NULL DEFAULT 0,
  jine_count INT NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO crm_classifier_words (word, poptavka_count, jine_count) VALUES
  ('poptávka', 5, 0), ('poptávku', 5, 0), ('poptávky', 5, 0), ('poptáváme', 5, 0),
  ('nabídku', 4, 0), ('nabídka', 4, 0), ('cenovou', 4, 0), ('cenovku', 3, 0),
  ('kolik', 3, 0), ('stálo', 2, 0), ('objednat', 3, 0), ('vyrobit', 3, 0),
  ('výrobu', 3, 0), ('zakázku', 3, 0), ('rozměry', 2, 0), ('rozměrech', 2, 0),
  ('dodání', 2, 0), ('dostupnost', 2, 0), ('skladem', 2, 0), ('množství', 2, 0),
  ('koupit', 3, 0), ('nákup', 2, 0),
  ('faktura', 0, 5), ('faktuře', 0, 4), ('fakturu', 0, 4), ('storno', 0, 3),
  ('reklamace', 0, 3), ('reklamaci', 0, 3), ('odhlásit', 0, 5), ('newsletter', 0, 5),
  ('pojištění', 0, 4), ('pojistné', 0, 4), ('výpis', 0, 3), ('upomínka', 0, 4),
  ('nevyzvednutá', 0, 3), ('zásilka', 0, 2), ('doručenka', 0, 2), ('reklama', 0, 3)
ON DUPLICATE KEY UPDATE word = word;
