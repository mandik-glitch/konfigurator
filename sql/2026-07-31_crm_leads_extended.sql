-- CRM/poptavky - rozsireni na plnohodnotnejsi CRM - bot5, 2026-07-31.
--
-- Robert po zakladni verzi (crm_leads/crm_lead_messages, viz
-- 2026-07-31_crm_leads.sql): "Crm ma přece více funkcí ... tak tam
-- všechno doplň" - po srovnani s bežnymi CRM funkcemi doplneno:
--   - hodnota obchodu (estimated_value) - pipeline dnes ukazoval jen
--     stav, ne kolik Kc v nem cekaji,
--   - ukoly/pripomenuti (crm_lead_tasks) - "zavolat v patek" apod.
--     s terminem, oddelene od vlakna zprav,
--   - interni poznamky (crm_lead_notes) - soukromy komentar k
--     poptavce, ktery se NIKDY neposila zakaznikovi jako e-mail (na
--     rozdil od crm_lead_messages/reply, ktera realny e-mail posila).

ALTER TABLE crm_leads
  ADD COLUMN estimated_value DECIMAL(12,2) NULL AFTER company_name,
  ADD COLUMN closed_at DATETIME NULL AFTER estimated_value;
-- closed_at: kdy lead presel do 'vyhrano'/'prohrano' (nastavuje
-- _apply_lead_update() v crm.py) - potreba pro dashboard "win rate
-- tento mesic", protoze last_message_at odrazi posledni ZPRAVU, ne
-- posledni ZMENU STAVU.

CREATE TABLE IF NOT EXISTS crm_lead_tasks (
  id INT AUTO_INCREMENT PRIMARY KEY,
  lead_id INT NOT NULL,
  title VARCHAR(255) NOT NULL,
  due_at DATETIME NULL,
  done TINYINT(1) NOT NULL DEFAULT 0,
  created_by INT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_crm_lead_tasks_lead FOREIGN KEY (lead_id) REFERENCES crm_leads(id) ON DELETE CASCADE,
  CONSTRAINT fk_crm_lead_tasks_user FOREIGN KEY (created_by) REFERENCES app_users(id) ON DELETE SET NULL,
  KEY idx_lead_done_due (lead_id, done, due_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS crm_lead_notes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  lead_id INT NOT NULL,
  author_id INT NULL,
  author_name VARCHAR(255),
  body TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_crm_lead_notes_lead FOREIGN KEY (lead_id) REFERENCES crm_leads(id) ON DELETE CASCADE,
  CONSTRAINT fk_crm_lead_notes_user FOREIGN KEY (author_id) REFERENCES app_users(id) ON DELETE SET NULL,
  KEY idx_lead_created (lead_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
