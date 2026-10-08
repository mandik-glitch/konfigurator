-- Schvalovani dokladu a nabidek (bot6, 2026-08-01).
--
-- Robert: "veskere doklady ktere maji byt schvaleny nejakou roli,
-- jakmile vzniknou musi se ihned objevit na dashboardu dane role ktera
-- to ma schvalovat" + potvrzeno (AskUserQuestion) ze schvalovani se ma
-- tykat: nakupnich objednavek (stav 'navrh' - uz existuje, zadna zmena
-- schematu), prijatych objednavek (stav 'nova' - dtto), NABIDEK a
-- FAKTUR/DOKLADU - ty dva posledni zadny schvalovaci stav nemely,
-- doplnuje se novym sloupcem.
--
-- approval_status: 'ceka_schvaleni' (novy zaznam) | 'schvaleno'.
-- Vsechny EXISTUJICI zaznamy se backfillnou na 'schvaleno' - schvalovani
-- plati pro nove vznikle od ted, ne zpetne pro historii.

ALTER TABLE shop_documents
  ADD COLUMN approval_status VARCHAR(20) NOT NULL DEFAULT 'ceka_schvaleni'
    COMMENT 'ceka_schvaleni | schvaleno - novy doklad ceka na schvaleni roli s pravem doklady/upravit',
  ADD COLUMN approved_by INT NULL,
  ADD COLUMN approved_at DATETIME NULL;

UPDATE shop_documents SET approval_status = 'schvaleno';

ALTER TABLE crm_quotes
  ADD COLUMN approval_status VARCHAR(20) NOT NULL DEFAULT 'ceka_schvaleni'
    COMMENT 'ceka_schvaleni | schvaleno - nova nabidka ceka na schvaleni roli s pravem nabidky/upravit',
  ADD COLUMN approved_by INT NULL,
  ADD COLUMN approved_at DATETIME NULL;

UPDATE crm_quotes SET approval_status = 'schvaleno';
