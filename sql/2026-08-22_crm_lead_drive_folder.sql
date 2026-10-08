-- CRM: automaticka slozka poptavky na Sdilenem disku + vlastni cislovani
-- vanRM-<cislo>-<zakaznik> - bot10, 2026-08-22 (Robert, viz TASKS.md
-- "CRM: automaticka slozka poptavky na Sdilenem disku + PRILOHY TAM PRIMO").
--
-- drive_folder_id: FK na shared_drive_folders (viz api/drive.py) - slozka
-- konkretni poptavky (Poptavky > nabidky > rok > mesic > vanRM-...).
-- ON DELETE SET NULL zamerne (mirror crm_quotes.lead_id) - slozka na Drive
-- je trvaly obchodni zaznam, prezije i pripadne smazani/odmitnuti leadu
-- (crm_admin_lead_reject dela fyzicky DELETE FROM crm_leads).
--
-- drive_folder_number: VLASTNI sekvence (viz crm_lead_folder_sequence
-- nize), NEZAVISLA na crm_leads.id - Robert 22.8.: cislo zacina na 1000
-- a roste jen pro poptavky, ktere DOSTANOU slozku.
ALTER TABLE crm_leads
  ADD COLUMN drive_folder_id INT NULL,
  ADD COLUMN drive_folder_number INT NULL,
  ADD CONSTRAINT fk_crm_leads_drive_folder
    FOREIGN KEY (drive_folder_id) REFERENCES shared_drive_folders(id) ON DELETE SET NULL;

-- Pocitadlo pro vanRM cislovani - stejny vzor jako crm_quote_sequence
-- (quotes.py::_next_quote_number), FOR UPDATE zamek v
-- crm.py::_next_lead_folder_number.
CREATE TABLE crm_lead_folder_sequence (
  id INT PRIMARY KEY,
  next_number INT NOT NULL
);
INSERT INTO crm_lead_folder_sequence (id, next_number) VALUES (1, 1000);
