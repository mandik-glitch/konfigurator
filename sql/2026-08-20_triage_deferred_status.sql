-- Reseni Emaily prichozi - "Nejasne" polozky (Robert, 2026-08-20):
-- "chci tlacitko presunout do dalsi davky" - misto vynuceni okamziteho
-- schvalit/zamitnout u polozky, kde admin jeste nema dost informaci,
-- at jde rozhodnuti odlozit bez ztraty kontextu. Novy stav 'deferred'
-- (odlisny od 'rejected', at je v historii videt rozdil mezi "bot
-- navrhl spatne" a "nemel jsem cas/info ted"). Konverzace zustava
-- open+nearchivovana, takze ji dalsi trideni (--list) proste znovu
-- najde - zadne dalsi propojeni na "davku" netreba.
ALTER TABLE support_email_triage_proposals
  MODIFY review_status ENUM('pending','approved','rejected','deferred') NOT NULL DEFAULT 'pending';
