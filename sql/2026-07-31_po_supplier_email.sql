-- Robert 2026-07-31: potvrzenim nakupni objednavky adminem se ma
-- automaticky odeslat objednavka dodavateli. E-maily se loguji do
-- shop_emails, jenze ten sloupec order_id byl NOT NULL - e-mail
-- DODAVATELI ale k zadne zakaznicke objednavce nepatri (patri k nakupni
-- objednavce). Proto:
--   1) order_id nullable (u dodavatelskych e-mailu zustane NULL)
--   2) novy sloupec purchase_order_id - vazba na nakupni objednavku
-- Zpetne kompatibilni: vsechny stavajici radky maji order_id vyplneny a
-- purchase_order_id NULL, zadny existujici dotaz se nemeni.

ALTER TABLE shop_emails
  MODIFY COLUMN order_id INT NULL,
  ADD COLUMN purchase_order_id INT NULL AFTER order_id,
  ADD INDEX idx_shop_emails_po (purchase_order_id);
