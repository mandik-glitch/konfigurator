-- Party model, faze 2/3/4 (bot18, 2026-09-05, Robert pres bot3, navazuje na
-- OFBiz srovnani "Za hranice objednavky" + schvaleny plan "Jedna identita,
-- pet fazi"). `parties` = centralni identita, existujici tabulky dostavaji
-- `party_id` jako ROLI napojenou na tuhle identitu - zadny existujici
-- sloupec se neruси ani nepreklada.
--
-- Aditivni migrace (stejny princip jako sql/2026-09-04_shop_orders_
-- delivery_billing_state.sql) - zadna existujici cesta cteni/zapisu se
-- timhle nezmeni, dokud kod sam explicitne nezacne party_id pouzivat.

SET SESSION lock_wait_timeout = 10;

CREATE TABLE parties (
  id INT AUTO_INCREMENT PRIMARY KEY,
  party_type ENUM('osoba','firma') NOT NULL DEFAULT 'osoba',
  full_name VARCHAR(255) NULL,
  primary_email VARCHAR(255) NULL,
  primary_phone VARCHAR(50) NULL,
  ico VARCHAR(20) NULL,
  dic VARCHAR(20) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

ALTER TABLE app_users
  ADD COLUMN party_id INT NULL AFTER id,
  ADD KEY idx_app_users_party (party_id),
  ADD CONSTRAINT fk_app_users_party FOREIGN KEY (party_id) REFERENCES parties(id) ON DELETE SET NULL;

ALTER TABLE shop_customers
  ADD COLUMN party_id INT NULL AFTER user_id,
  ADD KEY idx_shop_customers_party (party_id),
  ADD CONSTRAINT fk_shop_customers_party FOREIGN KEY (party_id) REFERENCES parties(id) ON DELETE SET NULL;

ALTER TABLE crm_leads
  ADD COLUMN party_id INT NULL AFTER customer_id,
  ADD KEY idx_crm_leads_party (party_id),
  ADD CONSTRAINT fk_crm_leads_party FOREIGN KEY (party_id) REFERENCES parties(id) ON DELETE SET NULL;

ALTER TABLE shop_orders
  ADD COLUMN party_id INT NULL AFTER user_id,
  ADD KEY idx_shop_orders_party (party_id),
  ADD CONSTRAINT fk_shop_orders_party FOREIGN KEY (party_id) REFERENCES parties(id) ON DELETE SET NULL;
