-- Přílohy příchozích support e-mailů - bot11, 2026-08-19.
--
-- Kontext: TASKS.md "Třídění příchozích e-mailů - přílohy faktur +
-- archivace objednávek". support_email_sync.py dosud přílohy ukládal
-- jen pro e-maily klasifikované jako 'poptavka'/'doklad' (starý
-- automatický klasifikátor, viz api/incoming_documents.py) - pro
-- VŠECHNY ostatní e-maily, co skončí v shop_support_conversations
-- (nový triage systém, api/support.py support_triage_proposal_review),
-- se přílohy dosud vůbec neukládaly, jen textový attachment_note.
--
-- Ukládá se PŘI SYNCHRONIZACI (ne až při ručním schválení triage
-- návrhu) - originální e-mail může mezitím zmizet z IMAPu (Robert si
-- e-maily ručně stahuje a tím je maže ze serveru), takže re-fetch při
-- pozdějším schválení by byl nespolehlivý.
--
-- Přesný vzor crm_lead_message_attachments (sql/2026-08-01_crm_quotes.sql).
CREATE TABLE shop_support_message_attachments (
  id INT AUTO_INCREMENT PRIMARY KEY,
  message_id INT NOT NULL,
  filename VARCHAR(255) NOT NULL,
  stored_filename VARCHAR(255) NOT NULL,
  content_type VARCHAR(150) NULL,
  size_bytes INT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_ssma_message (message_id),
  CONSTRAINT fk_ssma_message FOREIGN KEY (message_id) REFERENCES shop_support_messages(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
