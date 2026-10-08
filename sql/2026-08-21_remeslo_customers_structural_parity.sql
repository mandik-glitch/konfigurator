-- Strukturalni parita se shop_customers z hlavniho konfiguratoru
-- (Robert, 2026-08-21: "udelej zakazniky strukturalne na remesle
-- stejne jako na konfiguratoru") - stejna sada atributu, jen bez
-- e-shopove specifik nesouvisejicich s remeslnikovym klientem
-- (billing/delivery dualita pro dopravu zbozi, legacy_* migracni
-- sloupce, dealer schvaleni).
ALTER TABLE remeslo_customers
  ADD COLUMN customer_type VARCHAR(10) NOT NULL DEFAULT 'osoba' AFTER name,
  ADD COLUMN company_name VARCHAR(255) NULL AFTER customer_type,
  ADD COLUMN ico VARCHAR(20) NULL AFTER company_name,
  ADD COLUMN dic VARCHAR(20) NULL AFTER ico;
