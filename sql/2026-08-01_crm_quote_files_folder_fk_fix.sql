-- Oprava FK konfliktu v crm_quote_files - bot5, 2026-08-01.
--
-- Zjisteno pri overovacim testu: DELETE FROM crm_quotes (mazani cele
-- nabidky) selhavalo chybou "Cannot add or update a child row: a
-- foreign key constraint fails (crm_quote_files, CONSTRAINT
-- fk_cqfiles_quote ... ON DELETE CASCADE)".
--
-- Pricina: DVA rozdilne kaskadove smery se sbihaly na stejnou tabulku
-- crm_quote_files v jednom prikazu:
--   1) crm_quotes DELETE -> crm_quote_files DELETE (fk_cqfiles_quote CASCADE)
--   2) crm_quotes DELETE -> crm_quote_folders DELETE (fk_cqf_quote CASCADE)
--      -> crm_quote_files.folder_id SET NULL (fk_cqfiles_folder SET NULL)
-- InnoDB pri konfliktu mezi "smaz radek" (cesta 1) a "aktualizuj radek"
-- (cesta 2) na temze radku ve stejnem prikazu selze.
--
-- Oprava: fk_cqfiles_folder zmeneno z ON DELETE SET NULL na ON DELETE
-- CASCADE - obe cesty ted delaji totez (DELETE), zadny konflikt.
-- Aplikacni kod (quotes.py::quotes_admin_folder_delete) uz stejne resi
-- vlastni rekurzivni mazani souboru VYSLOVNE (fyzicke soubory na disku
-- + DB radky) PRED smazanim slozky - tahle FK je jen bezpecnostni sit
-- pro pripad, ze by nekdo smazal crm_quote_folders radek jinudy.

ALTER TABLE crm_quote_files DROP FOREIGN KEY fk_cqfiles_folder;
ALTER TABLE crm_quote_files ADD CONSTRAINT fk_cqfiles_folder
  FOREIGN KEY (folder_id) REFERENCES crm_quote_folders(id) ON DELETE CASCADE;
