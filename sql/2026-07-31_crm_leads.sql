-- CRM / poptavky (Robert 2026-07-31: "chodi ruzne maily, zdaleka ne vse
-- jsou poptavky" + "zalozime zaroven vedeni poptavek a cele CRM", + "ale
-- i nove" - CRM musi zachytit i uplne nove kontakty, ne jen stavajici
-- zakazniky).
--
-- Samostatne od shop_support_conversations/shop_support_messages (jiny
-- zivotni cyklus - pipeline stav, prirazeni obchodnikovi, konverze na
-- zakaznika/objednavku - support konverzace nic z toho nepotrebuje).
--
-- customer_id/order_id jsou NULLABLE FK - stejny vzor jako
-- shop_orders.user_id (snapshot + volitelna vazba, ne tvrdy pozadavek
-- na existujici ucet - poptavka muze prijit od uplne noveho kontaktu).

CREATE TABLE IF NOT EXISTS crm_leads (
  id INT AUTO_INCREMENT PRIMARY KEY,
  customer_id INT NULL,
  contact_name VARCHAR(255) NULL,
  contact_email VARCHAR(255) NOT NULL,
  contact_phone VARCHAR(50) NULL,
  company_name VARCHAR(255) NULL,
  source VARCHAR(20) NOT NULL DEFAULT 'email',
  subject VARCHAR(500) NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'nova',  -- nova|v_jednani|nabidnuto|vyhrano|prohrano
  assigned_to INT NULL,
  order_id INT NULL,                            -- vyplni se pri konverzi na objednavku
  unread_by_admin TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  last_message_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_crm_leads_customer FOREIGN KEY (customer_id) REFERENCES shop_customers(id) ON DELETE SET NULL,
  CONSTRAINT fk_crm_leads_assigned FOREIGN KEY (assigned_to) REFERENCES app_users(id) ON DELETE SET NULL,
  CONSTRAINT fk_crm_leads_order FOREIGN KEY (order_id) REFERENCES shop_orders(id) ON DELETE SET NULL,
  KEY idx_status_last (status, last_message_at),
  KEY idx_contact_email (contact_email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS crm_lead_messages (
  id INT AUTO_INCREMENT PRIMARY KEY,
  lead_id INT NOT NULL,
  sender_type VARCHAR(20) NOT NULL,   -- 'contact' | 'operator' | 'system'
  sender_user_id INT NULL,
  sender_name VARCHAR(255),
  body TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_crm_lead_msg_lead FOREIGN KEY (lead_id) REFERENCES crm_leads(id) ON DELETE CASCADE,
  KEY idx_lead_created (lead_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
