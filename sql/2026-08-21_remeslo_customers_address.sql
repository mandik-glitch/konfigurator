-- Chybejici zakladni atribut zakaznika (Robert, 2026-08-21: "nema
-- vyplnou ani adresu") - mista realizace zakazky se bez adresy neda
-- rozumne evidovat.
ALTER TABLE remeslo_customers ADD COLUMN address VARCHAR(255) NULL AFTER email;
