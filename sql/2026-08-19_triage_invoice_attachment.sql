-- Bot při psaní triage návrhu (scripts/2026-08-18_support_triage_submit.py)
-- rovnou označí, KTERÁ příloha e-mailu je samotná faktura (relevantní
-- jen pro proposed_destination='doklad', kdy e-mail může mít víc
-- příloh - Robert: "musí se podívat na všechny ty dokumenty... a
-- uloží tam pouze samotné faktury"). Stejný princip jako existující
-- attachment_note - lidský/botí úsudek zapsaný v okamžiku psaní
-- návrhu, ne automatický běhový heuristický výběr. bot11, 2026-08-19.
ALTER TABLE support_email_triage_proposals
  ADD COLUMN invoice_attachment_filename VARCHAR(255) NULL AFTER attachment_note;
